import re
import json
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
from neo4j import GraphDatabase

class FunctionCallAnalyzer:
    def __init__(self, driver, openai_api_key):
        self.driver = driver
        base_url = "http://host.docker.internal:1234/v1"
        self.llm = ChatOpenAI(
            api_key="not-needed", 
            model="qwen2.5-coder-1.5b-instruct",
            base_url=base_url,
            temperature=0
        )
    
    def _extract_function_calls(self, code):
        """Extract function calls using regex patterns"""
        if not isinstance(code, (str, bytes)):
            # print(f"Warning: code is not string or bytes, it is: {type(code)}")
            # print(f"Code value: {code}")
            return []
        
        # First, get the function name being defined (to exclude it)
        function_def_pattern = r'^(?:function\s+)?(\w+)\s*\([^)]*\)\s*{'
        function_name = None
        function_match = re.search(function_def_pattern, code.strip())
        if function_match:
            function_name = function_match.group(1)
        
        # print(f"\nAnalyzing function: {function_name}")  # Debug log
        
        patterns = [
            r'(?<!function\s)(?<!class\s)(\w+\.\w+)\s*\([^)]*\)',  # module.method(), instance.method()
            r'(?<!function\s)(?<!class\s)(?<!\.)\b(\w+)\s*\([^)]*\)'  # standalone function calls
        ]
        
        calls = set()
        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                call_name = match.group(1)
                # print(f"Found function call: {call_name}")  # Debug log
                # Don't include the function name itself
                if call_name != function_name:
                    calls.add(call_name)
                    # print(f"Added to calls: {call_name}")  # Debug log
        
        # print(f"Final calls for {function_name}: {list(calls)}\n")  # Debug log
        return list(calls)

    def _match_with_known_calls(self, extracted_calls, file_node, source_type="function"):
        """Match extracted calls with same-file targets first, then external calls"""
        matched_calls = []
        
        # Get all available targets in same file
        same_file_functions = file_node.get("names_of_functions_defined", [])
        # print("--------------------------------")
        # print(f"Debug - same_file_functions: {same_file_functions}")
        # print("--------------------------------")
        class_definitions = json.loads(file_node.get("class_definitions", "[]"))
        same_file_methods = {}  # {method_name: class_name}
        
        # Build method lookup
        for class_def in class_definitions:
            class_name = class_def["class_name"]
            for method in class_def.get("methods", []):
                same_file_methods[method["method_name"]] = class_name
        
        # Process external calls data
        known_calls_data = json.loads(file_node["function_calls"])
        
        for call in extracted_calls:
            # Check same-file functions first
            if call in same_file_functions:
                matched_calls.append({
                    "function_call": call,
                    "path": file_node["path"],
                    "is_same_file": True,
                    "type": "function"
                })
                continue
            
            # Check same-file methods
            if call in same_file_methods:
                matched_calls.append({
                    "function_call": call,
                    "path": file_node["path"],
                    "is_same_file": True,
                    "type": "method",
                    "class_name": same_file_methods[call]
                })
                continue
            
            # Check external calls
            for known_call in known_calls_data:
                if call == known_call["function_call"]:
                    known_call["is_same_file"] = False
                    matched_calls.append(known_call)
        
        return matched_calls

    def _analyze_with_llm(self, source_data, target_data, call_info):
        """Use LLM to determine exact target function/method"""
        prompt = {
            "source_imports": source_data["raw_imports"],
            "source_imported_functions": source_data["imported_functions"],
            "source_imported_variables": source_data["imported_variables"],
            "target_exports": {
                "functions": target_data["exported_functions"],
                "classes": target_data["exported_class"],
                "class_methods": [
                    {
                        "class_name": class_def["class_name"],
                        "methods": [m["method_name"] for m in class_def.get("methods", [])]
                    }
                    for class_def in json.loads(target_data["class_definitions"])
                ],
                "names_of_functions_defined": target_data["names_of_functions_defined"]
            },
            "function_call": call_info["function_call"],
            "target_path": call_info["path"]
        }
        
        message = HumanMessage(content=f"""
        Analyze this function call and determine if it's a standalone function or class method.

        Here are examples of different cases:

        1. Standalone Function (exported directly):
        ```javascript
        function add(a, b) {{ return a + b; }}
        module.exports = {{ add }};
        // Response for add():
        {{
            "type": "function",
            "name": "add",
            "class_name": null,
            "confidence": 1.0
        }}
        ```

        2. Class Method:
        ```javascript
        class Database {{
            query(sql) {{ return results; }}
        }}
        // Response for db.query():
        {{
            "type": "method",
            "name": "query",
            "class_name": "Database",
            "confidence": 1.0
        }}
        ```

        3. Module Method (not a class):
        ```javascript
        const utils = {{
            format(str) {{ return str; }}
        }};
        module.exports = utils;
        // Response for utils.format():
        {{
            "type": "function",
            "name": "format",
            "class_name": null,
            "confidence": 1.0
        }}
        ```

        4. Static Class Method:
        ```javascript
        class Math {{
            static abs(n) {{ return Math.abs(n); }}
        }}
        // Response for Math.abs():
        {{
            "type": "method",
            "name": "abs",
            "class_name": "Math",
            "confidence": 1.0
        }}
        ```

        Analyze this data and return the appropriate response:
        {json.dumps(prompt, indent=2)}

        Return your response in this exact format:

        ```json
        {{
            "type": "function|method",
            "name": "actualFunctionName",
            "class_name": "className" if method else null,
            "confidence": 0.0 to 1.0
        }}
        ```
        """)
        
        response = self.llm.invoke([message])
        # print('--------------------------------')
        # print(f"Debug - LLM Response: {response.content}")
        # print('--------------------------------')
        
        try:
            content = response.content
            if '```json' in content:
                content = content.split('```json')[1]
                if '```' in content:
                    content = content.split('```')[0]
            
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            # print(f"Error decoding JSON: {e}")
            # print(f"Raw response: {response.content}")
            return {
                "type": "function",
                "name": call_info["function_call"],
                "class_name": None,
                "confidence": 0.5
            }

    def _create_call_relationship(self, source_info, target_info):
        """Create CALLS relationship between any combination of Function/Method nodes"""
        with self.driver.session() as session:
            if source_info["type"] == "function":
                source_match = """
                MATCH (source:Function {name: $source_name, file_path: $source_path})
                """
            else:
                source_match = """
                MATCH (sourceClass:Class {name: $source_class_name})
                -[:CONTAINS_METHOD]->(source:Method {name: $source_name})
                WHERE sourceClass.file_path = $source_path
                """
            
            if target_info["type"] == "function":
                target_match = """
                MATCH (target:Function {name: $target_name})
                WHERE target.file_path = $target_path
                """
            else:
                target_match = """
                MATCH (targetClass:Class {name: $target_class_name})
                -[:CONTAINS_METHOD]->(target:Method {name: $target_name})
                WHERE targetClass.file_path = $target_path
                """

            cypher = f"""
            {source_match}
            {target_match}
            MERGE (source)-[:CALLS]->(target)
            """
            
            params = {
                "source_name": source_info["name"],
                "source_path": source_info["file_path"],
                "source_class_name": source_info.get("class_name"),
                "target_name": target_info["name"],
                "target_class_name": target_info.get("class_name"),
                "target_path": target_info.get("target_path")
            }
            
            # print("Debug - Cypher Query:", cypher)
            # print("Debug - Query Params:", params)
            
            session.run(cypher, params)

    def process_method_calls(self, method_node, class_node, file_node):
        """Process all calls within a method and create relationships"""
        # print(f"Debug - method_node keys: {method_node.keys()}")
        # print(f"Debug - method_node content: {method_node}")
        
        # Extract calls from method code
        method_code = method_node.get("code")
        if method_code is None:
            # print("Warning: code is None")
            return
        
        extracted_calls = self._extract_function_calls(method_code)
        
        # Match with same-file and external calls
        matched_calls = self._match_with_known_calls(
            extracted_calls, 
            file_node, 
            source_type="method"
        )
        
        source_info = {
            "type": "method",
            "name": method_node["name"],
            "class_name": class_node["class_name"],
            "file_path": file_node["path"]
        }
        
        for call in matched_calls:
            if call.get("is_same_file"):
                # Create relationship to same-file target
                target_info = {
                    "type": call["type"],
                    "name": call["function_call"],
                    "class_name": call.get("class_name"),
                    "target_path": call["path"]
                }
                self._create_call_relationship(source_info, target_info)
            else:
                # Handle external calls
                target_node = self._get_target_file_node(call["path"])
                if not target_node:
                    continue
                
                target_info = self._analyze_with_llm(file_node, target_node, call)
                if target_info["confidence"] > 0.8:
                    target_info["target_path"] = call["path"]  # Add target path here!
                    self._create_call_relationship(source_info, target_info)

    def process_function_calls(self, function_node, file_node):
        """Process all calls within a function and create relationships"""
        # Extract calls from function code
        extracted_calls = self._extract_function_calls(function_node["code"])
        # print('--------------------------------')
        # print(f"Debug - extracted_calls: {extracted_calls}")
        # print('--------------------------------')
        
        # Match with same-file functions first, then known external calls
        matched_calls = self._match_with_known_calls(extracted_calls, file_node)
        # print('--------------------------------')
        # print(f"Debug - matched_calls: {matched_calls}")
        # print('--------------------------------')
        
        source_info = {
            "type": "function",
            "name": function_node["name"],
            "file_path": file_node["path"]
        }
        
        for call in matched_calls:
            if call.get("is_same_file"):
                # Create relationship to function in same file
                # print('--------------------------------')
                # print(f"Debug - same file call: {call}")
                # print('--------------------------------')
                target_info = {
                    "type": call["type"],
                    "name": call["function_call"],
                    "target_path": call["path"]  
                }
                # print(f"Debug - target_info after path fix: {target_info}")
                # print('--------------------------------')
                self._create_call_relationship(source_info, target_info)
            else:
                # Handle external calls
                target_node = self._get_target_file_node(call["path"])
                # # print('--------------------------------')
                # # print(f"Debug - target_node: {target_node}")
                # # print('--------------------------------')
                if not target_node:
                    continue
                target_info = self._analyze_with_llm(file_node, target_node, call)
                # print('--------------------------------')
                # print(f"Debug - target_info: {target_info}")
                # print('--------------------------------')
                # print(f"Debug - source_info: {source_info}")
                # print('--------------------------------')
                if target_info["confidence"] > 0.8:
                    target_info["target_path"] = call["path"]  # Add target path here!
                    self._create_call_relationship(source_info, target_info)

    def _get_target_file_node(self, path):
        """get target node with file path"""
        with self.driver.session() as session:
            # Try exact path first
            result = session.run(
                "MATCH (f:File {path: $path}) RETURN f",
                path=path
            )
            record = result.single()

            return record["f"] if record else None

