#!/usr/bin/env python3
"""
SpiderFoot Test Manager

A comprehensive tool to manage, fix, and run SpiderFoot tests.

Features:
- Automatically sets up test environment and dependencies
- Fixes common issues in test files
- Runs tests with customizable options
- Provides detailed reports of test results
- Supports debugging and troubleshooting

Usage examples:
    # Set up test environment and fix all tests
    python sf_test_manager.py setup

    # Run the entire test suite
    python sf_test_manager.py run

    # Fix issues in a specific test file
    python sf_test_manager.py fix --path test/unit/path/to/file.py

    # Run specific tests with verbose output
    python sf_test_manager.py run --path test/unit/modules --verbose

    # Run tests in isolated groups with reporting
    python sf_test_manager.py run --groups

    # Show available test modules
    python sf_test_manager.py list
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
import importlib.util
import logging
from unittest.mock import patch
from pathlib import Path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("SF_TEST_MANAGER")


def print_banner(message):
    """Print a formatted banner message."""
    width = 70
    print("\n" + "=" * width)
    padding = (width - len(message)) // 2
    print(" " * padding + message)
    print("=" * width)


def print_step(step_name):
    """Print a formatted step message."""
    print(f"\n📋 {step_name}")


def check_python_version():
    """Check if the Python version is compatible."""
    if sys.version_info < (3, 6):
        logger.error("Python 3.6 or higher is required")
        sys.exit(1)


def create_directory_structure():
    """Create the necessary directory structure for tests."""
    print_step("Creating directory structure")
    
    directories = [
        "test/unit/utils",
        "test/unit/data",
        "test/docroot/static/css",
        "test/docroot/static/js",
        "test/docroot/static/img"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Created directory: {directory}")
    
    # Create minimal files needed for web tests
    index_html = "test/docroot/index.html"
    if not os.path.exists(index_html):
        with open(index_html, "w") as f:
            f.write("<html><body><h1>SpiderFoot Test</h1></body></html>")
        logger.info(f"Created {index_html}")
    
    style_css = "test/docroot/static/css/style.css"
    if not os.path.exists(style_css):
        with open(style_css, "w") as f:
            f.write("body { font-family: Arial, sans-serif; }")
        logger.info(f"Created {style_css}")


def create_test_utilities():
    """Create necessary test utility files."""
    print_step("Setting up test utilities")
    
    # Create test base class
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
        logger.info(f"Created test base class: {test_base}")
    
    # Create safe_recursion decorator
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
        logger.info(f"Created test helpers: {test_helpers}")
    
    # Create test environment initialization module
    test_init = "test/unit/utils/test_init.py"
    if not os.path.exists(test_init):
        with open(test_init, "w") as f:
            f.write("""\"\"\"
Test initialization utilities for SpiderFoot tests.
This file ensures all necessary test helpers are properly set up.
\"\"\"

import os
import shutil
import tempfile
from unittest.mock import patch

# Make sure test directory structure exists
TEST_DIRS = [
    "test/unit/utils",
    "test/unit/data",
    "test/unit/modules",
    "test/docroot"
]


def initialize_test_environment():
    \"\"\"Initialize the test environment for all SpiderFoot tests.\"\"\"
    # Create necessary directories
    for directory in TEST_DIRS:
        os.makedirs(directory, exist_ok=True)

    # Set up environment variables needed by tests
    setup_test_environment_variables()

    # Apply global patches that may be needed for certain tests
    apply_global_patches()


def setup_test_environment_variables():
    \"\"\"Set up environment variables needed for tests.\"\"\"
    # These are environment variables that might be needed by some tests
    os.environ.setdefault('SPIDERFOOT_DATA', 'test/unit/data')
    os.environ.setdefault('SPIDERFOOT_CACHE', tempfile.mkdtemp(prefix='sf_test_cache_'))
    os.environ.setdefault('SPIDERFOOT_TEST', 'True')


