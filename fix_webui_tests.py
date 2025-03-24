#!/usr/bin/env python3
"""
Script to fix SpiderFootWebUi tests
"""

import os
import re


def fix_webui_tests():
    """Fix SpiderFootWebUi tests to use the proper test environment."""
    filepath = "test/unit/test_sfwebui.py"
    
    if not os.path.exists(filepath):
        print(f"WebUI test file not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add the necessary imports
    if "from test.unit.utils.web_test_helpers import create_web_test_environment" not in content:
        import_pattern = r'(import unittest.*?\n)'
        import_replacement = r'\1from test.unit.utils.web_test_helpers import create_web_test_environment\n'
        content = re.sub(import_pattern, import_replacement, content, flags=re.DOTALL)
    
    # Fix the setUp method
    if "create_web_test_environment" not in content:
        setup_pattern = r'(def setUp\(self\):.*?\n)(\s+)self\.web = SpiderFootWebUi\(self\.default_opts\)'
        setup_replacement = r'\1\2self.default_opts = create_web_test_environment(self)\n\2self.web = SpiderFootWebUi(self.default_opts)'
        content = re.sub(setup_pattern, setup_replacement, content, flags=re.DOTALL)
    
    # Make sure tearDown cleans up properly
    if "def tearDown" not in content:
        teardown_code = """
    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
"""
        # Add after the class definition
        class_pattern = r'(class TestSpiderFootWebUi\(.*?\):)'
        content = re.sub(class_pattern, r'\1' + teardown_code, content, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed: {filepath}")
    return True


def fix_cli_tests():
    """Fix SpiderFootCli tests to use the proper test environment."""
    filepath = "test/unit/test_spiderfootcli.py"
    
    if not os.path.exists(filepath):
        print(f"CLI test file not found: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add the necessary imports
    if "from test.unit.utils.cli_test_helpers import setup_cli_test_environment" not in content:
        import_pattern = r'(import unittest.*?\n)'
        import_replacement = r'\1from test.unit.utils.cli_test_helpers import setup_cli_test_environment, mock_cli_arguments\n'
        content = re.sub(import_pattern, import_replacement, content, flags=re.DOTALL)
    
    # Fix the setUp method
    if "setup_cli_test_environment" not in content:
        setup_pattern = r'(def setUp\(self\):.*?\n)(\s+)(.*)'
        setup_replacement = r'\1\2setup_cli_test_environment(self)\n\2self.restore_argv = mock_cli_arguments()\n\2\3'
        content = re.sub(setup_pattern, setup_replacement, content, flags=re.DOTALL)
    
    # Make sure tearDown cleans up properly
    if "def tearDown" not in content:
        teardown_code = """
    def tearDown(self):
        """Clean up after each test."""
        self.restore_argv()
        super().tearDown()
"""
        # Add after the class definition
        class_pattern = r'(class TestSpiderFootCli\(.*?\):)'
        content = re.sub(class_pattern, r'\1' + teardown_code, content, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed: {filepath}")
    return True


if __name__ == "__main__":
    # Ensure the directory for test helpers exists
    os.makedirs("test/unit/utils", exist_ok=True)
    
    # Fix the tests
    fix_webui_tests()
    fix_cli_tests()
    
    print("WebUI and CLI tests fixed. Now run the tests with pytest.")
