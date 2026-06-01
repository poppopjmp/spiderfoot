"""Tests for spiderfoot.api.routers.data.

Focus areas:
  * Regression for the module-dependencies endpoint, which previously raised an
    uncaught NameError (it called a never-defined ``get_data_service`` in its
    fallback) whenever module metadata failed to load — turning a handled
    failure into a crash. It must now degrade to an empty-but-valid graph.
  * The literal /data/modules/* sub-paths (stats, dependencies, status) must not
    be shadowed by the parameterized /data/modules/{module_name} route.

Endpoints that require a live database/config are driven with ``get_app_config``
patched so the tests stay hermetic.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.data import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestModuleDependenciesRegression:
    def test_degrades_gracefully_when_config_unavailable(self, client, monkeypatch):
        # Simulate the metadata-load failure that previously triggered the
        # NameError crash via the dead get_data_service() fallback.
        def boom():
            raise RuntimeError("DB unavailable")

        monkeypatch.setattr(
            "spiderfoot.api.routers.data.get_app_config", boom)
        resp = client.get("/data/modules/dependencies")
        assert resp.status_code == 200  # no crash, graceful degradation
        body = resp.json()
        assert set(body) >= {"nodes", "edges", "event_types", "summary"}
        assert isinstance(body["nodes"], dict)
        assert isinstance(body["summary"]["total_modules"], int)

    def test_returns_graph_structure(self, client):
        # Even with the environment's default config, the endpoint must return
        # a well-formed graph (never raise).
        resp = client.get("/data/modules/dependencies")
        assert resp.status_code == 200
        assert "summary" in resp.json()


class TestLiteralSubPathsNotShadowed:
    """These must resolve to their own handlers, not get_module_details."""

    def test_dependencies_not_shadowed(self, client):
        resp = client.get("/data/modules/dependencies")
        # A shadowed route would hit get_module_details -> 404 "Module not found".
        assert resp.status_code == 200
        assert resp.json().get("nodes") is not None

    def test_stats_not_shadowed(self, client):
        resp = client.get("/data/modules/stats")
        assert resp.status_code == 200
