"""Backward-compatibility shim for notification_service.py.

This module re-exports from services/notification_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.notification_service import (
    Notification,
    NotificationChannel,
    SlackChannel,
    WebhookChannel,
    EmailChannel,
    LogChannel,
    NotificationService,
)

__all__ = [
    "Notification",
    "NotificationChannel",
    "SlackChannel",
    "WebhookChannel",
    "EmailChannel",
    "LogChannel",
    "NotificationService",
]
