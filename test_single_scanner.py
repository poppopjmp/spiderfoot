#!/usr/bin/env python3
"""
Test the specific hanging scanner test with emergency termination.
"""

import subprocess
import sys
import threading
import time
import os


def emergency_termination(timeout_seconds=45):
    """Emergency termination thread."""
    time.sleep(timeout_seconds)
    print(f"\n🚨 EMERGENCY: Test running for {timeout_seconds}s - forcefully terminating!")
    os._exit(1)


def main():
    print("🧪 Testing specific scanner test with emergency termination...")
    
    # Start emergency timeout
    emergency_thread = threading.Thread(target=emergency_termination, args=(45,), daemon=True)
    emergency_thread.start()
    
    try:
        # Run the specific test that hangs
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'test/unit/test_spiderfootscanner.py::TestSpiderFootScanner::test_init_argument_start_true_with_no_valid_modules_should_set_scanstatus_to_failed',
            '-v', '-s', '--tb=short'
        ], timeout=30)
        
        print(f"✅ Test completed with return code: {result.returncode}")
        return result.returncode
        
    except subprocess.TimeoutExpired:
        print("⏰ Test timed out after 30s - confirms hanging issue!")
        return 1
    except Exception as e:
        print(f"💥 Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
