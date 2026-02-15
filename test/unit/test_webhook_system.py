"""
Tests for the Webhook/Notification system — Cycle 17.

Covers:
  - WebhookConfig: creation, matches_event, to_dict
  - DeliveryRecord: creation, to_dict, elapsed_seconds
  - WebhookDispatcher: deliver, HMAC signing, retries, history, stats
  - NotificationManager: CRUD, notify, notify_async, test_webhook,
    wire_task_manager, wire_alert_engine, history, stats
  - Webhooks API router: all endpoints
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from spiderfoot.webhook_dispatcher import (
    DeliveryRecord,
    DeliveryStatus,
    WebhookConfig,
    WebhookDispatcher,
)
from spiderfoot.notification_manager import (
    NotificationManager,
    get_notification_manager,
    reset_notification_manager,
)


# =====================================================================
# WebhookConfig
# =====================================================================

class TestWebhookConfig(unittest.TestCase):

    def test_default_id_generated(self):
        cfg = WebhookConfig(url="https://example.com/hook")
        self.assertTrue(len(cfg.webhook_id) > 0)

    def test_explicit_id_preserved(self):
        cfg = WebhookConfig(webhook_id="wh-1", url="https://example.com/hook")
        self.assertEqual(cfg.webhook_id, "wh-1")

    def test_matches_event_no_filter(self):
        cfg = WebhookConfig(url="https://a.com", event_types=[])
        self.assertTrue(cfg.matches_event("scan.complete"))
        self.assertTrue(cfg.matches_event("anything"))

    def test_matches_event_exact(self):
        cfg = WebhookConfig(url="https://a.com", event_types=["scan.complete"])
        self.assertTrue(cfg.matches_event("scan.complete"))
        self.assertFalse(cfg.matches_event("task.complete"))

    def test_matches_event_prefix(self):
        cfg = WebhookConfig(url="https://a.com", event_types=["scan"])
        self.assertTrue(cfg.matches_event("scan.complete"))
        self.assertTrue(cfg.matches_event("scan.started"))
        self.assertFalse(cfg.matches_event("task.complete"))

    def test_to_dict_masks_secret(self):
        cfg = WebhookConfig(
            url="https://a.com",
            secret="supersecret",
            headers={"Authorization": "Bearer tok"},
        )
        d = cfg.to_dict()
        self.assertEqual(d["secret"], "***")
        self.assertEqual(d["headers"]["Authorization"], "***")

    def test_to_dict_empty_secret(self):
        cfg = WebhookConfig(url="https://a.com")
        d = cfg.to_dict()
        self.assertEqual(d["secret"], "")

    def test_description_field(self):
        cfg = WebhookConfig(url="https://a.com", description="Test hook")
        self.assertEqual(cfg.description, "Test hook")
        self.assertEqual(cfg.to_dict()["description"], "Test hook")


# =====================================================================
# DeliveryRecord
# =====================================================================

class TestDeliveryRecord(unittest.TestCase):

    def test_default_values(self):
        rec = DeliveryRecord()
        self.assertTrue(len(rec.delivery_id) > 0)
        self.assertGreater(rec.created_at, 0)
        self.assertEqual(rec.status, DeliveryStatus.PENDING)

    def test_to_dict(self):
        rec = DeliveryRecord(
            webhook_id="wh-1",
            event_type="scan.complete",
            status=DeliveryStatus.SUCCESS,
            attempts=1,
            status_code=200,
        )
        rec.completed_at = rec.created_at + 0.5
        d = rec.to_dict()
        self.assertEqual(d["status"], "success")
        self.assertEqual(d["status_code"], 200)
        self.assertAlmostEqual(d["elapsed_seconds"], 0.5, places=1)

    def test_elapsed_seconds_no_completion(self):
        rec = DeliveryRecord()
        elapsed = rec.elapsed_seconds
        self.assertGreaterEqual(elapsed, 0)


# =====================================================================
# WebhookDispatcher
# =====================================================================

class TestWebhookDispatcher(unittest.TestCase):

    def setUp(self):
        self.dispatcher = WebhookDispatcher(max_history=50)
        self.cfg = WebhookConfig(
            webhook_id="wh-t1",
            url="https://example.com/hook",
            max_retries=1,
        )

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_deliver_success(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.post.return_value = mock_resp

        record = self.dispatcher.deliver(
            self.cfg, "scan.complete", {"scan_id": "s1"},
        )
        self.assertEqual(record.status, DeliveryStatus.SUCCESS)
        self.assertEqual(record.status_code, 200)
        self.assertEqual(record.attempts, 1)
        mock_httpx.post.assert_called_once()

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_deliver_failure(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_httpx.post.return_value = mock_resp

        record = self.dispatcher.deliver(
            self.cfg, "scan.complete", {"scan_id": "s1"},
        )
        self.assertEqual(record.status, DeliveryStatus.FAILED)
        self.assertEqual(record.status_code, 500)

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_deliver_exception(self, mock_httpx):
        mock_httpx.post.side_effect = ConnectionError("refused")

        record = self.dispatcher.deliver(
            self.cfg, "task.complete", {"task_id": "t1"},
        )
        self.assertEqual(record.status, DeliveryStatus.FAILED)
        self.assertIn("refused", record.error)

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_deliver_retries(self, mock_httpx):
        cfg = WebhookConfig(
            webhook_id="wh-retry",
            url="https://example.com/hook",
            max_retries=2,
        )
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_httpx.post.side_effect = [mock_resp_500, mock_resp_200]

        with patch("spiderfoot.webhook_dispatcher.time.sleep"):
            record = self.dispatcher.deliver(cfg, "scan.complete", {})

        self.assertEqual(record.status, DeliveryStatus.SUCCESS)
        self.assertEqual(record.attempts, 2)

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_hmac_signing(self, mock_httpx):
        cfg = WebhookConfig(
            webhook_id="wh-hmac",
            url="https://example.com/hook",
            secret="my-secret",
            max_retries=1,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.post.return_value = mock_resp

        record = self.dispatcher.deliver(cfg, "test", {"data": 1})

        call_kwargs = mock_httpx.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        sig_header = headers.get("X-SpiderFoot-Signature", "")
        self.assertTrue(sig_header.startswith("sha256="))

        # Verify the signature
        body = call_kwargs.kwargs.get("content") or call_kwargs[1].get("content")
        expected = hmac.new(
            b"my-secret", body, hashlib.sha256,
        ).hexdigest()
        self.assertEqual(sig_header, f"sha256={expected}")

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_no_hmac_without_secret(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.post.return_value = mock_resp

        self.dispatcher.deliver(self.cfg, "test", {})

        call_kwargs = mock_httpx.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        self.assertNotIn("X-SpiderFoot-Signature", headers)

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_history(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.post.return_value = mock_resp

        self.dispatcher.deliver(self.cfg, "e1", {})
        self.dispatcher.deliver(self.cfg, "e2", {})

        history = self.dispatcher.get_history()
        self.assertEqual(len(history), 2)

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_history_filter_by_webhook(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.post.return_value = mock_resp

        cfg2 = WebhookConfig(webhook_id="other", url="https://b.com", max_retries=1)
        self.dispatcher.deliver(self.cfg, "e1", {})
        self.dispatcher.deliver(cfg2, "e2", {})

        filtered = self.dispatcher.get_history(webhook_id="other")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].webhook_id, "other")

    @patch("spiderfoot.webhook_dispatcher.HAS_HTTPX", True)
    @patch("spiderfoot.webhook_dispatcher.httpx")
    def test_stats(self, mock_httpx):
        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 500
        mock_httpx.post.side_effect = [mock_resp_ok, mock_resp_fail]

        self.dispatcher.deliver(self.cfg, "e1", {})
        self.dispatcher.deliver(self.cfg, "e2", {})

        s = self.dispatcher.stats
        self.assertEqual(s["total_deliveries"], 2)
        self.assertEqual(s["successful"], 1)
        self.assertEqual(s["failed"], 1)

    def test_clear_history(self):
        self.dispatcher._history.append(
            DeliveryRecord(webhook_id="x", event_type="e")
        )
        count = self.dispatcher.clear_history()
        self.assertEqual(count, 1)
        self.assertEqual(len(self.dispatcher.get_history()), 0)


# =====================================================================
# NotificationManager
# =====================================================================

class TestNotificationManager(unittest.TestCase):

    def setUp(self):
        reset_notification_manager()
        self.mock_dispatcher = MagicMock(spec=WebhookDispatcher)
        self.mock_dispatcher.get_history.return_value = []
        self.mock_dispatcher.stats = {
            "total_deliveries": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0.0,
        }
        self.mgr = NotificationManager(dispatcher=self.mock_dispatcher)

    def test_add_and_list_webhooks(self):
        cfg = WebhookConfig(webhook_id="wh-1", url="https://a.com")
        wid = self.mgr.add_webhook(cfg)
        self.assertEqual(wid, "wh-1")
        self.assertEqual(len(self.mgr.list_webhooks()), 1)

    def test_get_webhook(self):
        cfg = WebhookConfig(webhook_id="wh-2", url="https://b.com")
        self.mgr.add_webhook(cfg)
        result = self.mgr.get_webhook("wh-2")
        self.assertIsNotNone(result)
        self.assertEqual(result.url, "https://b.com")

    def test_get_webhook_not_found(self):
        self.assertIsNone(self.mgr.get_webhook("missing"))

    def test_remove_webhook(self):
        cfg = WebhookConfig(webhook_id="wh-3", url="https://c.com")
        self.mgr.add_webhook(cfg)
        self.assertTrue(self.mgr.remove_webhook("wh-3"))
        self.assertEqual(len(self.mgr.list_webhooks()), 0)

    def test_remove_nonexistent(self):
        self.assertFalse(self.mgr.remove_webhook("nope"))

    def test_update_webhook(self):
        cfg = WebhookConfig(webhook_id="wh-4", url="https://d.com")
        self.mgr.add_webhook(cfg)
        self.assertTrue(self.mgr.update_webhook("wh-4", url="https://e.com"))
        self.assertEqual(self.mgr.get_webhook("wh-4").url, "https://e.com")

    def test_update_nonexistent(self):
        self.assertFalse(self.mgr.update_webhook("nope", url="https://x.com"))

    def test_notify_dispatches_to_matching(self):
        cfg1 = WebhookConfig(
            webhook_id="wh-a", url="https://a.com",
            event_types=["scan"], max_retries=1,
        )
        cfg2 = WebhookConfig(
            webhook_id="wh-b", url="https://b.com",
            event_types=["task"], max_retries=1,
        )
        self.mgr.add_webhook(cfg1)
        self.mgr.add_webhook(cfg2)

        self.mock_dispatcher.deliver.return_value = DeliveryRecord(
            status=DeliveryStatus.SUCCESS,
        )
        records = self.mgr.notify("scan.complete", {"scan_id": "s1"})

        # Only cfg1 matches "scan.complete"
        self.assertEqual(len(records), 1)
        self.mock_dispatcher.deliver.assert_called_once()

    def test_notify_skips_disabled(self):
        cfg = WebhookConfig(
            webhook_id="wh-dis", url="https://a.com",
            enabled=False,
        )
        self.mgr.add_webhook(cfg)
        records = self.mgr.notify("scan.complete", {})
        self.assertEqual(len(records), 0)

    def test_notify_no_targets(self):
        records = self.mgr.notify("scan.complete", {})
        self.assertEqual(records, [])

    def test_notify_handles_dispatcher_exception(self):
        cfg = WebhookConfig(webhook_id="wh-err", url="https://a.com")
        self.mgr.add_webhook(cfg)
        self.mock_dispatcher.deliver.side_effect = RuntimeError("boom")

        records = self.mgr.notify("scan.complete", {})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].status, DeliveryStatus.FAILED)
        self.assertIn("boom", records[0].error)

    def test_test_webhook_found(self):
        cfg = WebhookConfig(webhook_id="wh-test", url="https://a.com")
        self.mgr.add_webhook(cfg)
        self.mock_dispatcher.deliver.return_value = DeliveryRecord(
            status=DeliveryStatus.SUCCESS,
        )
        rec = self.mgr.test_webhook("wh-test")
        self.assertIsNotNone(rec)
        self.mock_dispatcher.deliver.assert_called_once()
        call_args = self.mock_dispatcher.deliver.call_args
        self.assertEqual(call_args[1].get("event_type") or call_args[0][1], "webhook.test")

    def test_test_webhook_not_found(self):
        self.assertIsNone(self.mgr.test_webhook("missing"))

    def test_notify_async_fires(self):
        cfg = WebhookConfig(webhook_id="async-1", url="https://a.com")
        self.mgr.add_webhook(cfg)
        self.mock_dispatcher.deliver.return_value = DeliveryRecord(
            status=DeliveryStatus.SUCCESS
        )
        self.mgr.notify_async("scan.complete", {"x": 1})
        # Give the thread time to fire
        time.sleep(0.1)
        self.mock_dispatcher.deliver.assert_called_once()

    def test_stats_includes_webhook_counts(self):
        cfg = WebhookConfig(webhook_id="st-1", url="https://a.com")
        self.mgr.add_webhook(cfg)
        s = self.mgr.stats
        self.assertEqual(s["webhooks_registered"], 1)
        self.assertEqual(s["webhooks_enabled"], 1)

    def test_delivery_history_delegates(self):
        self.mgr.get_delivery_history(webhook_id="x", limit=10)
        self.mock_dispatcher.get_history.assert_called_once_with(
            webhook_id="x", limit=10,
        )


# =====================================================================
# Singleton
# =====================================================================

class TestSingleton(unittest.TestCase):

    def setUp(self):
        reset_notification_manager()

    def tearDown(self):
        reset_notification_manager()

    def test_get_returns_same_instance(self):
        m1 = get_notification_manager()
        m2 = get_notification_manager()
        self.assertIs(m1, m2)

    def test_reset_clears_singleton(self):
        m1 = get_notification_manager()
        reset_notification_manager()
        m2 = get_notification_manager()
        self.assertIsNot(m1, m2)


# =====================================================================
# Integration hooks
# =====================================================================

class TestWireTaskManager(unittest.TestCase):

    def setUp(self):
        reset_notification_manager()

    def tearDown(self):
        reset_notification_manager()

    @patch("spiderfoot.notification_manager.NotificationManager.notify_async")
    def test_wire_task_manager(self, mock_async):
        """wire_task_manager registers callback on TaskManager."""
        from spiderfoot.task_queue import get_task_manager, reset_task_manager
        reset_task_manager()
        try:
            mgr = NotificationManager()
            mgr.wire_task_manager()

            # Simulate a task completion callback
            task_mgr = get_task_manager()
            mock_record = MagicMock()
            mock_record.state = MagicMock()
            mock_record.state.value = "completed"
            mock_record.to_dict.return_value = {"task_id": "t1"}

            # Invoke the registered callback
            for cb in task_mgr._callbacks:
                cb(mock_record)

            mock_async.assert_called_once_with(
                "task.completed", {"task_id": "t1"},
            )
        finally:
            reset_task_manager()


class TestWireAlertEngine(unittest.TestCase):

    def setUp(self):
        reset_notification_manager()

    def tearDown(self):
        reset_notification_manager()

    @patch("spiderfoot.notification_manager.NotificationManager.notify_async")
    def test_wire_alert_engine(self, mock_async):
        """wire_alert_engine registers handler on AlertEngine."""
        mgr = NotificationManager()

        mock_engine = MagicMock()
        handlers = []
        mock_engine.add_handler.side_effect = lambda cb: handlers.append(cb)

        mgr.wire_alert_engine(engine=mock_engine)

        self.assertEqual(len(handlers), 1)

        # Simulate alert
        mock_alert = MagicMock()
        mock_alert.severity = MagicMock()
        mock_alert.severity.value = "critical"
        mock_alert.to_dict.return_value = {"rule": "r1"}

        handlers[0](mock_alert)
        mock_async.assert_called_once_with(
            "alert.critical", {"rule": "r1"},
        )


# =====================================================================
# API Router tests
# =====================================================================

class TestWebhooksAPI(unittest.TestCase):
    """Test the webhooks REST API endpoints."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            raise unittest.SkipTest("FastAPI not installed")

        reset_notification_manager()
        from spiderfoot.api.routers import webhooks as webhooks_mod
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(webhooks_mod.router, prefix="/api")
        cls.client = TestClient(app)

    def setUp(self):
        reset_notification_manager()

    def tearDown(self):
        reset_notification_manager()

    def _create_webhook(self, **overrides):
        payload = {
            "url": "https://example.com/hook",
            "secret": "s3cret",
            "event_types": ["scan"],
            "description": "test hook",
        }
        payload.update(overrides)
        return self.client.post("/api/webhooks", json=payload)

    # -- POST /api/webhooks -----------------------------------------------

    def test_create_webhook(self):
        resp = self._create_webhook()
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("webhook_id", data)
        self.assertEqual(data["url"], "https://example.com/hook")
        self.assertEqual(data["status"], "registered")

    def test_create_webhook_minimal(self):
        resp = self.client.post(
            "/api/webhooks", json={"url": "https://min.com/hook"},
        )
        self.assertEqual(resp.status_code, 201)

    # -- GET /api/webhooks ------------------------------------------------

    def test_list_webhooks_empty(self):
        resp = self.client.get("/api/webhooks")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)

    def test_list_webhooks_after_create(self):
        self._create_webhook()
        resp = self.client.get("/api/webhooks")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    # -- GET /api/webhooks/{id} -------------------------------------------

    def test_get_webhook_found(self):
        create_resp = self._create_webhook()
        wid = create_resp.json()["webhook_id"]
        resp = self.client.get(f"/api/webhooks/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["webhook_id"], wid)
        # Secret should be masked
        self.assertEqual(resp.json()["secret"], "***")

    def test_get_webhook_not_found(self):
        resp = self.client.get("/api/webhooks/nonexistent")
        self.assertEqual(resp.status_code, 404)

    # -- DELETE /api/webhooks/{id} ----------------------------------------

    def test_delete_webhook(self):
        create_resp = self._create_webhook()
        wid = create_resp.json()["webhook_id"]
        resp = self.client.delete(f"/api/webhooks/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "removed")

        # Verify it's gone
        resp2 = self.client.get(f"/api/webhooks/{wid}")
        self.assertEqual(resp2.status_code, 404)

    def test_delete_nonexistent(self):
        resp = self.client.delete("/api/webhooks/nope")
        self.assertEqual(resp.status_code, 404)

    # -- POST /api/webhooks/{id}/test -------------------------------------

    def test_test_webhook_endpoint(self):
        create_resp = self._create_webhook()
        wid = create_resp.json()["webhook_id"]

        # Mock the dispatcher to avoid real HTTP call
        mgr = get_notification_manager()
        mgr._dispatcher = MagicMock(spec=WebhookDispatcher)
        mgr._dispatcher.deliver.return_value = DeliveryRecord(
            webhook_id=wid,
            event_type="webhook.test",
            status=DeliveryStatus.SUCCESS,
        )

        resp = self.client.post(f"/api/webhooks/{wid}/test")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["event_type"], "webhook.test")

    def test_test_webhook_not_found(self):
        resp = self.client.post("/api/webhooks/missing/test")
        self.assertEqual(resp.status_code, 404)

    # -- GET /api/webhooks/stats ------------------------------------------

    def test_stats_endpoint(self):
        resp = self.client.get("/api/webhooks/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_deliveries", data)
        self.assertIn("webhooks_registered", data)

    # -- GET /api/webhooks/history ----------------------------------------

    def test_history_endpoint(self):
        resp = self.client.get("/api/webhooks/history")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("deliveries", resp.json())
        self.assertIn("count", resp.json())

    def test_history_with_filter(self):
        resp = self.client.get(
            "/api/webhooks/history?webhook_id=wh-1&limit=10",
        )
        self.assertEqual(resp.status_code, 200)

    # -- PATCH /api/webhooks/{id} -----------------------------------------

    def test_update_webhook(self):
        create_resp = self._create_webhook()
        wid = create_resp.json()["webhook_id"]
        resp = self.client.patch(
            f"/api/webhooks/{wid}",
            json={"url": "https://new-url.com/hook", "enabled": False},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "updated")
        self.assertIn("url", resp.json()["fields"])
        self.assertIn("enabled", resp.json()["fields"])

        # Verify update applied
        detail = self.client.get(f"/api/webhooks/{wid}").json()
        self.assertEqual(detail["url"], "https://new-url.com/hook")
        self.assertFalse(detail["enabled"])

    def test_update_nonexistent(self):
        resp = self.client.patch(
            "/api/webhooks/nope", json={"url": "https://x.com"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_update_empty_body(self):
        create_resp = self._create_webhook()
        wid = create_resp.json()["webhook_id"]
        resp = self.client.patch(f"/api/webhooks/{wid}", json={})
        self.assertEqual(resp.status_code, 400)

    # -- Route ordering: /stats and /history before /{webhook_id} ---------

    def test_stats_not_intercepted_by_id_route(self):
        """Stats endpoint should NOT be treated as webhook_id='stats'."""
        resp = self.client.get("/api/webhooks/stats")
        self.assertEqual(resp.status_code, 200)
        # If route ordering were wrong, this would be 404 (no webhook with id "stats")
        self.assertIn("total_deliveries", resp.json())

    def test_history_not_intercepted_by_id_route(self):
        """History endpoint should NOT be treated as webhook_id='history'."""
        resp = self.client.get("/api/webhooks/history")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("deliveries", resp.json())


if __name__ == "__main__":
    unittest.main()
