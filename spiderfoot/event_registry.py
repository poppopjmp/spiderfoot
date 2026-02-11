"""Backward compatibility shim for spiderfoot.event_registry.

Please import from spiderfoot.events.event_registry instead.
"""

from __future__ import annotations

from .events.event_registry import EventTypeMeta, ModuleNode, EventTypeRegistry

__all__ = ['EventTypeMeta', 'ModuleNode', 'EventTypeRegistry']
