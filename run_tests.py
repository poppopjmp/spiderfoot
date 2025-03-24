#!/usr/bin/env python3
"""
Script to run all SpiderFoot tests with proper setup
"""

import os
import sys
import subprocess
import time
import argparse


def ensure_test_helpers():
    """Ensure test helpers are available."""
    utils_dir = "test/unit/utils"
    os.makedirs(utils_dir, exist_ok=True)
    
    # Check for test_base.py
    if not os.path.exists(f"{utils_dir}/test_base.py"):
        print("Creating test_base.py...")
        with open(f"{utils_dir}/test_base.py", 'w') as f:
            f.write("""
import unittest

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
    
    # Check for test_helpers.py
    if not os.path.exists(f"{utils_dir}/test_helpers.py"):
        print("Creating test_helpers.py...")
        with open(f"{utils_dir}/test_helpers.py", 'w') as f:
            f.write("""
import functools

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


def run_fix_scripts():
    """Run all test fix scripts."""
    scripts = [
        "fix_reset_mock_objects.py",
        "fix_test_methods.py",
        "fix_all_tests.py",
        "fix_webui_tests.py"
    ]
    
    for script in scripts:
        if os.path.exists(script):
            print(f"Running {script}...")
            subprocess.run([sys.executable, script], check=True)
        else:
            print(f"Warning: {script} not found")
    
    print("All fix scripts completed.")


def run_tests(args):
    """Run the tests with pytest."""
    pytest_args = ["pytest"]
    
    # Add verbosity if requested
    if args.verbose:
        pytest_args.append("-v")
    
    # Add test path
    if args.path:
        pytest_args.append(args.path)
    else:
        pytest_args.append("test/unit")
    
    # Add specific test if provided
    if args.test:
        pytest_args.append(f"-k {args.test}")
    
    # Run the tests
    print(f"Running tests with: {' '.join(pytest_args)}")
    result = subprocess.run(pytest_args, check=False)
    return result.returncode


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run SpiderFoot tests with proper setup.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--skip-fixes", action="store_true", help="Skip running fix scripts")
    parser.add_argument("--path", help="Path to test directory or file")
    parser.add_argument("--test", help="Specific test function to run")
    args = parser.parse_args()
    
    print("Setting up SpiderFoot test environment...")
    start_time = time.time()
    
    # Ensure test helpers exist
    ensure_test_helpers()
    
    # Run fix scripts if not skipped
    if not args.skip_fixes:
        run_fix_scripts()
    
    # Run the tests
    result = run_tests(args)
    
    end_time = time.time()
    duration = end_time - start_time
    print(f"Test run completed in {duration:.2f} seconds")
    
    sys.exit(result)


if __name__ == "__main__":
    main()
