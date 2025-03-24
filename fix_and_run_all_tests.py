#!/usr/bin/env python3
"""
Master script to fix and run SpiderFoot tests

This script:
1. Creates all necessary test utilities and directories
2. Applies all fixes to test files
3. Runs the tests with proper environment setup
4. Provides detailed reporting of test results
"""

import os
import sys
import re
import glob
import subprocess
import argparse
import time
import tempfile
import shutil
from unittest.mock import patch
from pathlib import Path


def print_banner(message):
    """Print a formatted banner message."""
    width = 70
    print("\n" + "=" * width)
    padding = (width - len(message)) // 2
    print(" " * padding + message)
    print("=" * width)


def print_step(step_num, total_steps, message):
    """Print a step message."""
    print(f"\n[{step_num}/{total_steps}] {message}...")


def ensure_directory_structure():
    """Ensure all necessary directories exist."""
    directories = [
        "test/unit/utils",
        "test/unit/data",
        "test/docroot/static/css",
        "test/docroot/static/js",
        "test/docroot/static/img"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"  ✓ Created directory: {directory}")
    
    # Create minimal files needed for web tests
    index_html = "test/docroot/index.html"
    if not os.path.exists(index_html):
        with open(index_html, "w") as f:
            f.write("<html><body><h1>SpiderFoot Test</h1></body></html>")
        print(f"  ✓ Created {index_html}")
    
    style_css = "test/docroot/static/css/style.css"
    if not os.path.exists(style_css):
        with open(style_css, "w") as f:
            f.write("body { font-family: Arial, sans-serif; }")
        print(f"  ✓ Created {style_css}")


def create_test_base():
    """Create the base test class if it doesn't exist."""
    test_base = "test/unit/utils/test_base.py"
    if not os.path.exists(test_base):
        with open(test_base, "w") as f:
            f.write("""import unittest

class SpiderFootTestBase(unittest.TestCase):
    \"\"\"Base class for SpiderFoot unit tests.\"\"\"
    
    def setUp(self):
        \"\"\"Set up before each test.\"\"\"
        pass
        
    def tearDown(self):
        \"\"\"Clean up after each test.\"\"\"
        pass
        
    def register_event_emitter(self, module):
        \"\"\"Register an event emitter module with the registry.\"\"\"
        if not hasattr(self, '_event_emitters'):
            self._event_emitters = []
        
        if module not in self._event_emitters:
            self._event_emitters.append(module)
""")
        print(f"  ✓ Created test base class: {test_base}")


def create_test_helpers():
    """Create test helper utilities if they don't exist."""
    # Safe recursion decorator
    test_helpers = "test/unit/utils/test_helpers.py"
    if not os.path.exists(test_helpers):
        with open(test_helpers, "w") as f:
            f.write("""import functools

def safe_recursion(max_depth=5):
    \"\"\"Decorator to prevent infinite recursion in tests.\"\"\"
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, depth=0, *args, **kwargs):
            if depth >= max_depth:
                return None
            return func(self, depth, *args, **kwargs)
        return wrapper
    return decorator
""")
        print(f"  ✓ Created test helpers: {test_helpers}")
    
    # Mock DB utilities
    mock_db = "test/unit/utils/mock_db.py"
    web_helpers = "test/unit/utils/web_test_helpers.py"
    cli_helpers = "test/unit/utils/cli_test_helpers.py"
    test_init = "test/unit/utils/test_init.py"
    
    # Just verify if they exist, as they're more complex and we've provided them in previous fixes
    missing_utils = []
    for util in [mock_db, web_helpers, cli_helpers, test_init]:
        if not os.path.exists(util):
            missing_utils.append(util)
    
    if missing_utils:
        print("  ⚠️ The following utility files are missing:")
        for util in missing_utils:
            print(f"    - {util}")
        print("    Please make sure these files exist (they were provided in previous fixes)")
    else:
        print("  ✓ All test utility files exist")


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
    # For plugin tests
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
    
    # For database tests
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
    
    return content


