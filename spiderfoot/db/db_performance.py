# -------------------------------------------------------------------------------
# Name:         SpiderFoot DB Performance Utilities
# Purpose:      Table partitioning, VACUUM ANALYZE, dedup, caching, read replicas.
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-16
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Database performance utilities for SpiderFoot.

Implements Cycles 76–90 of the Phase 2 Performance roadmap:

- **Cycle 76**: Table partitioning helper for ``tbl_scan_results``
- **Cycle 77**: VACUUM ANALYZE post-scan task
- **Cycle 78**: INSERT ON CONFLICT deduplication
- **Cycle 79**: Redis scan statistics cache
- **Cycle 80–90**: Read replica routing
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

try:
    from psycopg2 import sql as pgsql
except ImportError:  # pragma: no cover – allow tests without psycopg2
    pgsql = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


# ====================================================================== #
# Cycle 76 — Table Partitioning Helper                                   #
# ====================================================================== #

class PartitionManager:
    """Manage PostgreSQL list partitions for ``tbl_scan_results``.

    Each scan gets its own partition keyed by ``scan_instance_id``.
    This enables instant partition drop for scan deletion instead of
    expensive ``DELETE FROM`` operations.

    Usage::

        pm = PartitionManager(conn)
        pm.ensure_partition("scan-guid-123")
        # ... insert events ...
        pm.drop_partition("scan-guid-123")

    NOTE: Partitioning requires the base table to be created as a
    partitioned table.  This manager provides both the DDL to convert
    the table and the runtime partition management.
    """

    # Strict: only hex chars and hyphens (UUID format)
    _SAFE_SCAN_ID = re.compile(r"^[a-fA-F0-9\-]{1,64}$")

    def __init__(self, conn: Any) -> None:
        if conn is None:
            raise ValueError("conn must be a valid database connection")
        self._conn = conn
        self._lock = threading.Lock()
        self._known_partitions: set[str] = set()

    @classmethod
    def _validate_scan_id(cls, scan_id: str) -> None:
        """Raise ValueError if scan_id is not a valid UUID-like string."""
        if not scan_id or not cls._SAFE_SCAN_ID.match(scan_id):
            raise ValueError(
                f"Invalid scan_id: must match UUID hex pattern, got {scan_id!r}"
            )

    @staticmethod
    def partition_name(scan_id: str) -> str:
        """Generate a safe partition name from a scan GUID."""
        safe = scan_id.lower().replace("-", "_")
        return f"tbl_scan_results_{safe}"

    @staticmethod
    def get_partitioned_table_ddl() -> list[str]:
        """Return DDL to create ``tbl_scan_results`` as a partitioned table.

        This is intended for new installations or migrations.
        Existing non-partitioned tables must be migrated separately.

        Returns:
            List of DDL strings.
        """
        return [
            """CREATE TABLE IF NOT EXISTS tbl_scan_results (
                scan_instance_id    VARCHAR NOT NULL,
                hash                VARCHAR NOT NULL,
                type                VARCHAR NOT NULL,
                generated           BIGINT NOT NULL,
                confidence          INT NOT NULL DEFAULT 100,
                visibility          INT NOT NULL DEFAULT 100,
                risk                INT NOT NULL DEFAULT 0,
                module              VARCHAR NOT NULL,
                data                TEXT,
                false_positive      INT NOT NULL DEFAULT 0,
                source_event_hash   VARCHAR DEFAULT 'ROOT'
            ) PARTITION BY LIST (scan_instance_id)""",
            # Default partition for any scan_id that doesn't have its own
            "CREATE TABLE IF NOT EXISTS tbl_scan_results_default PARTITION OF tbl_scan_results DEFAULT",
        ]

    def ensure_partition(self, scan_id: str) -> bool:
        """Create a partition for the given scan_id if it doesn't exist.

        Args:
            scan_id: Scan instance GUID.

        Returns:
            True if partition created (or already exists), False on error.
        """
        if scan_id in self._known_partitions:
            return True

        self._validate_scan_id(scan_id)
        part_name = self.partition_name(scan_id)
        with self._lock:
            try:
                cursor = self._conn.cursor()
                # Check if partition exists
                cursor.execute(
                    "SELECT 1 FROM pg_class WHERE relname = %s",
                    (part_name,)
                )
                if cursor.fetchone():
                    self._known_partitions.add(scan_id)
                    cursor.close()
                    return True

                # Create partition – use psycopg2.sql for safe identifier quoting
                if pgsql is not None:
                    stmt = pgsql.SQL(
                        "CREATE TABLE IF NOT EXISTS {} PARTITION OF tbl_scan_results FOR VALUES IN (%s)"
                    ).format(pgsql.Identifier(part_name))
                else:
                    # Fallback: already validated via _validate_scan_id
                    stmt = (
                        f'CREATE TABLE IF NOT EXISTS "{part_name}" '
                        f"PARTITION OF tbl_scan_results FOR VALUES IN (%s)"
                    )
                cursor.execute(stmt, (scan_id,))
                self._conn.commit()
                self._known_partitions.add(scan_id)
                cursor.close()
                log.info("Created partition %s for scan %s", part_name, scan_id)
                return True
            except Exception as e:
                log.warning("Failed to create partition for %s: %s", scan_id, e)
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                return False

    def drop_partition(self, scan_id: str) -> bool:
        """Drop the partition for the given scan_id (instant scan deletion).

        Args:
            scan_id: Scan instance GUID.

        Returns:
            True if dropped successfully, False on error.
        """
        self._validate_scan_id(scan_id)
        part_name = self.partition_name(scan_id)
        with self._lock:
            try:
                cursor = self._conn.cursor()
                if pgsql is not None:
                    stmt = pgsql.SQL("DROP TABLE IF EXISTS {}").format(
                        pgsql.Identifier(part_name)
                    )
                else:
                    stmt = f'DROP TABLE IF EXISTS "{part_name}"'
                cursor.execute(stmt)
                self._conn.commit()
                self._known_partitions.discard(scan_id)
                cursor.close()
                log.info("Dropped partition %s for scan %s", part_name, scan_id)
                return True
            except Exception as e:
                log.warning("Failed to drop partition for %s: %s", scan_id, e)
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                return False

    def list_partitions(self) -> list[str]:
        """List all scan result partitions."""
        with self._lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT inhrelid::regclass::text FROM pg_inherits "
                    "WHERE inhparent = 'tbl_scan_results'::regclass"
                )
                parts = [row[0] for row in cursor.fetchall()]
                cursor.close()
                return parts
            except Exception as e:
                log.debug("list_partitions failed: %s", e)
                return []


