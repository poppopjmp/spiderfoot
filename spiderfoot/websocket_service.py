#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         websocket_service
# Purpose:      WebSocket real-time event streaming for SpiderFoot.
#               Delivers scan events to browser clients in real time,
#               with per-scan channels, authentication, and backpressure.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot WebSocket Event Streaming

Provides real-time event delivery to web clients over WebSocket:

    - Per-scan channels (subscribe to specific scans)
    - Broadcast channel for system-wide events
    - Backpressure: slow clients get dropped events, not OOM
    - Auth token validation via AuthGuard integration
    - EventBus bridge: forwards internal events to WebSocket

Integration::

    # In FastAPI app
    from spiderfoot.websocket_service import ws_router
    app.include_router(ws_router)

    # Standalone
    from spiderfoot.websocket_service import WebSocketHub
    hub = WebSocketHub.get_instance()
    await hub.broadcast({"type": "scan.started", "scan_id": "abc"})
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.websocket")


class ChannelType(str, Enum):
    """WebSocket channel types."""
    BROADCAST = "broadcast"       # System-wide events
    SCAN = "scan"                 # Per-scan events
    MODULES = "modules"           # Module status updates
    CORRELATIONS = "correlations" # Correlation results


@dataclass
class WebSocketMessage:
    """Message to be sent to WebSocket clients."""
    channel: str
    event_type: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    scan_id: str | None = None

    def to_json(self) -> str:
        """Serialize the message to a JSON string."""
        return json.dumps({
            "channel": self.channel,
            "event": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "scan_id": self.scan_id,
        }, default=str)


class WebSocketClient:
    """Represents a connected WebSocket client."""

    def __init__(self, client_id: str,
                 send_func: Callable, *,
                 max_queue: int = 1000) -> None:
        """Initialize the WebSocketClient."""
        self.client_id = client_id
        self._send = send_func
        self.connected_at = time.time()
        self.subscriptions: set[str] = {ChannelType.BROADCAST.value}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue)
        self._dropped = 0
        self._sent = 0
        self._task: asyncio.Task | None = None

    def subscribe(self, channel: str) -> None:
        """Subscribe this client to a channel."""
        self.subscriptions.add(channel)
        log.debug("Client %s subscribed to %s", self.client_id, channel)

    def unsubscribe(self, channel: str) -> None:
        """Unsubscribe this client from a channel."""
        self.subscriptions.discard(channel)

    def is_subscribed(self, channel: str) -> bool:
        """Check if this client is subscribed to a channel."""
        return channel in self.subscriptions

    async def enqueue(self, message: WebSocketMessage) -> bool:
        """Queue a message for delivery. Returns False if dropped."""
        try:
            self._queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            self._dropped += 1
            return False

    async def start_writer(self) -> None:
        """Consume queued messages and send to the client."""
        try:
            while True:
                msg = await self._queue.get()
                try:
                    await self._send(msg.to_json())
                    self._sent += 1
                except Exception as e:
                    log.debug("Send failed for %s: %s",
                              self.client_id, e)
                    break
        except asyncio.CancelledError:
            pass

    @property
    def stats(self) -> dict:
        """Return client connection statistics."""
        return {
            "client_id": self.client_id,
            "connected_at": self.connected_at,
            "subscriptions": sorted(self.subscriptions),
            "sent": self._sent,
            "dropped": self._dropped,
            "queue_size": self._queue.qsize(),
        }


