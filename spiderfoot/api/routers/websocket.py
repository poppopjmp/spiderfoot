from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..dependencies import get_app_config
from spiderfoot import SpiderFootDb
import json
import time
import logging
from datetime import datetime
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

# WebSocket manager for real-time updates (move from sfapi.py)
class WebSocketManager:
    def __init__(self):
        self.active_connections = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

websocket_manager = WebSocketManager()

@router.websocket("/scans/{scan_id}")
async def websocket_scan_stream(websocket: WebSocket, scan_id: str):
    await websocket_manager.connect(websocket)
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        scan_info = db.scanInstanceGet(scan_id)
        if not scan_info:
            await websocket.send_text(json.dumps({"error": "Scan not found"}))
            return
        last_event_count = 0
        while True:
            current_scan_info = db.scanInstanceGet(scan_id)
            events = db.scanResultEvent(scan_id, ['ALL'])
            if current_scan_info:
                await websocket.send_text(json.dumps({
                    "type": "status_update",
                    "scan_id": scan_id,
                    "status": current_scan_info[6],
                    "event_count": len(events),
                    "timestamp": time.time()
                }))
            if len(events) > last_event_count:
                new_events = events[last_event_count:]
                await websocket.send_text(json.dumps({
                    "type": "new_events",
                    "scan_id": scan_id,
                    "events": [
                        {
                            "event_type": event[4],
                            "data": event[1],
                            "module": event[3],
                            "created": datetime.fromtimestamp(event[0]).isoformat() if event[0] else None
                        } for event in new_events
                    ]
                }))
                last_event_count = len(events)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error for scan {scan_id}: {e}")
