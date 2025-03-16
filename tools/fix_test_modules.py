"""
Script to fix common issues in SpiderFoot module test files.
This adds required docstrings and initializations to test files.
"""
import os
import re

def fix_test_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract module name from file path
    module_name = os.path.basename(file_path).replace('test_', '').replace('.py', '')
    class_name = module_name.replace('sfp_', '').title().replace('_', '')
    
    # Check if file already has a docstring
    has_docstring = re.search(r'^""".*?"""', content, re.DOTALL) is not None
    
    # Check if setUp already has default_options
    has_default_options = 'self.default_options' in content
    
    # Check if setUp already has module initialization
    has_module_init = 'self.module =' in content
    
    # Prepare the new content
    if not has_docstring:
        docstring = f'"""\nTest module for {module_name}.\nThis module contains unit tests for the {class_name} SpiderFoot plugin.\n"""\n'
        import_match = re.search(r'import.*?\n\n', content, re.DOTALL)
        if import_match:
            pos = import_match.end()
            content = content[:pos] + docstring + content[pos:]
        else:
            content = docstring + content
    
    # Fix setUp method
    setup_pattern = r'def setUp\(self\):(.*?)def'
    setup_match = re.search(setup_pattern, content, re.DOTALL)
    
    if setup_match:
        setup_content = setup_match.group(1)
        new_setup = '    def setUp(self):\n        """Set up before each test."""\n        super().setUp()\n'
        
        if not has_default_options:
            new_setup += '        # Initialize default options\n        self.default_options = self.default_options or {}\n'
        
        if not has_module_init:
            new_setup += f'        # Initialize module\n        self.module = {module_name}()\n'
        
        new_setup += '        # Register event emitters if they exist\n        self.register_event_emitter(self.module)\n'
        
        content = re.sub(setup_pattern, new_setup + '    def ', content, flags=re.DOTALL)
    else:
        # If no setUp method exists, add it after the class definition
        class_pattern = r'class TestModule.*?:\n'
        class_match = re.search(class_pattern, content)
        if class_match:
            pos = class_match.end()
            new_setup = '\n    def setUp(self):\n        """Set up before each test."""\n        super().setUp()\n'
            new_setup += '        # Initialize default options\n        self.default_options = self.default_options or {}\n'
            new_setup += f'        # Initialize module\n        self.module = {module_name}()\n'
            new_setup += '        # Register event emitters if they exist\n        self.register_event_emitter(self.module)\n\n'
            
            content = content[:pos] + new_setup + content[pos:]
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed {file_path}")

def main():
    test_dir = os.path.join( 'test', 'unit', 'modules')
    for filename in os.listdir(test_dir):
        if filename.startswith('test_sfp_') and filename.endswith('.py'):
            fix_test_file(os.path.join(test_dir, filename))

if __name__ == "__main__":
    main()
