"""Integration tests for wired modules — Steps 36-55.

Validates that previously disconnected modules now have production
callers and function correctly through their integration points:

1. stealth_integration.py → core.py → scan task pipeline
2. frontend_data.py → API router → FastAPI endpoints
3. request_orchestration.py + adaptive_stealth.py → stealth context
4. CLI → consolidated Go binary (cli/)
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════
# 1. Stealth Integration Pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestStealthIntegrationPipeline(unittest.TestCase):
    """Full stealth pipeline: context → middleware → fetchUrl."""

    def test_context_creation_all_levels(self):
        """All stealth levels create valid contexts."""
        from spiderfoot.recon.stealth_integration import create_stealth_context

        for level in ("low", "medium", "high", "paranoid"):
            ctx = create_stealth_context(stealth_level=level)
            self.assertTrue(ctx.is_active, f"Level {level} should be active")
            self.assertIsNotNone(ctx.engine)
            self.assertIsNotNone(ctx.throttler)

    def test_adaptive_stealth_wired_for_medium_plus(self):
        """Adaptive stealth is wired for medium, high, paranoid."""
        from spiderfoot.recon.stealth_integration import create_stealth_context

        low = create_stealth_context(stealth_level="low")
        self.assertIsNone(low.adaptive_manager)

        for level in ("medium", "high", "paranoid"):
            ctx = create_stealth_context(stealth_level=level)
            self.assertIsNotNone(
                ctx.adaptive_manager,
                f"Level {level} should have adaptive manager",
            )

    def test_orchestrator_wired_for_high_plus(self):
        """Request orchestrator is wired for high and paranoid."""
        from spiderfoot.recon.stealth_integration import create_stealth_context

        for level in ("low", "medium"):
            ctx = create_stealth_context(stealth_level=level)
            self.assertIsNone(ctx.orchestrator)

        for level in ("high", "paranoid"):
            ctx = create_stealth_context(stealth_level=level)
            self.assertIsNotNone(
                ctx.orchestrator,
                f"Level {level} should have orchestrator",
            )

    def test_context_stats_include_adaptive(self):
        """get_stats() includes adaptive stealth stats when available."""
        from spiderfoot.recon.stealth_integration import create_stealth_context

        ctx = create_stealth_context(stealth_level="high")
        stats = ctx.get_stats()

        self.assertIn("adaptive_stealth", stats)
        self.assertIn("orchestrator", stats)
        self.assertEqual(stats["stealth_level"], "high")

    def test_core_fetchurl_creates_full_middleware(self):
        """SpiderFoot.fetchUrl() creates StealthScanContext + middleware."""
        from spiderfoot.sflib.core import SpiderFoot

        sf = SpiderFoot.__new__(SpiderFoot)
        sf.opts = {"_stealth_level": "medium"}

        with patch("spiderfoot.sflib.network.getSession") as mock_gs:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.reason = "OK"
            mock_resp.content = b""
            mock_resp.headers = {}
            mock_resp.url = "https://example.com"
            mock_gs.return_value.get.return_value = mock_resp

            sf.fetchUrl("https://example.com")

        ctx = sf.stealth_context
        self.assertIsNotNone(ctx)
        self.assertIsNotNone(ctx.adaptive_manager)  # medium+ gets adaptive

    def test_scan_context_registry_lifecycle(self):
        """Register → get → unregister lifecycle works."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            register_scan_context,
            get_scan_context,
            unregister_scan_context,
        )

        ctx = create_stealth_context(stealth_level="low")
        sid = "integration-test-001"

        register_scan_context(sid, ctx)
        self.assertIs(get_scan_context(sid), ctx)
        self.assertTrue(ctx.is_active)

        unregister_scan_context(sid)
        self.assertIsNone(get_scan_context(sid))
        self.assertFalse(ctx.is_active)  # deactivated by unregister

    def test_middleware_passes_original_fetch(self):
        """StealthFetchMiddleware delegates to _original_fetch."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            StealthFetchMiddleware,
        )

        ctx = create_stealth_context(stealth_level="low")
        mw = StealthFetchMiddleware(ctx)

        mock_fetch = MagicMock(return_value={
            "code": "200",
            "status": "OK",
            "content": "test",
            "headers": {},
            "realurl": "https://example.com",
        })

        result = mw.fetch("https://example.com", _original_fetch=mock_fetch)
        mock_fetch.assert_called_once()
        self.assertEqual(result["code"], "200")


# ═══════════════════════════════════════════════════════════════════════
# 2. Frontend Data API Router
# ═══════════════════════════════════════════════════════════════════════


class TestFrontendDataRouter(unittest.TestCase):
    """Tests for the frontend_data API router."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from spiderfoot.api.routers.frontend_data import router
        from fastapi import FastAPI

        app = FastAPI()
        # Remove auth dependencies for testing
        router.dependencies = []
        app.include_router(router, prefix="/api")
        cls.client = TestClient(app)

    def test_module_health_endpoint(self):
        """POST /api/frontend/module-health returns aggregated data."""
        payload = {
            "metrics": [
                {
                    "module_name": "sfp_dns",
                    "events_processed": 100,
                    "events_produced": 50,
                    "error_count": 2,
                    "total_duration": 5.0,
                    "status": "running",
                },
                {
                    "module_name": "sfp_whois",
                    "events_processed": 30,
                    "events_produced": 15,
                    "error_count": 0,
                    "total_duration": 2.0,
                    "status": "idle",
                },
            ]
        }
        resp = self.client.post("/api/frontend/module-health", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_modules"], 2)
        self.assertEqual(data["healthy"], 1)  # sfp_whois has 0 errors
        self.assertEqual(data["failing"], 1)  # sfp_dns has errors

    def test_timeline_endpoint(self):
        """POST /api/frontend/timeline returns bucketed events."""
        import time
        now = time.time()
        payload = {
            "events": [
                {"timestamp": now, "event_type": "IP_ADDRESS", "data": "1.2.3.4"},
                {"timestamp": now + 60, "event_type": "DOMAIN_NAME", "data": "ex.com"},
            ],
            "bucket_seconds": 3600,
            "page": 1,
            "page_size": 50,
        }
        resp = self.client.post("/api/frontend/timeline", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["events_ingested"], 2)
        self.assertIn("buckets", data)
        self.assertIn("events", data)

    def test_filter_endpoint(self):
        """POST /api/frontend/results/filter applies multi-dimensional filters."""
        payload = {
            "results": [
                {"event_type": "IP_ADDRESS", "data": "1.2.3.4", "module": "sfp_dns"},
                {"event_type": "DOMAIN_NAME", "data": "example.com", "module": "sfp_whois"},
                {"event_type": "IP_ADDRESS", "data": "5.6.7.8", "module": "sfp_dns"},
            ],
            "event_types": ["IP_ADDRESS"],
            "page": 1,
            "page_size": 25,
        }
        resp = self.client.post("/api/frontend/results/filter", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Should only return IP_ADDRESS events
        self.assertEqual(data["results"]["total"], 2)
        self.assertIn("facets", data)

    def test_threat_map_endpoint(self):
        """POST /api/frontend/threat-map clusters geographic data."""
        payload = {
            "points": [
                {"lat": 37.7749, "lng": -122.4194, "label": "SF", "risk_level": "high"},
                {"lat": 37.7750, "lng": -122.4195, "label": "SF2", "risk_level": "medium"},
                {"lat": 51.5074, "lng": -0.1278, "label": "London", "risk_level": "low"},
            ],
            "precision": 2,
        }
        resp = self.client.post("/api/frontend/threat-map", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_points"], 3)
        self.assertIn("clusters", data)
        self.assertIn("by_region", data)
        self.assertIn("risk_summary", data)

    def test_scan_diff_endpoint(self):
        """POST /api/frontend/scan-diff formats diff data."""
        payload = {
            "added": [{"event_type": "IP_ADDRESS", "data": "1.2.3.4"}],
            "removed": [{"event_type": "DOMAIN_NAME", "data": "old.com"}],
            "changed": [],
            "unchanged_count": 42,
        }
        resp = self.client.post("/api/frontend/scan-diff", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["stats"]["added"], 1)
        self.assertEqual(data["stats"]["removed"], 1)
        self.assertEqual(data["stats"]["unchanged"], 42)

    def test_facets_endpoint(self):
        """GET /api/frontend/facets returns empty facet structure."""
        resp = self.client.get("/api/frontend/facets")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 0)


# ═══════════════════════════════════════════════════════════════════════
# 3. Adaptive Stealth + Request Orchestration
# ═══════════════════════════════════════════════════════════════════════


class TestAdaptiveStealthWiring(unittest.TestCase):
    """Tests that adaptive_stealth.py is wired and functional."""

    def test_target_stealth_manager_analyze(self):
        """TargetStealthManager.analyze_response works end-to-end."""
        from spiderfoot.recon.adaptive_stealth import TargetStealthManager

        mgr = TargetStealthManager()
        # Simulate a normal response
        event = mgr.analyze_response(
            target="example.com",
            status_code=200,
            headers={"Server": "nginx"},
            body="<html>Hello</html>",
        )
        self.assertIsNone(event)  # No detection

        # Simulate a Cloudflare block
        event = mgr.analyze_response(
            target="blocked.com",
            status_code=403,
            headers={"Server": "cloudflare"},
            body="Attention Required! | Cloudflare",
        )
        self.assertIsNotNone(event)

    def test_delay_multiplier_increases_on_detection(self):
        """Delay multiplier increases after detection events."""
        from spiderfoot.recon.adaptive_stealth import TargetStealthManager

        mgr = TargetStealthManager()

        # Normal delay
        before = mgr.get_delay_multiplier("target.com")

        # Trigger detection
        mgr.analyze_response(
            target="target.com",
            status_code=429,
            headers={},
            body="Rate limited",
        )

        after = mgr.get_delay_multiplier("target.com")
        self.assertGreaterEqual(after, before)


class TestRequestOrchestrationWiring(unittest.TestCase):
    """Tests that request_orchestration.py is wired and functional."""

    def test_orchestrator_enqueue_and_next(self):
        """RequestOrchestrator can enqueue and dequeue requests."""
        from spiderfoot.recon.request_orchestration import RequestOrchestrator

        orch = RequestOrchestrator(max_concurrent=2)
        rid = orch.enqueue("https://example.com/page1", priority=1)
        self.assertIsNotNone(rid)

        req, delay = orch.next_request()
        self.assertIsNotNone(req)
        self.assertGreaterEqual(delay, 0)
        self.assertEqual(req.url, "https://example.com/page1")

    def test_timing_profiles_available(self):
        """All expected timing profiles are available."""
        from spiderfoot.recon.request_orchestration import get_timing_profile

        for name in ("fast", "browsing", "research", "cautious", "paranoid"):
            profile = get_timing_profile(name)
            self.assertIsNotNone(profile, f"Profile {name} should exist")

    def test_orchestrator_get_stats(self):
        """RequestOrchestrator.get_stats() returns meaningful data."""
        from spiderfoot.recon.request_orchestration import RequestOrchestrator

        orch = RequestOrchestrator()
        orch.enqueue("https://example.com")
        stats = orch.get_stats()
        self.assertIn("queue_size", stats)


# ═══════════════════════════════════════════════════════════════════════
# 4. CLI Service — removed (CLI is now a Go binary, see cli/)
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 5. Stealth Stats API Endpoints
# ═══════════════════════════════════════════════════════════════════════


class TestStealthStatsAPI(unittest.TestCase):
    """Tests for the stealth stats API endpoints added to the scan router."""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from spiderfoot.api.routers.scan import router
        from fastapi import FastAPI

        app = FastAPI()
        router.dependencies = []
        app.include_router(router)
        cls.client = TestClient(app)

    def test_get_scan_stealth_stats_no_context(self):
        """GET /scans/{id}/stealth-stats returns 404 when no context."""
        resp = self.client.get("/scans/nonexistent-scan/stealth-stats")
        self.assertEqual(resp.status_code, 404)

    def test_get_scan_stealth_stats_with_context(self):
        """GET /scans/{id}/stealth-stats returns stats when context exists."""
        from spiderfoot.recon.stealth_integration import (
            create_stealth_context,
            register_scan_context,
            unregister_scan_context,
        )

        ctx = create_stealth_context(stealth_level="medium")
        scan_id = "test-stats-api-scan"
        register_scan_context(scan_id, ctx)

        try:
            resp = self.client.get(f"/scans/{scan_id}/stealth-stats")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["scan_id"], scan_id)
            self.assertIn("stealth", data)
            self.assertEqual(data["stealth"]["stealth_level"], "medium")
        finally:
            unregister_scan_context(scan_id)

    def test_get_all_stealth_stats(self):
        """GET /stealth-stats returns stats for all active scans."""
        resp = self.client.get("/stealth-stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("active_scans", data)
        self.assertIn("scans", data)


# ═══════════════════════════════════════════════════════════════════════
# 6. Replicate CLI — removed (CLI is now a Go binary, see cli/)
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 7. Audit CLI — removed (CLI is now a Go binary, see cli/)
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 8. Devtools CLI — removed (CLI is now a Go binary, see cli/)
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 9. Re-exports validation
# ═══════════════════════════════════════════════════════════════════════


class TestReExports(unittest.TestCase):
    """Validate that __init__.py re-exports are accessible."""

    def test_recon_init_exports(self):
        """spiderfoot.recon exports target_replication classes."""
        from spiderfoot.recon import (
            CloudProvider,
            TargetProfile,
            TargetProfileExtractor,
            TargetReplicator,
            TerraformGenerator,
            AnsibleGenerator,
            DockerComposeGenerator,
        )
        self.assertIsNotNone(TargetReplicator)
        self.assertIsNotNone(CloudProvider)

    def test_plugins_init_exports_audit(self):
        """spiderfoot.plugins exports module_audit classes."""
        from spiderfoot.plugins import (
            AuditReport,
            EventDependencyGraph,
            ModuleAuditRunner,
            ModuleContractAuditor,
            ModuleSourceAnalyzer,
        )
        self.assertIsNotNone(ModuleAuditRunner)

    def test_plugins_init_exports_devtools(self):
        """spiderfoot.plugins exports module_devtools classes."""
        from spiderfoot.plugins import (
            ModuleScaffolder,
            ModuleValidator,
            ScaffoldConfig,
            ValidationReport,
        )
        self.assertIsNotNone(ModuleScaffolder)
        self.assertIsNotNone(ScaffoldConfig)


if __name__ == "__main__":
    unittest.main()
