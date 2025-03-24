#!/usr/bin/env python3
"""
Script to fix all test issues and run the test suite
"""

import os
import sys
import subprocess
import argparse
import time
import importlib.util
import shutil


def ensure_file_exists(filepath, content):
    """Ensure a file exists with the given content."""
    directory = os.path.dirname(filepath)
    os.makedirs(directory, exist_ok=True)
    
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created {filepath}")
        return True
    return False


def ensure_all_test_utils():
    """Ensure all test utilities exist."""
    utils_dir = "test/unit/utils"
    os.makedirs(utils_dir, exist_ok=True)
    
    # Check all the utility files we've created
    utils_files = [
        "test_base.py", 
        "test_helpers.py", 
        "mock_db.py", 
        "web_test_helpers.py", 
        "cli_test_helpers.py",
        "test_init.py"
    ]
    
    missing = [f for f in utils_files if not os.path.exists(os.path.join(utils_dir, f))]
    if missing:
        print(f"Missing utility files: {missing}")
        print("You need to create these files first using the provided scripts.")
        return False
    
    print("All test utility files exist.")
    return True


def run_fix_script(script_path):
    """Run a fix script if it exists."""
    if os.path.exists(script_path):
        print(f"Running {script_path}...")
        try:
            subprocess.run([sys.executable, script_path], check=True)
            print(f"Successfully ran {script_path}")
            return True
        except subprocess.CalledProcessError:
            print(f"Error running {script_path}")
            return False
    else:
        print(f"Script not found: {script_path}")
        return False


def run_tests(args):
    """Run tests using pytest."""
    print("\nRunning tests...")
    
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
    
    # Print the command
    print(f"Running: {' '.join(pytest_args)}")
    
    # Run the tests
    try:
        result = subprocess.run(pytest_args, check=False)
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Fix all test issues and run the test suite.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Run tests with verbose output")
    parser.add_argument("--skip-fixes", action="store_true", help="Skip running fix scripts")
    parser.add_argument("--path", help="Specific test path to run")
    parser.add_argument("--test", help="Specific test name to run")
    args = parser.parse_args()
    
    start_time = time.time()
    print("SpiderFoot Test Suite - Fix and Run")
    print("==================================")
    
    # Ensure all test utils exist
    if not ensure_all_test_utils():
        print("Missing some test utilities. Please run the setup scripts first.")
        sys.exit(1)
    
    # Run fix scripts unless skipped
    if not args.skip_fixes:
        print("\nRunning fix scripts...")
        scripts = [
            "fix_reset_mock_objects.py",
            "fix_test_methods.py", 
            "fix_all_tests.py",
            "fix_webui_tests.py",
            "test/unit/test_sfwebui_fix.py",
            "test/unit/test_spiderfootcli_fix.py"
        ]
        
        for script in scripts:
            run_fix_script(script)
    
    # Run the tests
    exit_code = run_tests(args)
    
    # Print summary
    end_time = time.time()
    print(f"\nCompleted in {end_time - start_time:.2f} seconds")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
