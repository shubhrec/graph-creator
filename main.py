import os
from file_node_creator import FileNodeCreator

def main():
    # Initialize the creator for JavaScript
    creator = FileNodeCreator(language='javascript')
    
    try:
        # Path to the test project
        test_project_path = '/app/test/js-test-project'
        
        # Check if directory exists
        if not os.path.exists(test_project_path):
            print(f"Error: Test project directory not found at {test_project_path}")
            return
        
        print(f"Processing JavaScript codebase at: {test_project_path}")
        creator.process_codebase(test_project_path)
        print("Successfully processed the codebase!")
        
    except Exception as e:
        print(f"Error processing codebase: {str(e)}")
    
    finally:
        creator.close()

if __name__ == "__main__":
    main()
