#!/usr/bin/env python

import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spiderfoot import SpiderFootPlugin

def test_logging():
    print("Testing logging functionality...")
    
    # Create a plugin instance
    plugin = SpiderFootPlugin()
    
    # Test the log property
    log = plugin.log
    print(f"log property: {log}")
    print(f"log type: {type(log)}")
    
    # Test debug method
    try:
        plugin.debug("Test debug message")
        print("Debug method works!")
    except Exception as e:
        print(f"Debug method failed: {e}")
    
    # Test info method
    try:
        plugin.info("Test info message")
        print("Info method works!")
    except Exception as e:
        print(f"Info method failed: {e}")
    
    print("Logging test completed!")

if __name__ == "__main__":
    test_logging()
