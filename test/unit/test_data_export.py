"""Tests for spiderfoot.data_export module."""

from __future__ import annotations

import json
import unittest

from spiderfoot.data_export import (
    CsvExporter,
    ExportEvent,
    ExportOptions,
    ExportRegistry,
    JsonExporter,
    StixExporter,
    SummaryExporter,
)


def _sample_events() -> list:
    return [
        ExportEvent(event_type="IP_ADDRESS", data="1.2.3.4", module="sfp_dns", risk=50),
        ExportEvent(event_type="DOMAIN_NAME", data="example.com", module="sfp_dns", risk=10),
        ExportEvent(event_type="EMAILADDR", data="user@test.com", module="sfp_email", risk=30),
        ExportEvent(event_type="RAW_DATA", data="raw stuff", module="sfp_raw", risk=0),
    ]


class TestExportEvent(unittest.TestCase):
    def test_to_dict(self):
        e = ExportEvent(event_type="IP_ADDRESS", data="1.2.3.4", risk=50)
        d = e.to_dict()
        self.assertEqual(d["event_type"], "IP_ADDRESS")
        self.assertEqual(d["risk"], 50)


class TestJsonExporter(unittest.TestCase):
    def test_export(self):
        exp = JsonExporter()
        result = exp.export(_sample_events(), ExportOptions())
        data = json.loads(result)
        # RAW_DATA excluded by default (include_raw=False)
        self.assertEqual(data["event_count"], 3)

    def test_include_raw(self):
        exp = JsonExporter()
        result = exp.export(_sample_events(), ExportOptions(include_raw=True))
        data = json.loads(result)
        self.assertEqual(data["event_count"], 4)

    def test_min_risk(self):
        exp = JsonExporter()
        result = exp.export(_sample_events(), ExportOptions(min_risk=30, include_raw=True))
        data = json.loads(result)
        self.assertTrue(all(e["risk"] >= 30 for e in data["events"]))

    def test_max_results(self):
        exp = JsonExporter()
        result = exp.export(_sample_events(), ExportOptions(max_results=2, include_raw=True))
        data = json.loads(result)
        self.assertEqual(data["event_count"], 2)

    def test_event_type_filter(self):
        exp = JsonExporter()
        result = exp.export(_sample_events(), ExportOptions(event_types={"IP_ADDRESS"}))
        data = json.loads(result)
        self.assertEqual(data["event_count"], 1)

    def test_module_filter(self):
        exp = JsonExporter()
        result = exp.export(_sample_events(), ExportOptions(modules={"sfp_email"}))
        data = json.loads(result)
        self.assertEqual(data["event_count"], 1)

    def test_no_metadata(self):
        exp = JsonExporter()
        result = exp.export(_sample_events(), ExportOptions(include_metadata=False))
        data = json.loads(result)
        self.assertNotIn("metadata", data["events"][0])

    def test_format_info(self):
        exp = JsonExporter()
        self.assertEqual(exp.format_name, "JSON")
        self.assertEqual(exp.file_extension, ".json")
        self.assertEqual(exp.content_type, "application/json")


class TestCsvExporter(unittest.TestCase):
    def test_export(self):
        exp = CsvExporter()
        result = exp.export(_sample_events(), ExportOptions())
        lines = [l.rstrip("\r") for l in result.strip().split("\n")]
        self.assertEqual(lines[0], "event_type,data,module,risk,timestamp,metadata")
        # 3 data rows (RAW_DATA excluded)
        self.assertEqual(len(lines) - 1, 3)

    def test_no_metadata_column(self):
        exp = CsvExporter()
        result = exp.export(_sample_events(), ExportOptions(include_metadata=False))
        lines = result.strip().split("\n")
        self.assertNotIn("metadata", lines[0])

    def test_format_info(self):
        exp = CsvExporter()
        self.assertEqual(exp.format_name, "CSV")
        self.assertEqual(exp.file_extension, ".csv")


class TestStixExporter(unittest.TestCase):
    def test_export(self):
        exp = StixExporter()
        result = exp.export(_sample_events(), ExportOptions())
        data = json.loads(result)
        self.assertEqual(data["type"], "bundle")
        self.assertTrue(len(data["objects"]) > 0)

    def test_type_mapping(self):
        exp = StixExporter()
        result = exp.export(
            [ExportEvent(event_type="IP_ADDRESS", data="1.2.3.4")],
            ExportOptions(),
        )
        data = json.loads(result)
        self.assertEqual(data["objects"][0]["type"], "ipv4-addr")

    def test_unknown_type(self):
        exp = StixExporter()
        result = exp.export(
            [ExportEvent(event_type="CUSTOM_TYPE", data="x")],
            ExportOptions(),
        )
        data = json.loads(result)
        self.assertEqual(data["objects"][0]["type"], "x-spiderfoot-event")
        self.assertEqual(data["objects"][0]["x_event_type"], "CUSTOM_TYPE")

    def test_format_info(self):
        exp = StixExporter()
        self.assertEqual(exp.format_name, "STIX")


class TestSummaryExporter(unittest.TestCase):
    def test_export(self):
        exp = SummaryExporter()
        result = exp.export(_sample_events(), ExportOptions())
        self.assertIn("SpiderFoot Scan Summary", result)
        self.assertIn("Total Events:", result)
        self.assertIn("IP_ADDRESS", result)

    def test_risk_distribution(self):
        events = [
            ExportEvent(event_type="IP", data="x", risk=95),  # critical
            ExportEvent(event_type="IP", data="y", risk=75),  # high
            ExportEvent(event_type="IP", data="z", risk=5),   # info
        ]
        exp = SummaryExporter()
        result = exp.export(events, ExportOptions(include_raw=True))
        self.assertIn("CRITICAL: 1", result)
        self.assertIn("HIGH: 1", result)

    def test_format_info(self):
        exp = SummaryExporter()
        self.assertEqual(exp.format_name, "Summary")
        self.assertEqual(exp.file_extension, ".txt")


class TestExportRegistry(unittest.TestCase):
    def test_builtin_formats(self):
        reg = ExportRegistry()
        self.assertIn("json", reg.available_formats)
        self.assertIn("csv", reg.available_formats)
        self.assertIn("stix", reg.available_formats)
        self.assertIn("summary", reg.available_formats)

    def test_export_json(self):
        reg = ExportRegistry()
        result = reg.export("json", _sample_events())
        data = json.loads(result)
        self.assertIn("events", data)

    def test_export_unknown_format(self):
        reg = ExportRegistry()
        with self.assertRaises(ValueError):
            reg.export("xml", _sample_events())

    def test_unregister(self):
        reg = ExportRegistry()
        self.assertTrue(reg.unregister("json"))
        self.assertFalse(reg.unregister("nonexistent"))

    def test_get(self):
        reg = ExportRegistry()
        self.assertIsNotNone(reg.get("json"))
        self.assertIsNone(reg.get("nonexistent"))

    def test_to_dict(self):
        reg = ExportRegistry()
        d = reg.to_dict()
        self.assertIn("formats", d)
        self.assertIn("json", d["formats"])


if __name__ == "__main__":
    unittest.main()
