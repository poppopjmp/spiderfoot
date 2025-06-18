#!/usr/bin/env python3
"""Test the fixed SpiderFootScanner initialization."""

import sys
import os
import multiprocessing as mp

# Add the spiderfoot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sfscan import startSpiderFootScanner
from sflib import SpiderFoot

mp.set_start_method("spawn", force=True)

def test_scanner_initialization():
    """Test that SpiderFootScanner initializes correctly with targetType."""
    
    # Create minimal config
    config = {
        '__logging': True,
        'cacheperiod': 0,
        'logfile': '/tmp/test.log',
        'errorlog': '/tmp/test_error.log',
        'checkcert': False,
        '_socks1type': '',
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '__version__': '4.0',
        '__modules__': {}
    }
    
    # Load a minimal module config
    sf = SpiderFoot(config)
    
    # Set minimal module configuration
    config['__modules__'] = {
        'sfp__stor_db': {
            'name': 'Storage/DB',
            'cats': ['Internal'],
            'group': [],
            'description': 'Store scan data to the local SpiderFoot database.'
        }
    }
    
    # Test arguments
    scanName = "Test Scan"
    scanId = "test_12345"
    targetValue = "google.com"
    targetType = "INTERNET_NAME"
    moduleList = ["sfp__stor_db"]
    
    print(f"Testing scanner initialization with:")
    print(f"  scanName: {scanName}")
    print(f"  scanId: {scanId}")
    print(f"  targetValue: {targetValue}")
    print(f"  targetType: {targetType}")
    print(f"  moduleList: {moduleList}")
    
    try:
        # Create a dummy queue
        loggingQueue = mp.Queue()
        
        # This should now work without the targetType None error
        p = mp.Process(target=startSpiderFootScanner, args=(
            loggingQueue, scanName, scanId, targetValue, targetType, moduleList, config))
        p.daemon = True
        p.start()
        p.join(timeout=10)  # Wait up to 10 seconds
        
        if p.exitcode is None:
            print("Test TIMEOUT: Process did not complete within 10 seconds")
            p.terminate()
            return False
        elif p.exitcode == 0:
            print("Test PASSED: Scanner initialized successfully")
            return True
        else:
            print(f"Test FAILED: Process exited with code {p.exitcode}")
            return False
            
    except Exception as e:
        print(f"Test FAILED: Exception: {e}")
        return False

if __name__ == "__main__":
    print("Testing SpiderFootScanner initialization fix...")
    success = test_scanner_initialization()
    print(f"Overall result: {'PASSED' if success else 'FAILED'}")
