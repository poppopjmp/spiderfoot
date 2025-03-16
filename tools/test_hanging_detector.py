import os
import sys
import time
import subprocess
from pathlib import Path

def run_single_test(test_path):
    """Run a single test file with pytest and timeout."""
    print(f"Testing: {test_path}")
    try:
        # Run with verbose output and 30 second timeout
        result = subprocess.run(
            ["pytest", test_path, "-v"], 
            timeout=30,
            capture_output=True,
            text=True
        )
        return False, test_path, result.stdout
    except subprocess.TimeoutExpired:
        return True, test_path, "Test timed out after 30 seconds"

def main():
    unit_test_dir = Path("test/unit")
    if not unit_test_dir.exists():
        print(f"Error: {unit_test_dir} directory not found")
        sys.exit(1)

    print(f"Scanning for hanging tests in {unit_test_dir}")
    
    hanging_tests = []
    for test_file in unit_test_dir.glob("test_*.py"):
        hangs, path, output = run_single_test(test_file)
        if hangs:
            hanging_tests.append(path)
            print(f"❌ {path} - HANGS")
        else:
            print(f"✓ {path} - OK")
    
    if hanging_tests:
        print("\nThe following tests appear to hang:")
        for test in hanging_tests:
            print(f" - {test}")
        print("\nTips for fixing hanging tests:")
        print(" 1. Check for infinite loops")
        print(" 2. Ensure all threads/processes are terminated")
        print(" 3. Check for blocking I/O operations")
        print(" 4. Ensure proper teardown of test resources")
    else:
        print("\nNo hanging tests found. The issue might be in test interactions.")

if __name__ == "__main__":
    main()
