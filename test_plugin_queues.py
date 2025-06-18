#!/usr/bin/env python3
"""Test to reproduce the queue error"""

import queue
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot.plugin import SpiderFootPlugin

def test_plugin_queues():
    """Test plugin queue initialization directly."""
    print("Testing plugin queue initialization...")
    
    try:
        # Create a plugin instance
        plugin = SpiderFootPlugin()
        plugin.__name__ = "test_plugin"
        
        print(f"Initial queue state: incoming={plugin.incomingEventQueue}, outgoing={plugin.outgoingEventQueue}")
        
        # Test without queues - this should trigger the error
        print("Testing start() without queues...")
        plugin.start()  # This should show the error message
        
        # Now set up queues properly
        print("Setting up queues...")
        plugin.incomingEventQueue = queue.Queue()
        plugin.outgoingEventQueue = queue.Queue()
        
        print(f"After setup: incoming={plugin.incomingEventQueue is not None}, outgoing={plugin.outgoingEventQueue is not None}")
        
        # Test with queues - this should work
        print("Testing start() with queues...")
        plugin.start()  # This should work
        
        print("Plugin queue test completed")
        return True
        
    except Exception as e:
        print(f"Error during plugin test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_plugin_queues()
    sys.exit(0 if success else 1)
