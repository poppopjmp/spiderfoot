"""
WebSocket Router for SpiderFoot — real-time scan event streaming.

Provides WebSocket endpoints for streaming scan events to clients.
Uses the :class:`EventRelay` for push-based delivery when available,
falling back to database polling otherwise.

Endpoints:
  ws://.../ws/scans/{scan_id}  — Stream scan events in real-time
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..dependencies import get_app_config
import json
import time
import logging
from datetime import datetime
import asyncio

router = APIRouter()
log = logging.getLogger("spiderfoot.api.websocket")


class WebSocketManager:
    """Manages active WebSocket connections per scan.

    Thread-safe connection tracking with per-scan grouping,
    heartbeat support, and graceful disconnect handling.
    """

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, scan_id: str) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if scan_id not in self._connections:
                self._connections[scan_id] = set()
            self._connections[scan_id].add(websocket)
        log.info(
            "WebSocket connected: scan=%s (total=%d)",
            scan_id, self.connection_count(scan_id),
        )

    async def disconnect(self, websocket: WebSocket, scan_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            conns = self._connections.get(scan_id)
            if conns:
                conns.discard(websocket)
                if not conns:
                    del self._connections[scan_id]
        log.info("WebSocket disconnected: scan=%s", scan_id)

    async def send_to_scan(self, scan_id: str, message: dict) -> int:
        """Send a message to all WebSocket clients watching a scan.

        Returns the number of clients that received the message.
        """
        async with self._lock:
            conns = list(self._connections.get(scan_id, set()))

        text = json.dumps(message, default=str)
        delivered = 0
        failed = []
        for ws in conns:
            try:
                await ws.send_text(text)
                delivered += 1
            except Exception:
                failed.append(ws)

        # Clean up failed connections
        if failed:
            async with self._lock:
                conns_set = self._connections.get(scan_id)
                if conns_set:
                    for ws in failed:
                        conns_set.discard(ws)
                    if not conns_set:
                        del self._connections[scan_id]

        return delivered

    async def broadcast(self, message: dict) -> int:
        """Send a message to ALL connected clients."""
        async with self._lock:
            all_scan_ids = list(self._connections.keys())

        total = 0
        for sid in all_scan_ids:
            total += await self.send_to_scan(sid, message)
        return total

    def connection_count(self, scan_id: str | None = None) -> int:
        """Count active connections."""
        if scan_id:
            return len(self._connections.get(scan_id, set()))
        return sum(len(s) for s in self._connections.values())

    def active_scans(self) -> list[str]:
        """List scan IDs with active WebSocket connections."""
        return list(self._connections.keys())


websocket_manager = WebSocketManager()


async def _relay_mode(websocket: WebSocket, scan_id: str) -> None:
    """Event relay push mode — no database polling.

    Registers a consumer queue with the EventRelay and forwards
    events to the WebSocket client.
    """
    from spiderfoot.event_relay import get_event_relay

    relay = get_event_relay()
    queue = relay.register_consumer(scan_id)

    try:
        # Try to subscribe to EventBus for this scan
        try:
            await relay.subscribe_scan(scan_id)
        except Exception as e:
            log.debug("EventBus subscription not available: %s", e)

        while True:
            try:
                # Wait for events with timeout for keepalive
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                await websocket.send_text(json.dumps(event, default=str))

                # Check for scan completion
                if event.get("type") in ("scan_completed", "scan_error"):
                    # Send final message and close
                    await websocket.send_text(json.dumps({
                        "type": "stream_end",
                        "scan_id": scan_id,
                        "reason": "scan_completed",
                        "timestamp": time.time(),
                    }))
                    break

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                try:
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat",
                        "scan_id": scan_id,
                        "timestamp": time.time(),
                    }))
                except Exception:
                    break

            except WebSocketDisconnect:
                raise

    finally:
        relay.unregister_consumer(scan_id, queue)
        # Unsubscribe from EventBus if no more consumers for this scan
        if not relay.has_consumers(scan_id):
            try:
                await relay.unsubscribe_scan(scan_id)
            except Exception:
                pass


async def _polling_mode(websocket: WebSocket, scan_id: str) -> None:
    """Database polling fallback mode.

    Polls the database every 2 seconds for new events via
    ``ScanService``. Used when EventRelay has no EventBus wired or
    as a backward-compatible fallback.
    """
    try:
        from spiderfoot.db.repositories import (
            get_repository_factory,
            RepositoryFactory,
        )
        from spiderfoot.scan_service_facade import ScanService

        config = get_app_config()
        factory = get_repository_factory()
        if factory is None:
            factory = RepositoryFactory(config.get_config())
        repo = factory.scan_repo()
        svc = ScanService(repo, dbh=repo._dbh)
    except Exception as e:
        await websocket.send_text(json.dumps({
            "error": f"Service not available: {e}",
        }))
        return

    scan_record = svc.get_scan(scan_id)
    if not scan_record:
        await websocket.send_text(json.dumps({
            "error": "Scan not found",
            "scan_id": scan_id,
        }))
        svc.close()
        return

    last_event_count = 0

    try:
        while True:
            try:
                current_record = svc.get_scan(scan_id)
                events = svc.get_events(scan_id)

                if current_record:
                    status = current_record.status
                    await websocket.send_text(json.dumps({
                        "type": "status_update",
                        "scan_id": scan_id,
                        "data": {
                            "status": status,
                            "event_count": len(events),
                        },
                        "timestamp": time.time(),
                    }))

                    # Check if scan is done
                    if status in (DB_STATUS_FINISHED, DB_STATUS_ABORTED, DB_STATUS_ERROR_FAILED):
                        await websocket.send_text(json.dumps({
                            "type": "stream_end",
                            "scan_id": scan_id,
                            "reason": "scan_completed",
                            "timestamp": time.time(),
                        }))
                        break

                if len(events) > last_event_count:
                    new_events = events[last_event_count:]
                    await websocket.send_text(json.dumps({
                        "type": "new_events",
                        "scan_id": scan_id,
                        "data": {
                            "events": [
                                {
                                    "event_type": event[4],
                                    "data": event[1],
                                    "module": event[3],
                                    "created": (
                                        datetime.fromtimestamp(event[0]).isoformat()
                                        if event[0] else None
                                    ),
                                }
                                for event in new_events
                            ],
                        },
                        "timestamp": time.time(),
                    }))
                    last_event_count = len(events)

            except WebSocketDisconnect:
                raise
            except Exception as e:
                log.error("Polling error for scan %s: %s", scan_id, e)

            await asyncio.sleep(2)
    finally:
        svc.close()


@router.websocket("/scans/{scan_id}")
async def websocket_scan_stream(websocket: WebSocket, scan_id: str):
    """Stream scan events over WebSocket.

    Uses EventRelay push mode if the relay has an EventBus wired.
    Falls back to database polling otherwise.
    """
    await websocket_manager.connect(websocket, scan_id)

    try:
        # Decide mode: relay (push) vs polling
        use_relay = False
        try:
            from spiderfoot.event_relay import get_event_relay
            relay = get_event_relay()
from spiderfoot.scan_state_map import (
    DB_STATUS_ABORTED,
    DB_STATUS_ERROR_FAILED,
    DB_STATUS_FINISHED,
)

            # Use relay mode if EventBus is wired, or if there are
            # already consumers (events being pushed manually)
            use_relay = relay._eventbus is not None or relay.has_consumers(scan_id)
        except ImportError:
            pass

        if use_relay:
            log.info("Using relay mode for scan %s", scan_id)
            await _relay_mode(websocket, scan_id)
        else:
            log.info("Using polling mode for scan %s", scan_id)
            await _polling_mode(websocket, scan_id)

    except WebSocketDisconnect:
        log.info("Client disconnected: scan=%s", scan_id)
    except Exception as e:
        log.error("WebSocket error for scan %s: %s", scan_id, e)
    finally:
        await websocket_manager.disconnect(websocket, scan_id)