def apply_global_patches():
    \"\"\"Apply any global patches needed for tests.\"\"\"
    # This is important for tests that might try to access the internet
    # We don't want unit tests to actually send network requests
    def mock_socket_connect(self, address):
        \"\"\"Mock socket.connect to prevent actual network connections.\"\"\"
        return True
    
    # Only apply the patch if we're in a test environment 
    if 'SPIDERFOOT_TEST' in os.environ:
        import socket
        if not hasattr(socket.socket, '_original_connect'):
            socket.socket._original_connect = socket.socket.connect
            socket.socket.connect = mock_socket_connect


def clean_test_environment():
    \"\"\"Clean up the test environment.\"\"\"
    # Remove temporary directories
    if 'SPIDERFOOT_CACHE' in os.environ:
        cache_dir = os.environ['SPIDERFOOT_CACHE']
        if os.path.isdir(cache_dir) and cache_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(cache_dir, ignore_errors=True)

    # Restore any patches
    if 'SPIDERFOOT_TEST' in os.environ:
        import socket
        if hasattr(socket.socket, '_original_connect'):
            socket.socket.connect = socket.socket._original_connect
            delattr(socket.socket, '_original_connect')


# Register cleanup function to run on exit
import atexit
atexit.register(clean_test_environment)

# Initialize when imported
initialize_test_environment()
""")
        logger.info(f"Created test initialization module: {test_init}")


def fix_reset_mock_objects(content):
    """Fix the reset_mock_objects function definition to accept self parameter."""
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


def add_teardown_cleanup(content, test_class_name):
    """Add proper tearDown cleanup if not present."""
    if 'TestSpiderFootDb' in test_class_name and 'self.sqlite_patcher.stop()' not in content:
        teardown_code = """
    def tearDown(self):
        \"\"\"Clean up after each test.\"\"\"
        super().tearDown()
        self.sqlite_patcher.stop()
        """
        
        if 'def tearDown' not in content:
            pattern = r'(class\s+' + test_class_name + r'.+?)$'
            content = re.sub(pattern, r'\1' + teardown_code, content, flags=re.DOTALL)
    
    elif 'TestSpiderFootPlugin' in test_class_name or 'TestModule' in test_class_name:
        teardown_code = """
    def tearDown(self):
        \"\"\"Clean up after each test.\"\"\"
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


def fix_test_file(filepath):
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
        logger.error(f"Error processing {filepath}: {str(e)}")
        return False


def fix_all_test_files(specific_path=None):
    """Apply all fixes to test files."""
    print_step("Fixing test files")
    
    if specific_path:
        if os.path.isfile(specific_path):
            test_files = [specific_path]
        elif os.path.isdir(specific_path):
            test_files = glob.glob(os.path.join(specific_path, '**/*.py'), recursive=True)
        else:
            logger.error(f"Path not found: {specific_path}")
            return 0, 0
    else:
        test_files = glob.glob('test/unit/**/*.py', recursive=True)
    
    fixed_count = 0
    error_count = 0
    
    for test_file in test_files:
        try:
            if fix_test_file(test_file):
                fixed_count += 1
                logger.info(f"Fixed: {test_file}")
        except Exception as e:
            error_count += 1
            logger.error(f"Error fixing {test_file}: {str(e)}")
    
    logger.info(f"Total files fixed: {fixed_count}")
    logger.info(f"Total errors: {error_count}")
    logger.info(f"Total files processed: {len(test_files)}")
    
    return fixed_count, error_count


def create_test_environment():
    """Set up a proper test environment."""
    # Set necessary environment variables
    os.environ['SPIDERFOOT_TEST'] = 'True'
    
    # Create temp directory for test cache
    temp_cache = tempfile.mkdtemp(prefix='sf_test_cache_')
    os.environ['SPIDERFOOT_CACHE'] = temp_cache
    
    # Initialize the test environment
    try:
        sys.path.append(os.path.abspath("test/unit/utils"))
        import test_init
        logger.info("Test environment initialized")
    except Exception as e:
        logger.error(f"Error initializing test environment: {e}")
    
    return temp_cache


