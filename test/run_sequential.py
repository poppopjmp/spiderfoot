#!/usr/bin/env python3
"""
Run tests sequentially to avoid resource contention.
This can help identify tests that might be interfering with each other.
"""

import os
import sys
import subprocess
import time
import argparse
import gc
import signal
import psutil

def kill_child_processes():
    """Kill any child processes that might have been left behind."""
    current_process = psutil.Process()
    children = current_process.children(recursive=True)
    for child in children:
        try:
            print(f"Terminating child process: {child.pid} ({child.name()})")
            child.terminate()
        except psutil.NoSuchProcess:
            pass

def run_test_sequential(test_path, verbose=False, timeout=60):
    """Run a single test and return the result."""
    cmd = ["python", "-m", "pytest", test_path, "-v"] if verbose else ["python", "-m", "pytest", test_path]
    
    print(f"Running test: {test_path}")
    start_time = time.time()
    
    # Run with timeout to prevent hanging tests
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait for process to complete with timeout
        stdout_data = []
        stderr_data = []
        
        while proc.poll() is None:
            if time.time() - start_time > timeout:
                print(f"Test timed out after {timeout} seconds: {test_path}")
                proc.terminate()
                time.sleep(1)
                if proc.poll() is None:
                    proc.kill()
                return False
            
            # Read output without blocking
            if proc.stdout:
                line = proc.stdout.readline()
                if line:
                    stdout_data.append(line)
            
            if proc.stderr:
                line = proc.stderr.readline()
                if line:
                    stderr_data.append(line)
                
            time.sleep(0.1)
        
        # Read any remaining output
        if proc.stdout:
            for line in proc.stdout:
                stdout_data.append(line)
        
        if proc.stderr:
            for line in proc.stderr:
                stderr_data.append(line)
        
        stdout = "".join(stdout_data)
        stderr = "".join(stderr_data)
        return_code = proc.returncode
        
    except Exception as e:
        print(f"Error running test {test_path}: {str(e)}")
        return False
    
    elapsed = time.time() - start_time
    status = "PASSED" if return_code == 0 else "FAILED"
    
    print(f"{status} in {elapsed:.2f}s: {test_path}")
    
    if verbose or return_code != 0:
        print(stdout)
        print(stderr)
    
    # Aggressively clean up
    kill_child_processes()
    gc.collect()
    time.sleep(0.5)  # Give OS time to clean up resources
    
    return return_code == 0


def find_tests(directory):
    """Find all test files in the directory recursively."""
    test_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))
    return test_files


def main():
    parser = argparse.ArgumentParser(description='Run SpiderFoot tests sequentially')
    parser.add_argument('--test-dir', '-d', default='test/unit', help='Directory containing tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show verbose output')
    parser.add_argument('--exclude', '-e', nargs='+', default=[], help='Exclude test patterns')
    parser.add_argument('--timeout', '-t', type=int, default=60, help='Timeout for each test in seconds')
    args = parser.parse_args()

    test_files = find_tests(args.test_dir)
    
    # Filter out excluded tests
    if args.exclude:
        for exclude in args.exclude:
            test_files = [t for t in test_files if exclude not in t]
    
    print(f"Found {len(test_files)} test files to run")
    
    start_time = time.time()
    passed = 0
    failed = 0
    
    for test in test_files:
        if run_test_sequential(test, args.verbose, args.timeout):
            passed += 1
        else:
            failed += 1
    
    total_time = time.time() - start_time
    print(f"\nResults: {passed} passed, {failed} failed in {total_time:.2f}s")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