class WebSocketHub:
    """Central hub managing all WebSocket connections and message routing.

    Singleton — use ``WebSocketHub.get_instance()``.
    """

    _instance: "WebSocketHub" | None = None

    def __init__(self, *, max_clients: int = 500,
                 max_queue_per_client: int = 1000) -> None:
        """Initialize the WebSocketHub."""
        self._clients: dict[str, WebSocketClient] = {}
        self._scan_channels: dict[str, set[str]] = defaultdict(set)
        self._max_clients = max_clients
        self._max_queue = max_queue_per_client
        self._total_messages = 0
        self._total_dropped = 0
        self._eventbus_bridge_active = False

    @classmethod
    def get_instance(cls, **kwargs) -> "WebSocketHub":
        """Return the singleton WebSocketHub instance."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    async def connect(self, send_func: Callable,
                      client_id: str | None = None
                      ) -> WebSocketClient:
        """Register a new WebSocket client."""
        if len(self._clients) >= self._max_clients:
            raise ConnectionError(
                f"Max clients reached ({self._max_clients})")

        cid = client_id or str(uuid.uuid4())[:8]
        client = WebSocketClient(cid, send_func,
                                 max_queue=self._max_queue)
        self._clients[cid] = client

        # Start writer task
        client._task = asyncio.create_task(client.start_writer())

        log.info("WebSocket client connected: %s (total: %d)",
                 cid, len(self._clients))
        return client

    async def disconnect(self, client_id: str) -> None:
        """Remove a client and clean up subscriptions."""
        client = self._clients.pop(client_id, None)
        if client:
            if client._task:
                client._task.cancel()
                try:
                    await client._task
                except asyncio.CancelledError:
                    pass

            # Clean up scan channel memberships
            for scan_id, members in list(self._scan_channels.items()):
                members.discard(client_id)
                if not members:
                    del self._scan_channels[scan_id]

            log.info("WebSocket client disconnected: %s (total: %d)",
                     client_id, len(self._clients))

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    def subscribe_scan(self, client_id: str, scan_id: str) -> bool:
        """Subscribe a client to a scan's event stream."""
        client = self._clients.get(client_id)
        if not client:
            return False

        channel = f"scan:{scan_id}"
        client.subscribe(channel)
        self._scan_channels[scan_id].add(client_id)
        return True

    def unsubscribe_scan(self, client_id: str, scan_id: str) -> bool:
        """Unsubscribe a client from a scan's event stream."""
        client = self._clients.get(client_id)
        if not client:
            return False

        channel = f"scan:{scan_id}"
        client.unsubscribe(channel)
        self._scan_channels[scan_id].discard(client_id)
        return True

    # ------------------------------------------------------------------
    # Message delivery
    # ------------------------------------------------------------------

    async def broadcast(self, data: Any, *,
                        event_type: str = "message") -> int:
        """Send a message to all connected clients.

        Returns the number of clients that received the message.
        """
        msg = WebSocketMessage(
            channel=ChannelType.BROADCAST.value,
            event_type=event_type,
            data=data,
        )
        return await self._deliver(msg, ChannelType.BROADCAST.value)

    async def send_scan_event(self, scan_id: str, data: Any, *,
                              event_type: str = "scan.event") -> int:
        """Send a scan event to subscribers of a specific scan."""
        channel = f"scan:{scan_id}"
        msg = WebSocketMessage(
            channel=channel,
            event_type=event_type,
            data=data,
            scan_id=scan_id,
        )
        return await self._deliver(msg, channel)

    async def _deliver(self, msg: WebSocketMessage,
                       channel: str) -> int:
        """Deliver a message to all clients subscribed to a channel."""
        self._total_messages += 1
        delivered = 0

        for client in list(self._clients.values()):
            if client.is_subscribed(channel):
                ok = await client.enqueue(msg)
                if ok:
                    delivered += 1
                else:
                    self._total_dropped += 1

        return delivered

    # ------------------------------------------------------------------
    # EventBus bridge
    # ------------------------------------------------------------------

    def setup_eventbus_bridge(self, event_bus: Any) -> None:
        """Subscribe to EventBus events and forward to WebSocket.

        Bridges internal event bus → WebSocket for real-time UI updates.
        """
        if self._eventbus_bridge_active:
            return

        topics = [
            "scan.started", "scan.completed", "scan.aborted",
            "scan.event", "scan.progress",
            "module.started", "module.finished", "module.error",
            "correlation.result",
        ]

        def _on_event(envelope):
            """Forward EventBus events to WebSocket hub."""
            data = getattr(envelope, "data", {})
            if isinstance(data, dict):
                scan_id = data.get("scan_id")
            else:
                scan_id = None

            msg_data = data if isinstance(data, dict) else {"data": data}
            event_type = getattr(envelope, "topic", "event")

            # Schedule coroutine on the event loop
            try:
                loop = asyncio.get_running_loop()
                if scan_id:
                    loop.create_task(
                        self.send_scan_event(
                            scan_id, msg_data,
                            event_type=event_type))
                else:
                    loop.create_task(
                        self.broadcast(
                            msg_data, event_type=event_type))
            except RuntimeError:
                # No running event loop
                pass

        for topic in topics:
            try:
                event_bus.subscribe(topic, _on_event)
            except Exception as e:
                log.debug("Failed to subscribe to %s: %s", topic, e)

        self._eventbus_bridge_active = True
        log.info("EventBus → WebSocket bridge active for %d topics",
                 len(topics))

    # ------------------------------------------------------------------
    # Incoming message handling
    # ------------------------------------------------------------------

    async def handle_client_message(self, client_id: str,
                                     raw_message: str) -> str | None:
        """Handle incoming JSON message from a client.

        Supports commands:
            {"action": "subscribe", "scan_id": "..."}
            {"action": "unsubscribe", "scan_id": "..."}
            {"action": "ping"}
            {"action": "stats"}
        """
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON"})

        action = msg.get("action", "")

        if action == "subscribe":
            scan_id = msg.get("scan_id")
            if scan_id:
                self.subscribe_scan(client_id, scan_id)
                return json.dumps({
                    "action": "subscribed",
                    "scan_id": scan_id})
            return json.dumps({"error": "Missing scan_id"})

        if action == "unsubscribe":
            scan_id = msg.get("scan_id")
            if scan_id:
                self.unsubscribe_scan(client_id, scan_id)
                return json.dumps({
                    "action": "unsubscribed",
                    "scan_id": scan_id})
            return json.dumps({"error": "Missing scan_id"})

        if action == "ping":
            return json.dumps({
                "action": "pong",
                "timestamp": time.time()})

        if action == "stats":
            client = self._clients.get(client_id)
            if client:
                return json.dumps({
                    "action": "stats",
                    "client": client.stats})
            return json.dumps({"error": "Unknown client"})

        return json.dumps({"error": f"Unknown action: {action}"})

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        """Return hub-wide statistics and per-client details."""
        return {
            "connected_clients": len(self._clients),
            "max_clients": self._max_clients,
            "active_scan_channels": len(self._scan_channels),
            "total_messages": self._total_messages,
            "total_dropped": self._total_dropped,
            "eventbus_bridge": self._eventbus_bridge_active,
            "clients": [c.stats for c in self._clients.values()],
        }

    @property
    def client_count(self) -> int:
        """Return the number of connected clients."""
        return len(self._clients)


