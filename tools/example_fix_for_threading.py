# Example fix for a test using threading
import threading
import unittest
from unittest import mock

class TestWithThreads(unittest.TestCase):
    def setUp(self):
        # Store all threads we create so we can clean them up
        self.threads = []
        
    def create_thread(self, target):
        # Set daemon=True so thread doesn't block test exit
        thread = threading.Thread(target=target, daemon=True)
        self.threads.append(thread)
        return thread
    
    def tearDown(self):
        # Ensure all threads are stopped
        for thread in self.threads:
            if thread.is_alive():
                # Add timeout to join to prevent hanging
                thread.join(timeout=1.0)
                
        # Additional cleanup code as needed
        self.threads = []
