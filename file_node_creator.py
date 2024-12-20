import os
import re
from typing import Dict, List, Any
from code_ast import ast
from dotenv import load_dotenv
from neo4j import GraphDatabase
from global_regex import JS_PATTERNS, PY_PATTERNS

class FileNodeCreator:
    def __init__(self, language: str = 'javascript'):
        """Initialize the FileNodeCreator with specified language.
        
        Args:
            language (str): Programming language of the codebase ('javascript' or 'python')
        """
        self.language = language.lower()
        self.patterns = JS_PATTERNS if self.language == 'javascript' else PY_PATTERNS
        
        # Load Neo4j credentials from .env
        load_dotenv()
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))

    def _extract_imports(self, file_content: str) -> Dict[str, List[str]]:
        """Extract import information from file content.
        
        Args:
            file_content (str): Content of the file
            
        Returns:
            Dict containing raw_imports, imported_paths, and undefined_imports
        """
        import_info = {
            'raw_imports': [],
            'imported_paths': [],
            'undefined_imports': []
        }
        
        # Get all import patterns for the current language
        import_patterns = self.patterns['imports']
        
        for pattern_name, pattern in import_patterns.items():
            matches = re.finditer(pattern, file_content)
            for match in matches:
                # Get the full import statement
                full_line = match.group(0)
                import_info['raw_imports'].append(full_line.strip())
                
                # Get the path/module name
                path = match.group(1)
                if '/' in path:
                    import_info['imported_paths'].append(path)
                else:
                    import_info['undefined_imports'].append(path)
                    
        return import_info

    def _extract_functions_and_classes(self, ast_data: Any) -> Dict[str, List[str]]:
        """Extract function and class information from AST."""
        print("\n=== Starting function extraction ===")
        print(f"Initial AST data type: {type(ast_data)}")   
        info = {
            'names_of_functions_defined': [],
            'names_of_classes_defined': [],
            'methods_of_classes': [],
            'name_of_function_called_related_to_imports': [],
            'orphan_function': [],
            'arrow_functions': [],
            'object_methods': []
        }
        
        def visit_node(node, current_class=None):
            if not hasattr(node, 'type'):
                return
            
            node_type = node.get('type', '')
            print(f"\nVisiting node of type: {node_type}")
            
            # Handle function declarations
            if node_type == 'function_declaration':
                func_name = node.get('id', {}).get('name')
                print(f"Found function declaration: {func_name}")
                if func_name and not current_class:
                    info['names_of_functions_defined'].append(func_name)
                    
            # Handle class declarations
            elif node_type == 'class_declaration':
                class_name = node.get('id', {}).get('name')
                print(f"Found class declaration: {class_name}")
                if class_name:
                    info['names_of_classes_defined'].append(class_name)
                    info['methods_of_classes'].append({
                        'class_name': class_name,
                        'methods': []
                    })
                    # Visit class body with current_class context
                    class_body = node.get('body', {}).get('body', [])
                    for method_node in class_body:
                        visit_node(method_node, class_name)
                    
            # Handle method definitions
            elif node_type == 'method_definition':
                method_name = node.get('key', {}).get('name')
                print(f"Found method definition: {method_name}")
                if method_name and current_class:
                    class_methods = next(
                        (item for item in info['methods_of_classes'] if item['class_name'] == current_class),
                        None
                    )
                    if class_methods:
                        class_methods['methods'].append(method_name)
                    
            # Handle variable declarations with functions
            elif node_type == 'variable_declarator':
                var_name = node.get('id', {}).get('name')
                init = node.get('init', {})
                print(f"Found variable declaration: {var_name}")
                if init.get('type') in ['arrow_function', 'function_expression']:
                    info['names_of_functions_defined'].append(var_name)
                    if init.get('type') == 'arrow_function':
                        info['arrow_functions'].append(var_name)
                    
            # Handle object methods and pairs
            elif node_type == 'pair':
                key = node.get('key', {})
                value = node.get('value', {})
                method_name = key.get('name') or key.get('value')
                print(f"Found pair node with method name: {method_name}")
                
                if method_name:
                    if value.get('type') in ['function_expression', 'arrow_function']:
                        info['object_methods'].append(method_name)
                        info['names_of_functions_defined'].append(method_name)
                    
            # Handle property assignments
            elif node_type == 'property':
                key = node.get('key', {})
                value = node.get('value', {})
                prop_name = key.get('name')
                print(f"Found property assignment: {prop_name}")
                if prop_name and value.get('type') in ['function_expression', 'arrow_function']:
                    info['object_methods'].append(prop_name)
                    info['names_of_functions_defined'].append(prop_name)
                    
            # Handle assignment expressions
            elif node_type == 'assignment_expression':
                left = node.get('left', {})
                right = node.get('right', {})
                assign_name = left.get('name')
                print(f"Found assignment expression: {assign_name}")
                if assign_name and right.get('type') in ['function_expression', 'arrow_function']:
                    info['names_of_functions_defined'].append(assign_name)
                    
            # Handle function calls
            elif node_type == 'call_expression':
                callee = node.get('callee', {})
                if callee.get('type') == 'identifier':
                    func_name = callee.get('name')
                    print(f"Found call expression: {func_name}")
                    if func_name:
                        if func_name.startswith('_'):
                            info['orphan_function'].append(func_name)
                        elif func_name not in info['names_of_functions_defined']:
                            info['name_of_function_called_related_to_imports'].append(func_name)
                            
            # Recursively visit children
            for key, value in node.items():
                if isinstance(value, dict):
                    visit_node(value, current_class)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            visit_node(item, current_class)
        
        # Start the traversal
        print("Starting traversal from root node 1")
        print(f"AST data type: {type(ast_data)}")
        if hasattr(ast_data, 'source_tree'):
            print("Found source_tree, processing...")
            tree = ast_data.source_tree
            if hasattr(tree, 'root_node'):
                print(f"Found root_node, type: {type(tree.root_node)}")
                visit_node(tree.root_node)
        
        # Remove duplicates while preserving order
        for key in info:
            if isinstance(info[key], list):
                info[key] = list(dict.fromkeys(info[key]))
        
        return info

    def create_file_node(self, file_path: str) -> Dict[str, Any]:
        """Create a node representation for a file with all required metadata.
        
        Args:
            file_path (str): Path to the file
            
        Returns:
            Dict containing all metadata for the file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Generate AST
        ast_data = ast(content,self.language)
        
        # Extract imports
        import_info = self._extract_imports(content)
        
        # Extract functions and classes
        code_info = self._extract_functions_and_classes(ast_data)
        
        # Combine all metadata
        node_data = {
            'language': self.language,
            'code': content,
            **import_info,
            **code_info
        }
        
        return node_data

    def save_to_neo4j(self, node_data: Dict[str, Any], file_path: str):
        """Save the file node to Neo4j.
        
        Args:
            node_data (Dict): Node metadata
            file_path (str): Path to the file
        """
        with self.driver.session() as session:
            # Create node with all metadata
            cypher_query = """
            CREATE (f:File {
                path: $file_path,
                language: $language,
                code: $code,
                raw_imports: $raw_imports,
                imported_paths: $imported_paths,
                undefined_imports: $undefined_imports,
                names_of_functions_defined: $names_of_functions_defined,
                names_of_classes_defined: $names_of_classes_defined,
                methods_of_classes: $methods_of_classes,
                name_of_function_called_related_to_imports: $name_of_function_called_related_to_imports,
                orphan_function: $orphan_function
            })
            """
            session.run(cypher_query, 
                       file_path=file_path,
                       **node_data)

    def process_codebase(self, root_dir: str):
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
                    self.save_to_neo4j(node_data, file_path)
                elif self.language == 'python' and file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    node_data = self.create_file_node(file_path)
                    self.save_to_neo4j(node_data, file_path)

    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()
