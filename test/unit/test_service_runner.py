"""
Tests for the Service Runner (microservices entry point).
"""

import json
import os
import time
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch, MagicMock

from spiderfoot.service_runner import (
    _HealthStatus,
    _build_sf_config,
    _start_health_server,
    _SERVICE_MAP,
)


class TestHealthStatus(unittest.TestCase):
    """Test the shared health status object."""

    def test_default_state(self):
        h = _HealthStatus()
        d = h.to_dict()
        self.assertEqual(d["service"], "unknown")
        self.assertEqual(d["status"], "starting")
        self.assertGreater(d["uptime"], 0)

    def test_ready_state(self):
        h = _HealthStatus()
        h.ready = True
        h.service_name = "api"
        d = h.to_dict()
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["service"], "api")


class TestBuildSfConfig(unittest.TestCase):
    """Test env-to-config mapping."""

    def test_defaults(self):
        config = _build_sf_config()
        self.assertIn("_scheduler_max_scans", config)
        self.assertEqual(config["_scheduler_max_scans"], "3")

    @patch.dict(os.environ, {
        "SF_REDIS_URL": "redis://myhost:6379/1",
        "SF_VECTOR_ENDPOINT": "http://vector:8686",
    })
    def test_redis_and_vector(self):
        config = _build_sf_config()
        self.assertEqual(config["_eventbus_backend"], "redis")
        self.assertEqual(config["_eventbus_redis_url"], "redis://myhost:6379/1")
        self.assertEqual(config["_cache_backend"], "redis")
        self.assertEqual(config["_vector_enabled"], "1")
        self.assertEqual(config["_vector_endpoint"], "http://vector:8686")

    @patch.dict(os.environ, {
        "SF_POSTGRES_DSN": "postgresql://u:p@host/db",
    })
    def test_postgres(self):
        config = _build_sf_config()
        self.assertEqual(config["_dataservice_backend"], "http")


class TestServiceMap(unittest.TestCase):
    """Verify service map completeness."""

    def test_all_services_registered(self):
        self.assertIn("scanner", _SERVICE_MAP)
        self.assertIn("api", _SERVICE_MAP)
        self.assertIn("webui", _SERVICE_MAP)
        self.assertIn("all", _SERVICE_MAP)

    def test_services_are_callable(self):
        for name, func in _SERVICE_MAP.items():
            self.assertTrue(callable(func), f"{name} is not callable")


class TestHealthServer(unittest.TestCase):
    """Test the lightweight health HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.server = _start_health_server(19876)
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _get(self, path):
        conn = HTTPConnection("127.0.0.1", 19876, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        return resp.status, body

    def test_health_endpoint(self):
        status, body = self._get("/health")
        self.assertIn(status, (200, 503))
        data = json.loads(body)
        self.assertIn("service", data)
        self.assertIn("uptime", data)

    def test_healthz_endpoint(self):
        status, _ = self._get("/healthz")
        self.assertIn(status, (200, 503))

    def test_unknown_path(self):
        status, _ = self._get("/nonexistent")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
