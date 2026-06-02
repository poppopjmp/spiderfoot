"""Tests for spiderfoot.api.routers.ai_scan_config — AI scan recommendations."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from spiderfoot.api.routers.ai_scan_config import router
from spiderfoot.api.dependencies import get_api_key


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    app.include_router(router)
    return TestClient(app)


class TestMetadata:
    @pytest.mark.parametrize("path", [
        "/ai-config/presets",
        "/ai-config/target-types",
        "/ai-config/stealth-levels",
        "/ai-config/modules",
    ])
    def test_metadata_endpoints(self, client, path):
        assert client.get(path).status_code == 200


class TestRecommend:
    def test_recommend_returns_recommendation(self, client):
        resp = client.post("/ai-config/recommend",
                           json={"target": "example.com", "target_type": "domain"})
        assert resp.status_code == 200
        rec = resp.json()["recommendation"]
        assert rec["target"] == "example.com"
        assert "id" in rec

    def test_get_unknown_recommendation_404(self, client):
        assert client.get("/ai-config/recommend/nonexistent").status_code == 404
