#!/usr/bin/env python3
"""
Script to fix common test method issues in the SpiderFoot test files:
1. Fix reset_mock_objects() to accept self parameter
2. Fix test_handleEvent() to accept depth parameter when decorated with @safe_recursion
3. Fix selfdepth typos in parameter lists
4. Add proper mock setups in setUp methods
"""

import os
import re
import glob

def fix_reset_mock_objects(content):
    """Fix the reset_mock_objects function definition to accept self parameter."""
    pattern = r'def\s+reset_mock_objects\s*\(\s*\):'
    if re.search(pattern, content):
        return re.sub(pattern, 'def reset_mock_objects(self):', content)
    return content

def fix_test_handle_event_methods(content):
    """Fix test methods decorated with @safe_recursion to accept depth parameter."""
    # Look for @safe_recursion decorated methods that don't accept depth parameter
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

def add_setup_mocks(content, test_class_name):
    """Add proper mock setup to the setUp method if not already present."""
    # Different setup code depending on the class
    if 'TestSpiderFootPlugin' in test_class_name:
        setup_code = """
        self.plugin.__sfdb__ = MagicMock()
        self.plugin.sf = MagicMock()
        """
        
        # Check if setUp method exists but doesn't have these mocks
        if 'def setUp' in content and 'self.plugin.__sfdb__ = MagicMock()' not in content:
            pattern = r'(def setUp\(self\):.+?super\(\).setUp\(\))(.*?)((\n\s+?def)|$)'
            content = re.sub(pattern, r'\1' + setup_code + r'\2\3', content, flags=re.DOTALL)
    
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
        """
        
        if 'def setUp' in content and 'self.mock_conn = MagicMock()' not in content:
            pattern = r'(def setUp\(self\):.+?super\(\).setUp\(\))(.*?)((\n\s+?def)|$)'
            content = re.sub(pattern, r'\1' + setup_code + r'\2\3', content, flags=re.DOTALL)
    
    return content

def add_teardown_cleanup(content, test_class_name):
    """Add proper tearDown cleanup if not present."""
    if 'TestSpiderFootDb' in test_class_name:
        teardown_code = """
    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
        self.sqlite_patcher.stop()
        """
        
        if 'def tearDown' not in content:
            pattern = r'(class\s+' + test_class_name + r'.+?)$'
            content = re.sub(pattern, r'\1' + teardown_code, content, flags=re.DOTALL)
    
    return content

def process_file(filepath):
    """Process a single file to fix common test method issues."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    original_content = content
    
    # Extract test class name if present
    test_class_match = re.search(r'class\s+(\w+)\(', content)
    test_class_name = test_class_match.group(1) if test_class_match else ""
    
    # Apply fixes
    content = fix_reset_mock_objects(content)
    content = fix_test_handle_event_methods(content)
    content = fix_selfdepth_typo(content)
    content = add_setup_mocks(content, test_class_name)
    content = add_teardown_cleanup(content, test_class_name)
    
    # If changes were made, write the file
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

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
