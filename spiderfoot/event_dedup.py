"""Event Deduplication Engine for SpiderFoot.

Detects and filters duplicate events during scan processing using
content hashing, fuzzy matching, and configurable dedup strategies.
"""

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.event_dedup")


class DedupStrategy(Enum):
    """Deduplication strategy."""
    EXACT = "exact"           # Exact content match
    NORMALIZED = "normalized"  # Normalize whitespace/case before comparing
    SEMANTIC = "semantic"      # Content-aware (e.g., same IP in different formats)


class DedupAction(Enum):
    """Action to take on duplicate detection."""
    DROP = "drop"          # Silently discard
    MERGE = "merge"        # Merge into existing event (increment count)
    TAG = "tag"            # Allow but tag as duplicate


@dataclass
class DedupRecord:
    """Tracks a unique event occurrence."""
    event_type: str
    content_hash: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    count: int = 1
    modules: Set[str] = field(default_factory=set)
    original_data: str = ""

    def touch(self, module: str = "") -> None:
        """Record another occurrence."""
        self.last_seen = time.time()
        self.count += 1
        if module:
            self.modules.add(module)


@dataclass
class DedupStats:
    """Deduplication statistics."""
    total_events: int = 0
    unique_events: int = 0
    duplicates_found: int = 0
    duplicates_by_type: Dict[str, int] = field(default_factory=dict)
    duplicates_by_module: Dict[str, int] = field(default_factory=dict)

    @property
    def dedup_rate(self) -> float:
        """Percentage of events that were duplicates."""
        if self.total_events == 0:
            return 0.0
        return (self.duplicates_found / self.total_events) * 100

    def to_dict(self) -> dict:
        return {
            "total_events": self.total_events,
            "unique_events": self.unique_events,
            "duplicates_found": self.duplicates_found,
            "dedup_rate_pct": round(self.dedup_rate, 2),
            "duplicates_by_type": dict(self.duplicates_by_type),
            "duplicates_by_module": dict(self.duplicates_by_module),
        }


