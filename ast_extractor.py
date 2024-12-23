import code_ast
import json
from pathlib import Path
import os
import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class JavaScriptASTExtractor:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.processed_files = 0
        self.failed_files = 0

    def traverse_tree(self, node):
        """Convert code_ast node to dictionary format"""
        if node is None:
            logger.debug("Node is None")
            return None
        
        
        # Handle SourceCodeAST objects
        if hasattr(node, 'source_tree'):
            logger.debug("Found source_tree")
            tree = node.source_tree
            
            # Get the root node from the tree
            if hasattr(tree, 'root_node'):
                root = tree.root_node
                
                return self.process_node(root)
        
        return self.process_node(node)

    def process_node(self, node):
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
            # Handle named children separately
            elif hasattr(node, 'named_children'):
                children = []
                for child in node.named_children:
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

    def process_js_file(self, file_path):
        """Process a single JavaScript file and return its AST"""
        try:
            if not os.path.isfile(file_path):
                logger.error(f"File does not exist: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Handle empty files gracefully
            if not content or content.strip() == "":
                logger.warning(f"Empty file detected: {file_path}")
                return {
                    "type": "program",
                    "start_byte": 0,
                    "end_byte": 0,
                    "start_point": [0, 0],
                    "end_point": [0, 0],
                    "text": "",
                    "children": []
                }
  
            try:
                tree = code_ast.ast(content, lang="javascript")
                if tree:
                    self.processed_files += 1
                    return self.traverse_tree(tree)
                else:
                    logger.error(f"Failed to parse: {file_path}")
                    self.failed_files += 1
                    return None
            except ValueError as ve:
                if "empty" in str(ve).lower():
                    logger.warning(f"Empty file detected: {file_path}")
                    return {
                        "type": "program",
                        "start_byte": 0,
                        "end_byte": 0,
                        "start_point": [0, 0],
                        "end_point": [0, 0],
                        "text": "",
                        "children": []
                    }
                logger.error(f"Parsing error for {file_path}: {str(ve)}")
                logger.exception("Stack trace:")
                self.failed_files += 1
                return None
            except Exception as e:
                logger.error(f"Parsing error for {file_path}: {str(e)}")
                logger.exception("Stack trace:")
                self.failed_files += 1
                return None
                
        except UnicodeDecodeError:
            logger.error(f"Unicode decode error in {file_path}")
            try:
                with open(file_path, 'r', encoding='latin-1') as file:
                    content = file.read()
                logger.debug("Attempting parse with latin-1 encoding")
                tree = code_ast.ast(content, lang="javascript")
                if tree:
                    self.processed_files += 1
                    return self.traverse_tree(tree)
                self.failed_files += 1
                return None
            except Exception as e:
                logger.error(f"Failed with latin-1 encoding: {str(e)}")
                self.failed_files += 1
                return None

    
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract ASTs from JavaScript repository')
    parser.add_argument('repo_path', help='Path to the JavaScript repository')
    parser.add_argument('--mongodb-uri', default='mongodb://mongodb:27017/',
                      help='MongoDB connection URI')
    
    args = parser.parse_args()
    
    extractor = JavaScriptASTExtractor(args.repo_path, args.mongodb_uri)
    extractor.process_repository()