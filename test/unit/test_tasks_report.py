"""Tests for spiderfoot.tasks.report — report generation + MinIO storage helper.

The MinIO client, DB handle, and HTML renderer are mocked so the storage
helper, branding defaults, and the HTML report task run without external
services. _store_report is also used by the export task, so its upload and
fallback behaviour are covered here.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import spiderfoot.tasks.report as report


class TestStoreReport:
    def test_uploads_and_returns_url(self, monkeypatch):
        monkeypatch.setenv("SF_MINIO_ENDPOINT", "minio:9000")
        monkeypatch.setenv("SF_MINIO_SECURE", "false")
        fake_client = MagicMock()
        fake_minio_module = MagicMock()
        fake_minio_module.Minio.return_value = fake_client
        with patch.dict("sys.modules", {"minio": fake_minio_module}):
            url = report._store_report(b"data", "reports/s1/r.pdf", {})
        assert url == "http://minio:9000/sf-reports/reports/s1/r.pdf"
        fake_client.put_object.assert_called_once()

    def test_secure_url_scheme(self, monkeypatch):
        monkeypatch.setenv("SF_MINIO_ENDPOINT", "minio:9000")
        monkeypatch.setenv("SF_MINIO_SECURE", "true")
        fake_minio_module = MagicMock()
        with patch.dict("sys.modules", {"minio": fake_minio_module}):
            url = report._store_report(b"d", "k", {})
        assert url.startswith("https://")

    def test_failure_falls_back_to_minio_uri(self, monkeypatch):
        fake_minio_module = MagicMock()
        fake_minio_module.Minio.side_effect = RuntimeError("minio down")
        with patch.dict("sys.modules", {"minio": fake_minio_module}):
            url = report._store_report(b"d", "reports/x.pdf", {})
        assert url == "minio://reports/x.pdf"


class TestDefaultBranding:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("SF_REPORT_COMPANY", raising=False)
        branding = report._default_branding()
        assert branding["company_name"] == "SpiderFoot"
        assert "primary_color" in branding

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("SF_REPORT_COMPANY", "Acme Corp")
        assert report._default_branding()["company_name"] == "Acme Corp"


class TestGenerateHtmlReport:
    def test_completed(self, monkeypatch):
        dbh = MagicMock()
        dbh.scanInstanceGet.return_value = ["s1", "My Scan", "example.com"]
        dbh.scanResultEvent.return_value = []
        dbh.scanResultSummary.return_value = []
        fake_db_module = MagicMock()
        fake_db_module.SpiderFootDb.return_value = dbh

        renderer = MagicMock()
        renderer.render_html.return_value = "<html>report</html>"
        fake_pdf_module = MagicMock()
        fake_pdf_module.PDFRenderer.return_value = renderer

        with patch.dict("sys.modules", {
            "spiderfoot.db": fake_db_module,
            "spiderfoot.reporting.pdf_renderer": fake_pdf_module,
        }), patch.object(report, "_store_report",
                         return_value="http://minio/sf-reports/r.html"):
            result = report.generate_html_report.run("s1", {})

        assert result["status"] == "completed"
        assert result["storage_url"].endswith("r.html")
        assert result["file_size_bytes"] == len("<html>report</html>")
        renderer.render_html.assert_called_once()
