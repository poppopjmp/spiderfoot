#!/usr/bin/env python

import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spiderfoot import SpiderFootPlugin
import importlib.util

def test_maxthreads():
    print("Testing maxThreads attribute...")
    
    # Test base SpiderFootPlugin
    plugin = SpiderFootPlugin()
    print(f"Base plugin maxThreads: {plugin.maxThreads}")
    
    # Test a real module
    try:
        spec = importlib.util.spec_from_file_location("sfp_bingsharedip", "modules/sfp_bingsharedip.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Get the class
        plugin_class = getattr(module, 'sfp_bingsharedip')
        plugin_instance = plugin_class()
        
        print(f"Real module maxThreads: {plugin_instance.maxThreads}")
        print(f"Real module has maxThreads attribute: {hasattr(plugin_instance, 'maxThreads')}")
        
        # Test that we can access it without AttributeError
        try:
            max_threads = plugin_instance.maxThreads
            print(f"✓ maxThreads accessible: {max_threads}")
        except AttributeError as e:
            print(f"✗ maxThreads not accessible: {e}")
            
        print("maxThreads test completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_maxthreads()
