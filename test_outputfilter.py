#!/usr/bin/env python

import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spiderfoot import SpiderFootPlugin

def test_outputfilter():
    print("Testing __outputFilter__ attribute...")
    
    # Create a plugin instance
    plugin = SpiderFootPlugin()
    
    # Test that the __outputFilter__ attribute exists and is initialized
    print(f"__outputFilter__ exists: {hasattr(plugin, '__outputFilter__')}")
    print(f"__outputFilter__ value: {plugin.__outputFilter__}")
    
    # Test setting the output filter
    plugin.setOutputFilter(['test_type'])
    print(f"__outputFilter__ after setting: {plugin.__outputFilter__}")
    
    # Test _log attribute as well
    print(f"_log exists: {hasattr(plugin, '_log')}")
    print(f"_log value: {plugin._log}")
    
    # Test the log property
    log = plugin.log
    print(f"log property works: {log is not None}")
    print(f"log type: {type(log)}")
    
    print("All tests passed!")

if __name__ == "__main__":
    test_outputfilter()
