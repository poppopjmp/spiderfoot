#!/usr/bin/env python3
"""
Master script to fix all SpiderFoot test issues and run the test suite.
This script handles:
1. Creating all necessary test utilities
2. Running fix scripts in the correct order
3. Setting up a proper test environment
4. Running the tests
"""

import os
import sys
import subprocess
import argparse
import shutil
import tempfile
import time


def print_header(message):
    """Print a formatted header message."""
    print("\n" + "=" * 60)
    print(f" {message}")
    print("=" * 60)


def create_directory_structure():
    """Create the necessary directory structure for tests."""
    print_header("Creating directory structure")
    
    directories = [
        "test/unit/utils",
        "test/unit/data",
        "test/docroot/static/css",
        "test/docroot/static/js",
        "test/docroot/static/img"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created directory: {directory}")
    
    # Create a minimal index.html for WebUI tests
    with open("test/docroot/index.html", "w") as f:
        f.write("<html><body><h1>SpiderFoot Test</h1></body></html>")
    
    # Create a minimal CSS file
    with open("test/docroot/static/css/style.css", "w") as f:
        f.write("body { font-family: Arial, sans-serif; }")


def ensure_test_utilities():
    """Ensure all test utility files exist and are properly set up."""
    print_header("Setting up test utilities")
    
    # Copy existing utilities if they don't exist
    utility_files = [
        "test/unit/utils/test_base.py",
        "test/unit/utils/test_helpers.py",
        "test/unit/utils/mock_db.py",
        "test/unit/utils/web_test_helpers.py",
        "test/unit/utils/cli_test_helpers.py",
        "test/unit/utils/test_init.py"
    ]
    
    for file in utility_files:
        if not os.path.exists(file):
            print(f"⚠️ Missing utility file: {file}")
            print(f"   Please make sure this file exists before continuing.")
    
    # Import test_init to set up the environment
    try:
        sys.path.append(os.path.abspath("test/unit/utils"))
        import test_init
        print("✓ Test environment initialized")
    except Exception as e:
        print(f"⚠️ Error initializing test environment: {e}")


def run_fix_scripts():
    """Run all the fix scripts in the correct order."""
    print_header("Running fix scripts")
    
    scripts = [
        "fix_reset_mock_objects.py",  # Fix reset_mock_objects() methods
        "fix_test_methods.py",        # Fix test_handleEvent methods with @safe_recursion
        "fix_all_tests.py",           # Apply all fixes to test files
        "fix_webui_tests.py",         # Fix WebUI-specific issues
        "test/unit/test_sfwebui_fix.py",    # Fix WebUI test file
        "test/unit/test_spiderfootcli_fix.py"  # Fix CLI test file
    ]
    
    for script in scripts:
        if os.path.exists(script):
            print(f"Running: {script}")
            try:
                subprocess.run([sys.executable, script], check=True)
                print(f"✓ Successfully ran {script}")
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Error running {script}: {e}")
        else:
            print(f"⚠️ Script not found: {script}")


def run_specific_tests(args):
    """Run specific tests based on the arguments."""
    print_header("Running tests")
    
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
    
    # Add any additional arguments
    if args.pytest_args:
        pytest_args.extend(args.pytest_args)
    
    # Print the command
    print(f"Running: {' '.join(pytest_args)}")
    
    # Run the tests
    try:
        result = subprocess.run(pytest_args, check=False)
        return result.returncode
    except Exception as e:
        print(f"⚠️ Error running tests: {e}")
        return 1


def run_test_suite():
    """Run the full test suite step by step."""
    print_header("Running full test suite")
    
    test_groups = [
        ("Core SpiderFoot event tests", "test/unit/spiderfoot/test_spiderfootevent.py"),
        ("Core SpiderFoot helpers tests", "test/unit/spiderfoot/test_spiderfoothelpers.py"),
        ("Core SpiderFoot plugin tests", "test/unit/spiderfoot/test_spiderfootplugin.py"),
        ("Core SpiderFoot DB tests", "test/unit/spiderfoot/test_spiderfootdb.py"),
        ("Module tests", "test/unit/modules"),
        ("WebUI tests", "test/unit/test_sfwebui.py"),
        ("CLI tests", "test/unit/test_spiderfootcli.py")
    ]
    
    success = True
    for name, path in test_groups:
        if os.path.exists(path):
            print(f"\nRunning {name}...")
            result = subprocess.run(["pytest", "-v", path], check=False)
            if result.returncode != 0:
                success = False
                print(f"⚠️ {name} failed")
            else:
                print(f"✓ {name} passed")
        else:
            print(f"⚠️ Test path not found: {path}")
    
    return 0 if success else 1


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Fix all SpiderFoot test issues and run the test suite.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--skip-fixes", action="store_true", help="Skip running fix scripts")
    parser.add_argument("--path", help="Specific test path to run")
    parser.add_argument("--test", help="Specific test name to run")
    parser.add_argument("--full", action="store_true", help="Run full test suite step by step")
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, help="Additional pytest arguments")
    args = parser.parse_args()
    
    start_time = time.time()
    print_header("SpiderFoot Test Suite - Fix and Run")
    
    # Create directories and set up environment
    create_directory_structure()
    ensure_test_utilities()
    
    # Run fix scripts
    if not args.skip_fixes:
        run_fix_scripts()
    
    # Run tests
    if args.full:
        exit_code = run_test_suite()
    else:
        exit_code = run_specific_tests(args)
    
    # Print summary
    end_time = time.time()
    duration = end_time - start_time
    print_header(f"Test run completed in {duration:.2f} seconds")
    
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed. See output for details.")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
