#!/usr/bin/env python3
"""Script to systematically fix common issues in SpiderFoot test files."""

import os
import re
import ast
import argparse
from pathlib import Path


def find_test_files(base_path):
    """Find all test files in the given base path."""
    test_files = []
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))
    return test_files


def read_file(file_path):
    """Read the contents of a file."""
    with open(file_path, 'r') as f:
        return f.read()


def write_file(file_path, content):
    """Write content to a file."""
    with open(file_path, 'w') as f:
        f.write(content)


def add_imports(content):
    """Add necessary imports to the test file."""
    imports_to_add = [
        "from test.unit.utils.test_base import SpiderFootTestBase",
        "from test.unit.utils.test_helpers import safe_recursion"
    ]
    
    # Check if imports already exist
    for imp in imports_to_add:
        if imp in content:
            imports_to_add.remove(imp)
    
    if not imports_to_add:
        return content
    
    import_str = "\n".join(imports_to_add)
    
    # Try to add after existing imports
    if "import" in content:
        lines = content.split('\n')
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                last_import_idx = i
        
        if last_import_idx > 0:
            return '\n'.join(lines[:last_import_idx + 1]) + '\n' + import_str + '\n' + '\n'.join(lines[last_import_idx + 1:])
    
    # If no imports found, add at the top after any comments/docstring
    return import_str + '\n' + content


def update_class_inheritance(content):
    """Update test class to inherit from SpiderFootTestBase."""
    pattern = r'class\s+(\w+)\((?:unittest\.)?TestCase\):'
    return re.sub(pattern, r'class \1(SpiderFootTestBase):', content)


def add_setup_method(content):
    """Add or update setUp method to register emitters and mocks."""
    if "setUp" not in content:
        # Find the class definition
        class_pattern = r'class\s+(\w+)\(SpiderFootTestBase\):([^\n]*\n(?:\s+[^\n]*\n)*)'
        class_match = re.search(class_pattern, content)
        if class_match:
            indent = "    "  # Assuming 4-space indentation
            setup_method = f"{indent}def setUp(self):\n"
            setup_method += f"{indent}{indent}\"\"\"Set up before each test.\"\"\"\n"
            setup_method += f"{indent}{indent}super().setUp()\n"
            setup_method += f"{indent}{indent}# Register event emitters if they exist\n"
            setup_method += f"{indent}{indent}if hasattr(self, 'module'):\n"
            setup_method += f"{indent}{indent}{indent}self.register_event_emitter(self.module)\n"
            
            # Insert after class definition
            class_def_end = class_match.end()
            return content[:class_def_end] + "\n" + setup_method + content[class_def_end:]
    else:
        # Update existing setUp method
        setup_pattern = r'def setUp\(self\):(.*?)(?=\n\s*def|\n\s*$|\Z)'
        
        def setup_replacer(match):
            existing_setup = match.group(1)
            if "super().setUp()" not in existing_setup:
                existing_setup = "\n        super().setUp()" + existing_setup
            if "register_event_emitter" not in existing_setup:
                register_code = "\n        # Register event emitters if they exist"
                register_code += "\n        if hasattr(self, 'module'):"
                register_code += "\n            self.register_event_emitter(self.module)"
                existing_setup += register_code
            return f"def setUp(self):{existing_setup}"
        
        return re.sub(setup_pattern, setup_replacer, content, flags=re.DOTALL)
    
    return content


def update_teardown_method(content):
    """Add or update tearDown method to ensure super().tearDown() is called."""
    if "tearDown" not in content:
        # Find the class definition
        class_pattern = r'class\s+(\w+)\(SpiderFootTestBase\):'
        class_match = re.search(class_pattern, content)
        if class_match:
            # Find end of class to append tearDown
            class_end = len(content)
            indent = "    "  # Assuming 4-space indentation
            teardown_method = f"\n{indent}def tearDown(self):\n"
            teardown_method += f"{indent}{indent}\"\"\"Clean up after each test.\"\"\"\n"
            teardown_method += f"{indent}{indent}super().tearDown()\n"
            
            # Append at end of file
            return content + teardown_method
    else:
        # Update existing tearDown method
        teardown_pattern = r'def tearDown\(self\):(.*?)(?=\n\s*def|\n\s*$|\Z)'
        
        def teardown_replacer(match):
            existing_teardown = match.group(1)
            if "super().tearDown()" not in existing_teardown:
                if existing_teardown.strip():
                    # Add super call at end if there's content
                    existing_teardown = existing_teardown + "\n        super().tearDown()"
                else:
                    # Just add super call if empty
                    existing_teardown = "\n        super().tearDown()"
            return f"def tearDown(self):{existing_teardown}"
        
        return re.sub(teardown_pattern, teardown_replacer, content, flags=re.DOTALL)
    
    return content


