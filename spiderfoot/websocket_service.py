"""Backward-compatibility shim for websocket_service.py.

This module re-exports from services/websocket_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.websocket_service import (
    ChannelType,
    WebSocketMessage,
    WebSocketClient,
    WebSocketHub,
    create_ws_router,
)

__all__ = [
    "ChannelType",
    "WebSocketMessage",
    "WebSocketClient",
    "WebSocketHub",
    "create_ws_router",
]
