#!/usr/bin/env python3
"""Test the improved queue error handling"""

import queue
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot.plugin import SpiderFootPlugin

def test_improved_queue_handling():
    """Test the improved queue error handling."""
    print("Testing improved queue error handling...")
    
    try:
        # Create a plugin instance
        plugin = SpiderFootPlugin()
        plugin.__name__ = "test_plugin"
        
        print(f"Initial queue state: incoming={plugin.incomingEventQueue}, outgoing={plugin.outgoingEventQueue}")
        
        # Test without queues - should show graceful error handling
        print("Testing start() without queues (should show error but not crash)...")
        plugin.start()
        
        # Now set up queues properly
        print("Setting up queues...")
        plugin.incomingEventQueue = queue.Queue()
        plugin.outgoingEventQueue = queue.Queue()
        
        print(f"After setup: incoming={plugin.incomingEventQueue is not None}, outgoing={plugin.outgoingEventQueue is not None}")
        
        # Test with queues - this should work (but will fail due to missing sf setup, which is expected)
        print("Testing start() with queues...")
        plugin.start()
        
        print("Queue error handling test completed successfully")
        return True
        
    except Exception as e:
        print(f"Unexpected error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_improved_queue_handling()
    sys.exit(0 if success else 1)
