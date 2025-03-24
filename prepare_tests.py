#!/usr/bin/env python3
"""
Script to prepare SpiderFoot tests for running
1. Fix reset_mock_objects() to accept self parameter
2. Fix test_handleEvent() to accept depth parameter with @safe_recursion 
3. Fix mocking in test setups
4. Fix teardown cleanup methods
"""

import os
import re
import glob
import sys
import importlib.util
from pathlib import Path

def fix_reset_mock_objects(content):
    """Fix the reset_mock_objects function to accept self parameter."""
    pattern = r'def\s+reset_mock_objects\s*\(\s*\):'
    if re.search(pattern, content):
        return re.sub(pattern, 'def reset_mock_objects(self):', content)
    return content

def fix_test_handle_event_methods(content):
    """Fix test methods decorated with @safe_recursion to accept depth parameter."""
    pattern = r'(@safe_recursion\([^)]*\)\s*\n\s*)def\s+(test[^(]*)\s*\(\s*self\s*\):'
    if re.search(pattern, content):
        return re.sub(pattern, r'\1def \2(self, depth=0):', content)
    return content

def fix_selfdepth_typo(content):
    """Fix methods with selfdepth parameter typo."""
    pattern = r'def\s+(test[^(]*)\s*\(\s*selfdepth\s*=\s*0\s*\):'
    if re.search(pattern, content):
        return re.sub(pattern, r'def \1(self, depth=0):', content)
    return content

def add_import_statements(content, module_type):
    """Add necessary import statements."""
    imports = ""
    
    # Check if imports already exist
    if module_type == "plugin" and "import unittest" in content and "from unittest.mock import MagicMock, patch" not in content:
        imports = "from unittest.mock import MagicMock, patch\n"
    
    # Add the imports if needed
    if imports:
        # Find the right spot after the last import
        import_pattern = r'(import [^\n]+\n|from [^\n]+ import [^\n]+\n)'
        matches = list(re.finditer(import_pattern, content))
        if matches:
            last_match = matches[-1]
            content = content[:last_match.end()] + imports + content[last_match.end():]
    
    return content

def add_setup_mocks(content, test_class_name):
    """Add proper mock setup to the setUp method if not already present."""
    if 'TestSpiderFootPlugin' in test_class_name or 'TestModule' in test_class_name:
        setup_code = """
        # Setup proper mock objects
        if hasattr(self, 'plugin'):
            self.plugin.__sfdb__ = MagicMock()
            self.plugin.sf = MagicMock()
        # Setup proper module mock objects
        if hasattr(self, 'module'):
            self.module.__sfdb__ = MagicMock()
            self.module.sf = MagicMock()
        """
        
        # Check if setUp method exists
        if 'def setUp' in content:
            # If setup already has these mocks, don't add them
            if 'self.plugin.__sfdb__ = MagicMock()' not in content and 'self.module.__sfdb__ = MagicMock()' not in content:
                # Add after super().setUp() call
                pattern = r'(def setUp\(self\):.+?super\(\).setUp\(\))(.*?)((\n\s+?def)|$)'
                content = re.sub(pattern, r'\1' + setup_code + r'\2\3', content, flags=re.DOTALL)
        else:
            # Add a setUp method if it doesn't exist
            setup_method = f"""
    def setUp(self):
        super().setUp(){setup_code}
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)
"""
            # Add after class definition
            pattern = r'(class\s+{}\(.+?\):)(\s*)'.format(test_class_name)
            content = re.sub(pattern, r'\1\2' + setup_method, content, flags=re.DOTALL)
    
    elif 'TestSpiderFootDb' in test_class_name:
        setup_code = """
        # Create a mock cursor and connection
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        
        # Setup patching for sqlite3
        self.sqlite_patcher = patch('spiderfoot.db.sqlite3')
        self.mock_sqlite = self.sqlite_patcher.start()
        self.mock_sqlite.connect.return_value = self.mock_conn
        
        # Set default test options
        self.opts = {
            '__database': 'test.db',
            '__dbtype': 'sqlite'
        }
        
        # Initialize the db with our mocked connection
        self.db = SpiderFootDb(self.opts)
        """
        
        if 'def setUp' in content and 'self.mock_conn = MagicMock()' not in content:
            pattern = r'(def setUp\(self\):.+?super\(\).setUp\(\))(.*?)((\n\s+?def)|$)'
            content = re.sub(pattern, r'\1' + setup_code + r'\2\3', content, flags=re.DOTALL)
        
    elif 'TestSpiderFootWebUi' in test_class_name:
        # For WebUI tests, we need to mock the database and provide valid config options
        setup_code = """
        # Create a valid configuration for testing
        self.default_opts = {
            '__database': ':memory:',
            '__modules__': '',
            '__correlations__': '',
            '_dnsserver': '',
            '_fetchtimeout': 5,
            '_docroot': '',
            '_weblogfile': '',
            '_useragent': 'Mozilla',
            '__logging': True,
            '_debug': False,
            '_test': True
        }
        """
        
        if 'def setUp' in content and 'self.default_opts =' not in content:
            pattern = r'(def setUp\(self\):.+?super\(\).setUp\(\))(.*?)((\n\s+?def)|$)'
            content = re.sub(pattern, r'\1' + setup_code + r'\2\3', content, flags=re.DOTALL)
    
    return content