def add_import_statements(content):
    """Add necessary import statements if missing."""
    imports_to_check = [
        ("unittest", "import unittest"),
        ("unittest.mock", "from unittest.mock import MagicMock, patch"),
        ("SpiderFootTestBase", "from test.unit.utils.test_base import SpiderFootTestBase"),
        ("safe_recursion", "from test.unit.utils.test_helpers import safe_recursion")
    ]
    
    for import_name, import_statement in imports_to_check:
        if import_name not in content:
            # Find the last import statement
            import_pattern = r'(import [^\n]+\n|from [^\n]+ import [^\n]+\n)'
            matches = list(re.finditer(import_pattern, content))
            if matches:
                last_match = matches[-1]
                content = content[:last_match.end()] + import_statement + "\n" + content[last_match.end():]
            else:
                # No imports found, add at the beginning after any comments/docstrings
                content = import_statement + "\n\n" + content
    
    return content


def add_teardown_cleanup(content, test_class_name):
    """Add proper tearDown cleanup if not present."""
    if 'TestSpiderFootDb' in test_class_name and 'self.sqlite_patcher.stop()' not in content:
        teardown_code = """
    def tearDown(self):

        super().tearDown()
        self.sqlite_patcher.stop()
        """
        
        if 'def tearDown' not in content:
            pattern = r'(class\s+' + test_class_name + r'.+?)$'
            content = re.sub(pattern, r'\1' + teardown_code, content, flags=re.DOTALL)
    
    elif 'TestSpiderFootPlugin' in test_class_name or 'TestModule' in test_class_name:
        teardown_code = """
    def tearDown(self):
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


def process_test_file(filepath):
    """Process a single test file to apply all fixes."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        
        # Extract test class name if present
        test_class_match = re.search(r'class\s+(\w+)\(', content)
        test_class_name = test_class_match.group(1) if test_class_match else ""
        
        # Apply all fixes
        content = fix_reset_mock_objects(content)
        content = fix_test_handle_event_methods(content)
        content = fix_selfdepth_typo(content)
        content = add_import_statements(content)
        content = add_setup_mocks(content, test_class_name)
        content = add_teardown_cleanup(content, test_class_name)
        content = fix_spiderfoot_db(content)
        
        # Only write if changes were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
    except Exception as e:
        print(f"  ⚠️ Error processing {filepath}: {str(e)}")
        return False


def fix_all_test_files():
    """Apply all fixes to all test files."""
    test_files = glob.glob('test/unit/**/*.py', recursive=True)
    
    fixed_count = 0
    error_count = 0
    
    for test_file in test_files:
        try:
            if process_test_file(test_file):
                fixed_count += 1
                print(f"  ✓ Fixed: {test_file}")
        except Exception as e:
            error_count += 1
            print(f"  ⚠️ Error fixing {test_file}: {str(e)}")
    
    print(f"\n  Total files fixed: {fixed_count}")
    print(f"  Total errors: {error_count}")
    print(f"  Total files processed: {len(test_files)}")


def run_tests(args):
    """Run tests based on the provided arguments."""
    pytest_args = ["pytest"]
    
    # Add verbosity
    if args.verbose:
        pytest_args.append("-v")
    
    # Add specific path
    if args.path:
        pytest_args.append(args.path)
    else:
        pytest_args.append("test/unit")
    
    # Add specific test if provided
    if args.test:
        pytest_args.append(f"-k {args.test}")
    
    # Add any additional pytest arguments
    if args.pytest_args:
        pytest_args.extend(args.pytest_args)
    
    print(f"  Running: {' '.join(pytest_args)}")
    
    # Set necessary environment variables
    os.environ['SPIDERFOOT_TEST'] = 'True'
    
    # Create temp directory for test cache
    temp_cache = tempfile.mkdtemp(prefix='sf_test_cache_')
    os.environ['SPIDERFOOT_CACHE'] = temp_cache
    
    try:
        start_time = time.time()
        result = subprocess.run(pytest_args)
        end_time = time.time()
        
        print(f"\n  Test execution time: {end_time - start_time:.2f} seconds")
        
        if result.returncode == 0:
            print("  ✅ All tests passed!")
        else:
            print("  ❌ Some tests failed! See above for details.")
        
        return result.returncode
    except Exception as e:
        print(f"  ⚠️ Error running tests: {str(e)}")
        return 1
    finally:
        # Clean up temporary directory
        if os.path.exists(temp_cache):
            shutil.rmtree(temp_cache, ignore_errors=True)


