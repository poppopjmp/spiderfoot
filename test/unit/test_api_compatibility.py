# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         test_api_compatibility
# Purpose:      Test compatibility between CherryPy and FastAPI implementations
#
# Author:       Steve Micallef <steve@binarypool.com>
#
# Created:      Current Date
# Copyright:    (c) Steve Micallef
# License:      MIT
# -----------------------------------------------------------------
import json
import os
import subprocess
import sys
import time
import unittest
import requests

class TestApiCompatibility(unittest.TestCase):
    """Test API compatibility between CherryPy and FastAPI implementations."""

    cherrypy_port = 5001
    fastapi_port = 5002
    cherrypy_process = None
    fastapi_process = None
    cherrypy_base = f"http://127.0.0.1:{cherrypy_port}"
    fastapi_base = f"http://127.0.0.1:{fastapi_port}"
    test_scan_id = None
    test_target = "example.com"

    @classmethod
    def setUpClass(cls):
        """Start both API servers for testing."""
        # Set up test environment
        cls.config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "spiderfoot.cfg")
        
        # Start CherryPy API
        cls.cherrypy_process = subprocess.Popen(
            [sys.executable, "sfapi_controller.py", "-s", "cherrypy", "-p", str(cls.cherrypy_port), "-c", cls.config_file], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )

        # Start FastAPI API
        cls.fastapi_process = subprocess.Popen(
            [sys.executable, "sfapi_controller.py", "-s", "fastapi", "-p", str(cls.fastapi_port), "-c", cls.config_file], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )

        # Wait for servers to start
        time.sleep(5)
        
        # Check if both servers are running
        try:
            cherrypy_response = requests.get(f"{cls.cherrypy_base}/ping")
            fastapi_response = requests.get(f"{cls.fastapi_base}/ping")
            
            if cherrypy_response.status_code != 200 or fastapi_response.status_code != 200:
                raise Exception("Failed to start one or both API servers")
                
            # Create a test scan on CherryPy for testing endpoints that require a scan ID
            scan_data = {
                "scanname": "API Compatibility Test",
                "scantarget": cls.test_target,
                "usecase": "passive"
            }
            response = requests.post(f"{cls.cherrypy_base}/startscan", data=scan_data)
            response_json = response.json()
            if 'scan_id' in response_json:
                cls.test_scan_id = response_json['scan_id']
            
        except Exception as e:
            cls.tearDownClass()
            raise e

    @classmethod
    def tearDownClass(cls):
        """Terminate API servers."""
        if cls.cherrypy_process:
            cls.cherrypy_process.terminate()
        if cls.fastapi_process:
            cls.fastapi_process.terminate()

    def test_ping_endpoint(self):
        """Test ping endpoint returns same structure."""
        cherrypy_response = requests.get(f"{self.cherrypy_base}/ping")
        fastapi_response = requests.get(f"{self.fastapi_base}/ping")
        
        self.assertEqual(cherrypy_response.status_code, fastapi_response.status_code)
        
        # CherryPy returns a list, FastAPI returns a dict
        cherrypy_data = cherrypy_response.json()
        fastapi_data = fastapi_response.json()
        
        # Both should contain version info
        self.assertEqual(cherrypy_data[1], fastapi_data["version"])

    def test_scanlist_endpoint(self):
        """Test scanlist endpoint returns same structure."""
        cherrypy_response = requests.get(f"{self.cherrypy_base}/scanlist")
        fastapi_response = requests.get(f"{self.fastapi_base}/scanlist")
        
        self.assertEqual(cherrypy_response.status_code, fastapi_response.status_code)
        
        # Both should return a list of scans
        cherrypy_data = cherrypy_response.json()
        fastapi_data = fastapi_response.json()
        
        self.assertEqual(type(cherrypy_data), type(fastapi_data))
        
        # Check that the scan format is consistent
        if len(cherrypy_data) > 0 and len(fastapi_data) > 0:
            self.assertEqual(len(cherrypy_data[0]), len(fastapi_data[0]))

    def test_modules_endpoint(self):
        """Test modules endpoint returns same structure."""
        cherrypy_response = requests.get(f"{self.cherrypy_base}/modules")
        fastapi_response = requests.get(f"{self.fastapi_base}/modules")
        
        self.assertEqual(cherrypy_response.status_code, fastapi_response.status_code)
        
        # Both should return a list of modules
        cherrypy_data = cherrypy_response.json()
        fastapi_data = fastapi_response.json()
        
        self.assertEqual(type(cherrypy_data), type(fastapi_data))
        
        # Check that the module format is consistent
        if len(cherrypy_data) > 0 and len(fastapi_data) > 0:
            self.assertEqual(set(cherrypy_data[0].keys()), set(fastapi_data[0].keys()))

    def test_eventtypes_endpoint(self):
        """Test eventtypes endpoint returns same structure."""
        cherrypy_response = requests.get(f"{self.cherrypy_base}/eventtypes")
        fastapi_response = requests.get(f"{self.fastapi_base}/eventtypes")
        
        self.assertEqual(cherrypy_response.status_code, fastapi_response.status_code)
        
        # Both should return a list of event types
        cherrypy_data = cherrypy_response.json()
        fastapi_data = fastapi_response.json()
        
        self.assertEqual(type(cherrypy_data), type(fastapi_data))
        
        # Check that the event type format is consistent
        if len(cherrypy_data) > 0 and len(fastapi_data) > 0:
            self.assertEqual(set(cherrypy_data[0].keys()), set(fastapi_data[0].keys()))

    # Add more test methods for other endpoints