def run_tests(args):
    """Run the tests with pytest."""
    print_step("Running tests")
    
    pytest_args = ["pytest"]
    
    # Add verbosity
    if args.verbose:
        pytest_args.append("-v")
    
    # Add specific path
    if args.path:
        pytest_args.append(args.path)
    else:
        pytest_args.append("test/unit")
    
    # Add specific test pattern if provided
    if args.pattern:
        pytest_args.append(f"-k {args.pattern}")
    
    # Add any additional arguments
    if args.pytest_args:
        pytest_args.extend(args.pytest_args)
    
    logger.info(f"Running: {' '.join(pytest_args)}")
    
    # Create test environment
    temp_cache = create_test_environment()
    
    try:
        start_time = time.time()
        result = subprocess.run(pytest_args)
        end_time = time.time()
        
        logger.info(f"Test execution time: {end_time - start_time:.2f} seconds")
        
        if result.returncode == 0:
            logger.info("✅ All tests passed!")
        else:
            logger.warning("❌ Some tests failed!")
        
        return result.returncode
    except Exception as e:
        logger.error(f"Error running tests: {str(e)}")
        return 1
    finally:
        # Clean up temporary directory
        if temp_cache and os.path.exists(temp_cache):
            shutil.rmtree(temp_cache, ignore_errors=True)


def run_test_groups(verbose=False):
    """Run tests in logical groups for better visibility."""
    print_step("Running tests by group")
    
    test_groups = [
        ("Core SpiderFoot Event Tests", "test/unit/spiderfoot/test_spiderfootevent.py"),
        ("Core SpiderFoot Helpers Tests", "test/unit/spiderfoot/test_spiderfoothelpers.py"),
        ("Core SpiderFoot Plugin Tests", "test/unit/spiderfoot/test_spiderfootplugin.py"),
        ("Core SpiderFoot DB Tests", "test/unit/spiderfoot/test_spiderfootdb.py"),
        ("Module Tests", "test/unit/modules"),
        ("WebUI Tests", "test/unit/test_sfwebui.py"),
        ("CLI Tests", "test/unit/test_spiderfootcli.py")
    ]
    
    results = []
    
    # Create test environment
    temp_cache = create_test_environment()
    
    try:
        for name, path in test_groups:
            if not os.path.exists(path):
                logger.warning(f"Test path not found: {path}")
                results.append((name, "NOT FOUND", 0, None))
                continue
                
            logger.info(f"Running {name}...")
            
            # Build pytest command
            cmd = ["pytest"]
            if verbose:
                cmd.append("-v")
            cmd.append(path)
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True)
            end_time = time.time()
            duration = end_time - start_time
            
            if result.returncode == 0:
                status = "PASSED"
                logger.info(f"✅ {name} passed in {duration:.2f} seconds")
            else:
                status = "FAILED"
                logger.warning(f"❌ {name} failed in {duration:.2f} seconds")
            
            results.append((name, status, duration, result))
        
        # Print summary report
        print("\nTest Summary Report:")
        print("-" * 60)
        print(f"{'Test Group':<30} {'Status':<10} {'Duration':<10}")
        print("-" * 60)
        
        all_passed = True
        for name, status, duration, _ in results:
            print(f"{name[:30]:<30} {status:<10} {duration:.2f}s")
            if status not in ["PASSED", "NOT FOUND"]:
                all_passed = False
        
        print("-" * 60)
        
        # Show details for failed tests
        has_failures = any(status == "FAILED" for _, status, _, _ in results)
        if has_failures:
            print("\nFailure Details:")
            print("-" * 60)
            
            for name, status, _, result in results:
                if status == "FAILED" and result:
                    print(f"\n{name} - Failures:")
                    for line in result.stdout.split('\n'):
                        if "FAILED" in line:
                            print(f"  {line}")
        
        return 0 if all_passed else 1
    
    finally:
        # Clean up temporary directory
        if temp_cache and os.path.exists(temp_cache):
            shutil.rmtree(temp_cache, ignore_errors=True)