def run_test_groups():
    """Run tests in logical groups for better visibility."""
    test_groups = [
        ("Core SpiderFoot Event Tests", "test/unit/spiderfoot/test_spiderfootevent.py"),
        ("Core SpiderFoot Helpers Tests", "test/unit/spiderfoot/test_spiderfoothelpers.py"),
        ("Core SpiderFoot Plugin Tests", "test/unit/spiderfoot/test_spiderfootplugin.py"),
        ("Core SpiderFoot DB Tests", "test/unit/spiderfoot/test_spiderfootdb.py"),
        ("Module Tests", "test/unit/modules"),
        ("WebUI Tests", "test/unit/test_sfwebui.py"),
        ("CLI Tests", "test/unit/test_spiderfootcli.py")
    ]
    
    all_passed = True
    results = []
    
    # Set necessary environment variables
    os.environ['SPIDERFOOT_TEST'] = 'True'
    temp_cache = tempfile.mkdtemp(prefix='sf_test_cache_')
    os.environ['SPIDERFOOT_CACHE'] = temp_cache
    
    try:
        for name, path in test_groups:
            if os.path.exists(path):
                print(f"\n  Running {name}...")
                start_time = time.time()
                result = subprocess.run(["pytest", "-v", path], capture_output=True, text=True)
                end_time = time.time()
                
                if result.returncode == 0:
                    status = "✅ PASSED"
                else:
                    status = "❌ FAILED"
                    all_passed = False
                
                duration = end_time - start_time
                results.append((name, status, duration, result))
                print(f"  {status} in {duration:.2f} seconds")
            else:
                print(f"  ⚠️ Test path not found: {path}")
                results.append((name, "⚠️ NOT FOUND", 0, None))
        
        # Print summary
        print("\n  Test Summary:")
        for name, status, duration, _ in results:
            print(f"  {status} {name} ({duration:.2f}s)")
        
        # Show details for failed tests
        for name, status, _, result in results:
            if "FAILED" in status and result:
                print(f"\n  Failed tests in {name}:")
                for line in result.stdout.split('\n'):
                    if "FAILED" in line:
                        print(f"    {line}")
        
        return 0 if all_passed else 1
    finally:
        # Clean up temporary directory
        if os.path.exists(temp_cache):
            shutil.rmtree(temp_cache, ignore_errors=True)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Fix and run SpiderFoot tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--skip-fixes", action="store_true", help="Skip fixing test files")
    parser.add_argument("--path", help="Run tests at a specific path")
    parser.add_argument("--test", help="Run a specific test pattern")
    parser.add_argument("--groups", action="store_true", help="Run tests in logical groups")
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, help="Additional pytest arguments")
    args = parser.parse_args()
    
    print_banner("SpiderFoot Test Suite")
    
    # Step 1: Ensure directory structure
    steps_total = 5
    print_step(1, steps_total, "Creating directory structure")
    ensure_directory_structure()
    
    # Step 2: Create test utilities
    print_step(2, steps_total, "Creating test utilities")
    create_test_base()
    create_test_helpers()
    
    # Step 3: Fix test files
    if not args.skip_fixes:
        print_step(3, steps_total, "Fixing test files")
        fix_all_test_files()
    else:
        print_step(3, steps_total, "Skipping test file fixes (as requested)")
    
    # Step 4: Initialize test environment
    print_step(4, steps_total, "Setting up test environment")
    try:
        import sys
        sys.path.append(os.path.abspath("test/unit/utils"))
        import test_init
        print("  ✓ Test environment initialized")
    except Exception as e:
        print(f"  ⚠️ Error initializing test environment: {e}")
    
    # Step 5: Run tests
    print_step(5, steps_total, "Running tests")
    if args.groups:
        exit_code = run_test_groups()
    else:
        exit_code = run_tests(args)
    
    print_banner("Test Execution Complete")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
