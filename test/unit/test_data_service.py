"""
Tests for the DataService abstraction layer.
"""

import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.data_service.base import (
    DataService,
    DataServiceBackend,
    DataServiceConfig,
)
from spiderfoot.data_service.local import LocalDataService
from spiderfoot.data_service.factory import (
    create_data_service,
    create_data_service_from_config,
    create_data_service_from_env,
    DataServiceBridge,
)


class TestDataServiceConfig(unittest.TestCase):
    """Test DataServiceConfig and DataServiceBackend."""
    
    def test_default_config(self):
        config = DataServiceConfig()
        self.assertEqual(config.backend, DataServiceBackend.LOCAL)
        self.assertEqual(config.api_url, "http://localhost:8002")
        self.assertEqual(config.timeout, 30.0)
        self.assertEqual(config.max_retries, 3)

    def test_backend_enum(self):
        self.assertEqual(DataServiceBackend.LOCAL.value, "local")
        self.assertEqual(DataServiceBackend.HTTP.value, "http")
        self.assertEqual(DataServiceBackend.GRPC.value, "grpc")

    def test_custom_config(self):
        config = DataServiceConfig(
            backend=DataServiceBackend.HTTP,
            api_url="http://data-service:8002",
            api_key="secret",
            timeout=10.0,
            db_config={"__database": "test.db"},
        )
        self.assertEqual(config.backend, DataServiceBackend.HTTP)
        self.assertEqual(config.api_key, "secret")
        self.assertEqual(config.db_config["__database"], "test.db")


class TestDataServiceABC(unittest.TestCase):
    """Test that DataService cannot be instantiated directly."""
    
    def test_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            DataService()


class TestLocalDataService(unittest.TestCase):
    """Test LocalDataService with mocked DB."""
    
    def setUp(self):
        self.ds = LocalDataService(db_opts={"__database": ":memory:"})
        # Mock the DB handle
        self.mock_dbh = MagicMock()
        self.ds.set_db_handle(self.mock_dbh)
    
    def test_set_db_handle(self):
        self.assertTrue(self.ds._initialized)
        self.assertEqual(self.ds.dbh, self.mock_dbh)
    
    def test_scan_instance_create(self):
        result = self.ds.scan_instance_create("scan-1", "Test Scan", "example.com")
        self.assertTrue(result)
        self.mock_dbh.scanInstanceCreate.assert_called_once_with(
            "scan-1", "Test Scan", "example.com"
        )
    
    def test_scan_instance_create_error(self):
        self.mock_dbh.scanInstanceCreate.side_effect = Exception("DB error")
        result = self.ds.scan_instance_create("scan-1", "Test", "example.com")
        self.assertFalse(result)
    
    def test_scan_instance_get(self):
        self.mock_dbh.scanInstanceGet.return_value = [
            ("Test Scan", "example.com", 1000, 1001, 1002, "FINISHED")
        ]
        result = self.ds.scan_instance_get("scan-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Test Scan")
        self.assertEqual(result["target"], "example.com")
        self.assertEqual(result["status"], "FINISHED")
    
    def test_scan_instance_get_not_found(self):
        self.mock_dbh.scanInstanceGet.return_value = []
        result = self.ds.scan_instance_get("nonexistent")
        self.assertIsNone(result)
    
    def test_scan_instance_list(self):
        self.mock_dbh.scanInstanceList.return_value = [
            ("id-1", "Scan 1", "target1.com", 100, 101, 102, "FINISHED", 50),
            ("id-2", "Scan 2", "target2.com", 200, 201, 0, "RUNNING", 10),
        ]
        results = self.ds.scan_instance_list()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "id-1")
        self.assertEqual(results[1]["status"], "RUNNING")
    
    def test_scan_instance_delete(self):
        result = self.ds.scan_instance_delete("scan-1")
        self.assertTrue(result)
        self.mock_dbh.scanInstanceDelete.assert_called_once_with("scan-1")
    
    def test_scan_status_set(self):
        result = self.ds.scan_status_set("scan-1", "RUNNING", started=1000)
        self.assertTrue(result)
        self.mock_dbh.scanInstanceSet.assert_called_once()
    
    def test_event_get_by_scan(self):
        self.mock_dbh.scanResultEvent.return_value = [
            (1000, "data1", "sfp_test", "hash1", "IP_ADDRESS", "ROOT", 100, 100, 0),
        ]
        results = self.ds.event_get_by_scan("scan-1", event_type="IP_ADDRESS")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "IP_ADDRESS")
        self.assertEqual(results[0]["data"], "data1")
    
    def test_event_exists(self):
        self.mock_dbh.scanResultEvent.return_value = [
            (1000, "1.2.3.4", "sfp_test", "h1", "IP_ADDRESS", "ROOT", 100, 100, 0)
        ]
        self.assertTrue(self.ds.event_exists("scan-1", "IP_ADDRESS", "1.2.3.4"))
    
    def test_event_exists_not_found(self):
        self.mock_dbh.scanResultEvent.return_value = []
        self.assertFalse(self.ds.event_exists("scan-1", "IP_ADDRESS", "9.9.9.9"))
    
    def test_scan_log_event(self):
        result = self.ds.scan_log_event("scan-1", "STATUS", "Scan started", "core")
        self.assertTrue(result)
        self.mock_dbh.scanLogEvent.assert_called_once_with(
            "scan-1", "STATUS", "Scan started", "core"
        )
    
    def test_scan_log_get(self):
        self.mock_dbh.scanLogs.return_value = [
            (1000, "core", "STATUS", "Scan started", 1),
            (1001, "sfp_test", "DATA", "Found something", 2),
        ]
        results = self.ds.scan_log_get("scan-1")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["message"], "Scan started")
    
    def test_config_set_global(self):
        result = self.ds.config_set({"key1": "val1"})
        self.assertTrue(result)
        self.mock_dbh.configSet.assert_called_once_with({"key1": "val1"})
    
    def test_config_get(self):
        self.mock_dbh.configGet.return_value = {
            "opt1": "val1",
            "scope1:opt2": "val2",
        }
        result = self.ds.config_get("GLOBAL")
        self.assertEqual(result, {"opt1": "val1"})
    
    def test_scan_result_summary(self):
        self.mock_dbh.scanResultSummary.return_value = [
            ("IP_ADDRESS", "IP Address", 1000, 50, 25),
            ("DOMAIN_NAME", "Domain Name", 1001, 30, 15),
        ]
        result = self.ds.scan_result_summary("scan-1")
        self.assertEqual(result["IP_ADDRESS"], 50)
        self.assertEqual(result["DOMAIN_NAME"], 30)
    
    def test_event_types_list(self):
        self.mock_dbh.eventTypes.return_value = [
            ("IP Address", "IP_ADDRESS", 0, "ENTITY"),
        ]
        result = self.ds.event_types_list()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event"], "IP_ADDRESS")


