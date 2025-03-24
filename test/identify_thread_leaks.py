#!/usr/bin/env python3
"""
Identify tests that create threads but don't clean them up properly.
This can help identify tests that might be causing hangs.
"""

import os
import sys
import subprocess
import re
import json
import argparse


def find_tests(directory):
    """Find all test files in the directory recursively."""
    test_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))
    return test_files


def run_test_for_threads(test_path):
    """Run a single test and check for thread leaks."""
    cmd = ["python3", "-m", "pytest", test_path, "--verbose"]
    
    # Run with environment variable to enable thread tracking
    env = os.environ.copy()
    env["SPIDERFOOT_TEST_THREAD_DEBUG"] = "1"
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    # Extract thread info from output
    thread_pattern = re.compile(r"Active threads after test: (\d+)")
    thread_info_pattern = re.compile(r"Test left behind (\d+) thread")
    
    threads_after = []
    for line in result.stdout.splitlines():
        match = thread_pattern.search(line)
        if match:
            threads_after.append(int(match.group(1)))
        
        match = thread_info_pattern.search(line)
        if match:
            return {
                'test_file': test_path,
                'passed': result.returncode == 0,
                'thread_leaks': int(match.group(1)),
                'output': result.stdout,
            }
    
    # Look for thread leaks in each test
    thread_leak_detected = max(threads_after) > 2 if threads_after else False
    
    return {
        'test_file': test_path,
        'passed': result.returncode == 0,
        'thread_leaks': 'Unknown' if not threads_after else (threads_after[-1] - threads_after[0]),
        'output': result.stdout if thread_leak_detected else None,
    }


def main():
    parser = argparse.ArgumentParser(description='Find tests with thread leaks')
    parser.add_argument('--test-dir', '-d', default='test/unit', help='Directory containing tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show verbose output')
    parser.add_argument('--output', '-o', help='Output results to JSON file')
    args = parser.parse_args()

    test_files = find_tests(args.test_dir)
    print(f"Found {len(test_files)} test files to analyze")
    
    results = []
    leaky_tests = []
    
    for test in test_files:
        print(f"Checking {test}...")
        result = run_test_for_threads(test)
        results.append(result)
        
        if result['thread_leaks'] and result['thread_leaks'] != 'Unknown' and result['thread_leaks'] > 0:
            leaky_tests.append(result)
            if args.verbose:
                print(f"  Thread leak detected: {result['thread_leaks']} threads")
    
    print(f"\nFound {len(leaky_tests)} tests with potential thread leaks:")
    for test in leaky_tests:
        print(f"  {test['test_file']}: {test['thread_leaks']} thread(s)")
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
            print(f"Results written to {args.output}")
    
    return 0 if not leaky_tests else 1


if __name__ == "__main__":
    sys.exit(main())
