"""Backward compatibility shim for spiderfoot.event_dedup.

Please import from spiderfoot.events.event_dedup instead.
"""

from __future__ import annotations

from .events.event_dedup import DedupStrategy, DedupAction, DedupRecord, DedupStats, ContentNormalizer, EventDeduplicator, ScanDeduplicator

__all__ = ['DedupStrategy', 'DedupAction', 'DedupRecord', 'DedupStats', 'ContentNormalizer', 'EventDeduplicator', 'ScanDeduplicator']
