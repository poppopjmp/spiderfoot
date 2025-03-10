import unittest
from fastapi.testclient import TestClient
from sfapi import app, authenticate

client = TestClient(app)

class TestSfapi(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_authentication_success(self):
        response = self.client.get("/", auth=("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Welcome to SpiderFoot API"})

    def test_authentication_failure(self):
        response = self.client.get("/", auth=("invalid", "invalid"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Unauthorized"})

    def test_export_scan_results_csv(self):
        response = self.client.get("/export_scan_results/scan_id/csv", auth=("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv")

    def test_export_scan_results_json(self):
        response = self.client.get("/export_scan_results/scan_id/json", auth=("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")

    def test_custom_http_exception_handler(self):
        response = self.client.get("/nonexistent_endpoint", auth=("admin", "password"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"message": "Not Found"})

    def test_custom_exception_handler(self):
        with self.assertRaises(Exception):
            response = self.client.get("/trigger_exception", auth=("admin", "password"))
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json(), {"message": "An unexpected error occurred."})

    def test_fetch_scan_results(self):
        response = self.client.get("/scan_results/scan_id", auth=("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")

    def test_start_scan(self):
        response = self.client.post("/start_scan", json={"target": "example.com", "modules": ["module1", "module2"]}, auth=("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("scan_id", response.json())

    def test_stop_scan(self):
        response = self.client.post("/stop_scan/scan_id", auth=("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Scan stopped successfully"})

    def test_query_scans(self):
        response = self.client.get("/active_scans", auth=("admin", "password"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")
