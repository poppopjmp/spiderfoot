"""SpiderFoot events package.

This package contains all event-related functionality:
- Event creation and management
- Event deduplication
- Event filtering
- Event indexing
- Event pipeline processing
- Event registry
- Event relay
- Event storage
- Event taxonomy definitions
"""

from __future__ import annotations

# Core event class
from .event import SpiderFootEvent

# Deduplication
from .event_dedup import (
    DedupStrategy,
    DedupAction,
    DedupRecord,
    DedupStats,
    ContentNormalizer,
    EventDeduplicator,
    ScanDeduplicator,
)

# Filtering
from .event_filter import (
    FilterAction,
    FilterResult,
    FilterStats,
    EventFilter,
    TypeFilter,
    PatternFilter,
    RiskFilter,
    PredicateFilter,
    ModuleFilter,
    EventFilterChain,
)

# Indexing
from .event_indexer import (
    IndexerConfig,
    IndexerMetrics,
    BatchWriter,
    EventIndexer,
)

# Pipeline
from .event_pipeline import (
    StageResult,
    PipelineEvent,
    StageStats,
    PipelineStage,
    FunctionStage,
    ValidatorStage,
    TransformStage,
    TaggingStage,
    RouterStage,
    EventPipeline,
)

# Registry
from .event_registry import EventTypeMeta, ModuleNode, EventTypeRegistry

# Relay
from .event_relay import RelayEvent, EventRelay

# Store
from .event_store import (
    EventPriority,
    StoredEvent,
    EventQuery,
    RetentionPolicy,
    EventStore,
)

# Taxonomy
from .event_taxonomy import EventCategory, RiskLevel, EventTypeInfo, EventTaxonomy

__all__ = [
    # Core
    "SpiderFootEvent",
    # Deduplication
    "DedupStrategy",
    "DedupAction",
    "DedupRecord",
    "DedupStats",
    "ContentNormalizer",
    "EventDeduplicator",
    "ScanDeduplicator",
    # Filtering
    "FilterAction",
    "FilterResult",
    "FilterStats",
    "EventFilter",
    "TypeFilter",
    "PatternFilter",
    "RiskFilter",
    "PredicateFilter",
    "ModuleFilter",
    "EventFilterChain",
    # Indexing
    "IndexerConfig",
    "IndexerMetrics",
    "BatchWriter",
    "EventIndexer",
    # Pipeline
    "StageResult",
    "PipelineEvent",
    "StageStats",
    "PipelineStage",
    "FunctionStage",
    "ValidatorStage",
    "TransformStage",
    "TaggingStage",
    "RouterStage",
    "EventPipeline",
    # Registry
    "EventTypeMeta",
    "ModuleNode",
    "EventTypeRegistry",
    # Relay
    "RelayEvent",
    "EventRelay",
    # Store
    "EventPriority",
    "StoredEvent",
    "EventQuery",
    "RetentionPolicy",
    "EventStore",
    # Taxonomy
    "EventCategory",
    "RiskLevel",
    "EventTypeInfo",
    "EventTaxonomy",
]