# ====================================================================== #
# Cycle 77 — VACUUM ANALYZE Post-Scan Task                              #
# ====================================================================== #

class VacuumAnalyze:
    """Run VACUUM ANALYZE after scan completion.

    PostgreSQL VACUUM reclaims dead-tuple storage; ANALYZE updates
    planner statistics for better query plans.  Both are essential
    after bulk inserts.

    Usage::

        va = VacuumAnalyze(conn)
        va.vacuum_analyze_scan("scan-guid")  # analyse scan results
        va.vacuum_analyze_all()             # analyse all tables
    """

    # Tables to analyse after a scan
    SCAN_TABLES = [
        "tbl_scan_results",
        "tbl_scan_log",
        "tbl_scan_correlation_results",
        "tbl_scan_correlation_results_events",
    ]

    def __init__(self, conn: Any) -> None:
        if conn is None:
            raise ValueError("conn must be a valid database connection")
        self._conn = conn

    def _execute_vacuum(self, sql: str) -> bool:
        """Execute a VACUUM/ANALYZE statement (requires autocommit)."""
        old_autocommit = self._conn.autocommit
        try:
            self._conn.autocommit = True
            cursor = self._conn.cursor()
            cursor.execute(sql)
            cursor.close()
            return True
        except Exception as e:
            log.warning("VACUUM/ANALYZE failed: %s — %s", sql, e)
            return False
        finally:
            try:
                self._conn.autocommit = old_autocommit
            except Exception:
                pass

    def vacuum_analyze_scan(self, scan_id: str | None = None) -> dict[str, bool]:
        """Run VACUUM ANALYZE on scan-related tables.

        Args:
            scan_id: Optional scan GUID — if the table is partitioned,
                     only the partition for this scan is vacuumed.

        Returns:
            Dict mapping table name to success bool.
        """
        results: dict[str, bool] = {}
        for table in self.SCAN_TABLES:
            target = table
            if scan_id and table == "tbl_scan_results":
                PartitionManager._validate_scan_id(scan_id)
                part_name = PartitionManager.partition_name(scan_id)
                # Check if partition exists
                try:
                    cursor = self._conn.cursor()
                    cursor.execute(
                        "SELECT 1 FROM pg_class WHERE relname = %s",
                        (part_name,)
                    )
                    if cursor.fetchone():
                        target = f'"{part_name}"'
                    cursor.close()
                except Exception:
                    pass
            # VACUUM/ANALYZE only accepts static identifiers;
            # safe because target is either a hardcoded table name
            # or a validated partition name.
            results[target] = self._execute_vacuum(f"VACUUM ANALYZE {target}")
        return results

    def vacuum_analyze_all(self) -> bool:
        """Run VACUUM ANALYZE on the entire database."""
        return self._execute_vacuum("VACUUM ANALYZE")

    # Only allow known safe table names in analyze_only
    _ALLOWED_TABLES = frozenset({
        "tbl_scan_results", "tbl_scan_log",
        "tbl_scan_correlation_results",
        "tbl_scan_correlation_results_events",
        "tbl_scan_instance", "tbl_event_types",
        "tbl_workspaces", "tbl_config",
    })

    def analyze_only(self, table: str = "tbl_scan_results") -> bool:
        """Run ANALYZE (no VACUUM) on a specific table.

        Lighter-weight than full VACUUM — just updates planner statistics.

        Raises:
            ValueError: If *table* is not in the allow-list.
        """
        if table not in self._ALLOWED_TABLES:
            raise ValueError(f"Table {table!r} not in allow-list for ANALYZE")
        return self._execute_vacuum(f"ANALYZE {table}")