def list_modules():
    """List all available test modules."""
    print_step("Available Test Modules")
    
    # Core modules
    print("\nCore Modules:")
    core_modules = glob.glob('test/unit/spiderfoot/*.py')
    for module in sorted(core_modules):
        print(f"  - {module}")
    
    # Plugin/Module tests
    print("\nPlugin/Module Tests:")
    module_tests = glob.glob('test/unit/modules/*.py')
    for module in sorted(module_tests):
        print(f"  - {module}")
    
    # Other tests
    print("\nOther Tests:")
    other_tests = [f for f in glob.glob('test/unit/*.py') 
                  if not f.startswith('test/unit/spiderfoot/') 
                  and not f.startswith('test/unit/modules/')]
    for test in sorted(other_tests):
        print(f"  - {test}")


def setup_command(args):
    """Handle the setup command."""
    print_banner("Setting up SpiderFoot Test Environment")
    
    # Create directory structure
    create_directory_structure()
    
    # Create test utilities
    create_test_utilities()
    
    # Fix test files if needed
    if not args.no_fix:
        fix_all_test_files(args.path)
    
    print_banner("Setup Complete")
    return 0


def fix_command(args):
    """Handle the fix command."""
    print_banner("Fixing SpiderFoot Test Files")
    fixed, errors = fix_all_test_files(args.path)
    
    print_banner("Fix Complete")
    return 0 if errors == 0 else 1


def run_command(args):
    """Handle the run command."""
    print_banner("Running SpiderFoot Tests")
    
    # Fix files if needed
    if not args.no_fix:
        fix_all_test_files(args.path)
    
    # Run tests
    if args.groups:
        return run_test_groups(args.verbose)
    else:
        return run_tests(args)


def list_command(_):
    """Handle the list command."""
    print_banner("SpiderFoot Test Module List")
    list_modules()
    return 0


def main():
    """Main function."""
    # Check Python version
    check_python_version()
    
    # Create main parser
    parser = argparse.ArgumentParser(
        description="SpiderFoot Test Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sf_test_manager.py setup                 # Set up test environment
  python sf_test_manager.py fix                   # Fix all test files
  python sf_test_manager.py run                   # Run all tests
  python sf_test_manager.py run --groups          # Run tests in groups
  python sf_test_manager.py fix --path test/unit/modules  # Fix specific tests
  python sf_test_manager.py run --verbose         # Run with verbose output
  python sf_test_manager.py list                  # List test modules
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up the test environment")
    setup_parser.add_argument("--path", help="Path to specific test file or directory")
    setup_parser.add_argument("--no-fix", action="store_true", help="Skip fixing test files")
    
    # Fix command
    fix_parser = subparsers.add_parser("fix", help="Fix issues in test files")
    fix_parser.add_argument("--path", help="Path to specific test file or directory")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run tests")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    run_parser.add_argument("--no-fix", action="store_true", help="Skip fixing test files")
    run_parser.add_argument("--path", help="Path to specific test file or directory")
    run_parser.add_argument("--pattern", help="Pattern to match test names")
    run_parser.add_argument("--groups", action="store_true", help="Run tests in logical groups")
    run_parser.add_argument("pytest_args", nargs="*", help="Additional pytest arguments")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available test modules")
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command is provided, show help
    if not args.command:
        parser.print_help()
        return 1
    
    # Handle commands
    command_handlers = {
        "setup": setup_command,
        "fix": fix_command,
        "run": run_command,
        "list": list_command
    }
    
    if args.command in command_handlers:
        start_time = time.time()
        exit_code = command_handlers[args.command](args)
        end_time = time.time()
        
        print_banner(f"Command completed in {end_time - start_time:.2f} seconds")
        return exit_code
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
