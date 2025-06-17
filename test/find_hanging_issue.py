#!/usr/bin/env python33

import os
import sys
import time
import subprocess
import random
from pathlib import Path

def run_command(cmd, timeout=300):
    """Run command with timeout and return result."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, 
            timeout=timeout,
            capture_output=True,
            text=True
        )
        return True, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout expired"

def find_all_tests():
    """Find all test files in unit directory."""
    unit_dir = Path("test/unit/modules")
    return list(unit_dir.glob("test_*.py"))

def main():
    print("Diagnosing pytest hanging issue...")
    
    # Try running individual problematic test files
    print("\n=== Testing individual files that might hang ===")
    problem_files = [
        "test/unit/test_spiderfootscanner.py",
        "test/unit/test_spiderfootcli.py", 
        "test/unit/test_spiderfoot.py",
        "test/unit/spiderfoot/test_spiderfootdb.py"
    ]
    
    for test_file in problem_files:
        print(f"\nTesting {test_file}...")
        success, stdout, stderr = run_command(["python3", "-m", "pytest", test_file, "-v"], timeout=60)
        if not success:
            print(f"❌ {test_file} appears to hang or fail")
        else:
            print(f"✅ {test_file} completed successfully")
    
    # Try running with xvs flag for more verbose output and to run tests in random order
    # This can identify if the issue is order-dependent
    print("\n=== Running with randomized order and verbose output ===")
    success, stdout, stderr = run_command(["python3", "-m", "pytest", "test/unit/modules", "-xvs", "--random-order"])
    if success:
        print("✅ Tests completed successfully with randomized order")
    else:
        print("❌ Tests hung even with randomized order")
        
    # Try running with test isolation
    print("\n=== Running with complete process isolation (one test per process) ===")
    success, stdout, stderr = run_command(["python3", "-m", "pytest", "test/unit/modules", "-v", "--forked"])
    if success:
        print("✅ Tests completed successfully with process isolation")
        print("The issue is likely related to shared state or resource conflicts between tests")
    else:
        print("❌ Tests hung even with process isolation")
        
    # Check for thread leaks by running with the custom conftest.py
    print("\n=== Running with thread/resource tracking ===")
    success, stdout, stderr = run_command(["python3", "-m", "pytest", "test/unit/modules", "-v"])
    if success:
        print("✅ Tests completed with resource tracking")
        print("Check the pytest-debug.log file for threads or resources that weren't cleaned up")
    else:
        print("❌ Tests hung with resource tracking")
    
    print("\nAdditional debugging steps:")
    print(" 1. Run: python3 -m pytest --collect-only test/unit/modules/ (check test collection)")
    print(" 2. Run: python3 -m pytest test/unit/modules/ -k 'not handleEvent' (skip handleEvent tests)")
    print(" 3. Check for circular imports: python3 -c 'import test.unit.modules.test_sfp_base64'")
    print(" 4. Monitor threads: python3 -c 'import threading; print([t.name for t in threading.enumerate()])'")

if __name__ == "__main__":
    main()
