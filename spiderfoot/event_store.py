"""Backward compatibility shim for spiderfoot.event_store.

Please import from spiderfoot.events.event_store instead.
"""

from __future__ import annotations

from .events.event_store import EventPriority, StoredEvent, EventQuery, RetentionPolicy, EventStore

__all__ = ['EventPriority', 'StoredEvent', 'EventQuery', 'RetentionPolicy', 'EventStore']
