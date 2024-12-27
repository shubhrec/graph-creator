from neo4j import GraphDatabase
from ast_helper import ASTHelper
import os
from dotenv import load_dotenv
import json

class FunctionNodeCreator:
    def __init__(self):
        """Initialize the FunctionNodeCreator with Neo4j connection."""
        # Load Neo4j credentials from .env
        load_dotenv()
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
        self.ast_helper = ASTHelper()

    def process_file_nodes(self):
        """Process all File nodes in the database and create Function nodes."""
        with self.driver.session() as session:
            # Get all File nodes
            files = session.run("MATCH (f:File) RETURN f")
            
            for record in files:
                file_node = record['f']
                self._process_single_file(file_node)

    def _process_single_file(self, file_node):
        """Process a single file node and create Function, Class, and Method nodes."""
        file_path = file_node['path']
        
        # Process standalone functions
        function_definitions = json.loads(file_node['function_definitions'])
        for func_def in function_definitions:
            self._create_function_node(
                file_path=file_path,
                function_name=func_def['function_name'],
                function_code=func_def['function_code']
            )
        
        # Process classes and their methods
        class_definitions = json.loads(file_node['class_definitions'])
        for class_def in class_definitions:
            # Create class node
            class_node = self._create_class_node(
                file_path=file_path,
                class_name=class_def['class_name'],
                class_code=class_def['class_code']
            )
            
            # Create method nodes for each method in the class
            for method in class_def['methods']:
                self._create_method_node(
                    file_path=file_path,
                    method_name=method['method_name'],
                    method_code=method['method_code'],
                    class_name=class_def['class_name']
                )

    def _create_function_node(self, file_path: str, function_name: str, function_code: str):
        """Create a Function node and relationship to its containing file."""
        with self.driver.session() as session:
            cypher_query = """
            MATCH (f:File {path: $file_path})
            MERGE (func:Function {
                name: $function_name,
                code: $function_code,
                file_path: $file_path
            })
            MERGE (f)-[:CONTAINS_FUNCTION]->(func)
            """
            
            session.run(
                cypher_query,
                file_path=file_path,
                function_name=function_name,
                function_code=function_code
            )

    def _create_class_node(self, file_path: str, class_name: str, class_code: str):
        """Create a Class node and relationship to its containing file."""
        with self.driver.session() as session:
            cypher_query = """
            MATCH (f:File {path: $file_path})
            MERGE (c:Class {
                name: $class_name,
                code: $class_code,
                file_path: $file_path
            })
            MERGE (f)-[:CONTAINS_CLASS]->(c)
            """
            
            session.run(
                cypher_query,
                file_path=file_path,
                class_name=class_name,
                class_code=class_code
            )

    def _create_method_node(self, file_path: str, method_name: str, method_code: str, class_name: str):
        """Create a Method node and relationship to its containing class."""
        with self.driver.session() as session:
            cypher_query = """
            MATCH (c:Class {name: $class_name, file_path: $file_path})
            MERGE (m:Method {
                name: $method_name,
                code: $method_code,
                file_path: $file_path
            })
            MERGE (c)-[:CONTAINS_METHOD]->(m)
            """
            
            session.run(
                cypher_query,
                file_path=file_path,
                method_name=method_name,
                method_code=method_code,
                class_name=class_name
            )

    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()

if __name__ == "__main__":
    # Create and test the FunctionNodeCreator
    creator = FunctionNodeCreator()
    creator.process_file_nodes()
    creator.close()