# ====================================================================== #
# Cycle 78 — INSERT ON CONFLICT Deduplication                            #
# ====================================================================== #

def get_dedup_insert_query() -> str:
    """Return an INSERT ... ON CONFLICT DO NOTHING query for scan results.

    Requires a unique constraint on ``(scan_instance_id, hash)`` to work.
    If the event hash already exists for this scan, the insert is silently
    skipped, avoiding duplicate events without pre-checking.

    Returns:
        INSERT query string with %s placeholders.
    """
    return (
        "INSERT INTO tbl_scan_results "
        "(scan_instance_id, hash, type, generated, confidence, visibility, "
        "risk, module, data, source_event_hash) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (scan_instance_id, hash) DO NOTHING"
    )


def get_dedup_constraint_ddl() -> list[str]:
    """Return DDL to add the unique constraint needed for deduplication.

    Returns:
        List of DDL strings (safe to run idempotently).
    """
    return [
        # Add unique constraint if not present
        "DO $$ BEGIN "
        "IF NOT EXISTS ("
        "  SELECT 1 FROM pg_constraint WHERE conname = 'uq_scan_results_hash'"
        ") THEN "
        "  ALTER TABLE tbl_scan_results "
        "    ADD CONSTRAINT uq_scan_results_hash "
        "    UNIQUE (scan_instance_id, hash); "
        "END IF; "
        "END $$",
    ]


# ====================================================================== #
# Cycle 79 — Redis Scan Statistics Cache                                 #
# ====================================================================== #

