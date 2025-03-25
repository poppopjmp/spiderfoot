#!/usr/bin/env python3
"""
Script to fix issues in the SpiderFoot WebUI test file
"""

import os
import re
import shutil
import sqlite3
import tempfile
from unittest.mock import patch


def fix_webui_test_file():
    """Fix issues in the WebUI test file."""
    filepath = "test/unit/test_sfwebui.py"
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return False

    # Create a backup of the original file
    backup_path = f"{filepath}.bak"
    shutil.copy2(filepath, backup_path)
    print(f"Created backup at {backup_path}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix imports
    if "from unittest.mock import MagicMock, patch" not in content:
        pattern = r"(import unittest.*?)\n"
        replacement = r"\1\nfrom unittest.mock import MagicMock, patch\nfrom test.unit.utils.web_test_helpers import create_web_test_environment\nfrom test.unit.utils.test_base import SpiderFootTestBase\nfrom test.unit.utils.test_helpers import safe_recursion\n"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # Fix setUp method to create a valid temp database for testing
    setup_code = """
    def setUp(self):
        \"\"\"Set up before each test.\"\"\"
        super().setUp()
        
        # Create a valid test environment
        self.default_opts = create_web_test_environment(self)
        
        # Create a mock SpiderFootDb
        self.db_mock = MagicMock()
        with patch('sflib.SpiderFootDb', return_value=self.db_mock):
            self.web = SpiderFootWebUi(self.default_opts)
    """
    
    # Replace the setUp method
    setup_pattern = r"def setUp\(self\):.+?(?=def |$)"
    if re.search(setup_pattern, content, re.DOTALL):
        content = re.sub(setup_pattern, setup_code, content, re.DOTALL)
    else:
        # If no setUp method exists, add it after the class definition
        class_pattern = r"(class TestSpiderFootWebUi\(.+?\):)"
        content = re.sub(class_pattern, r"\1\n" + setup_code, content)

    # Add proper tearDown method
    teardown_code = """
    def tearDown(self):
        \"\"\"Clean up after each test.\"\"\"
        super().tearDown()
        patch.stopall()
    """

    # If tearDown doesn't exist, add it
    if "def tearDown" not in content:
        # Add after setUp method
        content = re.sub(r"(def setUp.+?)(def |$)", r"\1" + teardown_code + r"\2", content, re.DOTALL)
    
    # Fix test methods that directly access the database without checking if opts exist
    # Replace any self.web.opts references with self.default_opts
    content = re.sub(r"self\.web\.opts\['__database'\]", r"self.default_opts['__database']", content)

    # Fix methods that need database access to use the mock
    for method in ["test_scandelete", "test_savesettings", "test_reset_settings"]:
        pattern = fr"(def {method}\(self\).+?)(self\.web\.)"
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, r"\1# Set up database mocks\n        self.db_mock.configGet.return_value = {'test': 'value'}\n        \2", content, re.DOTALL)

    # Write the fixed content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed {filepath}")
    return True


def create_docroot_directory():
    """Create a minimal docroot directory structure for WebUI tests."""
    docroot_dir = "test/docroot"
    os.makedirs(docroot_dir, exist_ok=True)
    
    # Create static directories needed by the web UI
    static_dirs = ["static/css", "static/js", "static/img"]
    for static_dir in static_dirs:
        os.makedirs(os.path.join(docroot_dir, static_dir), exist_ok=True)
    
    # Create a minimal index.html
    with open(os.path.join(docroot_dir, "index.html"), 'w') as f:
        f.write("<html><body><h1>SpiderFoot Test</h1></body></html>")
    
    # Create a minimal style.css
    with open(os.path.join(docroot_dir, "static/css/style.css"), 'w') as f:
        f.write("body { font-family: Arial, sans-serif; }")
    
    print(f"Created minimal docroot directory at {docroot_dir}")
    return True


if __name__ == "__main__":
    # Create docroot directory first
    create_docroot_directory()
    
    # Fix the WebUI test file
    fix_webui_test_file()
