"""Tests for the HTTP DataService client."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.data_service.base import DataServiceBackend, DataServiceConfig
from spiderfoot.data_service.http_client import HttpDataService


class TestHttpDataServiceConfig(unittest.TestCase):
    """Test HttpDataService initialization."""

    def test_default_config(self):
        ds = HttpDataService()
        assert ds._base_url == "http://localhost:8002"
        assert ds._timeout == 30.0
        assert ds._max_retries == 3

    def test_custom_config(self):
        config = DataServiceConfig(
            backend=DataServiceBackend.HTTP,
            api_url="https://data.example.com:9000/api/",
            api_key="test-key",
            timeout=10.0,
            max_retries=5,
        )
        ds = HttpDataService(config=config)
        assert ds._base_url == "https://data.example.com:9000/api"
        assert ds._api_key == "test-key"
        assert ds._timeout == 10.0

    def test_url_building(self):
        ds = HttpDataService(
            config=DataServiceConfig(api_url="http://host:8001/api")
        )
        assert ds._url("/scans") == "http://host:8001/api/scans"
        assert ds._url("scans") == "http://host:8001/api/scans"


class TestHttpDataServiceScans(unittest.TestCase):
    """Test scan CRUD operations via HTTP."""

    def setUp(self):
        self.ds = HttpDataService(
            config=DataServiceConfig(
                backend=DataServiceBackend.HTTP,
                api_url="http://localhost:8001/api",
            )
        )
        self.mock_session = MagicMock()
        self.ds._session = self.mock_session

    def _mock_response(self, json_data, status_code=200):
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.status_code = status_code
        resp.content = json.dumps(json_data).encode()
        resp.raise_for_status = MagicMock()
        return resp

    def test_scan_instance_create(self):
        self.mock_session.post.return_value = self._mock_response(
            {"scan_id": "abc123", "status": "created"}
        )
        result = self.ds.scan_instance_create("abc123", "Test Scan", "example.com")
        assert result is True
        self.mock_session.post.assert_called_once()

    def test_scan_instance_list(self):
        scans = [{"id": "s1", "name": "Scan 1"}, {"id": "s2", "name": "Scan 2"}]
        self.mock_session.get.return_value = self._mock_response({"scans": scans})
        result = self.ds.scan_instance_list()
        assert len(result) == 2
        assert result[0]["id"] == "s1"

    def test_scan_instance_get(self):
        scan = {"id": "s1", "name": "Scan 1", "status": "RUNNING"}
        self.mock_session.get.return_value = self._mock_response({"scan": scan})
        result = self.ds.scan_instance_get("s1")
        assert result["status"] == "RUNNING"

    def test_scan_instance_delete(self):
        resp = MagicMock()
        resp.content = b""
        resp.raise_for_status = MagicMock()
        self.mock_session.delete.return_value = resp
        result = self.ds.scan_instance_delete("s1")
        assert result is True

    def test_scan_status_set(self):
        self.mock_session.patch.return_value = self._mock_response({"status": "ok"})
        result = self.ds.scan_status_set("s1", "RUNNING", started=1000)
        assert result is True


class TestHttpDataServiceEvents(unittest.TestCase):
    """Test event operations."""

    def setUp(self):
        self.ds = HttpDataService(
            config=DataServiceConfig(
                backend=DataServiceBackend.HTTP,
                api_url="http://localhost:8001/api",
            )
        )
        self.mock_session = MagicMock()
        self.ds._session = self.mock_session

    def _mock_response(self, json_data):
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.raise_for_status = MagicMock()
        return resp

    def test_event_store(self):
        self.mock_session.post.return_value = self._mock_response({"stored": True})
        result = self.ds.event_store(
            scan_id="s1",
            event_hash="hash1",
            event_type="IP_ADDRESS",
            module="sfp_dns",
            data="1.2.3.4",
        )
        assert result is True

    def test_event_get_by_scan(self):
        events = [
            {"hash": "h1", "type": "IP_ADDRESS", "data": "1.2.3.4"},
            {"hash": "h2", "type": "EMAILADDR", "data": "x@y.com"},
        ]
        self.mock_session.get.return_value = self._mock_response({"events": events})
        result = self.ds.event_get_by_scan("s1")
        assert len(result) == 2

    def test_event_get_by_scan_with_filter(self):
        events = [{"hash": "h1", "type": "IP_ADDRESS", "data": "1.2.3.4"}]
        self.mock_session.get.return_value = self._mock_response({"events": events})
        result = self.ds.event_get_by_scan("s1", event_type="IP_ADDRESS", limit=10)
        call_args = self.mock_session.get.call_args
        assert call_args[1]["params"]["event_type"] == "IP_ADDRESS"
        assert call_args[1]["params"]["limit"] == 10

    def test_event_exists_true(self):
        self.mock_session.get.return_value = self._mock_response({"exists": True})
        assert self.ds.event_exists("s1", "IP_ADDRESS", "1.2.3.4") is True

    def test_event_exists_false(self):
        self.mock_session.get.return_value = self._mock_response({"exists": False})
        assert self.ds.event_exists("s1", "IP_ADDRESS", "1.2.3.4") is False


class TestHttpDataServiceErrorHandling(unittest.TestCase):
    """Test graceful error handling."""

    def setUp(self):
        self.ds = HttpDataService(
            config=DataServiceConfig(
                backend=DataServiceBackend.HTTP,
                api_url="http://localhost:8001/api",
            )
        )
        self.mock_session = MagicMock()
        self.ds._session = self.mock_session

    def test_scan_list_on_connection_error(self):
        import requests
        self.mock_session.get.side_effect = requests.ConnectionError("refused")
        result = self.ds.scan_instance_list()
        assert result == []

    def test_event_store_on_timeout(self):
        import requests
        self.mock_session.post.side_effect = requests.Timeout("timeout")
        result = self.ds.event_store("s1", "h1", "T", "m", "d")
        assert result is False

    def test_scan_get_on_404(self):
        import requests
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("404")
        self.mock_session.get.return_value = resp
        result = self.ds.scan_instance_get("nonexistent")
        assert result is None


class TestHttpDataServiceFactory(unittest.TestCase):
    """Test that factory creates HTTP backend correctly."""

    def test_factory_creates_http_service(self):
        from spiderfoot.data_service.factory import create_data_service

        config = DataServiceConfig(
            backend=DataServiceBackend.HTTP,
            api_url="http://data:8001/api",
        )
        ds = create_data_service(config)
        assert isinstance(ds, HttpDataService)
        assert ds._base_url == "http://data:8001/api"


if __name__ == "__main__":
    unittest.main()
