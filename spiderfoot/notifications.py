# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Notification Service
# =============================================================================
# Sends notifications on scan lifecycle events: completion, failure,
# high-severity findings. Supports multiple channels:
#   - Webhooks (generic HTTP POST)
#   - Slack
#   - Discord
#   - Email (SMTP)
# =============================================================================

from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.notifications")


class NotificationChannel(str, Enum):
    """Supported notification channels."""
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"


class NotificationEvent(str, Enum):
    """Events that trigger notifications."""
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"
    HIGH_SEVERITY = "high_severity"
    REPORT_READY = "report_ready"
    SUBDOMAIN_CHANGE = "subdomain_change"


@dataclass
class NotificationConfig:
    """Notification configuration loaded from environment."""
    enabled: bool = False
    # Webhook
    webhook_url: str = ""
    webhook_secret: str = ""
    # Slack
    slack_webhook_url: str = ""
    slack_channel: str = "#spiderfoot"
    # Discord
    discord_webhook_url: str = ""
    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: list[str] = field(default_factory=list)
    smtp_tls: bool = True
    # Filtering
    events: list[NotificationEvent] = field(
        default_factory=lambda: [
            NotificationEvent.SCAN_COMPLETED,
            NotificationEvent.SCAN_FAILED,
            NotificationEvent.HIGH_SEVERITY,
        ]
    )
    channels: list[NotificationChannel] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> NotificationConfig:
        """Load notification config from environment variables."""
        channels = []
        webhook_url = os.environ.get("SF_NOTIFY_WEBHOOK_URL", "")
        slack_url = os.environ.get("SF_NOTIFY_SLACK_WEBHOOK", "")
        discord_url = os.environ.get("SF_NOTIFY_DISCORD_WEBHOOK", "")
        smtp_host = os.environ.get("SF_NOTIFY_SMTP_HOST", "")

        if webhook_url:
            channels.append(NotificationChannel.WEBHOOK)
        if slack_url:
            channels.append(NotificationChannel.SLACK)
        if discord_url:
            channels.append(NotificationChannel.DISCORD)
        if smtp_host:
            channels.append(NotificationChannel.EMAIL)

        to_list = os.environ.get("SF_NOTIFY_SMTP_TO", "")

        return cls(
            enabled=bool(channels) and os.environ.get("SF_NOTIFY_ENABLED", "true").lower() != "false",
            webhook_url=webhook_url,
            webhook_secret=os.environ.get("SF_NOTIFY_WEBHOOK_SECRET", ""),
            slack_webhook_url=slack_url,
            slack_channel=os.environ.get("SF_NOTIFY_SLACK_CHANNEL", "#spiderfoot"),
            discord_webhook_url=discord_url,
            smtp_host=smtp_host,
            smtp_port=int(os.environ.get("SF_NOTIFY_SMTP_PORT", "587")),
            smtp_user=os.environ.get("SF_NOTIFY_SMTP_USER", ""),
            smtp_password=os.environ.get("SF_NOTIFY_SMTP_PASSWORD", ""),
            smtp_from=os.environ.get("SF_NOTIFY_SMTP_FROM", ""),
            smtp_to=[t.strip() for t in to_list.split(",") if t.strip()],
            smtp_tls=os.environ.get("SF_NOTIFY_SMTP_TLS", "true").lower() != "false",
            channels=channels,
        )


