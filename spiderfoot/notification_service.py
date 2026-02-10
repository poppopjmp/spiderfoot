#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         notification_service
# Purpose:      Multi-channel notification service for SpiderFoot.
#               Send alerts via email, Slack, and webhook when scan
#               events or state changes occur.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Notification Service

Multi-channel notifications for scan events::

    from spiderfoot.notification_service import (
        NotificationService, NotificationChannel,
        SlackChannel, WebhookChannel, EmailChannel,
    )

    svc = NotificationService()

    # Add channels
    svc.add_channel(SlackChannel(
        webhook_url="https://hooks.slack.com/services/T.../B.../xxx"))
    svc.add_channel(WebhookChannel(url="https://example.com/hook"))
    svc.add_channel(EmailChannel(
        smtp_host="smtp.gmail.com", smtp_port=587,
        username="user@gmail.com", password="<YOUR_APP_PASSWORD>",
        from_addr="user@gmail.com", to_addrs=["ops@example.com"]))

    # Subscribe to topics
    svc.subscribe("scan.completed", channel_id="slack-default")
    svc.subscribe("scan.error", channel_id="email-default")

    # Send notification
    svc.notify("scan.completed", {
        "scan_id": "abc-123",
        "target": "example.com",
        "total_events": 450,
    })
"""

import json
import logging
import queue
import smtplib
import threading
import time
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

log = logging.getLogger("spiderfoot.notification_service")


# ---------------------------------------------------------------------------
# Notification data
# ---------------------------------------------------------------------------

@dataclass
class Notification:
    """A notification to be sent."""
    topic: str
    data: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    message: str = ""
    severity: str = "info"  # info, warning, error, critical
    timestamp: float = field(default_factory=time.time)

    def auto_title(self) -> str:
        """Generate a title from topic if none set."""
        if self.title:
            return self.title
        parts = self.topic.replace(".", " ").replace("_", " ").title()
        return f"SpiderFoot: {parts}"

    def auto_message(self) -> str:
        """Generate a message from data if none set."""
        if self.message:
            return self.message
        lines = [f"**{self.auto_title()}**", ""]
        for key, value in self.data.items():
            lines.append(f"- **{key}**: {value}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Channel base
# ---------------------------------------------------------------------------

class NotificationChannel(ABC):
    """Abstract notification channel."""

    def __init__(self, channel_id: str = "", name: str = "",
                 enabled: bool = True) -> None:
        self.channel_id = channel_id or self._default_id()
        self.name = name or self.channel_id
        self.enabled = enabled
        self.sent_count = 0
        self.error_count = 0
        self.last_error: str = ""

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True on success."""
        ...

    @abstractmethod
    def _default_id(self) -> str:
        ...

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "name": self.name,
            "type": self.__class__.__name__,
            "enabled": self.enabled,
            "sent_count": self.sent_count,
            "error_count": self.error_count,
        }


# ---------------------------------------------------------------------------
# Slack channel
# ---------------------------------------------------------------------------

class SlackChannel(NotificationChannel):
    """Send notifications to Slack via incoming webhook."""

    SEVERITY_COLORS = {
        "info": "#2196F3",
        "warning": "#FFC107",
        "error": "#F44336",
        "critical": "#B71C1C",
    }

    def __init__(self, webhook_url: str, *,
                 channel_id: str = "",
                 name: str = "Slack",
                 username: str = "SpiderFoot",
                 icon_emoji: str = ":spider:",
                 enabled: bool = True) -> None:
        super().__init__(channel_id=channel_id or "slack-default",
                        name=name, enabled=enabled)
        self.webhook_url = webhook_url
        self.username = username
        self.icon_emoji = icon_emoji

    def _default_id(self) -> str:
        return "slack-default"

    def send(self, notification: Notification) -> bool:
        color = self.SEVERITY_COLORS.get(
            notification.severity, "#2196F3")

        fields = []
        for key, value in notification.data.items():
            fields.append({
                "title": str(key),
                "value": str(value),
                "short": len(str(value)) < 30,
            })

        payload = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [{
                "color": color,
                "title": notification.auto_title(),
                "text": notification.message or "",
                "fields": fields,
                "ts": int(notification.timestamp),
            }],
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status < 300:
                    self.sent_count += 1
                    return True
                self.last_error = f"HTTP {resp.status}"
                self.error_count += 1
                return False
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            log.debug("Slack send error: %s", e)
            return False


# ---------------------------------------------------------------------------
# Generic webhook channel
# ---------------------------------------------------------------------------

