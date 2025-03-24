#!/usr/bin/env python3
"""
Script to fix reset_mock_objects() method in test files.
This fixes the TypeError: reset_mock_objects() takes 0 positional arguments but 1 was given
"""

import os
import re
import glob

def fix_reset_mock_objects(filepath):
    """Fix the reset_mock_objects function in a file."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Check if the file has the problematic function definition
    pattern = r'def\s+reset_mock_objects\s*\(\s*\):'
    if not re.search(pattern, content):
        return False
    
    # Replace the function definition with one that accepts self
    fixed_content = re.sub(pattern, 'def reset_mock_objects(self):', content)
    
    with open(filepath, 'w') as f:
        f.write(fixed_content)
    
    return True

# Find all test files
test_files = glob.glob('test/unit/**/*.py', recursive=True)

# Count how many files were fixed
fixed_count = 0

# Process each file
for test_file in test_files:
    if fix_reset_mock_objects(test_file):
        fixed_count += 1
        print(f"Fixed: {test_file}")

print(f"\nTotal files fixed: {fixed_count}")
