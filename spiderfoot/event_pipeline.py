"""Event Pipeline for SpiderFoot.

Composable event processing pipeline with typed stages for
transformation, validation, enrichment, and routing.
Supports async-compatible middleware pattern with error isolation.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.event_pipeline")


class StageResult(Enum):
    """Result of a pipeline stage."""
    CONTINUE = "continue"   # Pass to next stage
    DROP = "drop"           # Drop the event
    ERROR = "error"         # Error occurred


@dataclass
class PipelineEvent:
    """Event flowing through the pipeline."""
    event_type: str
    data: str
    module: str = ""
    source_event: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    _dropped: bool = False
    _drop_reason: str = ""

    def drop(self, reason: str = "") -> None:
        self._dropped = True
        self._drop_reason = reason

    @property
    def is_dropped(self) -> bool:
        return self._dropped

    @property
    def drop_reason(self) -> str:
        return self._drop_reason


@dataclass
class StageStats:
    """Statistics for a pipeline stage."""
    name: str
    processed: int = 0
    passed: int = 0
    dropped: int = 0
    errors: int = 0
    total_time: float = 0.0

    @property
    def avg_time(self) -> float:
        return self.total_time / self.processed if self.processed > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "processed": self.processed,
            "passed": self.passed,
            "dropped": self.dropped,
            "errors": self.errors,
            "avg_time_ms": round(self.avg_time * 1000, 3),
        }


class PipelineStage(ABC):
    """Base class for pipeline stages."""

    def __init__(self, name: str = "", enabled: bool = True) -> None:
        self.name = name or self.__class__.__name__
        self._enabled = enabled
        self._stats = StageStats(name=self.name)

    @abstractmethod
    def process(self, event: PipelineEvent) -> StageResult:
        """Process an event. Return CONTINUE, DROP, or ERROR."""
        ...

    @property
    def stats(self) -> StageStats:
        return self._stats

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False


class FunctionStage(PipelineStage):
    """Stage wrapping a callable."""

    def __init__(self, func: Callable[[PipelineEvent], StageResult], name: str = "") -> None:
        super().__init__(name=name or getattr(func, "__name__", "function_stage"))
        self._func = func

    def process(self, event: PipelineEvent) -> StageResult:
        return self._func(event)


class ValidatorStage(PipelineStage):
    """Validates events and drops invalid ones."""

    def __init__(
        self,
        allowed_types: set[str] | None = None,
        max_data_size: int | None = None,
        name: str = "validator",
    ) -> None:
        super().__init__(name=name)
        self.allowed_types = allowed_types
        self.max_data_size = max_data_size

    def process(self, event: PipelineEvent) -> StageResult:
        if self.allowed_types and event.event_type not in self.allowed_types:
            event.drop(f"Type '{event.event_type}' not allowed")
            return StageResult.DROP
        if self.max_data_size and len(event.data) > self.max_data_size:
            event.drop(f"Data exceeds {self.max_data_size} bytes")
            return StageResult.DROP
        return StageResult.CONTINUE


class TransformStage(PipelineStage):
    """Transforms event data using a function."""

    def __init__(
        self,
        transform: Callable[[str], str],
        name: str = "transform",
    ) -> None:
        super().__init__(name=name)
        self._transform = transform

    def process(self, event: PipelineEvent) -> StageResult:
        try:
            event.data = self._transform(event.data)
            return StageResult.CONTINUE
        except Exception as e:
            log.error("Transform '%s' error: %s", self.name, e)
            return StageResult.ERROR


class TaggingStage(PipelineStage):
    """Adds tags to events based on rules."""

    def __init__(self, rules: dict[str, str] | None = None, name: str = "tagger") -> None:
        super().__init__(name=name)
        self._rules: dict[str, str] = rules or {}

    def add_rule(self, pattern: str, tag: str) -> "TaggingStage":
        self._rules[pattern] = tag
        return self

    def process(self, event: PipelineEvent) -> StageResult:
        for pattern, tag in self._rules.items():
            if pattern in event.event_type or pattern in event.data:
                event.tags.add(tag)
        return StageResult.CONTINUE


class RouterStage(PipelineStage):
    """Routes events to named destinations based on predicates."""

    def __init__(self, name: str = "router") -> None:
        super().__init__(name=name)
        self._routes: list[tuple[Callable[[PipelineEvent], bool], str]] = []

    def add_route(self, predicate: Callable[[PipelineEvent], bool], destination: str) -> "RouterStage":
        self._routes.append((predicate, destination))
        return self

    def process(self, event: PipelineEvent) -> StageResult:
        for predicate, destination in self._routes:
            if predicate(event):
                event.metadata.setdefault("_routes", []).append(destination)
        return StageResult.CONTINUE


class EventPipeline:
    """Composable event processing pipeline.

    Events flow through stages sequentially. Each stage can
    transform, validate, tag, route, or drop events.

    Usage:
        pipeline = EventPipeline("main")
        pipeline.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS", "DOMAIN_NAME"}))
        pipeline.add_stage(TaggingStage({"MALICIOUS": "threat"}))

        event = PipelineEvent(event_type="IP_ADDRESS", data="1.2.3.4")
        result = pipeline.execute(event)
    """

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._stages: list[PipelineStage] = []
        self._error_handlers: list[Callable[[PipelineEvent, PipelineStage, Exception], None]] = []
        self._lock = threading.Lock()
        self._total_processed = 0
        self._total_passed = 0
        self._total_dropped = 0
        self._total_errors = 0

    def add_stage(self, stage: PipelineStage) -> "EventPipeline":
        with self._lock:
            self._stages.append(stage)
        return self

    def remove_stage(self, stage_name: str) -> bool:
        with self._lock:
            before = len(self._stages)
            self._stages = [s for s in self._stages if s.name != stage_name]
            return len(self._stages) < before

    def on_error(self, handler: Callable[[PipelineEvent, PipelineStage, Exception], None]) -> None:
        self._error_handlers.append(handler)

    def execute(self, event: PipelineEvent) -> StageResult:
        """Execute the pipeline on a single event."""
        self._total_processed += 1

        with self._lock:
            stages = list(self._stages)

        for stage in stages:
            if not stage.is_enabled:
                continue

            start = time.monotonic()
            stage._stats.processed += 1

            try:
                result = stage.process(event)
            except Exception as e:
                elapsed = time.monotonic() - start
                stage._stats.total_time += elapsed
                stage._stats.errors += 1
                self._total_errors += 1
                log.error("Pipeline stage '%s' error: %s", stage.name, e)
                for handler in self._error_handlers:
                    try:
                        handler(event, stage, e)
                    except Exception as e2:
                        log.debug("error handler handler(event, stage, e) failed: %s", e2)
                continue

            elapsed = time.monotonic() - start
            stage._stats.total_time += elapsed

            if result == StageResult.DROP:
                stage._stats.dropped += 1
                self._total_dropped += 1
                return StageResult.DROP
            elif result == StageResult.ERROR:
                stage._stats.errors += 1
                self._total_errors += 1
                continue
            else:
                stage._stats.passed += 1

        self._total_passed += 1
        return StageResult.CONTINUE

    def execute_batch(self, events: list[PipelineEvent]) -> list[tuple[PipelineEvent, StageResult]]:
        """Execute the pipeline on multiple events."""
        return [(event, self.execute(event)) for event in events]

    @property
    def stage_count(self) -> int:
        with self._lock:
            return len(self._stages)

    def get_stage_names(self) -> list[str]:
        with self._lock:
            return [s.name for s in self._stages]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "stages": len(self._stages),
                "total_processed": self._total_processed,
                "total_passed": self._total_passed,
                "total_dropped": self._total_dropped,
                "total_errors": self._total_errors,
                "stage_stats": [s.stats.to_dict() for s in self._stages],
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._total_processed = 0
            self._total_passed = 0
            self._total_dropped = 0
            self._total_errors = 0
            for s in self._stages:
                s._stats = StageStats(name=s.name)

    def to_dict(self) -> dict:
        return self.get_stats()
