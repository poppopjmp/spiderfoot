"""Backward compatibility shim for spiderfoot.event_indexer.

Please import from spiderfoot.events.event_indexer instead.
"""

from __future__ import annotations

from .events.event_indexer import IndexerConfig, IndexerMetrics, BatchWriter, EventIndexer

__all__ = ['IndexerConfig', 'IndexerMetrics', 'BatchWriter', 'EventIndexer']
