# JavaScript Regex Patterns
JS_PATTERNS = {
    'imports': {
        'es6_import': r'import\s+(?:{[^}]+}|\*\s+as\s+\w+|\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',
        'require': r'(?:const|let|var)\s+(?:\w+|\{[^}]+\})\s*=\s*require\s*\([\'"]([^\'"]+)[\'"]\)',
        'dynamic_import': r'import\s*\([\'"]([^\'"]+)[\'"]\)',
        'export_from': r'export\s+(?:{[^}]+}|\*)\s+from\s+[\'"]([^\'"]+)[\'"]',
        'side_effect_import': r'import\s+[\'"]([^\'"]+)[\'"]',
    },
    
    'functions': {
        'function_declaration': r'function\s+(\w+)\s*\([^)]*\)',
        'arrow_function': r'(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=]+)\s*=>\s*[{]?',
        'method': r'(\w+)\s*\([^)]*\)\s*{',
        'async_function': r'async\s+function\s*(\w+)\s*\([^)]*\)',
        'generator_function': r'function\s*\*\s*(\w+)\s*\([^)]*\)',
        'async_arrow': r'(?:const|let|var)\s+(\w+)\s*=\s*async\s*(?:\([^)]*\)|[^=]+)\s*=>\s*[{]?',
        'jsx_component': r'(?:function|const)\s+([A-Z]\w*)\s*(?:\([^)]*\)|=)',
    },
    
    'classes': {
        'class_declaration': r'class\s+(\w+)(?:\s+extends\s+(\w+))?',
        'class_expression': r'(?:const|let|var)\s+(\w+)\s*=\s*class\s*(?:\w+)?',
        'react_class': r'class\s+(\w+)\s+extends\s+(?:React\.Component|Component)',
        'decorator_class': r'@\w+(?:\([^)]*\))?\s*class\s+(\w+)',
    },
    
    'exports': {
        'named_export': r'export\s+(?:const|let|var|function|class)\s+(\w+)',
        'default_export': r'export\s+default\s+(?:class|function)?\s*(\w+)?',
        'export_object': r'export\s*{([^}]+)}',
    },

    'react_hooks': {
        'use_state': r'const\s+\[(\w+),\s*set(\w+)\]\s*=\s*useState',
        'use_effect': r'useEffect\s*\(\s*\(\)\s*=>\s*{',
        'use_callback': r'useCallback\s*\(\s*\([^)]*\)\s*=>\s*{',
        'use_memo': r'useMemo\s*\(\s*\(\)\s*=>\s*{',
        'use_ref': r'const\s+(\w+)\s*=\s*useRef',
        'custom_hook': r'const\s+(\w+)\s*=\s*use\w+',
    },

    'typescript': {
        'interface': r'interface\s+(\w+)(?:\s+extends\s+[^{]+)?',
        'type': r'type\s+(\w+)\s*=',
        'enum': r'enum\s+(\w+)',
        'generic_type': r'<[^>]+>',
    }
}

# Python Regex Patterns
PY_PATTERNS = {
    'imports': {
        'import': r'import\s+(\w+)',
        'from_import': r'from\s+([\w.]+)\s+import\s+(?:\w+(?:\s*,\s*\w+)*|\*)',
        'as_import': r'import\s+(\w+)\s+as\s+\w+',
        'multiple_import': r'from\s+([\w.]+)\s+import\s*\((?:[^)]+)\)',
        'relative_import': r'from\s*\.*(\w+)',
    },
    
    'functions': {
        'function_declaration': r'def\s+(\w+)\s*\([^)]*\)\s*:',
        'async_function': r'async\s+def\s+(\w+)\s*\([^)]*\)\s*:',
        'lambda': r'(\w+)\s*=\s*lambda[^:]+:',
        'decorated_function': r'@\w+(?:\([^)]*\))?\s*(?:async\s+)?def\s+(\w+)',
        'type_hinted_function': r'def\s+(\w+)\s*\([^)]*\)\s*->\s*\w+\s*:',
    },
    
    'classes': {
        'class_declaration': r'class\s+(\w+)(?:\([^)]*\))?:',
        'decorated_class': r'@\w+(?:\([^)]*\))?\s*class\s+(\w+)',
        'dataclass': r'@dataclass\s*class\s+(\w+)',
        'abc_class': r'class\s+(\w+)\((?:ABC|metaclass=\w+)\):',
    },
    
    'variables': {
        'global_vars': r'(?:^|\s+)(\w+)\s*=(?!=)',
        'type_annotated_vars': r'(\w+)\s*:\s*\w+(?:\[.+\])?\s*=',
        'class_vars': r'(?:^|\s+)(\w+)\s*:\s*\w+(?:\[.+\])?',
    },

    'async_patterns': {
        'coroutine': r'async\s+(?:def|with|for)',
        'await': r'await\s+\w+',
    },

    'type_hints': {
        'type_alias': r'(\w+)\s*=\s*(?:Union|Optional|List|Dict|Set|Tuple)',
        'protocol': r'class\s+(\w+)\(Protocol\):',
        'generic': r'(?:List|Dict|Set|Tuple)\[.+\]',
    }
}
