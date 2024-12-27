import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

class FileJoiner:
    def __init__(self):
        """Initialize FileJoiner with Neo4j connection"""
        load_dotenv()
        self.neo4j_uri = os.getenv('NEO4J_URI')
        self.neo4j_user = os.getenv('NEO4J_USER')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD')
        self.driver = GraphDatabase.driver(
            self.neo4j_uri, 
            auth=(self.neo4j_user, self.neo4j_password)
        )

    def normalize_path(self, path: str) -> str:
        """Remove .js extension if present"""
        return path.replace('.js', '')

    def create_import_relationships(self):
        """Create relationships between files based on their imports"""
        with self.driver.session() as session:
            # Get all files with their imported paths
            query = """
            MATCH (f:File)
            WHERE f.imported_paths IS NOT NULL
            RETURN f.path AS source_path, f.imported_paths AS imported_paths
            """
            result = session.run(query)
            print(result,"result")
            
            for record in result:
                source_path = record['source_path']
                imported_paths = record['imported_paths']
                
                for import_path in imported_paths:
                    
                    # Find and create relationship
                    relationship_query = """
                    MATCH (source:File {path: $source_path})
                    MATCH (target:File)
                    WHERE target.path contains $normalized_path
                    MERGE (source)-[r:IMPORTS]->(target)
                    """
                    session.run(relationship_query, 
                              source_path=source_path,
                              normalized_path=import_path)

    def verify_relationships(self):
        """Print all created relationships"""
        with self.driver.session() as session:
            query = """
            MATCH (f1:File)-[r:IMPORTS]->(f2:File)
            RETURN f1.path AS source, f2.path AS target
            """
            result = session.run(query)
            
            print("\nImport Relationships:")
            for record in result:
                print(f"{record['source']} -> {record['target']}")

    def process(self):
        """Main processing method"""
        try:
            self.create_import_relationships()
            self.verify_relationships()
        finally:
            self.close()

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()

if __name__ == "__main__":
    joiner = FileJoiner()
    joiner.process()
