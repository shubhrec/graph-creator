import code_ast
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ASTHelper:
    def __init__(self):
        pass

    def get_ast(self, file_content: str, language: str = "javascript") -> dict:
        """
        Create AST for a single file
        Args:
            file_content: Content of the file
            language: Programming language (default: javascript)
        Returns:
            Dictionary containing the AST
        """
        tree = code_ast.ast(file_content, lang=language)
        if tree:
            logger.debug("Successfully created AST")
            return self.traverse_tree(tree)
        else:
            logger.error("Failed to parse file content")
            return None

    def traverse_tree(self, node) -> dict:
        """Convert AST node to dictionary format"""
        if node is None:
            return None
        
        # Handle SourceCodeAST objects
        if hasattr(node, 'source_tree'):
            tree = node.source_tree
            if hasattr(tree, 'root_node'):
                return self.process_node(tree.root_node)
        
        return self.process_node(node)

    def process_node(self, node) -> dict:
        """Process individual AST nodes"""
        if node is None:
            return None
        
        try:
            # Basic node information
            result = {
                'type': node.type if hasattr(node, 'type') else node.__class__.__name__,
                'start_byte': node.start_byte if hasattr(node, 'start_byte') else None,
                'end_byte': node.end_byte if hasattr(node, 'end_byte') else None,
                'start_point': node.start_point if hasattr(node, 'start_point') else None,
                'end_point': node.end_point if hasattr(node, 'end_point') else None,
            }
            
            # Add text content
            if hasattr(node, 'text'):
                if isinstance(node.text, bytes):
                    result['text'] = node.text.decode('utf-8')
                else:
                    result['text'] = str(node.text)
            
            # Process child nodes
            if hasattr(node, 'children'):
                children = []
                for child in node.children:
                    child_result = self.process_node(child)
                    if child_result:
                        children.append(child_result)
                if children:
                    result['children'] = children
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing node: {e}")
            logger.exception("Stack trace:")
            return None

    def find_function_by_location(self, ast: dict, line: int) -> dict:
        """
        Find function node containing the given line number
        Args:
            ast: The AST dictionary
            line: Line number to search for
        Returns:
            Function node containing the line, or None
        """
        def search_node(node, line):
            if not node:
                return None
                
            start_line = node.get('start_point', [0])[0]
            end_line = node.get('end_point', [0])[0]
            
            # Check if this is a function node and contains our line
            if (node.get('type') in ['function_declaration', 'method_definition'] and 
                start_line <= line <= end_line):
                return node
            
            # Search children
            if 'children' in node:
                for child in node['children']:
                    result = search_node(child, line)
                    if result:
                        return result
            
            return None
        
        return search_node(ast, line)


    def find_function_by_hunk(self, ast: dict, hunk: str) -> dict:
        """
        Find function node containing the given hunk
        Args:
            ast: The AST dictionary
            hunk: The hunk content
        Returns:
            Function node containing the hunk
        """
        # Extract lines of code from the hunk (excluding diff markers)
        hunk_lines = [line for line in hunk.split('\n') if line.strip()]
        search_lines = []
        
        for line in hunk_lines:
            # Skip the @@ line
            if line.startswith('@@'):
                continue
            # Remove +/- and leading/trailing whitespace
            cleaned_line = line.lstrip('+ -').strip()
            if cleaned_line and not cleaned_line.startswith('//'):
                search_lines.append(cleaned_line)
        
        if not search_lines:
            return None

        def search_node(node):
            if not node:
                return None
            
            # Get node's text content
            node_text = node.get('text', '')
            
            # Check if this node contains any of our search lines
            if any(search_line in node_text for search_line in search_lines):
                # Check if current node is a function node
                if node.get('type') in [
                    'function_declaration',          # function foo() {}
                    'method_definition',            # class { foo() {} }
                    'arrow_function',               # const foo = () => {}
                    'function_expression',          # const foo = function() {}
                    'object_method',                # { foo() {} }
                    'pair',                         # { foo: function() {} }
                    'property',                     # { foo: () => {} }
                    'assignment_expression',        # foo = function() {}
                    'variable_declarator'           # const foo = function() {}
                ]:
                    return node
                
                # Walk up the tree to find the containing function
                current = node
                while current.get('parent'):
                    current = current.get('parent')
                    if current.get('type') in [
                        'function_declaration',
                        'method_definition',
                        'arrow_function',
                        'function_expression',
                        'object_method',
                        'pair',
                        'property',
                        'assignment_expression',
                        'variable_declarator'
                    ]:
                        return current
            
            # Search children
            if 'children' in node:
                for child in node['children']:
                    result = search_node(child)
                    if result:
                        return result
            
            return None
        
        # Find the function node
        function_node = search_node(ast)
        
        # If found, return its text content
        return function_node
        
        return None

    def find_functions_calling(self, ast: dict, function_name: str) -> list:
        """
        Find all functions that call the given function
        Args:
            ast: The AST dictionary
            function_name: Name of the function to search for calls
        Returns:
            List of function nodes that call the given function
        """
        calling_functions = []
        
        def search_node(node, current_function=None):
            if not node:
                return
            
            # If this is a function definition, update current_function
            if node.get('type') in ['method_definition', 'function_declaration']:
                current_function = node
            
            # Check if this node is a function call
            if node.get('type') == 'call_expression':
                call_text = node.get('text', '')
                if function_name in call_text and current_function:
                    if current_function not in calling_functions:
                        calling_functions.append(current_function)
            
            # Search children
            if 'children' in node:
                for child in node['children']:
                    search_node(child, current_function)
        
        search_node(ast)
        return calling_functions

    def find_function_text(self, ast: dict, function_name: str,code) -> str:
        """
        Find function text from AST by function name
        Args:
            ast: The AST dictionary
            function_name: Name of the function to find
        Returns:
            Function text if found, None otherwise
        """
        if not ast:
            return None
        
        def search_node(node):
            if not node:
                return None
            
            node_type = node.get('type')
            node_text = node.get('text', '')
            
            # Add handling for module.exports pattern
            if node_type == 'pair' and function_name in node_text:
                return node_text
            
            # Case 1: Regular function declarations
            if node_type == 'function_declaration':
                if any(child.get('text') == function_name for child in node.get('children', [])):
                    return node_text
            
            # Case 2: Method definitions in classes/objects
            elif node_type == 'method_definition':
                for child in node.get('children', []):
                    if child.get('type') == 'property_identifier' and child.get('text') == function_name:
                        return node_text
            
            # Case 3: Arrow functions in property pairs
            elif node_type == 'pair':
                children = node.get('children', [])
                if len(children) >= 2:
                    property_id = children[0]
                    if (property_id.get('type') == 'property_identifier' and 
                        property_id.get('text') == function_name and
                        any(c.get('type') == 'arrow_function' for c in children[1:])):
                        return node_text
            
            # Case 4: Variable declarations with function expressions
            elif node_type == 'variable_declarator':
                children = node.get('children', [])
                if len(children) >= 2:
                    identifier = children[0]
                    value = children[1]
                    if (identifier.get('text') == function_name and 
                        value.get('type') in ['function_expression', 'arrow_function']):
                        return node_text
            
            # Case 5: Object property with function expression
            elif node_type == 'property':
                key = node.get('key', {})
                value = node.get('value', {})
                if (key.get('name') == function_name and 
                    value.get('type') in ['FunctionExpression', 'ArrowFunctionExpression']):
                    return node_text
            
            # Case 6: Assignment expressions
            elif node_type == 'assignment_expression':
                children = node.get('children', [])
                if len(children) >= 2:
                    left = children[0]
                    right = children[1]
                    if (left.get('text') == function_name and 
                        right.get('type') in ['function_expression', 'arrow_function']):
                        return node.get('text')
            
            # Recursively search children
            if 'children' in node:
                for child in node['children']:
                    result = search_node(child)
                    if result:
                        return result
            
            return None
        
        return search_node(ast)

if __name__ == "__main__":
    # Test the AST helper with complete test code including all functions
    
    test_code = """
    function convertExcelFileBufferToJSONForBulkUploadForMultipleSheetsforBOSLtv(excelFileBuffer, sheetName) {
        // ...
    }
    """
    helper = ASTHelper()
    ast = helper.get_ast(test_code)
    
    if ast:
        print("AST created successfully")
        
        # Test finding function text
        print("\nTesting find_function_text:")
        test_functions = ["convertExcelFileBufferToJSONForBulkUploadForMultipleSheetsforBOSLtv"]
        
        for func_name in test_functions:
            print(f"\nLooking for function: {func_name}")
            func_text = helper.find_function_text(ast, func_name)
            if func_text:
                print(f"Found function text:\n{func_text}")
            else:
                print(f"Function {func_name} not found")
        
