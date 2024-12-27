import os
import re
from typing import Dict, List, Any
from dotenv import load_dotenv
from neo4j import GraphDatabase
from ast_extractor import TypeScriptASTExtractor
import json
import pathlib

# TypeScript built-ins (extending JavaScript ones)
TS_BUILT_INS = {
    # Core TypeScript
    'interface', 'type', 'enum', 'namespace',
    'public', 'private', 'protected', 'readonly',
    'abstract', 'implements', 'declare',
    
    # Angular specific
    'Component', 'Injectable', 'Input', 'Output',
    'ViewChild', 'HostListener', 'NgModule',
    
    # JavaScript built-ins (keeping the same as JS)
    'console', 'Math', 'JSON', 'Object', 'Array', 'String', 'Number',
    'Boolean', 'Date', 'RegExp', 'Error', 'Promise', 'setTimeout',
    'setInterval', 'require', 'Buffer'
}

TS_KEYWORDS = {
    # TypeScript specific
    'interface', 'type', 'enum', 'namespace', 'declare',
    'implements', 'abstract', 'public', 'private', 'protected',
    
    # JavaScript keywords (keeping same as JS)
    'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
    'continue', 'return', 'try', 'catch', 'finally', 'throw',
    'class', 'extends', 'new', 'this', 'super', 'import',
    'export', 'default', 'null', 'undefined', 'true', 'false'
}

