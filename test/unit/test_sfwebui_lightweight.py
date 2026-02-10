#!/usr/bin/env python3
"""
Lightweight Web UI tests that avoid CherryPy server startup for faster unit testing.
These tests focus on testing the Web UI logic without the overhead of a full web server.
"""
from __future__ import annotations

import unittest
from test.unit.utils.test_module_base import TestModuleBase
from unittest.mock import patch, MagicMock
from test.unit.utils.test_base import TestModuleBase
from test.unit.utils.resource_manager import get_test_resource_manager
from test.unit.utils.thread_registry import get_test_thread_registry


class TestSpiderFootWebUILightweight(TestModuleBase):
    """Lightweight Web UI tests that bypass CherryPy server initialization."""
    
    def setUp(self):
        super().setUp()
        self.web_config = self.web_default_options
        self.config = self.default_options.copy()
        
        # Mock all external dependencies to create a pure unit test
        with patch('sfwebui.SpiderFootDb') as mock_db, \
             patch('sfwebui.SpiderFoot') as mock_sf, \
             patch('sfwebui.logListenerSetup'), \
             patch('sfwebui.logWorkerSetup'), \
             patch('sfwebui.install_cherrypy_security'), \
             patch('sfwebui.SecureConfigManager'):
            
            # Configure mocks for minimal initialization
            mock_sf.return_value.configUnserialize.return_value = self.config
            mock_db.return_value.configGet.return_value = {}
            
            # Import and create a minimal WebUI instance
            from sfwebui import SpiderFootWebUi
            self.webui = SpiderFootWebUi(self.web_config, self.config)
        
        self.mock_db = mock_db
    
    def test_scanhistory_lightweight(self):
        """Test scanhistory method without CherryPy overhead."""
        # Mock the database at the point where it's used
        with patch('spiderfoot.webui.scan.SpiderFootDb') as mock_db:
            mock_db_instance = MagicMock()
            mock_db_instance.scanResultHistory.return_value = [
                ['scan_data', 'event_type', 'source_module'],
                ['another_data', 'another_type', 'another_source']
            ]
            mock_db.return_value = mock_db_instance
            
            # Test with valid scan ID
            result = self.webui.scanhistory('test_scan_id')
            
            # Verify results
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0], ['scan_data', 'event_type', 'source_module'])
            
            # Verify database interaction
            mock_db.assert_called_once_with(self.webui.config)
            mock_db_instance.scanResultHistory.assert_called_once_with('test_scan_id')
    
    def test_scanhistory_empty_id(self):
        """Test scanhistory with empty or None ID."""
        # Test with None
        result = self.webui.scanhistory(None)
        self.assertEqual(result, [])
        
        # Test with empty string
        result = self.webui.scanhistory('')
        self.assertEqual(result, [])
    
    def test_scanhistory_database_error(self):
        """Test scanhistory when database raises an exception."""
        with patch('spiderfoot.webui.scan.SpiderFootDb') as mock_db:
            mock_db_instance = MagicMock()
            mock_db_instance.scanResultHistory.side_effect = Exception("Database error")
            mock_db.return_value = mock_db_instance
            
            # Should return empty list on exception
            result = self.webui.scanhistory('test_scan_id')
            self.assertEqual(result, [])
    
    def test_webui_initialization_lightweight(self):
        """Test that WebUI can be initialized without errors in lightweight mode."""
        self.assertIsNotNone(self.webui)
        self.assertTrue(hasattr(self.webui, 'config'))
        self.assertIsInstance(self.webui.config, dict)
    
    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self, 'webui'):
            self.webui = None
        super().tearDown()


if __name__ == '__main__':
    unittest.main()
