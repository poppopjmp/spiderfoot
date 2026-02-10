"""
Report Storage & Caching for SpiderFoot.

Provides persistent storage and in-memory caching for generated reports.
Supports multiple backends:
  - SQLite (default, file-based)
  - In-memory (for testing / ephemeral use)

Reports are stored with full metadata and can be queried by scan ID,
status, or creation time. An LRU cache provides fast retrieval of
recently accessed reports.

Usage::

    from spiderfoot.report_storage import ReportStore, StoreConfig

    store = ReportStore(StoreConfig(db_path="reports.db"))
    store.save(report_data)
    report = store.get("report-id-123")
    reports = store.list_reports(scan_id="SCAN-001")
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from spiderfoot.constants import DEFAULT_TTL_ONE_HOUR

log = logging.getLogger("spiderfoot.report_storage")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class StorageBackend(Enum):
    """Storage backend type."""
    SQLITE = "sqlite"
    MEMORY = "memory"


@dataclass
class StoreConfig:
    """Configuration for the report store."""
    backend: StorageBackend = StorageBackend.SQLITE
    db_path: str = ""  # Empty = auto-detect from SpiderFoot config
    cache_max_size: int = 100  # Max reports in LRU cache
    cache_ttl_seconds: float = DEFAULT_TTL_ONE_HOUR  # Cache entry TTL (1 hour)
    auto_cleanup_days: int = 90  # Auto-delete reports older than N days (0=disable)

    def __post_init__(self):
        if not self.db_path and self.backend == StorageBackend.SQLITE:
            self.db_path = os.path.join(
                os.environ.get("SF_DATA_DIR", "."),
                "reports.db",
            )


# ---------------------------------------------------------------------------
# LRU Cache
# ---------------------------------------------------------------------------

class LRUCache:
    """Thread-safe LRU cache with TTL expiration."""

    def __init__(self, max_size: int = 100, ttl_seconds: float = DEFAULT_TTL_ONE_HOUR) -> None:
        self._max_size = max(1, max_size)
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple] = OrderedDict()  # key -> (data, timestamp)
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> dict[str, Any] | None:
        """Get item from cache. Returns None if not found or expired."""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            data, ts = self._cache[key]
            if self._ttl > 0 and (time.monotonic() - ts) > self._ttl:
                # Expired
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return data

    def put(self, key: str, data: dict[str, Any]) -> None:
        """Add or update item in cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = (data, time.monotonic())
            else:
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)  # Remove oldest
                self._cache[key] = (data, time.monotonic())

    def invalidate(self, key: str) -> bool:
        """Remove item from cache. Returns True if found."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": (self._hits / total * 100) if total > 0 else 0.0,
            }


# ---------------------------------------------------------------------------
# SQLite storage backend
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    report_type TEXT NOT NULL DEFAULT 'full',
    progress_pct REAL NOT NULL DEFAULT 0.0,
    message TEXT NOT NULL DEFAULT '',
    executive_summary TEXT,
    recommendations TEXT,
    sections_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    generation_time_ms REAL NOT NULL DEFAULT 0.0,
    total_tokens_used INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_scan_id ON reports(scan_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);
"""


