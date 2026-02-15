"""Tests for spiderfoot.openapi_spec."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from spiderfoot.openapi_spec import OpenAPIGenerator


class TestOpenAPIGenerator(unittest.TestCase):
    """Unit tests for OpenAPIGenerator."""

    def setUp(self):
        self.gen = OpenAPIGenerator()

    def test_generate_returns_dict(self):
        spec = self.gen.generate()
        self.assertIsInstance(spec, dict)

    def test_openapi_version(self):
        spec = self.gen.generate()
        self.assertEqual(spec["openapi"], "3.1.0")

    def test_info_section(self):
        spec = self.gen.generate()
        info = spec["info"]
        self.assertEqual(info["title"], "SpiderFoot API")
        self.assertIn("version", info)
        self.assertIn("license", info)
        self.assertEqual(info["license"]["name"], "MIT")

    def test_custom_title_and_version(self):
        gen = OpenAPIGenerator(title="Custom API", version="1.0.0",
                               description="Custom")
        spec = gen.generate()
        self.assertEqual(spec["info"]["title"], "Custom API")
        self.assertEqual(spec["info"]["version"], "1.0.0")
        self.assertEqual(spec["info"]["description"], "Custom")

    def test_servers_present(self):
        spec = self.gen.generate()
        self.assertIn("servers", spec)
        self.assertGreater(len(spec["servers"]), 0)

    def test_tags_present(self):
        spec = self.gen.generate()
        tags = spec["tags"]
        tag_names = [t["name"] for t in tags]
        self.assertIn("Scans", tag_names)
        self.assertIn("System", tag_names)

    def test_paths_present(self):
        spec = self.gen.generate()
        paths = spec["paths"]
        self.assertIn("/api/scans", paths)
        self.assertIn("/api/scans/{scan_id}", paths)
        self.assertIn("/health", paths)
        self.assertIn("/metrics", paths)

    def test_scan_crud_operations(self):
        spec = self.gen.generate()
        scans_path = spec["paths"]["/api/scans"]
        self.assertIn("get", scans_path)
        self.assertIn("post", scans_path)

        scan_detail = spec["paths"]["/api/scans/{scan_id}"]
        self.assertIn("get", scan_detail)
        self.assertIn("delete", scan_detail)

    def test_workspace_endpoints(self):
        spec = self.gen.generate()
        self.assertIn("/api/workspaces", spec["paths"])
        self.assertIn("/api/workspaces/{workspace_id}", spec["paths"])

    def test_config_endpoints(self):
        spec = self.gen.generate()
        self.assertIn("/api/config", spec["paths"])
        self.assertIn("/api/config/reload", spec["paths"])

    def test_correlation_endpoints(self):
        spec = self.gen.generate()
        self.assertIn("/api/correlation-rules", spec["paths"])
        self.assertIn("/api/correlations/analyze", spec["paths"])

    def test_visualization_endpoints(self):
        spec = self.gen.generate()
        self.assertIn("/api/visualization/graph/{scan_id}", spec["paths"])
        self.assertIn("/api/visualization/timeline/{scan_id}", spec["paths"])

    def test_gateway_endpoints(self):
        spec = self.gen.generate()
        self.assertIn("/gateway/route/{service}/{method}", spec["paths"])
        self.assertIn("/gateway/status", spec["paths"])

    def test_security_schemes(self):
        spec = self.gen.generate()
        schemes = spec["components"]["securitySchemes"]
        self.assertIn("ApiKeyAuth", schemes)
        self.assertIn("BearerAuth", schemes)
        self.assertIn("BasicAuth", schemes)

    def test_schemas(self):
        spec = self.gen.generate()
        schemas = spec["components"]["schemas"]
        self.assertIn("ScanRequest", schemas)
        self.assertIn("ScanSummary", schemas)
        self.assertIn("ScanEvent", schemas)
        self.assertIn("Workspace", schemas)
        self.assertIn("ModuleInfo", schemas)
        self.assertIn("HealthStatus", schemas)
        self.assertIn("Error", schemas)

    def test_parameters(self):
        spec = self.gen.generate()
        params = spec["components"]["parameters"]
        self.assertIn("ScanId", params)
        self.assertIn("WorkspaceId", params)

    def test_schema_required_fields(self):
        spec = self.gen.generate()
        scan_req = spec["components"]["schemas"]["ScanRequest"]
        self.assertIn("scanname", scan_req["required"])
        self.assertIn("scantarget", scan_req["required"])

    def test_all_paths_have_tags(self):
        spec = self.gen.generate()
        for path, methods in spec["paths"].items():
            for method, details in methods.items():
                self.assertIn("tags", details,
                              f"Missing tags for {method.upper()} {path}")

    def test_all_paths_have_operation_ids(self):
        spec = self.gen.generate()
        op_ids = set()
        for path, methods in spec["paths"].items():
            for method, details in methods.items():
                self.assertIn("operationId", details,
                              f"Missing operationId for {method.upper()} {path}")
                op_id = details["operationId"]
                self.assertNotIn(op_id, op_ids,
                                 f"Duplicate operationId: {op_id}")
                op_ids.add(op_id)

    def test_write_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = self.gen.write_json(path)
            self.assertTrue(result)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["openapi"], "3.1.0")
        finally:
            os.unlink(path)

    def test_write_yaml(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML not available")

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            result = self.gen.write_yaml(path)
            self.assertTrue(result)
            with open(path) as f:
                data = yaml.safe_load(f)
            self.assertEqual(data["openapi"], "3.1.0")
        finally:
            os.unlink(path)

    def test_spec_is_json_serializable(self):
        spec = self.gen.generate()
        serialized = json.dumps(spec)
        self.assertIsInstance(serialized, str)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized["openapi"], "3.1.0")

    def test_data_module_endpoints(self):
        spec = self.gen.generate()
        self.assertIn("/api/data/entity-types", spec["paths"])
        self.assertIn("/api/data/modules", spec["paths"])
        self.assertIn("/api/data/modules/{module_name}", spec["paths"])

    def test_scan_stop_rerun_clone(self):
        spec = self.gen.generate()
        self.assertIn("/api/scans/{scan_id}/stop", spec["paths"])
        self.assertIn("/api/scans/{scan_id}/rerun", spec["paths"])
        self.assertIn("/api/scans/{scan_id}/clone", spec["paths"])


if __name__ == "__main__":
    unittest.main()