class NotificationService:
    """Send notifications across configured channels.

    Usage::

        svc = NotificationService.from_env()
        svc.notify(
            event=NotificationEvent.SCAN_COMPLETED,
            title="Scan Complete",
            message="Scan 'example.com' finished with 142 findings.",
            data={"scan_id": "abc123", "target": "example.com"},
        )
    """

    def __init__(self, config: NotificationConfig) -> None:
        self.config = config

    @classmethod
    def from_env(cls) -> NotificationService:
        return cls(NotificationConfig.from_env())

    def notify(
        self,
        event: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send notification to all configured channels.

        Returns dict mapping channel → success boolean.
        """
        if not self.config.enabled:
            return {"skipped": True, "reason": "notifications disabled"}

        if event not in self.config.events:
            return {"skipped": True, "reason": f"event {event.value} not in filter"}

        results = {}
        for channel in self.config.channels:
            try:
                if channel == NotificationChannel.WEBHOOK:
                    self._send_webhook(event, title, message, data)
                    results[channel.value] = True
                elif channel == NotificationChannel.SLACK:
                    self._send_slack(event, title, message, data)
                    results[channel.value] = True
                elif channel == NotificationChannel.DISCORD:
                    self._send_discord(event, title, message, data)
                    results[channel.value] = True
                elif channel == NotificationChannel.EMAIL:
                    self._send_email(event, title, message, data)
                    results[channel.value] = True
            except Exception as e:
                log.error("Notification failed for %s: %s", channel.value, e)
                results[channel.value] = False

        return results

    # -----------------------------------------------------------------
    # Channel implementations
    # -----------------------------------------------------------------

    def _send_webhook(
        self,
        event: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None,
    ) -> None:
        """Send generic webhook notification."""
        payload = json.dumps({
            "event": event.value,
            "title": title,
            "message": message,
            "data": data or {},
            "source": "spiderfoot",
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.config.webhook_secret:
            import hashlib
            import hmac
            sig = hmac.new(
                self.config.webhook_secret.encode(),
                payload,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Signature-256"] = f"sha256={sig}"

        req = urllib.request.Request(
            self.config.webhook_url,
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass  # response body not needed
        log.info("Webhook notification sent: %s", title)

    def _send_slack(
        self,
        event: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None,
    ) -> None:
        """Send Slack notification via incoming webhook."""
        color = {
            NotificationEvent.SCAN_COMPLETED: "#36a64f",
            NotificationEvent.SCAN_FAILED: "#ff0000",
            NotificationEvent.HIGH_SEVERITY: "#ff9900",
            NotificationEvent.REPORT_READY: "#2196f3",
        }.get(event, "#808080")

        payload = json.dumps({
            "channel": self.config.slack_channel,
            "username": "SpiderFoot",
            "icon_emoji": ":spider:",
            "attachments": [
                {
                    "color": color,
                    "title": title,
                    "text": message,
                    "fields": [
                        {"title": k, "value": str(v), "short": True}
                        for k, v in (data or {}).items()
                        if k in ("scan_id", "target", "status", "findings_count")
                    ],
                    "footer": "SpiderFoot OSINT",
                }
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            self.config.slack_webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass  # response body not needed
        log.info("Slack notification sent: %s", title)

    def _send_discord(
        self,
        event: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None,
    ) -> None:
        """Send Discord notification via webhook."""
        color = {
            NotificationEvent.SCAN_COMPLETED: 0x36A64F,
            NotificationEvent.SCAN_FAILED: 0xFF0000,
            NotificationEvent.HIGH_SEVERITY: 0xFF9900,
            NotificationEvent.REPORT_READY: 0x2196F3,
        }.get(event, 0x808080)

        payload = json.dumps({
            "username": "SpiderFoot",
            "embeds": [
                {
                    "title": title,
                    "description": message,
                    "color": color,
                    "fields": [
                        {"name": k, "value": str(v), "inline": True}
                        for k, v in (data or {}).items()
                        if k in ("scan_id", "target", "status", "findings_count")
                    ],
                    "footer": {"text": "SpiderFoot OSINT"},
                }
            ],
        }).encode("utf-8")

        req = urllib.request.Request(
            self.config.discord_webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass  # response body not needed
        log.info("Discord notification sent: %s", title)

    def _send_email(
        self,
        event: NotificationEvent,
        title: str,
        message: str,
        data: dict[str, Any] | None,
    ) -> None:
        """Send email notification via SMTP."""
        import html
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        if not self.config.smtp_to:
            log.warning("No SMTP recipients configured, skipping email notification")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[SpiderFoot] {title}"
        msg["From"] = self.config.smtp_from or self.config.smtp_user
        msg["To"] = ", ".join(self.config.smtp_to)

        # Plain text
        text_body = f"{title}\n\n{message}"
        if data:
            text_body += "\n\nDetails:\n" + "\n".join(
                f"  {k}: {v}" for k, v in data.items()
            )
        msg.attach(MIMEText(text_body, "plain"))

        # HTML — escape all user-provided values to prevent stored XSS
        safe_title = html.escape(str(title))
        safe_message = html.escape(str(message))
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #1a73e8;">{safe_title}</h2>
            <p>{safe_message}</p>
            {"<table border='1' cellpadding='5' style='border-collapse: collapse;'>"
             + "".join(f"<tr><td><b>{html.escape(str(k))}</b></td><td>{html.escape(str(v))}</td></tr>" for k, v in (data or {}).items())
             + "</table>" if data else ""}
            <hr>
            <p style="color: #888; font-size: 12px;">SpiderFoot OSINT Platform</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
            if self.config.smtp_tls:
                server.starttls()
            if self.config.smtp_user and self.config.smtp_password:
                server.login(self.config.smtp_user, self.config.smtp_password)
            server.sendmail(
                self.config.smtp_from or self.config.smtp_user,
                self.config.smtp_to,
                msg.as_string(),
            )

        log.info("Email notification sent to %s: %s", self.config.smtp_to, title)


# Module-level convenience
_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """Get or create the singleton notification service."""
    global _service
    if _service is None:
        _service = NotificationService.from_env()
    return _service


def notify(
    event: NotificationEvent,
    title: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Module-level convenience for sending notifications."""
    return get_notification_service().notify(event, title, message, data)
