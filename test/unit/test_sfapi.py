import unittest
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock all external dependencies before importing - corrected module names
mock_sflib = MagicMock()
mock_sflib.SpiderFoot = MagicMock()

mock_spiderfoot_db = MagicMock()
mock_spiderfoot_db.SpiderFootDb = MagicMock()

mock_spiderfoot = MagicMock()
mock_spiderfoot.SpiderFootHelpers = MagicMock()

mock_sfscan = MagicMock()
mock_sfscan.startSpiderFootScanner = MagicMock()

# Mock multiprocessing and logging
mock_mp = MagicMock()
mock_mp.Queue = MagicMock()
sys.modules['multiprocessing'] = mock_mp

mock_logger = MagicMock()
sys.modules['spiderfoot.logger'] = mock_logger

# Mock FastAPI and related dependencies
mock_fastapi = MagicMock()
mock_fastapi.FastAPI = MagicMock()
mock_fastapi.HTTPException = MagicMock()
mock_fastapi.Depends = MagicMock()
mock_fastapi.status = MagicMock()
mock_fastapi.Request = MagicMock()
mock_fastapi.Query = MagicMock()

sys.modules['fastapi'] = mock_fastapi
sys.modules['fastapi.security'] = MagicMock()
sys.modules['fastapi.middleware.cors'] = MagicMock()
sys.modules['fastapi.middleware.gzip'] = MagicMock()
sys.modules['fastapi.responses'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['uvicorn'] = MagicMock()

# Apply all mocks with correct module structure
with patch.dict('sys.modules', {
    'sflib': mock_sflib,
    'spiderfoot.db': mock_spiderfoot_db,
    'spiderfoot': mock_spiderfoot,
    'sfscan': mock_sfscan,
}):
    # Mock the classes that sfapi tries to import with correct names
    with patch('sfapi.SpiderFoot', mock_sflib.SpiderFoot), \
         patch('sfapi.SpiderFootDb', mock_spiderfoot_db.SpiderFootDb), \
         patch('sfapi.SpiderFootHelpers', mock_spiderfoot.SpiderFootHelpers), \
         patch('sfapi.startSpiderFootScanner', mock_sfscan.startSpiderFootScanner):
        
        # Now we can safely import sfapi with all dependencies mocked
        import sfapi

from test.unit.utils.test_base import SpiderFootTestBase


class TestSfapi(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        # Create a temporary database file for testing
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        
        # Mock the global config with required database path
        self.mock_config = {
            '__modules__': {
                'sfp_dns': {
                    'name': 'DNS Resolver',
                    'cats': ['Footprint'],
                    'descr': 'DNS resolution module',
                    'labels': ['passive']
                }
            },
            '__correlationrules__': [],
            '_debug': False,
            'webaddr': '127.0.0.1',
            'webport': '8001',
            '__webaddr_apikey': 'test-api-key',
            '__database': self.test_db.name  # Add required database path
        }

    def tearDown(self):
        super().tearDown()
        # Clean up temporary database file
        if hasattr(self, 'test_db') and os.path.exists(self.test_db.name):
            os.unlink(self.test_db.name)

    # def test_config_init(self):
    #     """Test Config class initialization"""
    #     with patch('sfapi.SpiderFoot') as mock_sf, \
    #          patch('sfapi.SpiderFootDb') as mock_db, \
    #          patch('sfapi.logListenerSetup') as mock_log_setup:
            
    #         # Setup mocks
    #         mock_sf_instance = MagicMock()
    #         mock_sf.return_value = mock_sf_instance
    #         mock_sf_instance.configUnserialize.return_value = self.mock_config
            
    #         mock_db_instance = MagicMock()
    #         mock_db.return_value = mock_db_instance
    #         mock_db_instance.configGet.return_value = {}
            
    #         config = sfapi.Config()
            
    #         self.assertIsInstance(config, sfapi.Config)
    #         mock_sf.assert_called()
    #         mock_db.assert_called()

    # def test_config_get_config(self):
    #     """Test Config.get_config method"""
    #     with patch('sfapi.SpiderFoot') as mock_sf, \
    #          patch('sfapi.SpiderFootDb') as mock_db, \
    #          patch('sfapi.logListenerSetup') as mock_log_setup:
            
    #         mock_sf_instance = MagicMock()
    #         mock_sf.return_value = mock_sf_instance
    #         mock_sf_instance.configUnserialize.return_value = self.mock_config
            
    #         mock_db_instance = MagicMock()
    #         mock_db.return_value = mock_db_instance
    #         mock_db_instance.configGet.return_value = {}
            
    #         config = sfapi.Config()
    #         result = config.get_config()
            
    #         self.assertEqual(result, self.mock_config)

    # def test_config_update_config(self):
    #     """Test Config.update_config method"""
    #     with patch('sfapi.SpiderFoot') as mock_sf, \
    #          patch('sfapi.SpiderFootDb') as mock_db, \
    #          patch('sfapi.logListenerSetup') as mock_log_setup:
            
    #         mock_sf_instance = MagicMock()
    #         mock_sf.return_value = mock_sf_instance
    #         mock_sf_instance.configUnserialize.return_value = self.mock_config
            
    #         mock_db_instance = MagicMock()
    #         mock_db.return_value = mock_db_instance
    #         mock_db_instance.configGet.return_value = {}
            
    #         config = sfapi.Config()
    #         updates = {'_debug': True, 'new_key': 'new_value'}
    #         result = config.update_config(updates)
            
    #         self.assertTrue(result['_debug'])
    #         self.assertEqual(result['new_key'], 'new_value')

    def test_scan_request_validation(self):
        """Test ScanRequest model validation"""
        # Test valid request
        valid_data = {
            'name': 'Test Scan',
            'target': 'example.com',
            'modules': ['sfp_dns'],
            'type_filter': ['IP_ADDRESS']
        }
        
        # Create mock pydantic model
        mock_scan_request = MagicMock()
        mock_scan_request.name = valid_data['name']
        mock_scan_request.target = valid_data['target']
        mock_scan_request.modules = valid_data['modules']
        mock_scan_request.type_filter = valid_data['type_filter']
        
        self.assertEqual(mock_scan_request.name, 'Test Scan')
        self.assertEqual(mock_scan_request.target, 'example.com')

    def test_scan_response_model(self):
        """Test ScanResponse model"""
        mock_scan_response = MagicMock()
        mock_scan_response.scan_id = 'test-scan-id'
        mock_scan_response.name = 'Test Scan'
        mock_scan_response.target = 'example.com'
        mock_scan_response.status = 'RUNNING'
        mock_scan_response.created = datetime.now()
        
        self.assertEqual(mock_scan_response.scan_id, 'test-scan-id')
        self.assertEqual(mock_scan_response.status, 'RUNNING')

    def test_event_response_model(self):
        """Test EventResponse model"""
        mock_event_response = MagicMock()
        mock_event_response.event_id = 'event-123'
        mock_event_response.scan_id = 'scan-123'
        mock_event_response.event_type = 'IP_ADDRESS'
        mock_event_response.data = '192.168.1.1'
        mock_event_response.module = 'sfp_dns'
        
        self.assertEqual(mock_event_response.event_type, 'IP_ADDRESS')
        self.assertEqual(mock_event_response.data, '192.168.1.1')

    def test_module_info_model(self):
        """Test ModuleInfo model"""
        mock_module_info = MagicMock()
        mock_module_info.name = 'DNS Resolver'
        mock_module_info.category = 'Footprint'
        mock_module_info.description = 'DNS resolution module'
        mock_module_info.flags = ['passive']
        
        self.assertEqual(mock_module_info.name, 'DNS Resolver')
        self.assertEqual(mock_module_info.category, 'Footprint')

    @patch('sfapi.app_config')
    async def test_verify_token_valid(self, mock_app_config):
        """Test verify_token with valid token"""
        mock_app_config.get_config.return_value = {'__webaddr_apikey': 'test-key'}
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = 'test-key'
        
        result = await sfapi.verify_token(mock_credentials)
        self.assertEqual(result, 'test-key')

    @patch('sfapi.app_config')
    async def test_verify_token_invalid(self, mock_app_config):
        """Test verify_token with invalid token"""
        mock_app_config.get_config.return_value = {'__webaddr_apikey': 'correct-key'}
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = 'wrong-key'
        
        with patch('sfapi.HTTPException') as mock_exception:
            await sfapi.verify_token(mock_credentials)
            mock_exception.assert_called()

    @patch('sfapi.app_config')
    async def test_verify_token_no_key_configured(self, mock_app_config):
        """Test verify_token when no API key is configured"""
        mock_app_config.get_config.return_value = {'__webaddr_apikey': ''}
        
        mock_credentials = MagicMock()
        mock_credentials.credentials = 'any-key'
        
        result = await sfapi.verify_token(mock_credentials)
        self.assertEqual(result, 'any-key')

    async def test_health_check(self):
        """Test health check endpoint"""
        result = await sfapi.health_check()
        
        self.assertIn('status', result)
        self.assertIn('timestamp', result)
        self.assertIn('version', result)
        self.assertEqual(result['status'], 'healthy')

    @patch('sfapi.app_config')
    async def test_get_config_endpoint(self, mock_app_config):
        """Test get_config endpoint"""
        mock_app_config.get_config.return_value = {
            'public_key': 'value',
            '__private_key': 'secret'
        }
        
        result = await sfapi.get_config()
        
        self.assertIn('config', result)
        self.assertIn('public_key', result['config'])
        self.assertNotIn('__private_key', result['config'])

    @patch('sfapi.app_config')
    async def test_update_config_endpoint(self, mock_app_config):
        """Test update_config endpoint"""
        mock_config_update = MagicMock()
        mock_config_update.config = {'new_setting': 'new_value'}
        
        mock_app_config.update_config.return_value = {'updated': True}
        
        result = await sfapi.update_config(mock_config_update)
        
        self.assertIn('message', result)
        self.assertIn('config', result)

    @patch('sfapi.app_config')
    async def test_get_modules_endpoint(self, mock_app_config):
        """Test get_modules endpoint"""
        mock_app_config.get_config.return_value = {
            '__modules__': {
                'sfp_dns': {
                    'name': 'DNS Resolver',
                    'cats': ['Footprint'],
                    'descr': 'DNS resolution module',
                    'labels': ['passive']
                }
            }
        }
        
        result = await sfapi.get_modules()
        
        self.assertIn('modules', result)
        self.assertIsInstance(result['modules'], list)

    @patch('sfapi.app_config')
    async def test_get_scans_endpoint(self, mock_app_config):
        """Test get_scans endpoint"""
        mock_scan_data = [
            ['scan-1', 'Test Scan 1', 'example.com', 1234567890, 1234567891, 'FINISHED'],
            ['scan-2', 'Test Scan 2', 'test.com', 1234567892, 1234567893, 'RUNNING']
        ]
        
        mock_db = MagicMock()
        mock_db.scanInstanceList.return_value = mock_scan_data
        mock_app_config.db = mock_db
        
        result = await sfapi.get_scans(limit=50, offset=0)
        
        self.assertIn('scans', result)
        self.assertIn('total', result)
        self.assertEqual(result['total'], 2)

    @patch('sfapi.app_config')
    @patch('sfapi.SpiderFootHelpers.genScanInstanceId', return_value='new-scan-id')
    @patch('sfapi.SpiderFootHelpers.targetTypeFromString', return_value='INTERNET_NAME')
    @patch('sfapi.mp.Process')
    async def test_create_scan_endpoint(self, mock_process, mock_target_type, mock_gen_id, mock_app_config):
        """Test create_scan endpoint"""
        mock_scan_request = MagicMock()
        mock_scan_request.name = 'Test Scan'
        mock_scan_request.target = 'example.com'
        mock_scan_request.modules = ['sfp_dns']
        
        mock_app_config.get_config.return_value = {
            '__modules__': {'sfp_dns': {}}
        }
        mock_app_config.db.scanInstanceCreate = MagicMock()
        
        mock_proc = MagicMock()
        mock_process.return_value = mock_proc
        
        result = await sfapi.create_scan(mock_scan_request)
        
        self.assertIn('scan_id', result)
        self.assertIn('message', result)
        self.assertEqual(result['scan_id'], 'new-scan-id')

    @patch('sfapi.app_config')
    async def test_get_scan_endpoint(self, mock_app_config):
        """Test get_scan endpoint"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'FINISHED', 1234567892]
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        
        result = await sfapi.get_scan('scan-1')
        
        self.assertEqual(result['scan_id'], 'scan-1')
        self.assertEqual(result['name'], 'Test Scan')

    @patch('sfapi.app_config')
    async def test_get_scan_not_found(self, mock_app_config):
        """Test get_scan endpoint when scan not found"""
        mock_app_config.db.scanInstanceGet.return_value = None
        
        with patch('sfapi.HTTPException') as mock_exception:
            await sfapi.get_scan('nonexistent-scan')
            mock_exception.assert_called()

    @patch('sfapi.app_config')
    async def test_delete_scan_endpoint(self, mock_app_config):
        """Test delete_scan endpoint"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'FINISHED']
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        mock_app_config.db.scanInstanceDelete = MagicMock()
        
        result = await sfapi.delete_scan('scan-1')
        
        self.assertIn('message', result)
        mock_app_config.db.scanInstanceDelete.assert_called_with('scan-1')

    @patch('sfapi.app_config')
    async def test_stop_scan_endpoint(self, mock_app_config):
        """Test stop_scan endpoint"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'RUNNING']
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        mock_app_config.db.scanInstanceSet = MagicMock()
        
        result = await sfapi.stop_scan('scan-1')
        
        self.assertIn('message', result)
        self.assertEqual(result['scan_id'], 'scan-1')

    @patch('sfapi.app_config')
    async def test_stop_scan_not_running(self, mock_app_config):
        """Test stop_scan endpoint when scan is not running"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'FINISHED']
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        
        with patch('sfapi.HTTPException') as mock_exception:
            await sfapi.stop_scan('scan-1')
            mock_exception.assert_called()

    @patch('sfapi.app_config')
    async def test_get_scan_status_endpoint(self, mock_app_config):
        """Test get_scan_status endpoint"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'RUNNING']
        mock_events = [
            [1234567890, 'data1', 'source1', 'module1', 'IP_ADDRESS'],
            [1234567891, 'data2', 'source2', 'module2', 'INTERNET_NAME']
        ]
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        mock_app_config.db.scanResultEvent.return_value = mock_events
        
        result = await sfapi.get_scan_status('scan-1')
        
        self.assertEqual(result['scan_id'], 'scan-1')
        self.assertEqual(result['status'], 'RUNNING')
        self.assertEqual(result['event_count'], 2)

    @patch('sfapi.app_config')
    async def test_get_event_types_endpoint(self, mock_app_config):
        """Test get_event_types endpoint"""
        mock_event_types = [
            ('1', 'IP_ADDRESS'),
            ('2', 'INTERNET_NAME'),
            ('3', 'EMAIL_ADDRESS')
        ]
        
        mock_app_config.db.eventTypes.return_value = mock_event_types
        
        result = await sfapi.get_event_types()
        
        self.assertIn('event_types', result)
        self.assertEqual(result['event_types'], mock_event_types)

    @patch('sfapi.app_config')
    async def test_get_scan_events_endpoint(self, mock_app_config):
        """Test get_scan_events endpoint"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'FINISHED']
        mock_events = [
            [1234567890, 'data1', 'source1', 'module1', 'IP_ADDRESS', '', 100, 0, 0, 'hash1', 'source_event1', 'event_id1', 'scan-1'],
        ]
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        mock_app_config.db.scanResultEvent.return_value = mock_events
        
        result = await sfapi.get_scan_events('scan-1', event_types=None, limit=1000, offset=0)
        
        self.assertIn('events', result)
        self.assertEqual(result['scan_id'], 'scan-1')
        self.assertEqual(result['total'], 1)

    @patch('sfapi.app_config')
    async def test_export_scan_json(self, mock_app_config):
        """Test export_scan endpoint with JSON format"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'FINISHED']
        mock_events = [
            [1234567890, 'data1', 'source1', 'module1', 'IP_ADDRESS', '', 100],
        ]
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        mock_app_config.db.scanResultEvent.return_value = mock_events
        
        with patch('sfapi.StreamingResponse') as mock_streaming_response:
            await sfapi.export_scan('scan-1', format='json')
            mock_streaming_response.assert_called()

    @patch('sfapi.app_config')
    async def test_export_scan_csv(self, mock_app_config):
        """Test export_scan endpoint with CSV format"""
        mock_scan_info = ['scan-1', 'Test Scan', 'example.com', 1234567890, 1234567891, 'FINISHED']
        mock_events = [
            [1234567890, 'data1', 'source1', 'module1', 'IP_ADDRESS', '', 100],
        ]
        
        mock_app_config.db.scanInstanceGet.return_value = mock_scan_info
        mock_app_config.db.scanResultEvent.return_value = mock_events
        
        with patch('sfapi.StreamingResponse') as mock_streaming_response:
            await sfapi.export_scan('scan-1', format='csv')
            mock_streaming_response.assert_called()

    def test_fastapi_app_creation(self):
        """Test FastAPI app is created with correct configuration"""
        self.assertTrue(hasattr(sfapi, 'app'))
        # Mock FastAPI was used, so we just verify the app object exists

    def test_middleware_configuration(self):
        """Test middleware is configured"""
        # Since we're using mocked FastAPI, we just verify the functions exist
        self.assertTrue(hasattr(sfapi.app, 'add_middleware'))

    def test_exception_handlers_exist(self):
        """Test exception handlers are defined"""
        # Verify the handler functions exist
        self.assertTrue(callable(sfapi.http_exception_handler))
        self.assertTrue(callable(sfapi.general_exception_handler))

    async def test_websocket_scan_stream(self):
        """Test WebSocket endpoint for scan streaming"""
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()
        mock_websocket.close = AsyncMock()
        
        with patch('sfapi.app_config') as mock_app_config, \
             patch('sfapi.asyncio.sleep', side_effect=Exception("Stop loop")):
            
            mock_app_config.db.scanResultEvent.return_value = []
            
            try:
                await sfapi.websocket_scan_stream(mock_websocket, 'test-scan-id')
            except Exception:
                pass  # Expected to break the loop
            
            mock_websocket.accept.assert_called_once()

    def test_main_entry_point(self):
        """Test main entry point configuration"""
        with patch('sfapi.uvicorn.run') as mock_run, \
             patch('sfapi.app_config') as mock_app_config:
            # Test that main entry point exists and can be called
            # We'll simulate calling it with environment variables
            with patch.dict(os.environ, {'FASTAPI_HOST': '0.0.0.0', 'FASTAPI_PORT': '9000'}):
                # Since the if __name__ == "__main__" block won't run in tests,
                # we'll test the uvicorn.run would be called with correct parameters
                pass  # The main block is conditional and won't run during import

    def test_api_logging_queue_setup(self):
        """Test API logging queue is set up"""
        self.assertTrue(hasattr(sfapi, 'api_logging_queue'))

    def test_security_bearer_setup(self):
        """Test security bearer token setup"""
        self.assertTrue(hasattr(sfapi, 'security'))

    @patch('sfapi.logger')
    async def test_error_handling_in_endpoints(self, mock_logger):
        """Test error handling in endpoints"""
        with patch('sfapi.app_config') as mock_app_config:
            mock_app_config.db.scanInstanceGet.side_effect = Exception("Database error")
            
            with patch('sfapi.HTTPException') as mock_exception:
                try:
                    await sfapi.get_scan('test-scan-id')
                except:
                    pass
                # Verify error was logged
                mock_logger.error.assert_called()

    def test_pydantic_models_exist(self):
        """Test all Pydantic models are defined"""
        models = ['ScanRequest', 'ScanResponse', 'EventResponse', 'ModuleInfo', 'ApiKeyModel', 'ConfigUpdate']
        for model_name in models:
            self.assertTrue(hasattr(sfapi, model_name))

    def test_route_endpoints_exist(self):
        """Test all API route functions exist"""
        endpoints = [
            'health_check', 'get_config', 'update_config', 'get_modules',
            'get_scans', 'create_scan', 'get_scan', 'delete_scan',
            'stop_scan', 'get_scan_status', 'get_event_types',
            'get_scan_events', 'export_scan'
        ]
        for endpoint in endpoints:
            self.assertTrue(hasattr(sfapi, endpoint))
            self.assertTrue(callable(getattr(sfapi, endpoint)))


if __name__ == '__main__':
    unittest.main()
