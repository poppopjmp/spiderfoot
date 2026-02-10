"""Unit tests for spiderfoot.export_service."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from spiderfoot.export_service import (
    ExportConfig,
    ExportFormat,
    ExportService,
)


SAMPLE_EVENTS = [
    {
        "hash": "abc123",
        "type": "IP_ADDRESS",
        "data": "192.168.1.1",
        "module": "sfp_dnsresolve",
        "source_event": "ROOT",
        "confidence": 100,
        "visibility": 100,
        "risk": 0,
    },
    {
        "hash": "def456",
        "type": "DOMAIN_NAME",
        "data": "example.com",
        "module": "sfp_dnsresolve",
        "source_event": "abc123",
        "confidence": 100,
        "visibility": 100,
        "risk": 0,
    },
    {
        "hash": "ghi789",
        "type": "VULNERABILITY_CVE_CRITICAL",
        "data": "CVE-2024-1234",
        "module": "sfp_shodan",
        "source_event": "abc123",
        "confidence": 90,
        "visibility": 100,
        "risk": 100,
    },
    {
        "hash": "jkl012",
        "type": "EMAILADDR",
        "data": "admin@example.com",
        "module": "sfp_emailformat",
        "source_event": "def456",
        "confidence": 80,
        "visibility": 100,
        "risk": 0,
    },
]


class TestExportConfig(unittest.TestCase):

    def test_defaults(self):
        cfg = ExportConfig()
        self.assertTrue(cfg.include_raw_data)
        self.assertTrue(cfg.include_correlations)
        self.assertEqual(cfg.max_events, 0)

    def test_from_config(self):
        cfg = ExportConfig.from_config({
            "_export_max_events": "100",
            "_export_pretty": False,
        })
        self.assertEqual(cfg.max_events, 100)
        self.assertFalse(cfg.pretty_print)


class TestExportJSON(unittest.TestCase):

    def setUp(self):
        self.svc = ExportService()

    def test_json_structure(self):
        result = self.svc._to_json(
            {"scan_id": "test-1"}, SAMPLE_EVENTS)
        data = json.loads(result)
        self.assertIn("meta", data)
        self.assertIn("scan", data)
        self.assertIn("events", data)
        self.assertEqual(data["event_count"], 4)

    def test_json_format_version(self):
        result = self.svc._to_json({}, [])
        data = json.loads(result)
        self.assertEqual(data["meta"]["format"], "spiderfoot-json")


class TestExportCSV(unittest.TestCase):

    def setUp(self):
        self.svc = ExportService()

    def test_csv_header(self):
        result = self.svc._to_csv({}, SAMPLE_EVENTS)
        lines = result.strip().split("\n")
        self.assertIn("type", lines[0])
        self.assertIn("data", lines[0])

    def test_csv_data_rows(self):
        result = self.svc._to_csv({}, SAMPLE_EVENTS)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 5)  # header + 4 events

    def test_csv_empty(self):
        result = self.svc._to_csv({}, [])
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 1)  # header only


class TestExportSTIX(unittest.TestCase):

    def setUp(self):
        self.svc = ExportService()

    def test_stix_bundle_structure(self):
        result = self.svc._to_stix(
            {"scan_id": "test-1"}, SAMPLE_EVENTS)
        data = json.loads(result)
        self.assertEqual(data["type"], "bundle")
        self.assertIn("objects", data)
        self.assertGreater(len(data["objects"]), 0)

    def test_stix_identity(self):
        result = self.svc._to_stix({}, SAMPLE_EVENTS)
        data = json.loads(result)
        identities = [o for o in data["objects"]
                       if o["type"] == "identity"]
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0]["name"], "SpiderFoot")

    def test_stix_ip_mapping(self):
        result = self.svc._to_stix({}, SAMPLE_EVENTS)
        data = json.loads(result)
        ip_objs = [o for o in data["objects"]
                    if o.get("type") == "ipv4-addr"]
        self.assertEqual(len(ip_objs), 1)
        self.assertEqual(ip_objs[0]["value"], "192.168.1.1")

    def test_stix_vulnerability_mapping(self):
        result = self.svc._to_stix({}, SAMPLE_EVENTS)
        data = json.loads(result)
        vulns = [o for o in data["objects"]
                  if o.get("type") == "vulnerability"]
        self.assertEqual(len(vulns), 1)
        self.assertEqual(vulns[0]["name"], "CVE-2024-1234")


class TestExportSARIF(unittest.TestCase):

    def setUp(self):
        self.svc = ExportService()

    def test_sarif_structure(self):
        result = self.svc._to_sarif(
            {"scan_id": "test-1"}, SAMPLE_EVENTS)
        data = json.loads(result)
        self.assertEqual(data["version"], "2.1.0")
        self.assertIn("runs", data)
        self.assertEqual(len(data["runs"]), 1)

    def test_sarif_tool_info(self):
        result = self.svc._to_sarif({}, [])
        data = json.loads(result)
        tool = data["runs"][0]["tool"]["driver"]
        self.assertEqual(tool["name"], "SpiderFoot")

    def test_sarif_vuln_results(self):
        result = self.svc._to_sarif({}, SAMPLE_EVENTS)
        data = json.loads(result)
        results = data["runs"][0]["results"]
        # Only vulnerability events should be in SARIF
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["ruleId"],
                         "VULNERABILITY_CVE_CRITICAL")
        self.assertEqual(results[0]["level"], "error")


class TestExportToFile(unittest.TestCase):

    def test_export_json_file(self):
        svc = ExportService()
        svc._get_events = lambda sid, dbh: SAMPLE_EVENTS
        svc._get_scan_info = lambda sid, dbh: {"scan_id": sid}

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False
        ) as f:
            path = f.name

        try:
            svc.export_to_file("test", ExportFormat.JSON, path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["event_count"], 4)
        finally:
            os.unlink(path)


class TestNormalizeEvents(unittest.TestCase):

    def test_dict_input(self):
        svc = ExportService()
        result = svc._normalize_events([{"type": "IP_ADDRESS"}])
        self.assertEqual(len(result), 1)

    def test_tuple_input(self):
        svc = ExportService()
        result = svc._normalize_events([
            ("hash1", "IP_ADDRESS", "1.2.3.4", "mod", "src", 100, 100, 0),
        ])
        self.assertEqual(result[0]["type"], "IP_ADDRESS")
        self.assertEqual(result[0]["data"], "1.2.3.4")

    def test_type_filter(self):
        svc = ExportService(ExportConfig(event_types=["IP_ADDRESS"]))
        result = svc._normalize_events(SAMPLE_EVENTS)
        self.assertEqual(len(result), 1)

    def test_max_events(self):
        svc = ExportService(ExportConfig(max_events=2))
        result = svc._normalize_events(SAMPLE_EVENTS)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