def add_teardown_cleanup(content, test_class_name):
    """Add proper tearDown cleanup if not present."""
    if 'TestSpiderFootDb' in test_class_name and 'self.sqlite_patcher.stop()' not in content:
        teardown_code = """
    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
        self.sqlite_patcher.stop()
        """
        
        if 'def tearDown' not in content:
            pattern = r'(class\s+' + test_class_name + r'.+?)$'
            content = re.sub(pattern, r'\1' + teardown_code, content, flags=re.DOTALL)
    
    elif 'TestSpiderFootPlugin' in test_class_name or 'TestModule' in test_class_name:
        teardown_code = """
    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
        patch.stopall()
        """
        
        if 'def tearDown' not in content or 'patch.stopall' not in content:
            if 'def tearDown' in content:
                # Add to existing tearDown
                pattern = r'(def tearDown\(self\):.+?super\(\).tearDown\(\))(.*?)((\n\s+?def)|$)'
                content = re.sub(pattern, r'\1\n        patch.stopall()\2\3', content, flags=re.DOTALL)
            else:
                # Add new tearDown method
                pattern = r'(class\s+' + test_class_name + r'.+?)$'
                content = re.sub(pattern, r'\1' + teardown_code, content, flags=re.DOTALL)
    
    return content

def fix_spiderfoot_db(content):
    """Fix SpiderFootDb mocking in test_threadWorker methods."""
    # Replace SpiderFootDb with a proper mock in threadWorker tests
    pattern = r'(with patch\()\'spiderfoot\.plugin\.SpiderFootDb\''
    if re.search(pattern, content):
        content = re.sub(pattern, r'\1\'spiderfoot.plugin.SpiderFootDb\', create=True', content)
    return content

def process_file(filepath):
    """Process a single file to fix common test method issues."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    original_content = content
    
    # Extract test class name if present
    test_class_match = re.search(r'class\s+(\w+)\(', content)
    test_class_name = test_class_match.group(1) if test_class_match else ""
    
    # Determine module type for specific fixes
    module_type = "unknown"
    if 'test_spiderfootplugin.py' in filepath:
        module_type = "plugin"
    elif 'test_spiderfootdb.py' in filepath:
        module_type = "db"
    elif 'test_sfwebui.py' in filepath:
        module_type = "webui"
    elif '/modules/' in filepath:
        module_type = "module"
    
    # Apply general fixes
    content = fix_reset_mock_objects(content)
    content = fix_test_handle_event_methods(content)
    content = fix_selfdepth_typo(content)
    
    # Apply specific fixes
    content = add_import_statements(content, module_type)
    content = add_setup_mocks(content, test_class_name)
    content = add_teardown_cleanup(content, test_class_name)
    content = fix_spiderfoot_db(content)
    
    # If changes were made, write the file
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def verify_test_base():
    """Verify and fix the test base class if necessary."""
    base_file = "test/unit/utils/test_base.py"
    
    if not os.path.exists(base_file):
        print(f"Warning: Test base file {base_file} does not exist!")
        return False
    
    with open(base_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Make sure test base has proper register_event_emitter method
    if "def register_event_emitter" not in content:
        # Add the method if missing
        patch = """
    def register_event_emitter(self, module):
        """Register an event emitter module with the registry."""
        if not hasattr(self, '_event_emitters'):
            self._event_emitters = []
        
        if module not in self._event_emitters:
            self._event_emitters.append(module)
"""
        # Add after the class definition
        pattern = r'(class SpiderFootTestBase\(unittest\.TestCase\):)'
        content = re.sub(pattern, r'\1' + patch, content)
        
        # Write back the modified file
        with open(base_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Fixed: {base_file}")
        return True
    
    return False

def main():
    """Main function to process all test files."""
    # Verify the test base class first
    verify_test_base()
    
    # Find all test files
    test_files = glob.glob('test/unit/**/*.py', recursive=True)
    
    # Track statistics
    fixed_count = 0
    error_count = 0
    
    # Process each file
    for test_file in test_files:
        try:
            if process_file(test_file):
                fixed_count += 1
                print(f"Fixed: {test_file}")
        except Exception as e:
            error_count += 1
            print(f"Error processing {test_file}: {str(e)}")
    
    print(f"\nTotal files fixed: {fixed_count}")
    print(f"Total errors: {error_count}")
    print(f"Total files processed: {len(test_files)}")
    
    # Copy the mock_db.py file if it doesn't exist
    mock_db_file = "test/unit/utils/mock_db.py"
    if not os.path.exists(mock_db_file):
        os.makedirs(os.path.dirname(mock_db_file), exist_ok=True)
        # We'll need to create this file manually as it's a new utility

if __name__ == "__main__":
    main()