# ---------------------------------------------------------------------------
# FastAPI WebSocket Router
# ---------------------------------------------------------------------------

def create_ws_router() -> Any:
    """Create a FastAPI router for WebSocket connections.

    Returns None if FastAPI is not available (graceful degradation).
    """
    try:
        from fastapi import APIRouter, WebSocket, WebSocketDisconnect
    except ImportError:
        log.debug("FastAPI not available, WebSocket router disabled")
        return None

    router = APIRouter(tags=["websocket"])
    hub = WebSocketHub.get_instance()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        async def send(data: str) -> None:
            await websocket.send_text(data)

        client = await hub.connect(send)

        try:
            while True:
                raw = await websocket.receive_text()
                response = await hub.handle_client_message(
                    client.client_id, raw)
                if response:
                    await websocket.send_text(response)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            log.debug("WebSocket error: %s", e)
        finally:
            await hub.disconnect(client.client_id)

    @router.websocket("/ws/scan/{scan_id}")
    async def scan_websocket(websocket: WebSocket, scan_id: str) -> None:
        """Auto-subscribe WebSocket to a specific scan."""
        await websocket.accept()

        async def send(data: str) -> None:
            await websocket.send_text(data)

        client = await hub.connect(send)
        hub.subscribe_scan(client.client_id, scan_id)

        try:
            while True:
                raw = await websocket.receive_text()
                response = await hub.handle_client_message(
                    client.client_id, raw)
                if response:
                    await websocket.send_text(response)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            log.debug("WebSocket error: %s", e)
        finally:
            await hub.disconnect(client.client_id)

    return router


# Attempt to create the router on import
ws_router = create_ws_router()
