import os
from file_node_creator import FileNodeCreator
from file_joiner import FileJoiner
from function_node_creator import FunctionNodeCreator
from function_joiner import FunctionCallAnalyzer

def main():
    try:
        # Step 1: Create File nodes with metadata
        print("Step 1: Creating File nodes...")
        file_creator = FileNodeCreator(language='javascript')
        test_project_path = '/app/test/server'
        
        if not os.path.exists(test_project_path):
            print(f"Error: Test project directory not found at {test_project_path}")
            return
            
        file_creator.process_codebase(test_project_path)
        file_creator.close()
        print("Successfully created File nodes!")

        # Step 2: Create IMPORTS relationships between files
        print("\nStep 2: Creating import relationships...")
        file_joiner = FileJoiner()
        file_joiner.process()
        print("Successfully created import relationships!")

        # Step 3: Create Function nodes and relationships
        print("\nStep 3: Creating Function nodes...")
        function_creator = FunctionNodeCreator()
        function_creator.process_file_nodes()
        function_creator.close()
        print("Successfully created Function nodes!")

        # Step 4: Create CALLS relationships between functions
        print("\nStep 4: Creating function call relationships...")
        NEO4J_URI = "bolt://host.docker.internal:7687"
        NEO4J_USER = "neo4j"
        NEO4J_PASSWORD = "Shubh@123"
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        function_analyzer = FunctionCallAnalyzer(
            neo4j_uri=NEO4J_URI,
            neo4j_user=NEO4J_USER,
            neo4j_password=NEO4J_PASSWORD,
            openai_api_key=OPENAI_API_KEY
        )
        function_analyzer.process_all_functions()
        print("Successfully created function call relationships!")

    except Exception as e:
        print(f"Error in processing: {str(e)}")

if __name__ == "__main__":
    main()
