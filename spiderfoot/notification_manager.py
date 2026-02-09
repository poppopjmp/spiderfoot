"""
Notification Manager — routes events to registered webhooks.

Central hub that connects SpiderFoot's internal event sources
(AlertEngine, TaskManager, EventBus scan events) to outbound
webhook delivery via :class:`WebhookDispatcher`.

Usage::

    from spiderfoot.notification_manager import get_notification_manager

    mgr = get_notification_manager()
    mgr.add_webhook(WebhookConfig(
        url="https://slack.example.com/hook",
        event_types=["scan.complete", "alert"],
    ))

    # Manually notify:
    mgr.notify("scan.complete", {"scan_id": "s1", "target": "example.com"})
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from spiderfoot.webhook_dispatcher import (
    DeliveryRecord,
    DeliveryStatus,
    WebhookConfig,
    WebhookDispatcher,
)

log = logging.getLogger("spiderfoot.notifications")


class NotificationManager:
    """Routes events to registered webhook endpoints.

    Thread-safe.  Webhooks can filter by event type so only
    relevant notifications are dispatched.

    Parameters:
        dispatcher: Optional custom dispatcher (default creates one).
    """

    def __init__(
        self,
        dispatcher: Optional[WebhookDispatcher] = None,
    ):
        self._lock = threading.Lock()
        self._webhooks: Dict[str, WebhookConfig] = {}
        self._dispatcher = dispatcher or WebhookDispatcher()

    # -- Webhook CRUD -----------------------------------------------------

    def add_webhook(self, config: WebhookConfig) -> str:
        """Register a webhook endpoint.  Returns the webhook_id."""
        with self._lock:
            self._webhooks[config.webhook_id] = config
        log.info(
            "Webhook registered: %s -> %s (events=%s)",
            config.webhook_id,
            config.url,
            config.event_types or ["*"],
        )
        return config.webhook_id

    def remove_webhook(self, webhook_id: str) -> bool:
        """Remove a webhook.  Returns True if it existed."""
        with self._lock:
            return self._webhooks.pop(webhook_id, None) is not None

    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        with self._lock:
            return self._webhooks.get(webhook_id)

    def list_webhooks(self) -> List[WebhookConfig]:
        with self._lock:
            return list(self._webhooks.values())

    def update_webhook(
        self, webhook_id: str, **kwargs,
    ) -> bool:
        """Update specific fields on a webhook config."""
        with self._lock:
            cfg = self._webhooks.get(webhook_id)
            if cfg is None:
                return False
            for k, v in kwargs.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            return True

    # -- Notification dispatch --------------------------------------------

    def notify(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> List[DeliveryRecord]:
        """Dispatch a notification to all matching webhooks.

        Returns a list of :class:`DeliveryRecord` for each delivery.
        Disabled webhooks and those not matching the event type are
        skipped.
        """
        with self._lock:
            targets = [
                cfg
                for cfg in self._webhooks.values()
                if cfg.enabled and cfg.matches_event(event_type)
            ]

        if not targets:
            return []

        records = []
        for cfg in targets:
            try:
                record = self._dispatcher.deliver(cfg, event_type, payload)
                records.append(record)
            except Exception as e:
                log.error(
                    "Notification delivery error: %s -> %s: %s",
                    event_type, cfg.url, e,
                )
                records.append(
                    DeliveryRecord(
                        webhook_id=cfg.webhook_id,
                        event_type=event_type,
                        status=DeliveryStatus.FAILED,
                        error=str(e),
                    )
                )
        return records

    def notify_async(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        """Fire-and-forget notification in a background thread."""
        t = threading.Thread(
            target=self.notify,
            args=(event_type, payload),
            daemon=True,
        )
        t.start()

    def test_webhook(self, webhook_id: str) -> Optional[DeliveryRecord]:
        """Send a test event to a specific webhook.

        Returns the delivery record, or None if webhook not found.
        """
        cfg = self.get_webhook(webhook_id)
        if cfg is None:
            return None
        return self._dispatcher.deliver(
            cfg,
            event_type="webhook.test",
            payload={
                "message": "SpiderFoot webhook test",
                "timestamp": time.time(),
                "webhook_id": webhook_id,
            },
        )

    # -- Integration hooks ------------------------------------------------

    def wire_task_manager(self) -> None:
        """Register as a TaskManager callback."""
        try:
            from spiderfoot.task_queue import get_task_manager

            mgr = get_task_manager()
            mgr.on_task_complete(self._on_task_complete)
            log.info("NotificationManager wired to TaskManager")
        except ImportError:
            log.warning("TaskManager not available for notification wiring")

    def _on_task_complete(self, record) -> None:
        """TaskManager callback — fires task.* events."""
        event_type = f"task.{record.state.value}"
        self.notify_async(event_type, record.to_dict())

    def wire_alert_engine(self, engine=None) -> None:
        """Register as an AlertEngine handler.

        Args:
            engine: An existing AlertEngine instance. If not provided,
                    falls back to importing ``get_alert_engine`` (which
                    may not exist in all builds).
        """
        try:
            if engine is None:
                from spiderfoot.alert_rules import AlertEngine
                engine = AlertEngine()
            engine.add_handler(self._on_alert)
            log.info("NotificationManager wired to AlertEngine")
        except (ImportError, Exception) as e:
            log.warning("AlertEngine not available: %s", e)

    def _on_alert(self, alert) -> None:
        """AlertEngine handler — fires alert.* events."""
        event_type = f"alert.{alert.severity.value}" if hasattr(alert, "severity") else "alert"
        payload = alert.to_dict() if hasattr(alert, "to_dict") else {"message": str(alert)}
        self.notify_async(event_type, payload)

    # -- Query ------------------------------------------------------------

    def get_delivery_history(
        self,
        webhook_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[DeliveryRecord]:
        return self._dispatcher.get_history(webhook_id=webhook_id, limit=limit)

    @property
    def stats(self) -> Dict[str, Any]:
        delivery = self._dispatcher.stats
        delivery["webhooks_registered"] = len(self._webhooks)
        delivery["webhooks_enabled"] = sum(
            1 for c in self._webhooks.values() if c.enabled
        )
        return delivery


# -----------------------------------------------------------------------
# Singleton
# -----------------------------------------------------------------------

_manager: Optional[NotificationManager] = None
_manager_lock = threading.Lock()


def get_notification_manager() -> NotificationManager:
    """Get or create the global NotificationManager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = NotificationManager()
    return _manager


def reset_notification_manager() -> None:
    """Reset the singleton (for testing)."""
    global _manager
    with _manager_lock:
        _manager = None
