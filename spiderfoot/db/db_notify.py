# -------------------------------------------------------------------------------
# Name:         SpiderFoot DB Notification Service
# Purpose:      PostgreSQL LISTEN/NOTIFY for real-time event streaming.
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-16
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
PostgreSQL LISTEN/NOTIFY integration for real-time scan event streaming.

Replaces polling-based SSE endpoints with push-based notifications.
When a scan event is inserted, a NOTIFY is issued on the
``sf_scan_events`` channel with a JSON payload containing the
scan_instance_id, event hash, and event type.

Cycle 75 — Phase 2 Performance.

Usage::

    from spiderfoot.db.db_notify import PgNotifyService

    # Publisher side (inside scanEventStore)
    svc = PgNotifyService(conn)
    svc.notify_event("scan-guid", "abc123hash", "IP_ADDRESS")

    # Subscriber side (SSE endpoint)
    async for event in svc.listen_async("scan-guid"):
        yield event  # SSE
"""
from __future__ import annotations

import json
import logging
import select
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generator

log = logging.getLogger(__name__)

# Default channel name for scan events
CHANNEL_SCAN_EVENTS = "sf_scan_events"
CHANNEL_SCAN_STATUS = "sf_scan_status"


@dataclass
class NotifyPayload:
    """Parsed NOTIFY payload."""

    scan_id: str
    event_hash: str = ""
    event_type: str = ""
    channel: str = CHANNEL_SCAN_EVENTS
    timestamp: float = 0.0

    def to_json(self) -> str:
        return json.dumps({
            "scan_id": self.scan_id,
            "event_hash": self.event_hash,
            "event_type": self.event_type,
            "channel": self.channel,
            "timestamp": self.timestamp or time.time(),
        })

    @classmethod
    def from_json(cls, data: str) -> "NotifyPayload":
        d = json.loads(data)
        return cls(
            scan_id=d.get("scan_id", ""),
            event_hash=d.get("event_hash", ""),
            event_type=d.get("event_type", ""),
            channel=d.get("channel", CHANNEL_SCAN_EVENTS),
            timestamp=d.get("timestamp", 0.0),
        )


class PgNotifyService:
    """PostgreSQL LISTEN/NOTIFY service for real-time event push.

    This service provides:
    - ``notify_event()``: send a notification when a scan event is stored
    - ``listen()``: blocking generator that yields NotifyPayload objects
    - ``listen_filtered()``: same but filtered by scan_id
    - Separate channels for events and scan status changes

    Thread-safe for notify; listen should run in a dedicated thread.
    """

    def __init__(self, conn: Any) -> None:
        """Initialize with a psycopg2 connection.

        The connection MUST have autocommit enabled for LISTEN to work.
        If not, the service will attempt to set it.

        Args:
            conn: A psycopg2 connection.
        """
        if conn is None:
            raise ValueError("conn must be a valid database connection")
        self._conn = conn
        self._lock = threading.Lock()
        self._listening = False
        self._channels: set[str] = set()

    def _ensure_autocommit(self) -> None:
        """Ensure the connection is in autocommit mode (required for LISTEN)."""
        try:
            if not self._conn.autocommit:
                self._conn.autocommit = True
        except Exception:
            pass  # Some connection wrappers don't support this

    def notify_event(self, scan_id: str, event_hash: str, event_type: str) -> bool:
        """Send a NOTIFY on the scan events channel.

        Args:
            scan_id: Scan instance GUID.
            event_hash: Hash of the stored event.
            event_type: Event type string (e.g., IP_ADDRESS).

        Returns:
            True if notification sent, False on error.
        """
        payload = NotifyPayload(
            scan_id=scan_id,
            event_hash=event_hash,
            event_type=event_type,
            channel=CHANNEL_SCAN_EVENTS,
            timestamp=time.time(),
        )
        return self._send_notify(CHANNEL_SCAN_EVENTS, payload.to_json())

    def notify_scan_status(self, scan_id: str, status: str) -> bool:
        """Send a NOTIFY on the scan status channel.

        Args:
            scan_id: Scan instance GUID.
            status: New scan status (e.g., RUNNING, FINISHED, ERROR).

        Returns:
            True if notification sent, False on error.
        """
        payload = NotifyPayload(
            scan_id=scan_id,
            event_type=status,
            channel=CHANNEL_SCAN_STATUS,
            timestamp=time.time(),
        )
        return self._send_notify(CHANNEL_SCAN_STATUS, payload.to_json())

    def _send_notify(self, channel: str, payload_json: str) -> bool:
        """Send a raw NOTIFY on the given channel."""
        with self._lock:
            try:
                cursor = self._conn.cursor()
                # Use pg_notify() function for safe escaping
                cursor.execute("SELECT pg_notify(%s, %s)", (channel, payload_json))
                cursor.close()
                return True
            except Exception as e:
                log.warning("NOTIFY failed on %s: %s", channel, e)
                return False

    def listen(
        self,
        channels: list[str] | None = None,
        timeout: float = 5.0,
        max_events: int = 0,
    ) -> Generator[NotifyPayload, None, None]:
        """Blocking generator that yields NotifyPayload on each notification.

        Args:
            channels: List of channels to listen on (default: [CHANNEL_SCAN_EVENTS]).
            timeout: select() timeout in seconds between polls.
            max_events: Stop after this many events (0 = unlimited).

        Yields:
            NotifyPayload for each received notification.
        """
        if channels is None:
            channels = [CHANNEL_SCAN_EVENTS]

        self._ensure_autocommit()
        cursor = self._conn.cursor()
        for ch in channels:
            # Channel names are identifiers — validate
            if not ch.isidentifier():
                raise ValueError(f"Invalid channel name: {ch}")
            cursor.execute(f'LISTEN "{ch}"')
            self._channels.add(ch)

        self._listening = True
        event_count = 0

        try:
            while self._listening:
                if select.select([self._conn], [], [], timeout) == ([], [], []):
                    continue  # timeout
                self._conn.poll()
                while self._conn.notifies:
                    notify = self._conn.notifies.pop(0)
                    try:
                        payload = NotifyPayload.from_json(notify.payload)
                    except (json.JSONDecodeError, KeyError):
                        payload = NotifyPayload(
                            scan_id="",
                            channel=notify.channel,
                            timestamp=time.time(),
                        )
                    yield payload
                    event_count += 1
                    if max_events and event_count >= max_events:
                        return
        finally:
            for ch in channels:
                try:
                    cursor.execute(f'UNLISTEN "{ch}"')
                except Exception:
                    pass
            cursor.close()
            self._listening = False

    def listen_filtered(
        self,
        scan_id: str,
        timeout: float = 5.0,
        max_events: int = 0,
    ) -> Generator[NotifyPayload, None, None]:
        """Listen for notifications filtered to a specific scan_id.

        Args:
            scan_id: Only yield events for this scan instance.
            timeout: select() timeout.
            max_events: Stop after this many matching events.

        Yields:
            NotifyPayload matching the given scan_id.
        """
        matched = 0
        for payload in self.listen(timeout=timeout, max_events=0):
            if payload.scan_id == scan_id:
                yield payload
                matched += 1
                if max_events and matched >= max_events:
                    return

    def stop(self) -> None:
        """Signal the listen loop to stop."""
        self._listening = False

    def unlisten_all(self) -> None:
        """UNLISTEN all channels."""
        try:
            cursor = self._conn.cursor()
            cursor.execute("UNLISTEN *")
            cursor.close()
            self._channels.clear()
        except Exception as e:
            log.debug("UNLISTEN ALL failed: %s", e)