def add_safe_recursion_decorator(content):
    """Add safe_recursion decorator to recursive functions."""
    # Find test methods that might be recursive
    test_method_pattern = r'def\s+(test_\w+)\(self(?:,\s*\w+=[^)]+)?\):'
    
    def add_decorator(match):
        method_name = match.group(1)
        # Only add for certain methods we know are recursive
        if any(name in method_name for name in ["handleEvent", "recurse", "recursive"]):
            return f"@safe_recursion(max_depth=5)\n    {match.group(0)}"
        return match.group(0)
    
    return re.sub(test_method_pattern, add_decorator, content)


def update_method_signatures_with_depth(content):
    """Update method signatures of decorated functions to include depth parameter."""
    # Find methods with the safe_recursion decorator
    decorated_methods_pattern = r'@safe_recursion\(max_depth=\d+\)\s+def\s+(\w+)\(self((?:,\s*\w+=[^)]+)?)?\):'
    
    def update_signature(match):
        method_name = match.group(1)
        params = match.group(2) or ""
        
        if "depth=" not in params:
            params += ", depth=0" if params else "depth=0"
        
        return f"@safe_recursion(max_depth=5)\n    def {method_name}(self{params}):"
    
    return re.sub(decorated_methods_pattern, update_signature, content)


def register_mocks_in_setup(content):
    """Update setUp to register mocks."""
    # Check if setUp method exists and doesn't register mocks
    if "setUp" in content and "self.register_mock" not in content:
        setup_pattern = r'def setUp\(self\):(.*?)(?=\n\s*def|\n\s*$|\Z)'
        
        def setup_replacer(match):
            existing_setup = match.group(1)
            # Simple pattern to find common mock variable names
            mock_pattern = r'\s*(self\.mock_\w+|mock_\w+)\s*='
            mock_vars = re.findall(mock_pattern, existing_setup)
            
            if mock_vars:
                register_code = "\n        # Register mocks for cleanup during tearDown"
                for var in mock_vars:
                    if var.startswith("self."):
                        register_code += f"\n        self.register_mock({var})"
                    else:
                        register_code += f"\n        if '{var}' in locals():"
                        register_code += f"\n            self.register_mock({var})"
                
                existing_setup += register_code
            
            return f"def setUp(self):{existing_setup}"
        
        return re.sub(setup_pattern, setup_replacer, content, flags=re.DOTALL)
    
    return content


def register_patchers_in_setup(content):
    """Update setUp to register patchers."""
    # Check if setUp method exists and doesn't register patchers but uses patch
    if "setUp" in content and "patch(" in content and "self.register_patcher" not in content:
        setup_pattern = r'def setUp\(self\):(.*?)(?=\n\s*def|\n\s*$|\Z)'
        
        def setup_replacer(match):
            existing_setup = match.group(1)
            # Simple pattern to find patcher variables
            patcher_pattern = r'\s*(self\.(?:patcher|patch)_\w+|(?:patcher|patch)_\w+)\s*='
            patcher_vars = re.findall(patcher_pattern, existing_setup)
            
            # Also look for patch calls
            patch_pattern = r'(self\.)?(\w+)\s*=\s*patch\('
            patch_vars = re.findall(patch_pattern, existing_setup)
            patch_vars = [v[1] for v in patch_vars]
            
            all_patchers = set(patcher_vars + patch_vars)
            
            if all_patchers:
                register_code = "\n        # Register patchers for cleanup during tearDown"
                for var in all_patchers:
                    if var.startswith("self."):
                        register_code += f"\n        self.register_patcher({var})"
                    else:
                        register_code += f"\n        if '{var}' in locals():"
                        register_code += f"\n            self.register_patcher({var})"
                
                existing_setup += register_code
            
            return f"def setUp(self):{existing_setup}"
        
        return re.sub(setup_pattern, setup_replacer, content, flags=re.DOTALL)
    
    return content


def fix_file_operations(content):
    """Replace file operations with context managers."""
    # Find all open() calls first
    open_pattern = r'\bopen\s*\([^\)]+\)'
    open_calls = list(re.finditer(open_pattern, content))
    
    # Process each match from end to beginning to avoid offset issues
    for match in reversed(open_calls):
        start, end = match.span()
        
        # Get the line containing the match
        line_start = content.rfind('\n', 0, start) + 1
        line_end = content.find('\n', end)
        if line_end == -1:
            line_end = len(content)
        line = content[line_start:line_end]
        
        # Skip if already in a with statement or part of a function definition/return
        # or inside string literals
        if ('with ' in line and 'open(' in line) or 'def ' in line or 'return ' in line:
            continue
        if "'" + match.group(0) + "'" in line or '"' + match.group(0) + '"' in line:
            continue
        
        # Replace with context manager
        replacement = f"with {match.group(0)} as f"
        content = content[:start] + replacement + content[end:]
    
    return content


