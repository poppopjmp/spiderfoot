"""Tests for spiderfoot.api.routers.export — scan export endpoints.

ExportService is DB-backed; these tests substitute a fake service (paired with
the real ExportFormat enum) so the router's format mapping, response headers
(content-type + attachment filename), the STIX/SARIF convenience endpoints, and
the service-unavailable (501) and failure (400) paths are exercised hermetically.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.export as export_mod
from spiderfoot.api.routers.export import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.reporting.export_service import ExportFormat


class _FakeExportService:
    def __init__(self, content=b'{"ok": true}', raises=None):
        self._content = content
        self._raises = raises
        self.config = None
        self.calls = []

    def export_scan(self, scan_id, fmt, dbh=None):
        self.calls.append((scan_id, fmt))
        if self._raises is not None:
            raise self._raises
        return self._content


def _client(monkeypatch, svc):
    monkeypatch.setattr(export_mod, "_get_export_service",
                        lambda: (svc, ExportFormat))
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestExportFormats:
    @pytest.mark.parametrize("fmt,ctype,ext", [
        ("json", "application/json", ".json"),
        ("csv", "text/csv", ".csv"),
        ("stix", "application/json", ".json"),  # stix is JSON-based
        ("sarif", "application/json", ".sarif"),
    ])
    def test_export_sets_content_type_and_filename(self, monkeypatch, fmt, ctype, ext):
        svc = _FakeExportService()
        client = _client(monkeypatch, svc)
        resp = client.get(f"/scans/scan-1/export", params={"format": fmt})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(ctype.split("/")[0])
        assert ext in resp.headers["content-disposition"]
        # The router mapped the query param to the right ExportFormat enum.
        assert svc.calls[0][1] == ExportFormat[fmt.upper()]

    def test_invalid_format_422(self, monkeypatch):
        client = _client(monkeypatch, _FakeExportService())
        assert client.get("/scans/s1/export",
                          params={"format": "xml"}).status_code == 422


class TestConvenienceEndpoints:
    def test_stix_endpoint(self, monkeypatch):
        svc = _FakeExportService()
        client = _client(monkeypatch, svc)
        assert client.get("/scans/s1/export/stix").status_code == 200
        assert svc.calls[0][1] == ExportFormat.STIX

    def test_sarif_endpoint(self, monkeypatch):
        svc = _FakeExportService()
        client = _client(monkeypatch, svc)
        assert client.get("/scans/s1/export/sarif").status_code == 200
        assert svc.calls[0][1] == ExportFormat.SARIF


class TestErrorPaths:
    def test_service_unavailable_501(self, monkeypatch):
        monkeypatch.setattr(export_mod, "_get_export_service",
                            lambda: (None, None))
        app = FastAPI()
        app.dependency_overrides[get_api_key] = lambda: "k"
        app.include_router(router)
        client = TestClient(app)
        assert client.get("/scans/s1/export").status_code == 501

    def test_value_error_becomes_400(self, monkeypatch):
        svc = _FakeExportService(raises=ValueError("no such scan"))
        client = _client(monkeypatch, svc)
        assert client.get("/scans/s1/export").status_code == 400

    def test_unexpected_error_becomes_500(self, monkeypatch):
        svc = _FakeExportService(raises=RuntimeError("boom"))
        client = _client(monkeypatch, svc)
        assert client.get("/scans/s1/export").status_code == 500