class TestFactory(unittest.TestCase):
    """Test factory functions."""
    
    def test_create_default(self):
        ds = create_data_service()
        self.assertIsInstance(ds, LocalDataService)
    
    def test_create_local_explicit(self):
        config = DataServiceConfig(backend=DataServiceBackend.LOCAL)
        ds = create_data_service(config)
        self.assertIsInstance(ds, LocalDataService)
    
    def test_create_http_fallback(self):
        config = DataServiceConfig(backend=DataServiceBackend.HTTP)
        ds = create_data_service(config)
        # Falls back to local until HTTP is implemented
        self.assertIsInstance(ds, LocalDataService)
    
    def test_create_from_config(self):
        sf_config = {
            "_dataservice_backend": "local",
            "__database": "test.db",
            "__dbtype": "sqlite",
        }
        ds = create_data_service_from_config(sf_config)
        self.assertIsInstance(ds, LocalDataService)
    
    def test_create_from_config_unknown_backend(self):
        sf_config = {"_dataservice_backend": "unknown"}
        ds = create_data_service_from_config(sf_config)
        self.assertIsInstance(ds, LocalDataService)
    
    @patch.dict("os.environ", {"SF_DATASERVICE_BACKEND": "local"})
    def test_create_from_env(self):
        ds = create_data_service_from_env()
        self.assertIsInstance(ds, LocalDataService)


class TestDataServiceBridge(unittest.TestCase):
    """Test legacy bridge compatibility."""
    
    def setUp(self):
        self.ds = LocalDataService()
        self.mock_dbh = MagicMock()
        self.ds.set_db_handle(self.mock_dbh)
        self.bridge = DataServiceBridge(self.ds)
    
    def test_scanInstanceCreate(self):
        self.bridge.scanInstanceCreate("id-1", "Scan", "target.com")
        self.mock_dbh.scanInstanceCreate.assert_called_once_with(
            "id-1", "Scan", "target.com"
        )
    
    def test_scanInstanceGet(self):
        self.mock_dbh.scanInstanceGet.return_value = [
            ("Test", "target.com", 100, 101, 102, "FINISHED")
        ]
        result = self.bridge.scanInstanceGet("id-1")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "Test")
    
    def test_scanInstanceList(self):
        self.mock_dbh.scanInstanceList.return_value = [
            ("id-1", "Scan", "target.com", 100, 101, 102, "FINISHED", 50)
        ]
        result = self.bridge.scanInstanceList()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "id-1")
    
    def test_scanLogEvent(self):
        self.bridge.scanLogEvent("id-1", "STATUS", "Started", "core")
        self.mock_dbh.scanLogEvent.assert_called_once_with(
            "id-1", "STATUS", "Started", "core"
        )
    
    def test_configSet(self):
        self.bridge.configSet({"key": "val"})
        self.mock_dbh.configSet.assert_called_once_with({"key": "val"})
    
    def test_eventTypes(self):
        self.mock_dbh.eventTypes.return_value = [
            ("IP Address", "IP_ADDRESS", 0, "ENTITY"),
        ]
        result = self.bridge.eventTypes()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], "IP_ADDRESS")


if __name__ == "__main__":
    unittest.main()
