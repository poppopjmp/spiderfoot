"""Tests for spiderfoot.tasks.export — the export_scan_data Celery task.

ExportService and the MinIO _store_report helper are mocked so the task body
runs without external services. The bound task's update_state is patched out
(no live task context when invoked synchronously).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import spiderfoot.tasks.export as exp


def _run(scan_id="scan-1", fmt="json", content=b'{"x": 1}', filename="scan-1.json"):
    fake_svc = MagicMock()
    fake_svc.export_scan.return_value = (content, filename)
    with patch("spiderfoot.reporting.export_service.ExportService",
               return_value=fake_svc), \
            patch("spiderfoot.tasks.report._store_report",
                  return_value=f"minio://exports/{scan_id}/{filename}") as store, \
            patch.object(exp.export_scan_data, "update_state"):
        result = exp.export_scan_data.run(scan_id, fmt, {})
    return result, fake_svc, store


class TestExportScanData:
    def test_completed_result_shape(self):
        result, _, _ = _run()
        assert result["status"] == "completed"
        assert result["scan_id"] == "scan-1"
        assert result["format"] == "json"
        assert result["filename"] == "scan-1.json"
        assert result["file_size_bytes"] == len(b'{"x": 1}')
        assert result["storage_url"].startswith("minio://")

    def test_delegates_to_export_service(self):
        _, svc, _ = _run(fmt="csv")
        svc.export_scan.assert_called_once()
        # Format is passed through to the service.
        assert svc.export_scan.call_args.kwargs["format"] == "csv"

    def test_stores_under_exports_prefix(self):
        _, _, store = _run(scan_id="abc", filename="abc.json")
        report_key = store.call_args.args[1]
        assert report_key == "exports/abc/abc.json"

    def test_content_type_for_csv(self):
        _, _, store = _run(fmt="csv", filename="x.csv")
        assert store.call_args.kwargs["content_type"] == "text/csv"