class ScanStatsCache:
    """Cache scan statistics in Redis with TTL.

    Caches event counts, type distribution, risk distribution, and
    module contribution for a scan.  Invalidated on new event insertion
    or after TTL expiry.

    Usage::

        cache = ScanStatsCache(redis_client)
        stats = cache.get(scan_id)
        if stats is None:
            stats = compute_stats_from_db(scan_id)
            cache.set(scan_id, stats)

        # On new event insert:
        cache.invalidate(scan_id)
    """

    KEY_PREFIX = "sf:scan_stats:"
    DEFAULT_TTL = 30  # seconds

    def __init__(self, redis_client: Any = None, ttl: int = DEFAULT_TTL) -> None:
        """Initialize with a Redis client.

        Args:
            redis_client: A redis.Redis (or compatible) client, or None.
                         If None, caching is disabled (passthrough).
            ttl: Cache TTL in seconds (default: 30).
        """
        self._redis = redis_client
        self._ttl = ttl
        self._hits = 0
        self._misses = 0

    @property
    def enabled(self) -> bool:
        """Whether the cache is active."""
        return self._redis is not None

    def _key(self, scan_id: str) -> str:
        return f"{self.KEY_PREFIX}{scan_id}"

    def get(self, scan_id: str) -> dict | None:
        """Get cached stats for a scan.

        Returns:
            Parsed dict of stats, or None if not cached.
        """
        if not self.enabled:
            return None
        try:
            raw = self._redis.get(self._key(scan_id))
            if raw is None:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(raw)
        except Exception as e:
            log.debug("ScanStatsCache.get failed: %s", e)
            self._misses += 1
            return None

    def set(self, scan_id: str, stats: dict) -> bool:
        """Cache stats for a scan.

        Args:
            scan_id: Scan instance GUID.
            stats: Dict of statistics to cache.

        Returns:
            True if cached successfully.
        """
        if not self.enabled:
            return False
        try:
            self._redis.setex(
                self._key(scan_id),
                self._ttl,
                json.dumps(stats),
            )
            return True
        except Exception as e:
            log.debug("ScanStatsCache.set failed: %s", e)
            return False

    def invalidate(self, scan_id: str) -> bool:
        """Invalidate cached stats for a scan.

        Call this after inserting new events.

        Returns:
            True if key was deleted.
        """
        if not self.enabled:
            return False
        try:
            return bool(self._redis.delete(self._key(scan_id)))
        except Exception as e:
            log.debug("ScanStatsCache.invalidate failed: %s", e)
            return False

    def invalidate_all(self) -> int:
        """Invalidate all cached scan stats.

        Returns:
            Number of keys deleted.
        """
        if not self.enabled:
            return 0
        try:
            keys = self._redis.keys(f"{self.KEY_PREFIX}*")
            if keys:
                return self._redis.delete(*keys)
            return 0
        except Exception as e:
            log.debug("ScanStatsCache.invalidate_all failed: %s", e)
            return 0

    @property
    def stats(self) -> dict:
        """Return cache hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total else 0.0,
            "enabled": self.enabled,
        }


# ====================================================================== #
# Cycles 80–90 — Read Replica Routing                                    #
# ====================================================================== #

@dataclass
class ReplicaConfig:
    """Configuration for a read replica."""

    dsn: str
    name: str = "replica"
    weight: int = 1  # for weighted round-robin
    max_lag_seconds: float = 30.0  # max acceptable replication lag
    enabled: bool = True


class ReadReplicaRouter:
    """Route read queries to replicas, writes to primary.

    Implements a connection factory that routes SELECT queries to
    read replicas and all write operations to the primary.

    Supports:
    - Weighted round-robin across multiple replicas
    - Automatic failover to primary if replicas are down
    - Replication lag awareness (skip replicas that are too far behind)

    Usage::

        router = ReadReplicaRouter(primary_conn)
        router.add_replica(ReplicaConfig(dsn="host=replica1 ..."))
        router.add_replica(ReplicaConfig(dsn="host=replica2 ..."))

        # For reads
        conn = router.get_read_connection()

        # For writes (always primary)
        conn = router.get_write_connection()
    """

    def __init__(self, primary_conn: Any) -> None:
        """Initialize with the primary database connection.

        Args:
            primary_conn: A psycopg2 connection to the primary server.
        """
        if primary_conn is None:
            raise ValueError("primary_conn must be a valid database connection")
        self._primary = primary_conn
        self._replicas: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._rr_index = 0

    def add_replica(self, config: ReplicaConfig) -> bool:
        """Register a read replica.

        Args:
            config: ReplicaConfig with DSN and settings.

        Returns:
            True if the replica was connected and added.
        """
        try:
            import psycopg2
            conn = psycopg2.connect(config.dsn)
            conn.set_session(readonly=True, autocommit=True)
            with self._lock:
                self._replicas.append({
                    "config": config,
                    "conn": conn,
                    "healthy": True,
                    "last_check": time.time(),
                })
            log.info("Added read replica: %s", config.name)
            return True
        except Exception as e:
            log.warning("Failed to add replica %s: %s", config.name, e)
            return False

    def get_write_connection(self) -> Any:
        """Get the primary connection for write operations.

        Returns:
            Primary psycopg2 connection.
        """
        return self._primary

    def get_read_connection(self) -> Any:
        """Get a read connection — preferring replicas via round-robin.

        Falls back to primary if no healthy replicas are available.

        Returns:
            A psycopg2 connection (replica or primary).
        """
        with self._lock:
            healthy = [r for r in self._replicas if r["healthy"] and r["config"].enabled]
            if not healthy:
                return self._primary

            # Weighted round-robin
            total_weight = sum(r["config"].weight for r in healthy)
            if total_weight == 0:
                return self._primary

            self._rr_index = (self._rr_index + 1) % len(healthy)
            replica = healthy[self._rr_index]

            # Health check
            try:
                cursor = replica["conn"].cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                return replica["conn"]
            except Exception:
                replica["healthy"] = False
                log.warning("Replica %s is unhealthy, falling back to primary",
                            replica["config"].name)
                return self._primary

    def check_replica_lag(self) -> dict[str, float]:
        """Check replication lag for all replicas.

        Returns:
            Dict mapping replica name to lag in seconds.
        """
        lags: dict[str, float] = {}
        for replica in self._replicas:
            try:
                cursor = replica["conn"].cursor()
                cursor.execute(
                    "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))"
                )
                row = cursor.fetchone()
                lag = float(row[0]) if row and row[0] is not None else 0.0
                cursor.close()
                lags[replica["config"].name] = lag

                # Mark unhealthy if lag exceeds threshold
                if lag > replica["config"].max_lag_seconds:
                    replica["healthy"] = False
                    log.warning("Replica %s lag %.1fs exceeds threshold %.1fs",
                                replica["config"].name, lag, replica["config"].max_lag_seconds)
                else:
                    replica["healthy"] = True
            except Exception as e:
                lags[replica["config"].name] = -1.0
                replica["healthy"] = False
                log.debug("Lag check failed for %s: %s", replica["config"].name, e)
        return lags

    def close_replicas(self) -> None:
        """Close all replica connections."""
        with self._lock:
            for replica in self._replicas:
                try:
                    replica["conn"].close()
                except Exception:
                    pass
            self._replicas.clear()

    @property
    def replica_count(self) -> int:
        """Number of registered replicas."""
        return len(self._replicas)

    @property
    def healthy_replica_count(self) -> int:
        """Number of healthy replicas."""
        return sum(1 for r in self._replicas if r["healthy"])

    def status(self) -> dict[str, Any]:
        """Return full replica router status."""
        return {
            "primary": "connected",
            "replicas": [
                {
                    "name": r["config"].name,
                    "healthy": r["healthy"],
                    "weight": r["config"].weight,
                    "enabled": r["config"].enabled,
                }
                for r in self._replicas
            ],
            "total": self.replica_count,
            "healthy": self.healthy_replica_count,
        }
