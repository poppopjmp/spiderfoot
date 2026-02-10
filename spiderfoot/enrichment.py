"""Event Enrichment Pipeline for SpiderFoot.

Provides a composable pipeline for enriching events with additional
context, metadata, and derived data. Enrichers can be chained,
filtered, and configured per event type.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.enrichment")


class EnrichmentPriority(Enum):
    """Priority levels for enrichment ordering."""
    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 80
    DEFERRED = 100


@dataclass
class EnrichmentContext:
    """Context passed through the enrichment pipeline."""
    event_type: str
    data: str
    module: str = ""
    scan_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    enrichments: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    skip_remaining: bool = False  # If True, stop pipeline early
    _timings: dict[str, float] = field(default_factory=dict)

    def add_enrichment(self, key: str, value: Any) -> None:
        """Add an enrichment result."""
        self.enrichments[key] = value

    def add_tag(self, tag: str) -> None:
        """Add a classification tag."""
        self.tags.add(tag)

    def has_enrichment(self, key: str) -> bool:
        return key in self.enrichments

    def get_enrichment(self, key: str, default: Any = None) -> Any:
        return self.enrichments.get(key, default)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "module": self.module,
            "scan_id": self.scan_id,
            "metadata": dict(self.metadata),
            "enrichments": dict(self.enrichments),
            "tags": sorted(self.tags),
            "timings": dict(self._timings),
        }


class Enricher(ABC):
    """Base class for event enrichers."""

    def __init__(
        self,
        name: str = "",
        priority: EnrichmentPriority = EnrichmentPriority.NORMAL,
        event_types: set[str] | None = None,
    ) -> None:
        self.name = name or self.__class__.__name__
        self.priority = priority
        self.event_types = event_types  # None = all types
        self._enabled = True
        self._call_count = 0
        self._error_count = 0
        self._total_time = 0.0

    @abstractmethod
    def enrich(self, ctx: EnrichmentContext) -> EnrichmentContext:
        """Enrich the context. Must return the context (possibly modified)."""
        ...

    def accepts(self, event_type: str) -> bool:
        """Check if this enricher handles the given event type."""
        if self.event_types is None:
            return True
        return event_type in self.event_types

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def stats(self) -> dict:
        return {
            "name": self.name,
            "calls": self._call_count,
            "errors": self._error_count,
            "total_time_ms": round(self._total_time * 1000, 2),
            "avg_time_ms": round(
                (self._total_time / self._call_count * 1000) if self._call_count > 0 else 0, 2
            ),
        }


class FunctionEnricher(Enricher):
    """Enricher that wraps a plain function."""

    def __init__(
        self,
        func: Callable[[EnrichmentContext], EnrichmentContext],
        name: str = "",
        priority: EnrichmentPriority = EnrichmentPriority.NORMAL,
        event_types: set[str] | None = None,
    ) -> None:
        super().__init__(name=name or func.__name__, priority=priority, event_types=event_types)
        self._func = func

    def enrich(self, ctx: EnrichmentContext) -> EnrichmentContext:
        return self._func(ctx)


class EnrichmentPipeline:
    """Composable pipeline for event enrichment.

    Usage:
        pipeline = EnrichmentPipeline()

        # Add enrichers
        pipeline.add(GeoIPEnricher())
        pipeline.add(ThreatIntelEnricher(), priority=EnrichmentPriority.HIGH)

        # Or use decorator
        @pipeline.enricher(event_types={"IP_ADDRESS"})
        def add_asn(ctx):
            ctx.add_enrichment("asn", "AS1234")
            return ctx

        # Process events
        ctx = EnrichmentContext(event_type="IP_ADDRESS", data="1.2.3.4")
        result = pipeline.process(ctx)
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._enrichers: list[Enricher] = []
        self._lock = threading.Lock()
        self._total_processed = 0
        self._total_errors = 0
        self._error_handlers: list[Callable] = []

    def add(
        self,
        enricher: Enricher,
        priority: EnrichmentPriority | None = None,
    ) -> "EnrichmentPipeline":
        """Add an enricher to the pipeline (chainable)."""
        if priority is not None:
            enricher.priority = priority
        with self._lock:
            self._enrichers.append(enricher)
            self._enrichers.sort(key=lambda e: e.priority.value)
        return self

    def add_function(
        self,
        func: Callable[[EnrichmentContext], EnrichmentContext],
        name: str = "",
        priority: EnrichmentPriority = EnrichmentPriority.NORMAL,
        event_types: set[str] | None = None,
    ) -> "EnrichmentPipeline":
        """Add a function as an enricher (chainable)."""
        return self.add(FunctionEnricher(func, name, priority, event_types))

    def enricher(
        self,
        name: str = "",
        priority: EnrichmentPriority = EnrichmentPriority.NORMAL,
        event_types: set[str] | None = None,
    ):
        """Decorator to register a function as an enricher."""
        def decorator(func):
            self.add_function(func, name=name or func.__name__, priority=priority, event_types=event_types)
            return func
        return decorator

    def remove(self, enricher_name: str) -> bool:
        """Remove an enricher by name."""
        with self._lock:
            before = len(self._enrichers)
            self._enrichers = [e for e in self._enrichers if e.name != enricher_name]
            return len(self._enrichers) < before

    def process(self, ctx: EnrichmentContext) -> EnrichmentContext:
        """Run the event through the pipeline."""
        with self._lock:
            enrichers = list(self._enrichers)

        self._total_processed += 1

        for enricher in enrichers:
            if ctx.skip_remaining:
                break
            if not enricher.is_enabled:
                continue
            if not enricher.accepts(ctx.event_type):
                continue

            start = time.time()
            try:
                ctx = enricher.enrich(ctx)
                enricher._call_count += 1
            except Exception as e:
                enricher._error_count += 1
                self._total_errors += 1
                log.error("Enricher '%s' error: %s", enricher.name, e)
                self._fire_error_handlers(enricher, ctx, e)
            finally:
                elapsed = time.time() - start
                enricher._total_time += elapsed
                ctx._timings[enricher.name] = elapsed

        return ctx

    def process_batch(
        self, contexts: list[EnrichmentContext]
    ) -> list[EnrichmentContext]:
        """Process multiple events through the pipeline."""
        return [self.process(ctx) for ctx in contexts]

    def on_error(self, handler: Callable) -> None:
        """Register an error handler.

        Signature: handler(enricher, context, exception)
        """
        self._error_handlers.append(handler)

    def _fire_error_handlers(
        self, enricher: Enricher, ctx: EnrichmentContext, exc: Exception
    ) -> None:
        for handler in self._error_handlers:
            try:
                handler(enricher, ctx, exc)
            except Exception as e:
                log.error("Error handler failed: %s", e)

    @property
    def enricher_count(self) -> int:
        with self._lock:
            return len(self._enrichers)

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        with self._lock:
            return {
                "name": self.name,
                "enricher_count": len(self._enrichers),
                "total_processed": self._total_processed,
                "total_errors": self._total_errors,
                "enrichers": [e.stats for e in self._enrichers],
            }

    def get_enricher_names(self) -> list[str]:
        with self._lock:
            return [e.name for e in self._enrichers]

    def list_enrichers(self) -> list[dict]:
        """List all enrichers with their configuration."""
        with self._lock:
            return [
                {
                    "name": e.name,
                    "priority": e.priority.value,
                    "enabled": e.is_enabled,
                    "event_types": sorted(e.event_types) if e.event_types else None,
                    "stats": e.stats,
                }
                for e in self._enrichers
            ]


