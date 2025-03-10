#!/usr/bin/env python3
"""
Script to update SpiderFoot module test files to use the new wrapper pattern.
This script will modify test files to use the create_module_wrapper method
from the SpiderFootModuleTestCase class.
"""

import os
import re
import sys
import ast

# Path to the test modules directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(BASE_DIR, 'test', 'unit', 'modules')

# Regular expressions for matching patterns in test files
MODULE_IMPORT_RE = re.compile(r'from modules\.([^\s]+) import ([^\s]+)')
TEST_CLASS_RE = re.compile(r'class TestModule([^\(]+)\(SpiderFootModuleTestCase\):')

# Template for the updated setUp method
SETUP_TEMPLATE = """
    def setUp(self):

        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()
        
        # Create module wrapper class dynamically
        self.module_class = self.create_module_wrapper(
            {module_name},
            module_attributes={{
                'descr': "{module_description}",
                # Add any other specific attributes needed by this module
            }}
        )
"""

# Template for test methods
TEST_METHODS_TEMPLATE = """
    def test_opts(self):

        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):

        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, self.default_options)
        self.assertIsNotNone(module.options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):

        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):

        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)
"""


def extract_module_description(file_path, module_name):
    """Extract the module description from the module file."""
    try:
        module_path = os.path.join(BASE_DIR, 'modules', f'{module_name}.py')
        if not os.path.exists(module_path):
            return "Module description unavailable"
        
        with open(module_path, 'r') as file:
            content = file.read()
            
        # Try to parse the Python file
        tree = ast.parse(content)
        
        # Look for class definition
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Look for descr attribute in the class
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == 'descr':
                                if isinstance(item.value, ast.Str):
                                    return item.value.s
                                elif isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                    return item.value.value
        
        return "Module description unavailable"
    except Exception as e:
        print(f"Error extracting description for {module_name}: {e}")
        return "Module description unavailable"


def update_test_file(file_path):
    """Update a single test file to use the wrapper pattern."""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Extract module import
        module_import = MODULE_IMPORT_RE.search(content)
        if not module_import:
            print(f"No module import found in {file_path}, skipping...")
            return False
        
        module_file = module_import.group(1)
        module_name = module_import.group(2)
        
        # Extract test class name
        test_class = TEST_CLASS_RE.search(content)
        if not test_class:
            print(f"No test class found in {file_path}, skipping...")
            return False
        
        # Get module description
        module_description = extract_module_description(file_path, module_file)
        
        # Check if file already has our wrapper pattern
        if 'self.module_class = self.create_module_wrapper(' in content:
            print(f"File {file_path} already uses wrapper pattern, skipping...")
            return False
        
        # Make sure the necessary imports are included
        if 'from unittest.mock import patch, MagicMock' not in content:
            content = content.replace('import unittest', 'import unittest\nfrom unittest.mock import patch, MagicMock')
        
        # Replace any direct module instantiation patterns
        content = re.sub(
            r'module = {}\(\)'.format(module_name), 
            'module = self.module_class()', 
            content
        )
        
        # Add or update setUp method
        if 'def setUp(self):' in content:
            # Replace existing setUp method
            content = re.sub(
                r'def setUp\(self\):.*?(?=\n    def |$)',
                SETUP_TEMPLATE.format(
                    module_name=module_name,
                    module_description=module_description
                ),
                content,
                flags=re.DOTALL
            )
        else:
            # Add setUp method after class definition
            insert_point = content.find('):') + 2
            content = content[:insert_point] + '\n' + SETUP_TEMPLATE.format(
                module_name=module_name,
                module_description=module_description
            ) + content[insert_point:]
        
        # Check if we need to update test methods
        if 'def test_opts(self):' not in content:
            # Insert test methods before the end of class or next method
            match = re.search(r'class TestModule.*?\):', content)
            if match:
                insert_point = match.end()
                content = content[:insert_point] + TEST_METHODS_TEMPLATE + content[insert_point:]
        
        # Write the updated content back
        with open(file_path, 'w') as file:
            file.write(content)
            
        print(f"Updated {file_path}")
        return True
        
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False


def update_all_test_files():
    """Update all test files in the test directory."""
    count = 0
    skipped = 0
    failed = 0
    
    for filename in os.listdir(TEST_DIR):
        if not filename.startswith('test_sfp_') or not filename.endswith('.py'):
            continue
            
        file_path = os.path.join(TEST_DIR, filename)
        print(f"Processing {file_path}...")
        
        result = update_test_file(file_path)
        if result:
            count += 1
        else:
            skipped += 1
    
    print(f"\nUpdated {count} files, skipped {skipped} files, failed {failed} files")


if __name__ == '__main__':
    print("Updating SpiderFoot test files to use the wrapper pattern...")
    update_all_test_files()