class WebhookChannel(NotificationChannel):
    """Send notifications via generic HTTP webhook (JSON POST)."""

    def __init__(self, url: str, *,
                 channel_id: str = "",
                 name: str = "Webhook",
                 headers: dict[str, str] | None = None,
                 method: str = "POST",
                 enabled: bool = True) -> None:
        super().__init__(channel_id=channel_id or "webhook-default",
                        name=name, enabled=enabled)
        self.url = url
        self.headers = headers or {}
        self.method = method

    def _default_id(self) -> str:
        return "webhook-default"

    def send(self, notification: Notification) -> bool:
        payload = {
            "topic": notification.topic,
            "title": notification.auto_title(),
            "message": notification.auto_message(),
            "severity": notification.severity,
            "timestamp": notification.timestamp,
            "data": notification.data,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req_headers = {"Content-Type": "application/json"}
            req_headers.update(self.headers)

            req = urllib.request.Request(
                self.url, data=data,
                headers=req_headers,
                method=self.method,
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status < 300:
                    self.sent_count += 1
                    return True
                self.last_error = f"HTTP {resp.status}"
                self.error_count += 1
                return False
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            log.debug("Webhook send error: %s", e)
            return False


# ---------------------------------------------------------------------------
# Email channel
# ---------------------------------------------------------------------------

class EmailChannel(NotificationChannel):
    """Send notifications via SMTP email."""

    def __init__(self, smtp_host: str, smtp_port: int = 587, *,
                 username: str = "", password: str = "",
                 from_addr: str = "", to_addrs: list[str] | None = None,
                 use_tls: bool = True,
                 channel_id: str = "",
                 name: str = "Email",
                 enabled: bool = True) -> None:
        super().__init__(channel_id=channel_id or "email-default",
                        name=name, enabled=enabled)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def _default_id(self) -> str:
        return "email-default"

    def send(self, notification: Notification) -> bool:
        if not self.to_addrs:
            self.last_error = "No recipients configured"
            self.error_count += 1
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = notification.auto_title()
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        # Plain text
        text_body = notification.auto_message()
        msg.attach(MIMEText(text_body, "plain"))

        # HTML
        html_body = self._render_html(notification)
        msg.attach(MIMEText(html_body, "html"))

        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port,
                                      timeout=15)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port,
                                      timeout=15)

            if self.username and self.password:
                server.login(self.username, self.password)

            server.sendmail(self.from_addr, self.to_addrs,
                           msg.as_string())
            server.quit()
            self.sent_count += 1
            return True
        except Exception as e:
            self.last_error = str(e)
            self.error_count += 1
            log.debug("Email send error: %s", e)
            return False

    @staticmethod
    def _render_html(notification: Notification) -> str:
        severity_color = {
            "info": "#2196F3", "warning": "#FFC107",
            "error": "#F44336", "critical": "#B71C1C",
        }.get(notification.severity, "#2196F3")

        rows = ""
        for key, value in notification.data.items():
            rows += f"<tr><td><strong>{key}</strong></td><td>{value}</td></tr>"

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px;">
            <div style="background: {severity_color}; color: white;
                        padding: 12px 16px; border-radius: 4px 4px 0 0;">
                <h2 style="margin: 0;">{notification.auto_title()}</h2>
            </div>
            <div style="padding: 16px; border: 1px solid #ddd;
                        border-top: none; border-radius: 0 0 4px 4px;">
                {f'<p>{notification.message}</p>' if notification.message else ''}
                <table style="width: 100%; border-collapse: collapse;">
                    {rows}
                </table>
            </div>
        </body>
        </html>
        """


# ---------------------------------------------------------------------------
# Log channel (for testing / audit)
# ---------------------------------------------------------------------------

class LogChannel(NotificationChannel):
    """Log notifications to Python logger (useful for dev/testing)."""

    def __init__(self, channel_id: str = "log-default",
                 name: str = "Logger", enabled: bool = True,
                 logger: logging.Logger | None = None) -> None:
        super().__init__(channel_id=channel_id, name=name,
                        enabled=enabled)
        self._logger = logger or log

    def _default_id(self) -> str:
        return "log-default"

    def send(self, notification: Notification) -> bool:
        self._logger.info(
            "[%s] %s: %s | data=%s",
            notification.severity.upper(),
            notification.topic,
            notification.auto_title(),
            json.dumps(notification.data, default=str),
        )
        self.sent_count += 1
        return True


# ---------------------------------------------------------------------------
# Notification Service
# ---------------------------------------------------------------------------

class NotificationService:
    """Manages channels, subscriptions, and async dispatch."""

    def __init__(self, *, async_dispatch: bool = True,
                 max_queue_size: int = 1000) -> None:
        self._channels: dict[str, NotificationChannel] = {}
        self._subscriptions: dict[str, set[str]] = {}  # topic → channel_ids
        self._lock = threading.Lock()
        self._async = async_dispatch
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._worker: threading.Thread | None = None
        self._running = False
        self._total_sent = 0
        self._total_failed = 0

        if self._async:
            self._start_worker()

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    def add_channel(self, channel: NotificationChannel) -> None:
        """Register a notification channel."""
        with self._lock:
            self._channels[channel.channel_id] = channel
        log.info("Added notification channel: %s (%s)",
                channel.channel_id, channel.__class__.__name__)

    def remove_channel(self, channel_id: str) -> bool:
        with self._lock:
            removed = self._channels.pop(channel_id, None) is not None
            # Remove from subscriptions
            for topic_channels in self._subscriptions.values():
                topic_channels.discard(channel_id)
        return removed

    def get_channel(self, channel_id: str
                    ) -> NotificationChannel | None:
        return self._channels.get(channel_id)

    def list_channels(self) -> list[dict]:
        return [ch.to_dict() for ch in self._channels.values()]

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def subscribe(self, topic: str, channel_id: str) -> bool:
        """Subscribe a channel to a topic.

        Topic supports wildcards: ``scan.*`` matches ``scan.completed``.
        """
        if channel_id not in self._channels:
            log.warning("Channel %s not found", channel_id)
            return False

        with self._lock:
            self._subscriptions.setdefault(topic, set()).add(channel_id)
        return True

    def unsubscribe(self, topic: str, channel_id: str) -> bool:
        with self._lock:
            channels = self._subscriptions.get(topic)
            if channels:
                channels.discard(channel_id)
                return True
        return False

    def list_subscriptions(self) -> dict[str, list[str]]:
        with self._lock:
            return {
                topic: sorted(channels)
                for topic, channels in self._subscriptions.items()
            }

    # ------------------------------------------------------------------
    # Notify
    # ------------------------------------------------------------------

    def notify(self, topic: str, data: dict[str, Any] | None = None,
               *, title: str = "", message: str = "",
               severity: str = "info") -> int:
        """Send a notification to all channels subscribed to this topic.

        Returns number of channels notified.
        """
        notification = Notification(
            topic=topic,
            data=data or {},
            title=title,
            message=message,
            severity=severity,
        )

        # Find matching channels
        target_channels = self._resolve_channels(topic)

        if not target_channels:
            return 0

        if self._async and self._running:
            for ch_id in target_channels:
                try:
                    self._queue.put_nowait((ch_id, notification))
                except queue.Full:
                    log.warning("Notification queue full, dropping "
                              "notification for %s", ch_id)
        else:
            self._dispatch_sync(target_channels, notification)

        return len(target_channels)

    def _resolve_channels(self, topic: str) -> set[str]:
        """Find channels subscribed to this topic (with wildcard)."""
        matched = set()
        with self._lock:
            for pattern, channel_ids in self._subscriptions.items():
                if self._topic_matches(pattern, topic):
                    matched.update(channel_ids)
        return matched

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a subscription pattern.

        Supports:
        - Exact match: ``scan.completed``
        - Wildcard suffix: ``scan.*``
        - Global wildcard: ``*``
        """
        if pattern == "*":
            return True
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic.startswith(prefix + ".") or topic == prefix
        return False

    def _dispatch_sync(self, channel_ids: set[str],
                       notification: Notification) -> None:
        for ch_id in channel_ids:
            channel = self._channels.get(ch_id)
            if not channel or not channel.enabled:
                continue
            try:
                if channel.send(notification):
                    self._total_sent += 1
                else:
                    self._total_failed += 1
            except Exception as e:
                self._total_failed += 1
                log.debug("Channel %s send error: %s", ch_id, e)

    # ------------------------------------------------------------------
    # Async worker
    # ------------------------------------------------------------------

    def _start_worker(self) -> None:
        self._running = True
        self._worker = threading.Thread(
            target=self._worker_loop, daemon=True,
            name="notification-worker")
        self._worker.start()

    def _worker_loop(self) -> None:
        while self._running:
            try:
                ch_id, notification = self._queue.get(timeout=1.0)
                channel = self._channels.get(ch_id)
                if channel and channel.enabled:
                    try:
                        if channel.send(notification):
                            self._total_sent += 1
                        else:
                            self._total_failed += 1
                    except Exception as e:
                        self._total_failed += 1
                        log.debug("Async send error: %s", e)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                continue

    def shutdown(self, timeout: float = 5.0) -> None:
        """Stop the async worker and drain remaining notifications."""
        self._running = False
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        return {
            "channels": len(self._channels),
            "subscriptions": sum(
                len(ch) for ch in self._subscriptions.values()),
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "queue_size": self._queue.qsize(),
            "async_enabled": self._async,
        }

    # ------------------------------------------------------------------
    # EventBus integration
    # ------------------------------------------------------------------

    def setup_eventbus_bridge(self) -> bool:
        """Subscribe to EventBus scan events and forward as notifications."""
        try:
            from spiderfoot.service_registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            event_bus = registry.get("event_bus")
            if not event_bus:
                return False

            topics = [
                "scan.started", "scan.completed", "scan.error",
                "scan.aborted",
            ]
            for topic in topics:
                event_bus.subscribe(
                    topic,
                    lambda data, t=topic: self.notify(t, data or {}),
                )

            log.info("EventBus bridge configured for %d topics",
                    len(topics))
            return True
        except Exception as e:
            log.debug("EventBus bridge not available: %s", e)
            return False