def fix_monkey_patching(content):
    """Fix monkey patching issues by ensuring proper restoration."""
    # Pattern for direct attribute assignment (monkey patching)
    monkey_patch_pattern = r'(\w+(?:\.\w+)*)\.(\w+)\s*=\s*([^;]+)'
    
    # Find all potential monkey patches
    monkey_patches = re.findall(monkey_patch_pattern, content)
    
    # If no monkey patches found, return original content
    if not monkey_patches:
        return content
        
    # Create backup and restoration code for each monkey patch
    restore_code = []
    backup_code = []
    
    for obj, attr, replacement in monkey_patches:
        # Skip if it's a simple variable assignment, not monkey patching
        if '.' not in obj and not re.search(r'\[|\(|\{', obj):
            continue
            
        # Skip common non-monkey-patch assignments
        if any(skip in f"{obj}.{attr}" for skip in ['self.options', 'self.db', 'self.sf']):
            continue
            
        # Generate a unique backup variable name
        backup_var = f"_original_{obj.replace('.', '_')}_{attr}"
        
        # Add backup code to setUp
        backup_code.append(f"self.{backup_var} = {obj}.{attr} if hasattr({obj}, '{attr}') else None")
        
        # Add restoration code to tearDown
        restore_code.append(f"if hasattr(self, '{backup_var}') and self.{backup_var} is not None:")
        restore_code.append(f"    {obj}.{attr} = self.{backup_var}")
        restore_code.append(f"elif hasattr({obj}, '{attr}'):")
        restore_code.append(f"    delattr({obj}, '{attr}')")
    
    # If we found monkey patches, update setUp and tearDown methods
    if backup_code:
        # Update setUp to include backup code
        if "setUp" in content:
            setup_pattern = r'def setUp\(self\):(.*?)(?=\n\s*def|\n\s*$|\Z)'
            
            def setup_replacer(match):
                existing_setup = match.group(1)
                backup_str = "\n        # Backup original methods before monkey patching\n        "
                backup_str += "\n        ".join(backup_code)
                existing_setup += backup_str
                return f"def setUp(self):{existing_setup}"
            
            content = re.sub(setup_pattern, setup_replacer, content, flags=re.DOTALL)
        
        # Update tearDown to include restoration code
        if "tearDown" in content:
            teardown_pattern = r'def tearDown\(self\):(.*?)(?=\n\s*super\(\)\.tearDown|\n\s*def|\n\s*$|\Z)'
            
            def teardown_replacer(match):
                existing_teardown = match.group(1)
                restore_str = "\n        # Restore original methods after monkey patching\n        "
                restore_str += "\n        ".join(restore_code)
                existing_teardown += restore_str
                return f"def tearDown(self):{existing_teardown}"
            
            content = re.sub(teardown_pattern, teardown_replacer, content, flags=re.DOTALL)
    
    # Add code to use the register_monkey_patch method from SpiderFootTestBase
    if "monkey patching" in content.lower() and "register_monkey_patch" not in content:
        setup_pattern = r'def setUp\(self\):(.*?)(?=\n\s*def|\n\s*$|\Z)'
        
        def setup_replacer(match):
            existing_setup = match.group(1)
            # Extract potential objects being patched
            obj_pattern = r'(\w+(?:\.\w+)*)\.\w+\s*='
            objs = re.findall(obj_pattern, existing_setup)
            
            if objs:
                register_code = "\n        # Register monkey patches for automatic restoration\n"
                for obj in set(objs):
                    if '.' in obj:  # Only add for object attributes, not simple variables
                        obj_parts = obj.split('.')
                        base_obj = '.'.join(obj_parts[:-1])
                        attr = obj_parts[-1]
                        register_code += f"        # Register monkey patch for restoration\n"
                        register_code += f"        self.register_monkey_patch({base_obj}, '{attr}')\n"
                
                existing_setup += register_code
            
            return f"def setUp(self):{existing_setup}"
            
        content = re.sub(setup_pattern, setup_replacer, content, flags=re.DOTALL)
    
    return content


def process_file(file_path, dry_run=False):
    """Process a single test file and apply all fixes."""
    print(f"Processing {file_path}...")
    content = read_file(file_path)
    original_content = content
    
    # Apply fixes
    content = add_imports(content)
    content = update_class_inheritance(content)
    content = add_setup_method(content)
    content = update_teardown_method(content)
    content = add_safe_recursion_decorator(content)
    content = update_method_signatures_with_depth(content)
    content = register_mocks_in_setup(content)
    content = register_patchers_in_setup(content)
    content = fix_file_operations(content)
    content = fix_monkey_patching(content)
    
    if content != original_content:
        print(f"Changes needed for {file_path}")
        if not dry_run:
            write_file(file_path, content)
            print(f"Updated {file_path}")
        else:
            print("Dry run: no changes made")
    else:
        print(f"No changes needed for {file_path}")


def main():
    """Main function to fix test files."""
    parser = argparse.ArgumentParser(description="Fix common issues in SpiderFoot test files")
    parser.add_argument("--base-path", default="test/unit", help="Base path to search for test files")
    parser.add_argument("--dry-run", action="store_true", help="Don't make any actual changes")
    parser.add_argument("--file", help="Process a specific file instead of searching")
    args = parser.parse_args()
    
    base_path = args.base_path
    dry_run = args.dry_run
    
    if args.file:
        process_file(args.file, dry_run)
    else:
        test_files = find_test_files(base_path)
        print(f"Found {len(test_files)} test files")
        
        for file_path in test_files:
            process_file(file_path, dry_run)


if __name__ == "__main__":
    main()
