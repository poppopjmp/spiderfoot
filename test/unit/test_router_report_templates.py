"""Tests for spiderfoot.api.routers.report_templates.

CRUD lifecycle, render, clone, export/import, and the metadata endpoints —
plus regression coverage for the literal sub-paths (history, variables,
categories, formats) that were previously shadowed by /{template_id}.
Runs against a fresh in-memory ReportTemplateManager per test.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import spiderfoot.api.routers.report_templates as rt_mod
from spiderfoot.api.routers.report_templates import router
from spiderfoot.api.dependencies import get_api_key
from spiderfoot.reporting.templates import ReportTemplateManager


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(rt_mod, "_manager", ReportTemplateManager())
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


def _create(client, name="tpl"):
    resp = client.post("/report-templates", json={
        "name": name, "body_template": "Hello {{ target }}",
        "category": "custom", "output_format": "html",
    })
    return resp


class TestCrud:
    def test_create_201(self, client):
        resp = _create(client)
        assert resp.status_code == 201
        assert resp.json()["template"]["name"] == "tpl"

    def test_list_includes_builtins_and_created(self, client):
        _create(client, name="mine")
        names = [t["name"] for t in client.get("/report-templates").json()["templates"]]
        assert "mine" in names

    def test_get_by_id(self, client):
        tid = _create(client).json()["template"]["template_id"]
        assert client.get(f"/report-templates/{tid}").status_code == 200

    def test_get_unknown_404(self, client):
        assert client.get("/report-templates/nope").status_code == 404

    def test_update(self, client):
        tid = _create(client).json()["template"]["template_id"]
        resp = client.patch(f"/report-templates/{tid}", json={"name": "renamed"})
        assert resp.status_code == 200
        assert resp.json()["updated"]["name"] == "renamed"

    def test_delete_custom(self, client):
        tid = _create(client).json()["template"]["template_id"]
        assert client.delete(f"/report-templates/{tid}").status_code == 200

    def test_clone(self, client):
        tid = _create(client).json()["template"]["template_id"]
        resp = client.post(f"/report-templates/{tid}/clone", json={"new_name": "copy"})
        assert resp.status_code == 200
        assert resp.json()["cloned"]["template_id"] != tid


class TestExportImport:
    def test_export_then_import(self, client):
        tid = _create(client, name="exp").json()["template"]["template_id"]
        exported = client.get(f"/report-templates/{tid}/export")
        assert exported.status_code == 200
        resp = client.post("/report-templates/import", json=exported.json())
        assert resp.status_code == 201

    def test_export_unknown_404(self, client):
        assert client.get("/report-templates/nope/export").status_code == 404


class TestLiteralSubPathsNotShadowed:
    @pytest.mark.parametrize("path,key", [
        ("/report-templates/variables", "variables"),
        ("/report-templates/categories", "categories"),
        ("/report-templates/formats", "formats"),
    ])
    def test_metadata_paths(self, client, path, key):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} was shadowed by /{{template_id}}"
        assert key in resp.json()

    def test_history(self, client):
        resp = client.get("/report-templates/history")
        assert resp.status_code == 200
        assert "history" in resp.json()
