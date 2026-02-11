"""Backward compatibility shim for spiderfoot.event_taxonomy.

Please import from spiderfoot.events.event_taxonomy instead.
"""

from __future__ import annotations

from .events.event_taxonomy import EventCategory, RiskLevel, EventTypeInfo, EventTaxonomy

__all__ = ['EventCategory', 'RiskLevel', 'EventTypeInfo', 'EventTaxonomy']
