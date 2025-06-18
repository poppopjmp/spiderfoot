#!/usr/bin/env python3
"""Simple test for multiprocessing argument passing."""

import sys
import os
import multiprocessing as mp
import time

# Add the spiderfoot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

mp.set_start_method("spawn", force=True)

def test_function(loggingQueue, arg1, arg2, arg3, arg4, arg5, arg6):
    """Test function to receive multiprocessing arguments."""
    print(f"Received args: arg1={repr(arg1)} ({type(arg1)})")
    print(f"Received args: arg2={repr(arg2)} ({type(arg2)})")
    print(f"Received args: arg3={repr(arg3)} ({type(arg3)})")
    print(f"Received args: arg4={repr(arg4)} ({type(arg4)})")
    print(f"Received args: arg5={repr(arg5)} ({type(arg5)})")
    print(f"Received args: arg6={repr(arg6)} ({type(arg6)})")
    
    if arg4 is None:
        print("ERROR: arg4 (targetType) is None!")
        sys.exit(1)
    else:
        print("SUCCESS: All arguments received correctly")
        sys.exit(0)

def test_multiprocessing_args():
    """Test multiprocessing argument passing."""
    
    # Create a dummy queue
    loggingQueue = mp.Queue()
    
    # These are the same types of arguments the web UI passes
    scanname = "Test Scan"
    scanId = "test_12345"
    scantarget = "google.com"
    targetType = "INTERNET_NAME"  # This should NOT be None
    modlist = ["sfp__stor_db"]
    cfg = {"test": "config"}
    
    print(f"Passing args: scanname={scanname}, scanId={scanId}, scantarget={scantarget}, targetType={targetType}")
    
    try:
        # This mimics the web UI call
        p = mp.Process(target=test_function, args=(
            loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg))
        p.daemon = True
        p.start()
        p.join(timeout=10)  # Wait up to 10 seconds
        
        if p.exitcode == 0:
            print("Test PASSED: Arguments passed correctly")
            return True
        else:
            print(f"Test FAILED: Process exited with code {p.exitcode}")
            return False
            
    except Exception as e:
        print(f"Test FAILED: Exception: {e}")
        return False

if __name__ == "__main__":
    print("Testing multiprocessing argument passing...")
    success = test_multiprocessing_args()
    print(f"Overall result: {'PASSED' if success else 'FAILED'}")
