"""Backward compatibility shim for spiderfoot.event_relay.

Please import from spiderfoot.events.event_relay instead.
"""

from __future__ import annotations

from .events.event_relay import RelayEvent, EventRelay

__all__ = ['RelayEvent', 'EventRelay']
