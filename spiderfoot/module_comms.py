"""Backward-compatibility shim for module_comms.py.

This module re-exports from plugins/module_comms.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_comms import (
    ChannelStats,
    Message,
    MessageBus,
    MessagePriority,
    get_message_bus,
)

__all__ = [
    "ChannelStats",
    "Message",
    "MessageBus",
    "MessagePriority",
    "get_message_bus",
]