class SQLiteBackend:
    """SQLite-based report storage."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._local = threading.local()
        # Initialize schema
        conn = self._get_conn()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def save(self, data: dict[str, Any]) -> None:
        """Insert or update a report."""
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            """INSERT OR REPLACE INTO reports
            (report_id, scan_id, title, status, report_type, progress_pct,
             message, executive_summary, recommendations, sections_json,
             metadata_json, generation_time_ms, total_tokens_used,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["report_id"],
                data.get("scan_id", ""),
                data.get("title", ""),
                data.get("status", "pending"),
                data.get("report_type", "full"),
                data.get("progress_pct", 0.0),
                data.get("message", ""),
                data.get("executive_summary"),
                data.get("recommendations"),
                json.dumps(data.get("sections", []), default=str),
                json.dumps(data.get("metadata", {}), default=str),
                data.get("generation_time_ms", 0.0),
                data.get("total_tokens_used", 0),
                data.get("created_at", now),
                now,
            ),
        )
        conn.commit()

    def get(self, report_id: str) -> dict[str, Any] | None:
        """Retrieve a report by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM reports WHERE report_id = ?", (report_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def delete(self, report_id: str) -> bool:
        """Delete a report. Returns True if found."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM reports WHERE report_id = ?", (report_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def list_reports(
        self,
        scan_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List reports with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM reports"
        params: list[Any] = []
        conditions = []

        if scan_id:
            conditions.append("scan_id = ?")
            params.append(scan_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def count(self, scan_id: str | None = None) -> int:
        """Count reports, optionally filtered by scan_id."""
        conn = self._get_conn()
        if scan_id:
            row = conn.execute(
                "SELECT COUNT(*) FROM reports WHERE scan_id = ?", (scan_id,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM reports").fetchone()
        return row[0] if row else 0

    def cleanup_old(self, max_age_days: int) -> int:
        """Delete reports older than max_age_days. Returns count deleted."""
        if max_age_days <= 0:
            return 0
        cutoff = time.time() - (max_age_days * 86400)
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM reports WHERE created_at < ?", (cutoff,)
        )
        conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        """Close connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a SQLite row to a report dict."""
        d = dict(row)
        # Parse JSON fields
        d["sections"] = json.loads(d.pop("sections_json", "[]"))
        d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
        return d


# ---------------------------------------------------------------------------
# In-memory storage backend
# ---------------------------------------------------------------------------

class MemoryBackend:
    """In-memory report storage (for testing)."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def save(self, data: dict[str, Any]) -> None:
        with self._lock:
            data["updated_at"] = time.time()
            if "created_at" not in data:
                data["created_at"] = time.time()
            self._store[data["report_id"]] = data.copy()

    def get(self, report_id: str) -> dict[str, Any] | None:
        with self._lock:
            d = self._store.get(report_id)
            return d.copy() if d else None

    def delete(self, report_id: str) -> bool:
        with self._lock:
            return self._store.pop(report_id, None) is not None

    def list_reports(
        self,
        scan_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._lock:
            reports = list(self._store.values())

        if scan_id:
            reports = [r for r in reports if r.get("scan_id") == scan_id]
        if status:
            reports = [r for r in reports if r.get("status") == status]

        reports.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        return [r.copy() for r in reports[offset: offset + limit]]

    def count(self, scan_id: str | None = None) -> int:
        with self._lock:
            if scan_id:
                return sum(1 for r in self._store.values() if r.get("scan_id") == scan_id)
            return len(self._store)

    def cleanup_old(self, max_age_days: int) -> int:
        if max_age_days <= 0:
            return 0
        cutoff = time.time() - (max_age_days * 86400)
        with self._lock:
            to_delete = [
                rid for rid, r in self._store.items()
                if r.get("created_at", 0) < cutoff
            ]
            for rid in to_delete:
                del self._store[rid]
            return len(to_delete)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Main ReportStore (facade)
# ---------------------------------------------------------------------------

class ReportStore:
    """Unified report storage with caching.

    Combines a persistent backend (SQLite or memory) with an LRU cache
    for fast reads.
    """

    def __init__(self, config: StoreConfig | None = None) -> None:
        self.config = config or StoreConfig(backend=StorageBackend.MEMORY)

        # Initialize cache
        self._cache = LRUCache(
            max_size=self.config.cache_max_size,
            ttl_seconds=self.config.cache_ttl_seconds,
        )

        # Initialize backend
        if self.config.backend == StorageBackend.SQLITE:
            self._backend = SQLiteBackend(self.config.db_path)
        else:
            self._backend = MemoryBackend()

        log.info(
            "ReportStore initialized: backend=%s, cache_size=%d",
            self.config.backend.value,
            self.config.cache_max_size,
        )

    def save(self, data: dict[str, Any]) -> str:
        """Save a report. Returns the report_id.

        Args:
            data: Report dict (must contain 'report_id').

        Returns:
            The report_id.
        """
        report_id = data["report_id"]
        self._backend.save(data)
        self._cache.put(report_id, data)
        return report_id

    def get(self, report_id: str) -> dict[str, Any] | None:
        """Retrieve a report by ID. Uses cache first."""
        # Check cache
        cached = self._cache.get(report_id)
        if cached is not None:
            return cached

        # Fall back to backend
        data = self._backend.get(report_id)
        if data is not None:
            self._cache.put(report_id, data)
        return data

    def update(self, report_id: str, updates: dict[str, Any]) -> bool:
        """Update specific fields of a report.

        Args:
            report_id: Report to update.
            updates: Dict of fields to update.

        Returns:
            True if report was found and updated.
        """
        data = self._backend.get(report_id)
        if data is None:
            return False

        data.update(updates)
        self._backend.save(data)
        self._cache.put(report_id, data)
        return True

    def delete(self, report_id: str) -> bool:
        """Delete a report."""
        self._cache.invalidate(report_id)
        return self._backend.delete(report_id)

    def list_reports(
        self,
        scan_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List reports with optional filters."""
        return self._backend.list_reports(
            scan_id=scan_id, status=status, limit=limit, offset=offset
        )

    def count(self, scan_id: str | None = None) -> int:
        """Count reports."""
        return self._backend.count(scan_id=scan_id)

    def cleanup(self) -> int:
        """Run cleanup of old reports based on config."""
        if self.config.auto_cleanup_days <= 0:
            return 0
        count = self._backend.cleanup_old(self.config.auto_cleanup_days)
        if count > 0:
            self._cache.clear()
            log.info("Cleaned up %d old reports", count)
        return count

    @property
    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache.stats

    def close(self) -> None:
        """Close backend connections."""
        self._backend.close()
        self._cache.clear()