class TypeScriptFileNodeCreator:
    def __init__(self):
        """Initialize TypeScript file node creator with Neo4j connection"""
        # Load Neo4j credentials
        load_dotenv()
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
        
    def resolve_relative_path(self, file_path: str, relative_path: str) -> str:
        """Resolve relative import paths"""
        current_path = pathlib.Path(file_path).parent
        resolved_path = (current_path / relative_path).resolve()
        resolved_path = str(str(resolved_path).replace('.ts', ''))
        return str(resolved_path).replace('\\', '/')

    def _extract_imports(self, ast: Dict, file_path: str) -> dict:
        """Extract TypeScript imports including type imports"""
        raw_imports = []
        imported_paths = []
        undefined_imports = []
        imported_variables = []  # Will store [variable_name, path]
        imported_functions = []  # Will store [function_name, path]
        
        try:
            def process_node(node):
                if not isinstance(node, dict):
                    return
                    
                node_type = node.get('type')
                text = node.get('text', '')
                
                # Regular imports and type imports
                if node_type == 'import_statement':
                    raw_imports.append(text)
                    
                    # Get the source path
                    current_path = None
                    for child in node.get('children', []):
                        if child.get('type') == 'string':
                            path = child.get('text', '').strip("'").strip('"')
                            if path.startswith('.'):
                                current_path = self.resolve_relative_path(file_path, path)
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
                                    # Handle named imports including type imports
                                    for spec in clause_child.get('children', []):
                                        if spec.get('type') == 'import_specifier':
                                            # Check if parent import statement is a type-only import
                                            parent_text = node.get('text', '')
                                            if parent_text.startswith('import type'):
                                                continue
                                                    
                                            spec_text = spec.get('text', '')
                                            # Check for inline type imports
                                            if 'type ' in spec_text or any(child.get('text') == 'type' for child in spec.get('children', [])):
                                                continue
                                                    
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
                elif node_type == 'await_expression':
                    if 'import(' in text:
                        raw_imports.append(text)
                        # Extract path from dynamic import
                        path_match = re.search(r"import\(['\"]([^'\"]+)['\"]\)", text)
                        if path_match:
                            path = path_match.group(1)
                            if path.startswith('.'):
                                imported_paths.append(self.resolve_relative_path(file_path, path))
                            else:
                                undefined_imports.append(path)
                
                # Require statements
                elif node_type == 'lexical_declaration' and 'require(' in text:
                    raw_imports.append(text)
                    
                    # Get the require path
                    current_path = None
                    path_match = re.search(r"require\(['\"]([^'\"]+)['\"]\)", text)
                    if path_match:
                        path = path_match.group(1)
                        if path.startswith('.'):
                            current_path = self.resolve_relative_path(file_path, path)
                            imported_paths.append(current_path)
                        else:
                            current_path = path
                            undefined_imports.append(path)
                    
                    # Get variable name
                    var_match = re.search(r"const\s+(\w+)\s*=\s*require", text)
                    if var_match:
                        imported_variables.append([var_match.group(1), current_path])
                
                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)

            if ast and isinstance(ast, dict):
                process_node(ast)

            # Remove duplicates and sort
            return {
                'raw_imports': sorted(set(raw_imports)),
                'imported_paths': sorted(set(imported_paths)),
                'undefined_imports': sorted(set(undefined_imports)),
                'imported_variables': sorted(imported_variables, key=lambda x: x[0]),
                'imported_functions': sorted(imported_functions, key=lambda x: x[0])
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

    def _extract_functions_and_classes(self, ast: Dict) -> Dict[str, Any]:
        """Extract TypeScript functions and classes including decorators"""
        names_of_functions_defined = []
        names_of_classes_defined = []
        function_definitions = []
        class_definitions = []
        methods_of_classes = []
        current_overload_group = None
        current_decorators = []

        try:
            def process_node(node):
                nonlocal current_overload_group, current_decorators
                if not isinstance(node, dict):
                    return

                node_type = node.get('type')
                text = node.get('text', '')
                
                # Handle classes
                if node_type in ['class_declaration', 'abstract_class_declaration']:
                    class_info = {
                        'class_name': '',
                        'class_code': '',
                        'class_start_point': node.get('start_point', [0])[0] + 1,
                        'class_end_point': node.get('end_point', [0])[0] + 1,
                        'methods': []
                    }
                    
                    # Get decorators if any exist
                    decorator_text = ''
                    for child in node.get('children', []):
                        if child.get('type') == 'decorator':
                            decorator_text += child.get('text', '') + '\n'
                    
                    class_info['class_code'] = decorator_text + text
                    
                    # Find class name from type_identifier
                    for child in node.get('children', []):
                        if child.get('type') == 'type_identifier':
                            class_info['class_name'] = child.get('text', '')
                            if class_info['class_name'] not in names_of_classes_defined:
                                names_of_classes_defined.append(class_info['class_name'])
                    
                    # Process class body for methods
                    for child in node.get('children', []):
                        if child.get('type') == 'class_body':
                            for member in child.get('children', []):
                                # Handle abstract method declarations
                                if member.get('type') == 'abstract_method_signature':
                                    method_name = ''
                                    for method_child in member.get('children', []):
                                        if method_child.get('type') == 'property_identifier':
                                            method_name = method_child.get('text', '')
                                    
                                    if method_name:
                                        methods_of_classes.append(method_name)
                                        method_info = {
                                            'method_name': method_name,
                                            'method_code': member.get('text', ''),
                                            'method_start_point': member.get('start_point', [0])[0] + 1,
                                            'method_end_point': member.get('end_point', [0])[0] + 1
                                        }
                                        class_info['methods'].append(method_info)
                                
                                # Handle regular methods
                                elif member.get('type') == 'method_definition':
                                    method_name = ''
                                    decorator_text = ''
                                    
                                    # Get decorators for method
                                    prev_sibling = member.get('prev_sibling')
                                    while prev_sibling and prev_sibling.get('type') == 'decorator':
                                        decorator_text = prev_sibling.get('text', '') + '\n    ' + decorator_text
                                        prev_sibling = prev_sibling.get('prev_sibling')
                                    
                                    for method_child in member.get('children', []):
                                        if method_child.get('type') in ['property_identifier', 'identifier']:
                                            method_name = method_child.get('text', '')
                                        elif method_child.get('type') == 'get':
                                            for id_child in member.get('children', []):
                                                if id_child.get('type') == 'property_identifier':
                                                    method_name = 'get_' + id_child.get('text', '')
                                        elif method_child.get('type') == 'set':
                                            for id_child in member.get('children', []):
                                                if id_child.get('type') == 'property_identifier':
                                                    method_name = 'set_' + id_child.get('text', '')
                                    
                                    if method_name:
                                        methods_of_classes.append(method_name)
                                        method_info = {
                                            'method_name': method_name,
                                            'method_code': decorator_text + member.get('text', ''),
                                            'method_start_point': member.get('start_point', [0])[0] + 1,
                                            'method_end_point': member.get('end_point', [0])[0] + 1
                                        }
                                        class_info['methods'].append(method_info)
                    
                    if class_info['class_name']:
                        class_definitions.append(class_info)
                elif node_type in ['function_declaration', 'generator_function_declaration']:
                    function_name = ''
                    has_body = False
                    
                    for child in node.get('children', []):
                        if child.get('type') == 'identifier':
                            function_name = child.get('text', '')
                        elif child.get('type') == 'statement_block':
                            has_body = True

                    if function_name:
                        if not has_body:  # Overload signature
                            if current_overload_group and current_overload_group['function_name'] == function_name:
                                current_overload_group['function_code'] += '\n' + text
                            else:
                                current_overload_group = {
                                    'function_name': function_name,
                                    'function_code': text,
                                    'start_line': node.get('start_point', [0])[0] + 1
                                }
                        else:  # Implementation
                            if current_overload_group and current_overload_group['function_name'] == function_name:
                                names_of_functions_defined.append(function_name)
                                function_definitions.append({
                                    'function_name': function_name,
                                    'function_code': current_overload_group['function_code'] + '\n' + text,
                                    'start_line': current_overload_group['start_line'],
                                    'end_line': node.get('end_point', [0])[0] + 1
                                })
                                current_overload_group = None
                            else:
                                names_of_functions_defined.append(function_name)
                                function_definitions.append({
                                    'function_name': function_name,
                                    'function_code': text,
                                    'start_line': node.get('start_point', [0])[0] + 1,
                                    'end_line': node.get('end_point', [0])[0] + 1
                                })

                # Handle arrow functions
                elif node_type == 'lexical_declaration':
                    for child in node.get('children', []):
                        if child.get('type') == 'variable_declarator':
                            function_name = ''
                            for subchild in child.get('children', []):
                                if subchild.get('type') == 'identifier':
                                    function_name = subchild.get('text', '')
                                elif subchild.get('type') == 'arrow_function':
                                    if function_name:
                                        names_of_functions_defined.append(function_name)
                                        function_definitions.append({
                                            'function_name': function_name,
                                            'function_code': text,
                                            'start_line': node.get('start_point', [0])[0] + 1,
                                            'end_line': node.get('end_point', [0])[0] + 1
                                        })

                # Process children recursively
                for child in node.get('children', []):
                    process_node(child)

            if ast and isinstance(ast, dict):
                process_node(ast)
            
            print("\nFinal Results:")
            print(f"Classes found: {names_of_classes_defined}")
            print(f"Methods found: {methods_of_classes}")

            return {
                'names_of_functions_defined': sorted(set(names_of_functions_defined)),
                'names_of_classes_defined': sorted(set(names_of_classes_defined)),
                'function_definitions': function_definitions,
                'class_definitions': class_definitions,
                'methods_of_classes': sorted(set(methods_of_classes))
            }

        except Exception as e:
            print(f"Error extracting functions and classes: {e}")
            return {
                'names_of_functions_defined': [],
                'names_of_classes_defined': [],
                'function_definitions': [],
                'class_definitions': [],
                'methods_of_classes': []
            }

    def _extract_exports(self, ast: Dict, defined_functions: List[str], defined_classes: List[str]) -> Dict[str, List]:
        """Extract TypeScript exports including type exports"""
        
        pass

    def _extract_function_calls_with_path(self, ast: Dict, imported_variables: List, imported_functions: List) -> List[Dict[str, str]]:
        """Extract function calls including Angular decorator calls"""
        # Will implement parsing for:
        # - Regular function calls (like JS)
        # - Decorator function calls
        # - Angular lifecycle hooks
        pass

    def create_file_node(self, file_path: str) -> Dict[str, Any]:
        """Create node representation for TypeScript file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        extractor = TypeScriptASTExtractor("")
        ast = extractor.process_ts_file(file_path)
        
        # Extract all required information
        import_info = self._extract_imports(ast, file_path)
        function_calls_info = self._extract_function_calls_with_path(ast, import_info['imported_variables'], import_info['imported_functions'])
        code_info = self._extract_functions_and_classes(ast)
        print(code_info,"code_info")
        input("Press Enter to continue...")
        exports_info = self._extract_exports(ast, code_info['names_of_functions_defined'], code_info['names_of_classes_defined'])
        barrel_directories = self._identify_barrels(import_info['imported_paths'])
        
        # Combine metadata
        node_data = {
            'language': 'typescript',
            'code': content,
            **import_info,
            **code_info,
            **exports_info,
            'barrel_directories': barrel_directories,
            'function_calls': function_calls_info
        }
        
        return node_data

    def save_to_neo4j(self, node_data: Dict[str, Any], file_path: str, remove: str):
        """Save TypeScript file node to Neo4j"""
        # Same implementation as JavaScript version
        pass

    def process_codebase(self, root_dir: str, remove: str):
        """Process TypeScript codebase"""
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith(('.ts', '.tsx')):  # Handle both .ts and .tsx
                    file_path = os.path.join(root, file)
                    print(f"Processing file: {file_path}")
                    node_data = self.create_file_node(file_path)
                    self.save_to_neo4j(node_data, file_path, remove)

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()

    def _identify_barrels(self, imported_paths: List[str]) -> List[str]:
        """Identify TypeScript barrel files"""
        # Same implementation as JavaScript version
        pass

if __name__ == "__main__":
    creator = TypeScriptFileNodeCreator()
    test_file = "test.ts"
    print(f"\nProcessing file: {test_file}")
    creator.create_file_node(test_file)
