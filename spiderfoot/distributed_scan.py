"""
Distributed Scanning — coordinate scan execution across multiple workers.

Provides:
  - Scan work distribution and partitioning across Celery workers
  - Worker pool management with health monitoring
  - Scan chunk assignment with load balancing strategies
  - Progress aggregation from distributed workers
  - Fault tolerance with chunk re-assignment on worker failure
  - Worker capability matching (module availability)

v5.7.0
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.distributed_scan")


class WorkerStatus(str, Enum):
    ONLINE = "online"
    BUSY = "busy"
    DRAINING = "draining"     # Finishing current work, accepting no new
    OFFLINE = "offline"
    UNHEALTHY = "unhealthy"


class ChunkStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REASSIGNED = "reassigned"


class BalancingStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    CAPABILITY_MATCH = "capability_match"
    RANDOM = "random"


@dataclass
class WorkerNode:
    """A registered scan worker."""
    worker_id: str = ""
    hostname: str = ""
    ip_address: str = ""
    status: str = WorkerStatus.ONLINE.value
    capabilities: list[str] = field(default_factory=list)  # Module names
    max_concurrent: int = 4
    current_load: int = 0
    total_completed: int = 0
    total_failed: int = 0
    last_heartbeat: float = 0.0
    registered_at: float = 0.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def available_slots(self) -> int:
        return max(0, self.max_concurrent - self.current_load)

    @property
    def is_available(self) -> bool:
        return (
            self.status == WorkerStatus.ONLINE.value
            and self.available_slots > 0
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["available_slots"] = self.available_slots
        d["is_available"] = self.is_available
        return d


@dataclass
class ScanChunk:
    """A portion of a scan assigned to a worker."""
    chunk_id: str = ""
    scan_id: str = ""
    worker_id: str = ""
    modules: list[str] = field(default_factory=list)
    target: str = ""
    status: str = ChunkStatus.PENDING.value
    priority: int = 5     # 1=highest, 10=lowest
    attempt: int = 0
    max_attempts: int = 3
    assigned_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    events_found: int = 0
    error: str = ""
    progress_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DistributedScan:
    """A scan distributed across multiple workers."""
    scan_id: str = ""
    target: str = ""
    modules: list[str] = field(default_factory=list)
    chunks: list[ScanChunk] = field(default_factory=list)
    strategy: str = BalancingStrategy.LEAST_LOADED.value
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    total_events: int = 0
    status: str = "pending"  # pending, running, completed, failed, partial

    @property
    def progress(self) -> float:
        if not self.chunks:
            return 0.0
        completed = sum(1 for c in self.chunks
                       if c.status in (ChunkStatus.COMPLETED.value,))
        return (completed / len(self.chunks)) * 100

    def to_dict(self) -> dict:
        d = asdict(self)
        d["progress"] = round(self.progress, 1)
        d["chunk_count"] = len(self.chunks)
        return d


class DistributedScanManager:
    """Manages distributed scan execution across a worker pool.

    Features:
      - Worker registration and heartbeat monitoring
      - Automatic scan partitioning by module groups
      - Multiple load balancing strategies
      - Chunk reassignment on worker failure
      - Aggregated progress tracking
    """

    HEARTBEAT_TIMEOUT = 60  # seconds before marking offline
    MODULE_GROUPS = {
        "dns": [
            "sfp_dns", "sfp_dnsbrute", "sfp_dnsresolve",
            "sfp_dnszonexfer", "sfp_dnsneighbor",
        ],
        "web": [
            "sfp_spider", "sfp_httpx", "sfp_webserver",
            "sfp_webframework", "sfp_robots",
        ],
        "osint": [
            "sfp_shodan", "sfp_censys", "sfp_greynoise",
            "sfp_virustotal", "sfp_abuseipdb",
        ],
        "email": [
            "sfp_email", "sfp_emailformat", "sfp_hunter",
            "sfp_haveibeenpwned",
        ],
        "vuln": [
            "sfp_nuclei", "sfp_nmap", "sfp_vulndb",
            "sfp_cve_search",
        ],
        "social": [
            "sfp_twitter", "sfp_linkedin", "sfp_github",
            "sfp_instagram",
        ],
        "passive": [
            "sfp_dnspassive", "sfp_certspotter",
            "sfp_crt", "sfp_subfinder",
        ],
        "infra": [
            "sfp_whois", "sfp_bgp", "sfp_netblock",
            "sfp_cloudflare", "sfp_asn",
        ],
    }

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._workers: dict[str, WorkerNode] = {}
        self._scans: dict[str, DistributedScan] = {}
        self._rr_index = 0  # Round-robin counter

    # ── Worker management ─────────────────────────────────────────────

    def register_worker(self, worker: dict) -> WorkerNode:
        """Register a new worker node."""
        node = WorkerNode(**{
            k: v for k, v in worker.items()
            if k in WorkerNode.__dataclass_fields__
        })
        if not node.worker_id:
            node.worker_id = str(uuid.uuid4())[:12]
        node.registered_at = time.time()
        node.last_heartbeat = time.time()
        node.status = WorkerStatus.ONLINE.value

        self._workers[node.worker_id] = node
        self._persist_worker(node)
        _log.info("Worker registered: %s (%s)", node.worker_id, node.hostname)
        return node

    def heartbeat(self, worker_id: str, load: int | None = None) -> bool:
        """Process a worker heartbeat."""
        node = self._workers.get(worker_id)
        if not node:
            return False

        node.last_heartbeat = time.time()
        if node.status == WorkerStatus.UNHEALTHY.value:
            node.status = WorkerStatus.ONLINE.value
        if load is not None:
            node.current_load = load

        self._persist_worker(node)
        return True

    def deregister_worker(self, worker_id: str) -> bool:
        """Remove a worker from the pool."""
        node = self._workers.pop(worker_id, None)
        if node:
            # Reassign any active chunks
            self._reassign_worker_chunks(worker_id)
            if self._redis:
                try:
                    self._redis.hdel("sf:dist:workers", worker_id)
                except Exception:
                    pass
            return True
        return False

    def list_workers(self, status: str | None = None) -> list[WorkerNode]:
        """List registered workers."""
        self._check_heartbeats()
        workers = list(self._workers.values())
        if status:
            workers = [w for w in workers if w.status == status]
        return workers

    def get_worker(self, worker_id: str) -> WorkerNode | None:
        return self._workers.get(worker_id)

    def drain_worker(self, worker_id: str) -> bool:
        """Put a worker in draining mode (finish current, no new work)."""
        node = self._workers.get(worker_id)
        if not node:
            return False
        node.status = WorkerStatus.DRAINING.value
        self._persist_worker(node)
        return True

    # ── Scan distribution ─────────────────────────────────────────────

    def distribute_scan(
        self,
        scan_id: str,
        target: str,
        modules: list[str],
        strategy: str = BalancingStrategy.LEAST_LOADED.value,
    ) -> DistributedScan:
        """Partition a scan across available workers.

        Splits modules into groups and assigns each group as a chunk
        to an available worker based on the selected strategy.
        """
        self._check_heartbeats()

        dscan = DistributedScan(
            scan_id=scan_id,
            target=target,
            modules=modules,
            strategy=strategy,
            created_at=time.time(),
        )

        # Partition modules into groups
        groups = self._partition_modules(modules)

        # Assign each group as a chunk
        for group_name, group_modules in groups.items():
            chunk = ScanChunk(
                chunk_id=f"{scan_id}-{group_name}-{str(uuid.uuid4())[:6]}",
                scan_id=scan_id,
                modules=group_modules,
                target=target,
            )

            worker = self._select_worker(chunk, strategy)
            if worker:
                chunk.worker_id = worker.worker_id
                chunk.status = ChunkStatus.ASSIGNED.value
                chunk.assigned_at = time.time()
                worker.current_load += 1
                self._persist_worker(worker)
            else:
                chunk.status = ChunkStatus.PENDING.value
                _log.warning("No worker available for chunk %s", chunk.chunk_id)

            dscan.chunks.append(chunk)

        if any(c.status == ChunkStatus.ASSIGNED.value for c in dscan.chunks):
            dscan.status = "running"
            dscan.started_at = time.time()
        else:
            dscan.status = "pending"

        self._scans[scan_id] = dscan
        self._persist_scan(dscan)

        _log.info("Distributed scan %s: %d chunks across workers (strategy=%s)",
                  scan_id, len(dscan.chunks), strategy)
        return dscan

    def update_chunk_progress(
        self,
        chunk_id: str,
        progress_pct: float | None = None,
        events_found: int | None = None,
        status: str | None = None,
        error: str | None = None,
    ) -> ScanChunk | None:
        """Update progress for a scan chunk."""
        for dscan in self._scans.values():
            for chunk in dscan.chunks:
                if chunk.chunk_id == chunk_id:
                    if progress_pct is not None:
                        chunk.progress_pct = progress_pct
                    if events_found is not None:
                        chunk.events_found = events_found
                    if status:
                        chunk.status = status
                        if status == ChunkStatus.RUNNING.value and not chunk.started_at:
                            chunk.started_at = time.time()
                        elif status == ChunkStatus.COMPLETED.value:
                            chunk.completed_at = time.time()
                            # Free worker slot
                            w = self._workers.get(chunk.worker_id)
                            if w:
                                w.current_load = max(0, w.current_load - 1)
                                w.total_completed += 1
                                self._persist_worker(w)
                        elif status == ChunkStatus.FAILED.value:
                            chunk.completed_at = time.time()
                            w = self._workers.get(chunk.worker_id)
                            if w:
                                w.current_load = max(0, w.current_load - 1)
                                w.total_failed += 1
                                self._persist_worker(w)
                            # Auto-retry if attempts remain
                            if chunk.attempt < chunk.max_attempts:
                                self._retry_chunk(dscan, chunk)
                    if error:
                        chunk.error = error

                    # Update scan-level status
                    self._update_scan_status(dscan)
                    self._persist_scan(dscan)
                    return chunk
        return None

    def get_scan(self, scan_id: str) -> DistributedScan | None:
        return self._scans.get(scan_id)

    def list_scans(self, status: str | None = None) -> list[DistributedScan]:
        scans = list(self._scans.values())
        if status:
            scans = [s for s in scans if s.status == status]
        return scans

    def get_scan_progress(self, scan_id: str) -> dict | None:
        """Get aggregated progress for a distributed scan."""
        dscan = self._scans.get(scan_id)
        if not dscan:
            return None

        chunks_total = len(dscan.chunks)
        chunks_completed = sum(
            1 for c in dscan.chunks
            if c.status == ChunkStatus.COMPLETED.value
        )
        chunks_running = sum(
            1 for c in dscan.chunks
            if c.status == ChunkStatus.RUNNING.value
        )
        chunks_failed = sum(
            1 for c in dscan.chunks
            if c.status == ChunkStatus.FAILED.value
        )
        total_events = sum(c.events_found for c in dscan.chunks)

        return {
            "scan_id": scan_id,
            "status": dscan.status,
            "progress": round(dscan.progress, 1),
            "chunks_total": chunks_total,
            "chunks_completed": chunks_completed,
            "chunks_running": chunks_running,
            "chunks_failed": chunks_failed,
            "chunks_pending": chunks_total - chunks_completed - chunks_running - chunks_failed,
            "total_events": total_events,
            "workers_involved": len(set(c.worker_id for c in dscan.chunks if c.worker_id)),
            "elapsed_seconds": (
                time.time() - dscan.started_at if dscan.started_at else 0
            ),
        }

    def get_pool_stats(self) -> dict:
        """Get worker pool statistics."""
        self._check_heartbeats()
        workers = list(self._workers.values())
        return {
            "total_workers": len(workers),
            "online": sum(1 for w in workers if w.status == WorkerStatus.ONLINE.value),
            "busy": sum(1 for w in workers if w.status == WorkerStatus.BUSY.value),
            "draining": sum(1 for w in workers if w.status == WorkerStatus.DRAINING.value),
            "offline": sum(1 for w in workers if w.status == WorkerStatus.OFFLINE.value),
            "unhealthy": sum(1 for w in workers if w.status == WorkerStatus.UNHEALTHY.value),
            "total_capacity": sum(w.max_concurrent for w in workers),
            "current_load": sum(w.current_load for w in workers),
            "available_slots": sum(w.available_slots for w in workers),
            "total_completed": sum(w.total_completed for w in workers),
            "total_failed": sum(w.total_failed for w in workers),
            "active_scans": sum(
                1 for s in self._scans.values() if s.status == "running"
            ),
        }

    # ── Private helpers ───────────────────────────────────────────────

    def _partition_modules(self, modules: list[str]) -> dict[str, list[str]]:
        """Partition modules into logical groups for distribution."""
        groups: dict[str, list[str]] = {}
        assigned = set()

        # Match against known groups
        for group_name, group_modules in self.MODULE_GROUPS.items():
            matched = [m for m in modules if m in group_modules]
            if matched:
                groups[group_name] = matched
                assigned.update(matched)

        # Remaining modules go into a catch-all group
        remaining = [m for m in modules if m not in assigned]
        if remaining:
            # Split remaining into chunks of ~5 modules
            for i in range(0, len(remaining), 5):
                chunk = remaining[i:i + 5]
                groups[f"misc_{i // 5}"] = chunk

        return groups if groups else {"all": modules}

    def _select_worker(
        self, chunk: ScanChunk, strategy: str,
    ) -> WorkerNode | None:
        """Select a worker for a chunk based on the balancing strategy."""
        available = [
            w for w in self._workers.values()
            if w.is_available
        ]
        if not available:
            return None

        if strategy == BalancingStrategy.LEAST_LOADED.value:
            return min(available, key=lambda w: w.current_load)

        elif strategy == BalancingStrategy.ROUND_ROBIN.value:
            self._rr_index = (self._rr_index + 1) % len(available)
            return available[self._rr_index]

        elif strategy == BalancingStrategy.CAPABILITY_MATCH.value:
            # Prefer workers that have all required modules
            best = None
            best_score = -1
            for w in available:
                if not w.capabilities:
                    score = 0
                else:
                    score = sum(
                        1 for m in chunk.modules if m in w.capabilities
                    )
                if score > best_score:
                    best_score = score
                    best = w
            return best

        else:  # RANDOM
            import random
            return random.choice(available)

    def _retry_chunk(self, dscan: DistributedScan, chunk: ScanChunk) -> None:
        """Re-assign a failed chunk to a different worker."""
        chunk.attempt += 1
        chunk.status = ChunkStatus.REASSIGNED.value
        chunk.error = ""

        # Try a different worker
        exclude = {chunk.worker_id}
        available = [
            w for w in self._workers.values()
            if w.is_available and w.worker_id not in exclude
        ]
        if available:
            new_worker = min(available, key=lambda w: w.current_load)
            chunk.worker_id = new_worker.worker_id
            chunk.status = ChunkStatus.ASSIGNED.value
            chunk.assigned_at = time.time()
            new_worker.current_load += 1
            self._persist_worker(new_worker)
            _log.info("Chunk %s reassigned to worker %s (attempt %d)",
                      chunk.chunk_id, new_worker.worker_id, chunk.attempt)
        else:
            chunk.status = ChunkStatus.PENDING.value
            _log.warning("No workers available for retry of chunk %s",
                         chunk.chunk_id)

    def _reassign_worker_chunks(self, worker_id: str) -> None:
        """Reassign all chunks from a departing worker."""
        for dscan in self._scans.values():
            for chunk in dscan.chunks:
                if (chunk.worker_id == worker_id
                        and chunk.status in (
                            ChunkStatus.ASSIGNED.value,
                            ChunkStatus.RUNNING.value,
                        )):
                    _log.info("Reassigning chunk %s from departed worker %s",
                              chunk.chunk_id, worker_id)
                    self._retry_chunk(dscan, chunk)

    def _update_scan_status(self, dscan: DistributedScan) -> None:
        """Update scan-level status based on chunk statuses."""
        statuses = [c.status for c in dscan.chunks]
        if all(s == ChunkStatus.COMPLETED.value for s in statuses):
            dscan.status = "completed"
            dscan.completed_at = time.time()
            dscan.total_events = sum(c.events_found for c in dscan.chunks)
        elif all(s == ChunkStatus.FAILED.value for s in statuses):
            dscan.status = "failed"
            dscan.completed_at = time.time()
        elif any(s in (ChunkStatus.RUNNING.value, ChunkStatus.ASSIGNED.value)
                 for s in statuses):
            dscan.status = "running"
        elif (any(s == ChunkStatus.COMPLETED.value for s in statuses)
              and any(s == ChunkStatus.FAILED.value for s in statuses)
              and not any(s in (ChunkStatus.RUNNING.value,
                                ChunkStatus.ASSIGNED.value,
                                ChunkStatus.PENDING.value)
                          for s in statuses)):
            dscan.status = "partial"
            dscan.completed_at = time.time()

    def _check_heartbeats(self) -> None:
        """Mark workers as unhealthy if heartbeat timed out."""
        now = time.time()
        for w in self._workers.values():
            if (w.status in (WorkerStatus.ONLINE.value, WorkerStatus.BUSY.value)
                    and now - w.last_heartbeat > self.HEARTBEAT_TIMEOUT):
                w.status = WorkerStatus.UNHEALTHY.value
                _log.warning("Worker %s marked unhealthy (no heartbeat for %ds)",
                             w.worker_id, int(now - w.last_heartbeat))

    def _persist_worker(self, node: WorkerNode) -> None:
        if self._redis:
            try:
                self._redis.hset("sf:dist:workers", node.worker_id,
                                 json.dumps(node.to_dict()))
            except Exception:
                pass

    def _persist_scan(self, dscan: DistributedScan) -> None:
        if self._redis:
            try:
                self._redis.hset("sf:dist:scans", dscan.scan_id,
                                 json.dumps(dscan.to_dict()))
            except Exception:
                pass