def test_analyzer(neo4j_uri, neo4j_user, neo4j_password, openai_api_key):
    """Process all functions and methods in the graph"""
    driver = GraphDatabase.driver(
        neo4j_uri, 
        auth=(neo4j_user, neo4j_password)
    )
    
    analyzer = FunctionCallAnalyzer(driver, openai_api_key)
    
    with driver.session() as session:
        # Process all functions
        function_result = session.run("""
        MATCH (func:Function)<-[:CONTAINS_FUNCTION]-(file:File)
        RETURN func, file
        """)


        
        for record in function_result:
            function_node = record["func"]
            file_node = record["file"]
            # print(f"Processing function: {function_node['name']} in {file_node['path']}")
            analyzer.process_function_calls(function_node, file_node)
            
        # Process all methods
        # method_result = session.run("""
        # MATCH (method:Method)<-[:CONTAINS_METHOD]-(class:Class)<-[:CONTAINS_CLASS]-(file:File)
        # RETURN method, class, file
        # """)
        
        # for record in method_result:
        #     method_node = record["method"]
        #     class_node = record["class"]
        #     file_node = record["file"]
        #     # print(f"Processing method: {method_node['name']} in class {class_node['name']} in {file_node['path']}")
        #     analyzer.process_method_calls(method_node, class_node, file_node)
    
    driver.close()

if __name__ == "__main__":
    import os
    
    NEO4J_URI = "bolt://host.docker.internal:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "Shubh@123"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    test_analyzer(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, OPENAI_API_KEY)
