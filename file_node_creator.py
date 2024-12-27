import os
import re
from typing import Dict, List, Any
from dotenv import load_dotenv
from neo4j import GraphDatabase
from global_regex import JS_PATTERNS, PY_PATTERNS
from ast_extractor import JavaScriptASTExtractor
import json
import pathlib

# JavaScript built-in functions and keywords
BUILT_INS = {
    # Core objects
    'console', 'Math', 'JSON', 'Object', 'Array', 'String', 'Number', 
    'Boolean', 'Date', 'RegExp', 'Error', 'Promise', 'setTimeout', 
    'setInterval', 'require', 'Buffer',
    
    # Promise methods
    'then', 'catch', 'finally', 'resolve', 'reject',
    
    # Array methods
    'map', 'filter', 'reduce', 'forEach', 'some', 'every', 'find', 'includes',
    'push', 'pop', 'shift', 'unshift', 'slice', 'splice', 'join',
    
    # String methods
    'toString', 'split', 'replace', 'trim', 'substring', 'substr',
    
    # Number methods
    'toFixed', 'toPrecision', 'toExponential',
    
    # Global functions
    'parseInt', 'parseFloat', 'isNaN', 'isFinite', 'isArray',
    
    # Common callbacks
    'callback',
    
    # Object methods
    'hasOwnProperty', 'assign', 'keys', 'values',
    
    # Console methods
    'log', 'error', 'warn', 'info',
    
    # Moment.js methods
    'format', 'endOf', 'isBefore', 'isSame', 
    'isSameOrBefore', 'isValid', 'startOf'
}
KEYWORDS = {'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'return', 'try', 'catch', 'finally', 'throw', 'class', 'extends', 'new', 'this', 'super', 'import', 'export', 'default', 'null', 'undefined', 'true', 'false'}

class FileNodeCreator:
    def __init__(self, language: str = 'javascript',remove: str = '/app/test/'):
        """Initialize the FileNodeCreator with specified language.
        
        Args:
            language (str): Programming language of the codebase ('javascript' or 'python')
        """
        self.language = language.lower()
        self.patterns = JS_PATTERNS if self.language == 'javascript' else PY_PATTERNS
        self.remove = remove

        # Load Neo4j credentials from .env
        load_dotenv()
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
    
    def resolve_relative_path(self,file_path,relative_path):
        current_path = pathlib.Path(file_path).parent
        resolved_path = str((current_path / relative_path).resolve())
        print(resolved_path, "resolved_path")
        if os.path.isfile(resolved_path+'.js'):
            print("Entered this")
            if not resolved_path.endswith('.js'):
                resolved_path = resolved_path + '.js'
        if(str(resolved_path).startswith(self.remove)):
            return str(resolved_path).replace(self.remove, '')
        return str(resolved_path).replace('\\', '/')

    def _extract_imports(self,ast,file_path) -> dict:
        raw_imports = []
        imported_paths = []
        undefined_imports = []
        imported_variables = []  # Will now store [variable_name, path]
        imported_functions = []  # Will now store [function_name, path]
        
        try:
            def process_node(node):
                if not isinstance(node, dict):
                    return
                    
                node_type = node.get('type')
                text = node.get('text', '')
                
                # Regular imports
                if node_type == 'import_statement':
                    raw_imports.append(text)
                    
                    # Get the source path
                    current_path = None
                    for child in node.get('children', []):
                        if child.get('type') == 'string':
                            path = child.get('text', '').strip("'").strip('"')
                            if path.startswith('.'):
                                current_path = self.resolve_relative_path(file_path,path)
                                imported_paths.append(current_path)
                            else:
                                current_path = path
                                undefined_imports.append(path)
                    
                    # Process import clause
                    for child in node.get('children', []):
                        if child.get('type') == 'import_clause':
                            # Default import
                            for clause_child in child.get('children', []):
                                if clause_child.get('type') == 'identifier':
                                    imported_variables.append([clause_child.get('text'), current_path])
                                elif clause_child.get('type') == 'named_imports':
                                    # Handle named imports
                                    for spec in clause_child.get('children', []):
                                        if spec.get('type') == 'import_specifier':
                                            spec_text = spec.get('text', '')
                                            if ' as ' in spec_text:
                                                imported_functions.append([spec_text.split(' as ')[1].strip(), current_path])
                                            else:
                                                imported_functions.append([spec_text, current_path])
                                elif clause_child.get('type') == 'namespace_import':
                                    # Handle namespace import
                                    namespace_text = clause_child.get('text')
                                    if ' as ' in namespace_text:
                                        imported_variables.append([namespace_text.split(' as ')[1].strip(), current_path])
                
                # Dynamic imports
                elif node_type in ['await_expression', 'expression_statement']:
                    if 'import(' in text:
                        raw_imports.append(text)
                        # Extract path from dynamic import
                        path_match = re.search(r"import\(['\"]([^'\"]+)['\"]\)", text)
                        if path_match:
                            path = path_match.group(1)
                            if path.startswith('.'):
                                imported_paths.append(self.resolve_relative_path(file_path,path))
                            else:
                                undefined_imports.append(path)
                
                # Require statements
                elif node_type == 'lexical_declaration' and re.match(r'.*const\s+(?:\w+|\{[^}]+\})\s*=\s*require\([\'"].*[\'"]\).*', text):
                    raw_imports.append(text)
                    
                    # Get the require path
                    current_path = None
                    path_match = re.search(r"require\(['\"]([^'\"]+)['\"]\)", text)
                    if path_match:
                        path = path_match.group(1)
                        if path.startswith('.'):
                            current_path = self.resolve_relative_path(file_path,path)
                            imported_paths.append(current_path)
                        else:
                            current_path = path
                            undefined_imports.append(path)
                    
                    # Handle destructured require
                    if '{' in text:
                        for child in node.get('children', []):
                            if child.get('type') == 'variable_declarator':
                                for var_child in child.get('children', []):
                                    if var_child.get('type') == 'object_pattern':
                                        for prop in var_child.get('children', []):
                                            if prop.get('type') == 'shorthand_property_identifier_pattern':
                                                imported_functions.append([prop.get('text'), current_path])
                    else:
                        # Regular require
                        var_match = re.search(r"const\s+(\w+)\s*=\s*require", text)
                        if var_match:
                            imported_variables.append([var_match.group(1), current_path])

                # Process children
                for child in node.get('children', []):
                    process_node(child)

            if ast and isinstance(ast, dict):
                process_node(ast)

            # Remove duplicates and sort
            return {
                'raw_imports': sorted(set(raw_imports)),
                'imported_paths': sorted(set(imported_paths)),
                'undefined_imports': sorted(set(undefined_imports)),
                'imported_variables': sorted(imported_variables, key=lambda x: x[0]),  # Sort by variable name
                'imported_functions': sorted(imported_functions, key=lambda x: x[0])   # Sort by function name
            }
            
        except Exception as e:
            print(f"Error processing imports: {e}")
            return {
                'raw_imports': [],
                'imported_paths': [],
                'undefined_imports': [],
                'imported_variables': [],
                'imported_functions': []
            }

    def _extract_functions_and_classes(self, ast) -> Dict[str, Any]:
        """Extract function and class information using AST."""
        info = {
            'names_of_functions_defined': [],
            'names_of_classes_defined': [],
            'methods_of_classes': [],
            'function_definitions': [],
            'class_definitions': []
        }
        
        try:
            def get_node_lines(node):
                start = node.get('start_point', [0, 0])[0] + 1
                end = node.get('end_point', [0, 0])[0] + 1
                return start, end

            def add_function_definition(name, code, node):
                start, end = get_node_lines(node)
                info['function_definitions'].append({
                    'function_name': name,
                    'function_code': code,
                    'start_line': start,
                    'end_line': end
                })
            
            def process_node(node):
                if not isinstance(node, dict):
                    return
                    
                node_type = node.get('type')
                text = node.get('text', '')
                
                # Object method definitions using regex
                if node_type == 'pair':
                    # Match patterns like: functionName: function(...) or functionName: (...) =>
                    method_match = re.match(r'^\s*(\w+)\s*:\s*(?:(?:async\s+)?function\s*\(.*\)|(?:\([^)]*\)|[^=]+)\s*=>)', text)
                    if method_match:
                        method_name = method_match.group(1)
                        if method_name and method_name not in info['names_of_functions_defined']:
                            info['names_of_functions_defined'].append(method_name)
                            add_function_definition(method_name, text, node)
                
                elif node_type == 'method_definition':
                    for child in node.get('children', []):
                        if child.get('type') == 'property_identifier':
                            method_name = child.get('text')
                            if method_name:
                                info['names_of_functions_defined'].append(method_name)
                                add_function_definition(method_name, text, node)
                
                # Function declarations (including generator functions)

                elif node_type == 'function_declaration':
                    for child in node.get('children', []):
                        if child.get('type') == 'identifier':
                            func_name = child.get('text')
                            if func_name and func_name not in info['names_of_functions_defined']:
                                info['names_of_functions_defined'].append(func_name)
                                add_function_definition(func_name, text, node)
                
                # Generator functions
                elif node_type == 'generator_function_declaration':
                    for child in node.get('children', []):
                        if child.get('type') == 'identifier':
                            func_name = child.get('text')
                            if func_name and func_name not in info['names_of_functions_defined']:
                                info['names_of_functions_defined'].append(func_name)
                                add_function_definition(func_name, text, node)
                
                # Arrow functions and variable declarations
                elif node_type == 'lexical_declaration':
                    print(text, "text", "lexical_declaration type")
                    # Modified regex to catch both function and arrow function declarations, but not callbacks
                    func_match = re.search(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:(?:async\s+)?function\s*\(|\([^)]*\)\s*=>|[^=]*=>\s*\{)', text)
                    print(func_match, "func_match", "lexical_declaration type")
                    if func_match:
                        func_name = func_match.group(1)
                        if func_name and func_name not in info['names_of_functions_defined']:
                            info['names_of_functions_defined'].append(func_name)
                            add_function_definition(func_name, text, node)
                    
                    # Keep the existing AST traversal as backup
                    for child in node.get('children', []):
                        if child.get('type') == 'variable_declarator':
                            func_name = None
                            for var_child in child.get('children', []):
                                if var_child.get('type') == 'identifier':
                                    func_name = var_child.get('text')
                                elif var_child.get('type') in ['arrow_function', 'function']:
                                    if func_name and func_name not in info['names_of_functions_defined']:
                                        info['names_of_functions_defined'].append(func_name)
                                        add_function_definition(func_name, text, node)
                
                # Classes and their methods
                elif node_type == 'class_declaration':
                    class_info = {
                        'class_name': '',
                        'class_code': text,
                        'class_start_point': get_node_lines(node)[0],
                        'class_end_point': get_node_lines(node)[1],
                        'methods': []
                    }
                    
                    # Get class name
                    for child in node.get('children', []):
                        if child.get('type') == 'identifier':
                            class_info['class_name'] = child.get('text')
                            if class_info['class_name'] not in info['names_of_classes_defined']:
                                info['names_of_classes_defined'].append(class_info['class_name'])
                    
                    # Get methods
                    for child in node.get('children', []):
                        if child.get('type') == 'class_body':
                            for method in child.get('children', []):
                                if method.get('type') == 'method_definition':
                                    method_name = ''
                                    for method_child in method.get('children', []):
                                        if method_child.get('type') == 'property_identifier':
                                            method_name = method_child.get('text')
                                            
                                    if method_name:
                                        class_info['methods'].append({
                                            'method_name': method_name,
                                            'method_code': method.get('text', ''),
                                            'method_start_point': get_node_lines(method)[0],
                                            'method_end_point': get_node_lines(method)[1]
                                        })
                
                    info['class_definitions'].append(class_info)
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
            
            if ast and isinstance(ast, dict):
                process_node(ast)
            
            # Sort all lists for consistency
            for key in info:
                if isinstance(info[key], list):
                    if key == 'methods_of_classes':
                        for class_info in info['methods_of_classes']:
                            class_info['methods'].sort()
                    elif key == 'function_definitions':
                        info[key].sort(key=lambda x: x['function_name'])
                    elif key == 'class_definitions':
                        info[key].sort(key=lambda x: x['class_name'])
                    else:
                        info[key].sort()
            
            return info
            
        except Exception as e:
            print(f"Error processing functions and classes: {e}")
            return {
                'names_of_functions_defined': [],
                'names_of_classes_defined': [],
                'methods_of_classes': [],
                'function_definitions': [],
                'class_definitions': []
            }

    def _extract_exports(self, ast, defined_functions, defined_classes) -> Dict[str, list]:
        exports = {
            'exported_functions': [],
            'exported_variables': [],
            'exported_class': []
        }
        
        try:
            def process_node(node):
                if not isinstance(node, dict):
                    return
                    
                node_type = node.get('type')
                text = node.get('text', '')
                
                # ES6 exports
                if node_type == 'export_statement':
                    # Direct exports: export class/function/const
                    export_match = re.search(r'export\s+(class|function|const)\s+(\w+)', text)
                    if export_match:
                        export_type, name = export_match.groups()
                        if export_type == 'class':
                            exports['exported_class'].append(name)
                        elif export_type == 'function':
                            exports['exported_functions'].append(name)
                        elif export_type == 'const':
                            if name in defined_functions:
                                exports['exported_functions'].append(name)
                            else:
                                exports['exported_variables'].append(name)
                
                    # Named exports: export { name1, name2 }
                    export_list = re.findall(r'export\s*{\s*([\w\s,]+)\s*}', text)
                    if export_list:
                        names = re.findall(r'\w+', export_list[0])
                        for name in names:
                            if name in defined_functions:
                                exports['exported_functions'].append(name)
                            elif name in defined_classes:
                                exports['exported_class'].append(name)
                            else:
                                exports['exported_variables'].append(name)
                
                # CommonJS exports
                elif node_type == 'expression_statement':
                    # Direct module.exports = variable_name
                    direct_export = re.search(r'module\.exports\s*=\s*(\w+)(?:\s*;)?', text)
                    if direct_export:
                        name = direct_export.group(1)
                        if name in defined_functions:
                            exports['exported_functions'].append(name)
                        elif name in defined_classes:
                            exports['exported_class'].append(name)
                        else:
                            exports['exported_variables'].append(name)
                    
                    # For any text containing module.exports
                    if 'module.exports' in text:
                        # Check for all defined functions in the text
                        for func in defined_functions:
                            # Look for any occurrence of the function name that looks like an export
                            # This could be: func: function(){}, func(){}, func: func, etc.
                            if any(pattern.format(func) in text for pattern in [
                                '{}:', # object key
                                '{},', # last item in object
                                '{}()', # method shorthand
                            ]):
                                exports['exported_functions'].append(func)
                    
                    # Named exports: module.exports.name = ...
                    named_match = re.search(r'module\.exports\.(\w+)\s*=\s*(class|function)?', text)
                    if named_match:
                        name, export_type = named_match.groups()
                        if export_type == 'class' or name in defined_classes:
                            exports['exported_class'].append(name)
                        elif export_type == 'function' or name in defined_functions:
                            exports['exported_functions'].append(name)
                        else:
                            exports['exported_variables'].append(name)
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)
            
            if ast and isinstance(ast, dict):
                process_node(ast)
            
            # Remove duplicates and sort
            for key in exports:
                exports[key] = sorted(set(exports[key]))
            
            return exports
            
        except Exception as e:
            print(f"Error processing exports: {e}")
            return {
                'exported_functions': [],
                'exported_variables': [],
                'exported_class': []
            }

    def _extract_function_calls_with_path(self, ast, imported_variables, imported_functions) -> List[Dict[str, str]]:
        function_calls = []
        seen_calls = set()  # Add this to track seen calls
        text = ast.get('text', '')
        
        try:
            # First find all instances where imported classes are instantiated
            variable_mappings = {}  # Will store 'service' -> 'DefaultService' mappings
            potential_class_names = set()
            potential_class_names.update(var[0] for var in imported_variables)
            potential_class_names.update(func[0] for func in imported_functions)
            
            imported_class_names = '|'.join(potential_class_names)
            if imported_class_names:
                instance_pattern = rf'const\s+(\w+)\s*=\s*new\s+({imported_class_names})'
                
                # Find all instances
                for match in re.finditer(instance_pattern, text):
                    var_name = match.group(1)    # e.g., 'service'
                    class_name = match.group(2)  # e.g., 'DefaultService'
                    variable_mappings[var_name] = class_name

            # Now create patterns for function calls using both original imports and instantiated variables
            all_var_names = set()
            
            # Add original imported variables
            all_var_names.update(var[0] for var in imported_variables)
            
            # Add instantiated variable names
            all_var_names.update(variable_mappings.keys())
            
            # Create patterns
            imported_vars = '|'.join(all_var_names)
            imported_funcs = '|'.join([func[0] for func in imported_functions])
            
            # When adding a function call, check if we've seen it:
            def add_function_call(func_call, path):
                call_key = f"{func_call}:{path}"
                if call_key not in seen_calls:
                    function_calls.append({
                        'function_call': func_call,
                        'path': path
                    })
                    seen_calls.add(call_key)

            # Find direct function calls
            if imported_funcs:
                direct_pattern = rf'({imported_funcs})\('
                for match in re.finditer(direct_pattern, text):
                    func_name = match.group(1)
                    for name, path in imported_functions:
                        if name == func_name:
                            add_function_call(func_name, path)
            
            # Find method calls on both imported and instantiated variables
            if imported_vars:
                method_pattern = rf'({imported_vars})\.(\w+)\('
                for match in re.finditer(method_pattern, text):
                    var_name = match.group(1)
                    method_name = match.group(2)
                    
                    # If it's an instantiated variable, look up its class
                    if var_name in variable_mappings:
                        class_name = variable_mappings[var_name]
                        # Find the path for the class
                        for name, path in imported_variables:
                            if name == class_name:
                                add_function_call(f"{var_name}.{method_name}", path)
                    else:
                        # Direct imported variable
                        for name, path in imported_variables:
                            if name == var_name:
                                add_function_call(f"{var_name}.{method_name}", path)
            
            return function_calls
            
        except Exception as e:
            print(f"Error processing function calls: {e}")
            return []

    def create_file_node(self, file_path: str) -> Dict[str, Any]:
        """Create a node representation for a file with all required metadata.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            Dict containing all metadata for the file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        extractor = JavaScriptASTExtractor("")
        ast = extractor.process_js_file(file_path)
        with open("ast.json", "w") as f:
            json.dump(ast, f, indent=4)
        # Extract imports
        import_info = self._extract_imports(ast,file_path)
        print(import_info, "import_info")
        
        # Extract function calls with path info
        function_calls_info = self._extract_function_calls_with_path(
            ast,
            import_info['imported_variables'],
            import_info['imported_functions']
        )
        print("--------------------------------")
        print(function_calls_info, "function_calls_info")
        print("--------------------------------")
        
        # Extract functions and classes
        code_info = self._extract_functions_and_classes(ast)
        print("--------------------------------")
        print(code_info, "code_info")
        print("--------------------------------")

        # Extract exports
        exports_info = self._extract_exports(ast,code_info['names_of_functions_defined'],code_info['names_of_classes_defined'])
        print("--------------------------------")
        print(exports_info, "exports_info")
        print("--------------------------------")

        barrel_directories = self._identify_barrels(import_info['imported_paths'])
        print("--------------------------------")
        print(barrel_directories, "barrel_directories")
        print("--------------------------------")
        
        # Combine all metadata
        node_data = {
            'language': self.language,
            'code': content,
            **import_info,
            **code_info,
            **exports_info,
            'barrel_directories': barrel_directories,
            'function_calls': function_calls_info
        }
        
        return node_data

    def save_to_neo4j(self, node_data: Dict[str, Any], file_path: str, remove: str):
        """Save the file node to Neo4j.
        
        Args:
            node_data (Dict): Node metadata
            file_path (str): Path to the file
            remove (str): Path prefix to remove
        """
        with self.driver.session() as session:
            # Remove prefix from file_path
            file_path = file_path.replace(remove, '')
            
            node_data['imported_variables'] = json.dumps(node_data['imported_variables'])
            node_data['imported_functions'] = json.dumps(node_data['imported_functions'])
            node_data['methods_of_classes'] = json.dumps(node_data['methods_of_classes'])
            node_data['function_calls'] = json.dumps(node_data['function_calls'])
            node_data['function_definitions'] = json.dumps(node_data['function_definitions'])
            node_data['class_definitions'] = json.dumps(node_data['class_definitions'])
            
            # Create node with all metadata
            cypher_query = """
            CREATE (f:File {
                path: $file_path,
                language: $language,
                code: $code,
                raw_imports: $raw_imports,
                imported_paths: $imported_paths,
                undefined_imports: $undefined_imports,
                imported_variables: $imported_variables,
                imported_functions: $imported_functions,
                names_of_functions_defined: $names_of_functions_defined,
                names_of_classes_defined: $names_of_classes_defined,
                methods_of_classes: $methods_of_classes,
                function_calls: $function_calls,
                function_definitions: $function_definitions,
                class_definitions: $class_definitions,
                exported_functions: $exported_functions,
                exported_variables: $exported_variables,
                exported_class: $exported_class,
                barrel_directories: $barrel_directories
            })
            """
            # print(file_path, "file_path")
            session.run(cypher_query, file_path=file_path, **node_data)

    def process_codebase(self, root_dir: str,remove: str):
        """Process entire codebase and create nodes for all files.
        
        Args:
            root_dir (str): Root directory of the codebase
        """
        for root, _, files in os.walk(root_dir):
            for file in files:
                if self.language == 'javascript' and file.endswith('.js'):
                    file_path = os.path.join(root, file)
                    print(f"Processing file: {file_path}")
                    node_data = self.create_file_node(file_path)
                    self.save_to_neo4j(node_data, file_path, remove)

    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()

    def _identify_barrels(self, imported_paths: List[str]) -> List[str]:
        """Identify directories that are being imported (which must contain barrel files).
        
        Args:
            imported_paths (List[str]): List of resolved import paths
            
        Returns:
            List[str]: List of directory paths that are being imported
        """
        barrel_directories = []
        
        for path in imported_paths:
            # If the path exists and is a directory, it must contain a barrel file
            if os.path.isdir(path):
                barrel_directories.append(path.replace('\\', '/'))
        
        return sorted(set(barrel_directories))

if __name__ == "__main__":
    # Initialize FileNodeCreator
    remove = '/app/test/'
    creator = FileNodeCreator(language='javascript',remove=remove)
    
    # Specify the test file
    test_file = "/app/test/server/product/engines/data-sync/custodian-data/transaction-processing/pre-processor-utils.js"
    print(f"\nProcessing file: {test_file}")
    
    node_data = creator.create_file_node(test_file)
    del node_data['code']
    print(node_data, "node_data")
    input("Press Enter to continue...")
    creator.save_to_neo4j(node_data, test_file, remove)

