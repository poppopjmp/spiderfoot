"""Tests for spiderfoot.notification_service."""
from __future__ import annotations

import json
import time
import threading

import pytest

from spiderfoot.notification_service import (
    EmailChannel,
    LogChannel,
    Notification,
    NotificationChannel,
    NotificationService,
    SlackChannel,
    WebhookChannel,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

class MockChannel(NotificationChannel):
    """In-memory channel for testing."""

    def __init__(self, channel_id="mock", should_fail=False):
        super().__init__(channel_id=channel_id, name="Mock")
        self.received = []
        self.should_fail = should_fail

    def _default_id(self):
        return "mock"

    def send(self, notification):
        if self.should_fail:
            self.error_count += 1
            self.last_error = "Simulated failure"
            return False
        self.received.append(notification)
        self.sent_count += 1
        return True


# ---------------------------------------------------------------------------
# Notification dataclass
# ---------------------------------------------------------------------------

class TestNotification:
    def test_auto_title(self):
        n = Notification(topic="scan.completed")
        assert "Scan Completed" in n.auto_title()

    def test_custom_title(self):
        n = Notification(topic="scan.completed", title="Custom Title")
        assert n.auto_title() == "Custom Title"

    def test_auto_message(self):
        n = Notification(
            topic="scan.completed",
            data={"target": "example.com", "events": 42})
        msg = n.auto_message()
        assert "target" in msg
        assert "example.com" in msg

    def test_custom_message(self):
        n = Notification(topic="test", message="Hello World")
        assert n.auto_message() == "Hello World"

    def test_defaults(self):
        n = Notification(topic="test")
        assert n.severity == "info"
        assert n.timestamp > 0
        assert n.data == {}


# ---------------------------------------------------------------------------
# Channel tests
# ---------------------------------------------------------------------------

class TestLogChannel:
    def test_send(self):
        ch = LogChannel()
        n = Notification(topic="test", data={"key": "val"})
        assert ch.send(n) is True
        assert ch.sent_count == 1

    def test_to_dict(self):
        ch = LogChannel(channel_id="log-1", name="My Logger")
        d = ch.to_dict()
        assert d["channel_id"] == "log-1"
        assert d["type"] == "LogChannel"


class TestSlackChannel:
    def test_init(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/xxx")
        assert ch.channel_id == "slack-default"
        assert ch.username == "SpiderFoot"


class TestWebhookChannel:
    def test_init(self):
        ch = WebhookChannel(url="https://example.com/hook")
        assert ch.channel_id == "webhook-default"
        assert ch.method == "POST"


class TestEmailChannel:
    def test_init(self):
        ch = EmailChannel(
            smtp_host="smtp.example.com",
            to_addrs=["user@example.com"])
        assert ch.channel_id == "email-default"
        assert ch.smtp_port == 587
        assert ch.use_tls is True

    def test_no_recipients(self):
        ch = EmailChannel(smtp_host="smtp.example.com", to_addrs=[])
        n = Notification(topic="test")
        assert ch.send(n) is False
        assert "recipients" in ch.last_error


# ---------------------------------------------------------------------------
# Notification Service tests
# ---------------------------------------------------------------------------

class TestNotificationService:
    def test_add_remove_channel(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        assert svc.get_channel("ch1") is ch
        assert svc.remove_channel("ch1") is True
        assert svc.get_channel("ch1") is None
        svc.shutdown()

    def test_list_channels(self):
        svc = NotificationService(async_dispatch=False)
        svc.add_channel(MockChannel("a"))
        svc.add_channel(MockChannel("b"))
        channels = svc.list_channels()
        assert len(channels) == 2
        svc.shutdown()

    def test_subscribe_and_notify(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("scan.completed", "ch1")

        count = svc.notify("scan.completed", {"target": "example.com"})
        assert count == 1
        assert len(ch.received) == 1
        assert ch.received[0].data["target"] == "example.com"
        svc.shutdown()

    def test_no_subscribers(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        # No subscription
        count = svc.notify("scan.completed")
        assert count == 0
        assert len(ch.received) == 0
        svc.shutdown()

    def test_wildcard_subscription(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("scan.*", "ch1")

        svc.notify("scan.completed")
        svc.notify("scan.error")
        svc.notify("other.event")

        assert len(ch.received) == 2
        svc.shutdown()

    def test_global_wildcard(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("*", "ch1")

        svc.notify("anything")
        svc.notify("something.else")
        assert len(ch.received) == 2
        svc.shutdown()

    def test_multiple_channels(self):
        svc = NotificationService(async_dispatch=False)
        ch1 = MockChannel("ch1")
        ch2 = MockChannel("ch2")
        svc.add_channel(ch1)
        svc.add_channel(ch2)
        svc.subscribe("test", "ch1")
        svc.subscribe("test", "ch2")

        count = svc.notify("test")
        assert count == 2
        assert len(ch1.received) == 1
        assert len(ch2.received) == 1
        svc.shutdown()

    def test_disabled_channel(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        ch.enabled = False
        svc.add_channel(ch)
        svc.subscribe("test", "ch1")

        svc.notify("test")
        assert len(ch.received) == 0
        svc.shutdown()

    def test_failing_channel(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1", should_fail=True)
        svc.add_channel(ch)
        svc.subscribe("test", "ch1")

        svc.notify("test")
        assert svc._total_failed == 1
        svc.shutdown()

    def test_unsubscribe(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("test", "ch1")
        svc.unsubscribe("test", "ch1")

        svc.notify("test")
        assert len(ch.received) == 0
        svc.shutdown()

    def test_subscribe_nonexistent_channel(self):
        svc = NotificationService(async_dispatch=False)
        assert svc.subscribe("test", "ghost") is False
        svc.shutdown()

    def test_list_subscriptions(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("scan.completed", "ch1")
        svc.subscribe("scan.error", "ch1")

        subs = svc.list_subscriptions()
        assert "scan.completed" in subs
        assert "scan.error" in subs
        svc.shutdown()

    def test_stats(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("test", "ch1")
        svc.notify("test")

        stats = svc.stats
        assert stats["channels"] == 1
        assert stats["total_sent"] == 1
        assert stats["async_enabled"] is False
        svc.shutdown()

    def test_async_dispatch(self):
        svc = NotificationService(async_dispatch=True)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("test", "ch1")

        svc.notify("test", {"key": "value"})

        # Wait for async processing
        time.sleep(0.3)
        assert len(ch.received) == 1
        svc.shutdown()

    def test_topic_matches(self):
        m = NotificationService._topic_matches
        assert m("scan.completed", "scan.completed") is True
        assert m("scan.*", "scan.completed") is True
        assert m("scan.*", "scan.error") is True
        assert m("scan.*", "other.event") is False
        assert m("*", "anything") is True
        assert m("scan.completed", "scan.error") is False

    def test_severity_in_notification(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("alert", "ch1")

        svc.notify("alert", severity="critical")
        assert ch.received[0].severity == "critical"
        svc.shutdown()

    def test_remove_channel_clears_subscriptions(self):
        svc = NotificationService(async_dispatch=False)
        ch = MockChannel("ch1")
        svc.add_channel(ch)
        svc.subscribe("test", "ch1")

        svc.remove_channel("ch1")
        # Should not deliver
        svc.notify("test")
        assert len(ch.received) == 0
        svc.shutdown()

    def test_shutdown_idempotent(self):
        svc = NotificationService(async_dispatch=True)
        svc.shutdown()
        svc.shutdown()  # Second call should be safe
