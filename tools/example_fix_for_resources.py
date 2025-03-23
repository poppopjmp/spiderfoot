# Example fix for a test using external resources
import unittest
import socket
import time

class TestWithResources(unittest.TestCase):
    def setUp(self):
        # Track resources to ensure cleanup
        self.resources = []
        
    def create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set a timeout to prevent blocking indefinitely
        sock.settimeout(5.0)
        self.resources.append(sock)
        return sock
    
    def tearDown(self):
        # Clean up all resources
        for resource in self.resources:
            try:
                if isinstance(resource, socket.socket):
                    resource.close()
                # Add other resource types as needed
            except Exception as e:
                print(f"Error cleaning up resource: {e}")