class ContentNormalizer:
    """Normalizes event content for comparison."""

    @staticmethod
    def normalize(event_type: str, data: str) -> str:
        """Normalize content based on event type."""
        if not data:
            return ""

        normalized = data.strip()

        # IP address normalization
        if "IP_ADDRESS" in event_type:
            normalized = ContentNormalizer._normalize_ip(normalized)
        # Email normalization
        elif "EMAILADDR" in event_type:
            normalized = normalized.lower().strip()
        # URL normalization
        elif "URL" in event_type or "INTERNET_NAME" in event_type:
            normalized = ContentNormalizer._normalize_url(normalized)
        # Domain normalization
        elif "DOMAIN" in event_type:
            normalized = normalized.lower().strip().rstrip(".")
        # General text normalization
        else:
            normalized = " ".join(normalized.lower().split())

        return normalized

    @staticmethod
    def _normalize_ip(ip: str) -> str:
        """Normalize IP address representation."""
        ip = ip.strip()
        # Handle IPv4 with leading zeros
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                return ".".join(str(int(p)) for p in parts)
            except ValueError:
                pass
        return ip.lower()

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for comparison."""
        url = url.lower().strip()
        # Remove default ports
        url = url.replace(":80/", "/").replace(":443/", "/")
        url = url.replace(":80", "").replace(":443", "")
        # Remove fragment
        if "#" in url:
            url = url.split("#")[0]
        # Remove trailing slash
        url = url.rstrip("/")
        return url


class EventDeduplicator:
    """Main deduplication engine for scan events.

    Thread-safe deduplication with configurable strategies and actions.

    Usage:
        dedup = EventDeduplicator(strategy=DedupStrategy.NORMALIZED)
        is_dup = dedup.check("IP_ADDRESS", "192.168.1.1", module="sfp_dns")
        if not is_dup:
            # Process the event
            pass
    """

    def __init__(
        self,
        strategy: DedupStrategy = DedupStrategy.EXACT,
        action: DedupAction = DedupAction.DROP,
        scope: str = "global",
        max_records: int = 100000,
    ):
        self.strategy = strategy
        self.action = action
        self.scope = scope  # "global", "per_module", "per_type"
        self.max_records = max_records

        self._records: Dict[str, DedupRecord] = {}
        self._lock = threading.Lock()
        self._stats = DedupStats()
        self._callbacks: List[Callable] = []
        self._enabled = True
        self._normalizer = ContentNormalizer()

    def check(
        self,
        event_type: str,
        data: str,
        module: str = "",
    ) -> bool:
        """Check if an event is a duplicate.

        Returns True if the event is a duplicate, False if it's new.
        """
        if not self._enabled:
            return False

        content_hash = self._compute_hash(event_type, data, module)

        with self._lock:
            self._stats.total_events += 1

            if content_hash in self._records:
                # Duplicate found
                record = self._records[content_hash]
                record.touch(module)
                self._stats.duplicates_found += 1
                self._stats.duplicates_by_type[event_type] = (
                    self._stats.duplicates_by_type.get(event_type, 0) + 1
                )
                if module:
                    self._stats.duplicates_by_module[module] = (
                        self._stats.duplicates_by_module.get(module, 0) + 1
                    )

                self._fire_callbacks(event_type, data, module, record)
                return True

            # New unique event
            if len(self._records) < self.max_records:
                self._records[content_hash] = DedupRecord(
                    event_type=event_type,
                    content_hash=content_hash,
                    modules={module} if module else set(),
                    original_data=data[:500],  # Store truncated for reference
                )
            self._stats.unique_events += 1
            return False

    def check_batch(
        self,
        events: List[Tuple[str, str, str]],
    ) -> List[bool]:
        """Check multiple events at once.

        Args:
            events: List of (event_type, data, module) tuples.

        Returns:
            List of booleans, True if duplicate.
        """
        return [self.check(et, d, m) for et, d, m in events]

    def _compute_hash(self, event_type: str, data: str, module: str) -> str:
        """Compute content hash based on strategy and scope."""
        if self.strategy == DedupStrategy.NORMALIZED:
            content = self._normalizer.normalize(event_type, data)
        elif self.strategy == DedupStrategy.SEMANTIC:
            content = self._normalizer.normalize(event_type, data)
        else:  # EXACT
            content = data

        # Build hash key based on scope
        if self.scope == "per_module":
            key = f"{event_type}:{module}:{content}"
        elif self.scope == "per_type":
            key = f"{event_type}:{content}"
        else:  # global
            key = f"{event_type}:{content}"

        return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()

    def get_record(self, event_type: str, data: str, module: str = "") -> Optional[DedupRecord]:
        """Get the dedup record for specific content."""
        content_hash = self._compute_hash(event_type, data, module)
        with self._lock:
            return self._records.get(content_hash)

    def get_duplicates(self, min_count: int = 2) -> List[DedupRecord]:
        """Get all records with at least min_count occurrences."""
        with self._lock:
            return [
                r for r in self._records.values()
                if r.count >= min_count
            ]

    def get_top_duplicates(self, n: int = 10) -> List[DedupRecord]:
        """Get the most frequently duplicated events."""
        with self._lock:
            records = sorted(
                self._records.values(),
                key=lambda r: r.count,
                reverse=True,
            )
            return [r for r in records[:n] if r.count > 1]

    def get_stats(self) -> DedupStats:
        """Get deduplication statistics."""
        with self._lock:
            return DedupStats(
                total_events=self._stats.total_events,
                unique_events=self._stats.unique_events,
                duplicates_found=self._stats.duplicates_found,
                duplicates_by_type=dict(self._stats.duplicates_by_type),
                duplicates_by_module=dict(self._stats.duplicates_by_module),
            )

    def on_duplicate(self, callback: Callable) -> None:
        """Register a callback for duplicate detection.

        Callback signature: callback(event_type, data, module, record)
        """
        self._callbacks.append(callback)

    def _fire_callbacks(
        self,
        event_type: str,
        data: str,
        module: str,
        record: DedupRecord,
    ) -> None:
        """Fire duplicate detection callbacks."""
        for cb in self._callbacks:
            try:
                cb(event_type, data, module, record)
            except Exception as e:
                log.error("Dedup callback error: %s", e)

    def reset(self) -> None:
        """Clear all dedup records and stats."""
        with self._lock:
            self._records.clear()
            self._stats = DedupStats()

    def enable(self) -> None:
        """Enable deduplication."""
        self._enabled = True

    def disable(self) -> None:
        """Disable deduplication (all events pass through)."""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def record_count(self) -> int:
        with self._lock:
            return len(self._records)

    def to_dict(self) -> dict:
        """Serialize state for inspection."""
        with self._lock:
            return {
                "strategy": self.strategy.value,
                "action": self.action.value,
                "scope": self.scope,
                "enabled": self._enabled,
                "record_count": len(self._records),
                "max_records": self.max_records,
                "stats": self._stats.to_dict(),
            }


class ScanDeduplicator:
    """Per-scan deduplication manager with type-specific strategies.

    Allows different dedup strategies for different event types.

    Usage:
        scan_dedup = ScanDeduplicator(scan_id="scan-001")
        scan_dedup.set_strategy("IP_ADDRESS", DedupStrategy.NORMALIZED)
        scan_dedup.set_strategy("EMAILADDR", DedupStrategy.NORMALIZED)

        if not scan_dedup.is_duplicate("IP_ADDRESS", "192.168.1.1", "sfp_dns"):
            # Process event
            pass
    """

    def __init__(
        self,
        scan_id: str,
        default_strategy: DedupStrategy = DedupStrategy.EXACT,
        default_action: DedupAction = DedupAction.DROP,
    ):
        self.scan_id = scan_id
        self._default_strategy = default_strategy
        self._default_action = default_action
        self._type_strategies: Dict[str, DedupStrategy] = {}
        self._deduplicator = EventDeduplicator(
            strategy=default_strategy,
            action=default_action,
        )
        self._type_deduplicators: Dict[str, EventDeduplicator] = {}
        self._lock = threading.Lock()

    def set_strategy(
        self,
        event_type: str,
        strategy: DedupStrategy,
        action: Optional[DedupAction] = None,
    ) -> None:
        """Set a specific strategy for an event type."""
        with self._lock:
            self._type_strategies[event_type] = strategy
            self._type_deduplicators[event_type] = EventDeduplicator(
                strategy=strategy,
                action=action or self._default_action,
            )

    def is_duplicate(
        self,
        event_type: str,
        data: str,
        module: str = "",
    ) -> bool:
        """Check if an event is a duplicate, using type-specific strategy if set."""
        with self._lock:
            dedup = self._type_deduplicators.get(event_type, self._deduplicator)

        return dedup.check(event_type, data, module)

    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics from all deduplicators."""
        with self._lock:
            stats = {
                "scan_id": self.scan_id,
                "default": self._deduplicator.get_stats().to_dict(),
                "type_specific": {},
            }
            for etype, dedup in self._type_deduplicators.items():
                s = dedup.get_stats()
                if s.total_events > 0:
                    stats["type_specific"][etype] = s.to_dict()
            return stats

    def get_all_duplicates(self, min_count: int = 2) -> List[DedupRecord]:
        """Get all duplicates across all deduplicators."""
        with self._lock:
            results = list(self._deduplicator.get_duplicates(min_count))
            for dedup in self._type_deduplicators.values():
                results.extend(dedup.get_duplicates(min_count))
            return results

    def reset(self) -> None:
        """Reset all dedup state."""
        with self._lock:
            self._deduplicator.reset()
            for dedup in self._type_deduplicators.values():
                dedup.reset()


# Singleton
_global_dedup: Optional[EventDeduplicator] = None
_dedup_lock = threading.Lock()


def get_event_deduplicator() -> EventDeduplicator:
    """Get the global event deduplicator singleton."""
    global _global_dedup
    if _global_dedup is None:
        with _dedup_lock:
            if _global_dedup is None:
                _global_dedup = EventDeduplicator(
                    strategy=DedupStrategy.NORMALIZED,
                )
    return _global_dedup
