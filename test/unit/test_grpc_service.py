"""
Tests for the gRPC/HTTP service layer.
"""
from __future__ import annotations

import json
import time
import unittest
from http.client import HTTPConnection
from unittest.mock import MagicMock, patch

from spiderfoot.grpc_service import (
    ServiceClient,
    ServiceServer,
    ServiceCallError,
    ServiceDirectory,
)


class TestServiceServer(unittest.TestCase):
    """Test the RPC server."""

    @classmethod
    def setUpClass(cls):
        cls.server = ServiceServer("test", port=19877)
        cls.server.register("Echo", lambda payload: {"echo": payload})
        cls.server.register("Add", lambda p: {"sum": p.get("a", 0) + p.get("b", 0)})
        cls.server.register("HealthCheck", lambda p: {"status": "ok"})
        cls.server.start(background=True)
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _post(self, method, payload=None):
        conn = HTTPConnection("127.0.0.1", 19877, timeout=5)
        body = json.dumps(payload or {}).encode()
        conn.request("POST", f"/rpc/test/{method}", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        return resp.status, data

    def test_echo(self):
        status, data = self._post("Echo", {"message": "hello"})
        self.assertEqual(status, 200)
        self.assertEqual(data["echo"]["message"], "hello")

    def test_add(self):
        status, data = self._post("Add", {"a": 3, "b": 7})
        self.assertEqual(status, 200)
        self.assertEqual(data["sum"], 10)

    def test_unknown_method(self):
        status, _ = self._post("NonExistent")
        self.assertEqual(status, 404)

    def test_health_check(self):
        status, data = self._post("HealthCheck")
        self.assertEqual(data["status"], "ok")


class TestServiceClient(unittest.TestCase):
    """Test the RPC client against the test server."""

    @classmethod
    def setUpClass(cls):
        cls.server = ServiceServer("client_test", port=19878)
        cls.server.register("Ping", lambda p: {"pong": True})
        cls.server.register("Greet", lambda p: {"msg": f"Hello {p.get('name', 'World')}"})
        cls.server.start(background=True)
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_call(self):
        client = ServiceClient("client_test", "127.0.0.1:19878", use_grpc=False)
        result = client.call("Ping")
        self.assertTrue(result["pong"])

    def test_call_with_payload(self):
        client = ServiceClient("client_test", "127.0.0.1:19878", use_grpc=False)
        result = client.call("Greet", {"name": "SpiderFoot"})
        self.assertEqual(result["msg"], "Hello SpiderFoot")

    def test_health_check(self):
        client = ServiceClient("client_test", "127.0.0.1:19878", use_grpc=False)
        # HealthCheck not registered, so it should return error
        result = client.health_check()
        self.assertIn("status", result)

    def test_unreachable_service(self):
        client = ServiceClient("bad", "127.0.0.1:19999", use_grpc=False)
        with self.assertRaises(ServiceCallError):
            client.call("Ping", timeout=1.0)


class TestServiceDirectory(unittest.TestCase):
    """Test service discovery."""

    def test_default_endpoints(self):
        ep = ServiceDirectory.get_endpoint("scanner")
        self.assertEqual(ep, "localhost:5003")

    @patch.dict("os.environ", {"SF_SCANNER_ENDPOINT": "scanner.prod:5003"})
    def test_env_override(self):
        ep = ServiceDirectory.get_endpoint("scanner")
        self.assertEqual(ep, "scanner.prod:5003")

    def test_unknown_service(self):
        ep = ServiceDirectory.get_endpoint("unknown_svc")
        self.assertEqual(ep, "")

    def test_get_client(self):
        client = ServiceDirectory.get_client("scanner")
        self.assertIsInstance(client, ServiceClient)

    def test_get_client_unknown(self):
        with self.assertRaises(ServiceCallError):
            ServiceDirectory.get_client("nonexistent_service")


if __name__ == "__main__":
    unittest.main()
