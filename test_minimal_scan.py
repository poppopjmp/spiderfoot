#!/usr/bin/env python

import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tempfile
from spiderfoot import SpiderFootScanner, SpiderFootTarget, SpiderFootDb
from spiderfoot.helpers import SpiderFootHelpers

def test_minimal_scan():
    print("Testing minimal scan functionality...")
    
    try:
        # Create a temporary database
        dbh = SpiderFootDb()
        
        # Load modules
        print("Loading modules...")
        modules = SpiderFootHelpers.loadModulesAsDict()
        print(f"Loaded {len(modules)} modules")
        
        # Create a scanner instance
        scanner = SpiderFootScanner("test_scan", dbh, modules)
        
        # Create a target
        target = SpiderFootTarget("1.1.1.1", "IP_ADDRESS")
        
        # Test that the scanner can be initialized
        scanner.setTarget(target)
        print("Scanner initialization successful!")
        
        # Test that modules can be accessed and have the required attributes
        test_module_name = 'sfp_bingsharedip'
        if test_module_name in modules:
            module_info = modules[test_module_name]
            print(f"Test module info: {module_info}")
            
            # Check for required attributes
            required_attrs = ['name', 'descr', 'cats', 'labels', 'opts', 'optdescs']
            for attr in required_attrs:
                if attr not in module_info:
                    print(f"Missing attribute: {attr}")
                else:
                    print(f"✓ {attr}: {module_info[attr]}")
        
        print("Minimal scan test completed successfully!")
        
    except Exception as e:
        print(f"Scan test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_minimal_scan()
