#!/usr/bin/env python3
"""
Script to fix common test method issues in the SpiderFoot test files:
1. Fix reset_mock_objects() to accept self parameter
2. Fix test_handleEvent() to accept depth parameter when decorated with @safe_recursion
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

def process_file(filepath):
    """Process a single file to fix common test method issues."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    original_content = content
    
    # Apply fixes
    content = fix_reset_mock_objects(content)
    content = fix_test_handle_event_methods(content)
    
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