# Pre-built enrichers for common patterns

class TagEnricher(Enricher):
    """Adds tags based on event type patterns."""

    TAG_RULES = {
        "MALICIOUS_": "threat",
        "VULNERABILITY_": "vulnerability",
        "IP_ADDRESS": "network",
        "EMAILADDR": "identity",
        "DOMAIN_NAME": "infrastructure",
        "URL_": "web",
        "SSL_CERTIFICATE_": "certificate",
        "DNS_": "dns",
        "PHONE_NUMBER": "identity",
        "HUMAN_NAME": "identity",
        "COMPANY_NAME": "identity",
    }

    def __init__(self) -> None:
        super().__init__(
            name="tag_enricher",
            priority=EnrichmentPriority.CRITICAL,
        )

    def enrich(self, ctx: EnrichmentContext) -> EnrichmentContext:
        for pattern, tag in self.TAG_RULES.items():
            if ctx.event_type.startswith(pattern) or ctx.event_type == pattern:
                ctx.add_tag(tag)
        return ctx


class DataSizeEnricher(Enricher):
    """Adds data size metadata."""

    def __init__(self) -> None:
        super().__init__(
            name="data_size_enricher",
            priority=EnrichmentPriority.CRITICAL,
        )

    def enrich(self, ctx: EnrichmentContext) -> EnrichmentContext:
        ctx.add_enrichment("data_length", len(ctx.data))
        ctx.add_enrichment("data_is_empty", len(ctx.data.strip()) == 0)
        return ctx


def create_default_pipeline() -> EnrichmentPipeline:
    """Create an enrichment pipeline with standard enrichers."""
    pipeline = EnrichmentPipeline(name="default")
    pipeline.add(TagEnricher())
    pipeline.add(DataSizeEnricher())
    return pipeline
