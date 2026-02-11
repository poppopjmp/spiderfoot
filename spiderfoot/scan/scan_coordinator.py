#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         scan_coordinator
# Purpose:      Coordinate scans across multiple SpiderFoot scanner instances.
#               Handles work distribution, heartbeat monitoring, failover,
#               and result aggregation.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
Distributed Scan Coordination

Distributes scan workloads across multiple scanner nodes with automatic
health monitoring and failover::

    from spiderfoot.scan.scan_coordinator import ScanCoordinator, ScannerNode

    coord = ScanCoordinator()
    coord.register_node(ScannerNode("scanner-1", "http://scanner1:8001"))
    coord.register_node(ScannerNode("scanner-2", "http://scanner2:8001"))

    work_id = coord.submit_work(ScanWork(
        scan_id="abc123",
        target="example.com",
        modules=["sfp_dnsresolve", "sfp_shodan"],
    ))
    status = coord.get_work_status(work_id)
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ..config.constants import DEFAULT_TTL_ONE_HOUR

log = logging.getLogger("spiderfoot.scan_coordinator")

__all__ = [
    "NodeState",
    "WorkState",
    "DistributionStrategy",
    "ScannerNode",
    "ScanWork",
    "WorkAssignment",
    "ScanCoordinator",
    "get_coordinator",
]


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class NodeState(Enum):
    """Scanner node lifecycle states."""
    ONLINE = "online"
    OFFLINE = "offline"
    DRAINING = "draining"      # no new work, finish existing
    MAINTENANCE = "maintenance"  # manually paused


class WorkState(Enum):
    """Distributed work item states."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REASSIGNED = "reassigned"
    CANCELLED = "cancelled"


class DistributionStrategy(Enum):
    """Work distribution algorithm."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    HASH_BASED = "hash_based"     # consistent hashing by target
    RANDOM = "random"


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class ScannerNode:
    """Represents a remote scanner instance."""

    node_id: str
    endpoint: str
    state: NodeState = NodeState.ONLINE
    capacity: int = 5        # max concurrent scans
    tags: list[str] = field(default_factory=list)  # e.g. ["gpu", "high-mem"]
    weight: int = 1          # for weighted round-robin

    # Runtime state (managed by coordinator)
    active_work: int = 0
    last_heartbeat: float = 0.0
    total_completed: int = 0
    total_failed: int = 0
    registered_at: float = field(default_factory=time.time)

    @property
    def available_capacity(self) -> int:
        """Return the remaining work capacity for this node."""
        return max(0, self.capacity - self.active_work)

    @property
    def is_available(self) -> bool:
        """Return True if the node is online and has spare capacity."""
        return (
            self.state == NodeState.ONLINE
            and self.available_capacity > 0
        )

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "node_id": self.node_id,
            "endpoint": self.endpoint,
            "state": self.state.value,
            "capacity": self.capacity,
            "active_work": self.active_work,
            "available_capacity": self.available_capacity,
            "tags": self.tags,
            "weight": self.weight,
            "last_heartbeat": self.last_heartbeat,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
        }


@dataclass
class ScanWork:
    """A unit of work to be distributed."""

    scan_id: str
    target: str
    modules: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    priority: int = 0       # higher = more urgent
    required_tags: list[str] = field(default_factory=list)
    timeout_seconds: int = DEFAULT_TTL_ONE_HOUR
    max_retries: int = 2

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "modules": self.modules,
            "options": self.options,
            "priority": self.priority,
            "required_tags": self.required_tags,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
        }


@dataclass
class WorkAssignment:
    """Tracks a specific work-to-node binding."""

    work_id: str
    work: ScanWork
    node_id: str | None = None
    state: WorkState = WorkState.PENDING
    assigned_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    retries: int = 0
    error: str = ""
    result: dict | None = None

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "work_id": self.work_id,
            "scan_id": self.work.scan_id,
            "target": self.work.target,
            "node_id": self.node_id,
            "state": self.state.value,
            "assigned_at": self.assigned_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retries": self.retries,
            "error": self.error,
        }


# ------------------------------------------------------------------
# Coordinator
# ------------------------------------------------------------------

class ScanCoordinator:
    """Distributes scan work across multiple scanner nodes.

    Thread-safe coordinator that manages node registration, work
    submission, health monitoring, and automatic failover.
    """

    def __init__(self, *,
                 strategy: DistributionStrategy = DistributionStrategy.LEAST_LOADED,
                 heartbeat_interval: float = 30.0,
                 heartbeat_timeout: float = 90.0,
                 auto_monitor: bool = False) -> None:
        """Initialize the ScanCoordinator."""
        self._lock = threading.Lock()
        self._nodes: dict[str, ScannerNode] = {}
        self._work: dict[str, WorkAssignment] = {}
        self._pending_queue: list[str] = []  # work_ids ordered by priority
        self._strategy = strategy
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout
        self._rr_index = 0  # round-robin counter
        self._callbacks: dict[str, list[Callable]] = {
            "work_assigned": [],
            "work_completed": [],
            "work_failed": [],
            "node_offline": [],
            "node_online": [],
        }
        self._monitor_thread: threading.Thread | None = None
        self._running = False

        if auto_monitor:
            self.start_monitor()

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def register_node(self, node: ScannerNode) -> None:
        """Register a scanner node."""
        with self._lock:
            node.last_heartbeat = time.time()
            self._nodes[node.node_id] = node
            log.info("Registered node %s at %s (capacity=%d)",
                     node.node_id, node.endpoint, node.capacity)
            self._fire("node_online", node)

    def unregister_node(self, node_id: str, *,
                        reassign: bool = True) -> ScannerNode | None:
        """Remove a node, optionally reassigning its active work."""
        with self._lock:
            node = self._nodes.pop(node_id, None)
            if node is None:
                return None
            if reassign:
                self._reassign_from_node(node_id)
            log.info("Unregistered node %s", node_id)
            return node

    def get_node(self, node_id: str) -> ScannerNode | None:
        """Return a registered node by its ID, or None."""
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> list[ScannerNode]:
        """Return a list of all registered scanner nodes."""
        with self._lock:
            return list(self._nodes.values())

    def set_node_state(self, node_id: str, state: NodeState) -> bool:
        """Change node state (e.g., to DRAINING)."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            old = node.state
            node.state = state
            log.info("Node %s: %s -> %s", node_id, old.value, state.value)
            if state == NodeState.OFFLINE:
                self._fire("node_offline", node)
                self._reassign_from_node(node_id)
            return True

    def heartbeat(self, node_id: str, *,
                  active_work: int | None = None) -> bool:
        """Record a heartbeat from a node."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.last_heartbeat = time.time()
            if active_work is not None:
                node.active_work = active_work
            if node.state == NodeState.OFFLINE:
                node.state = NodeState.ONLINE
                log.info("Node %s came back online", node_id)
                self._fire("node_online", node)
            return True

    # ------------------------------------------------------------------
    # Work submission
    # ------------------------------------------------------------------

    def submit_work(self, work: ScanWork) -> str:
        """Submit work for distribution. Returns work_id."""
        work_id = str(uuid.uuid4())[:12]
        assignment = WorkAssignment(work_id=work_id, work=work)

        with self._lock:
            self._work[work_id] = assignment

            # Try immediate assignment
            node = self._select_node(work)
            if node:
                self._assign(assignment, node)
            else:
                # Queue for later
                self._enqueue(work_id, work.priority)
                log.info("Work %s queued (no node available)", work_id)

        return work_id

    def cancel_work(self, work_id: str) -> bool:
        """Cancel pending or assigned work."""
        with self._lock:
            assignment = self._work.get(work_id)
            if assignment is None:
                return False
            if assignment.state in (WorkState.COMPLETED, WorkState.CANCELLED):
                return False

            old_node_id = assignment.node_id
            assignment.state = WorkState.CANCELLED
            assignment.completed_at = time.time()

            # Free capacity
            if old_node_id:
                node = self._nodes.get(old_node_id)
                if node:
                    node.active_work = max(0, node.active_work - 1)

            # Remove from pending queue
            if work_id in self._pending_queue:
                self._pending_queue.remove(work_id)

            log.info("Cancelled work %s", work_id)
            return True

    def get_work_status(self, work_id: str) -> dict | None:
        """Get status of a work item."""
        with self._lock:
            a = self._work.get(work_id)
            return a.to_dict() if a else None

    def list_work(self, *, state: WorkState | None = None) -> list[dict]:
        """List all work items, optionally filtered by state."""
        with self._lock:
            items = self._work.values()
            if state:
                items = [a for a in items if a.state == state]
            return [a.to_dict() for a in items]

    # ------------------------------------------------------------------
    # Work lifecycle callbacks (from scanner nodes)
    # ------------------------------------------------------------------

    def report_started(self, work_id: str) -> bool:
        """Scanner reports work has started executing."""
        with self._lock:
            a = self._work.get(work_id)
            if a is None or a.state != WorkState.ASSIGNED:
                return False
            a.state = WorkState.RUNNING
            a.started_at = time.time()
            return True

    def report_completed(self, work_id: str,
                         result: dict | None = None) -> bool:
        """Scanner reports work completed successfully."""
        with self._lock:
            a = self._work.get(work_id)
            if a is None:
                return False
            a.state = WorkState.COMPLETED
            a.completed_at = time.time()
            a.result = result

            # Free capacity
            if a.node_id:
                node = self._nodes.get(a.node_id)
                if node:
                    node.active_work = max(0, node.active_work - 1)
                    node.total_completed += 1

            self._fire("work_completed", a)
            self._try_assign_pending()
            return True

    def report_failed(self, work_id: str, error: str = "") -> bool:
        """Scanner reports work failed."""
        with self._lock:
            a = self._work.get(work_id)
            if a is None:
                return False

            # Free capacity
            if a.node_id:
                node = self._nodes.get(a.node_id)
                if node:
                    node.active_work = max(0, node.active_work - 1)
                    node.total_failed += 1

            a.error = error
            a.retries += 1

            if a.retries <= a.work.max_retries:
                # Retry on a different node
                a.state = WorkState.REASSIGNED
                a.node_id = None
                node = self._select_node(a.work, exclude={a.node_id} if a.node_id else set())
                if node:
                    self._assign(a, node)
                else:
                    self._enqueue(work_id, a.work.priority)
                log.warning("Work %s failed (retry %d/%d): %s",
                            work_id, a.retries, a.work.max_retries, error)
            else:
                a.state = WorkState.FAILED
                a.completed_at = time.time()
                log.error("Work %s permanently failed: %s", work_id, error)
                self._fire("work_failed", a)

            self._try_assign_pending()
            return True

    # ------------------------------------------------------------------
    # Distribution logic
    # ------------------------------------------------------------------

    def _select_node(self, work: ScanWork,
                     exclude: set[str] | None = None) -> ScannerNode | None:
        """Select the best node for the work based on strategy."""
        exclude = exclude or set()
        candidates = [
            n for n in self._nodes.values()
            if n.is_available
            and n.node_id not in exclude
            and self._matches_tags(n, work.required_tags)
        ]
        if not candidates:
            return None

        if self._strategy == DistributionStrategy.LEAST_LOADED:
            return min(candidates, key=lambda n: n.active_work / max(n.capacity, 1))

        if self._strategy == DistributionStrategy.ROUND_ROBIN:
            idx = self._rr_index % len(candidates)
            self._rr_index += 1
            return candidates[idx]

        if self._strategy == DistributionStrategy.HASH_BASED:
            h = int(hashlib.md5(work.target.encode()).hexdigest(), 16)
            return candidates[h % len(candidates)]

        if self._strategy == DistributionStrategy.RANDOM:
            import random
            return random.choice(candidates)

        return candidates[0]

    def _matches_tags(self, node: ScannerNode,
                      required: list[str]) -> bool:
        """Check that node has all required tags."""
        if not required:
            return True
        return all(tag in node.tags for tag in required)

    def _assign(self, assignment: WorkAssignment,
                node: ScannerNode) -> None:
        """Assign work to a node (caller holds lock)."""
        assignment.node_id = node.node_id
        assignment.state = WorkState.ASSIGNED
        assignment.assigned_at = time.time()
        node.active_work += 1

        log.info("Assigned work %s -> node %s",
                 assignment.work_id, node.node_id)
        self._fire("work_assigned", assignment)

    def _enqueue(self, work_id: str, priority: int) -> None:
        """Insert work_id into pending queue ordered by priority (descending)."""
        if work_id in self._pending_queue:
            return
        # Simple insertion sort — priority descending
        inserted = False
        for i, existing_id in enumerate(self._pending_queue):
            existing = self._work.get(existing_id)
            if existing and existing.work.priority < priority:
                self._pending_queue.insert(i, work_id)
                inserted = True
                break
        if not inserted:
            self._pending_queue.append(work_id)

    def _try_assign_pending(self) -> None:
        """Try to assign queued work to available nodes (caller holds lock)."""
        assigned = []
        for work_id in list(self._pending_queue):
            a = self._work.get(work_id)
            if a is None:
                assigned.append(work_id)
                continue
            node = self._select_node(a.work)
            if node:
                self._assign(a, node)
                assigned.append(work_id)
        for wid in assigned:
            if wid in self._pending_queue:
                self._pending_queue.remove(wid)

    def _reassign_from_node(self, node_id: str) -> None:
        """Re-queue all active work from a failed/removed node (caller holds lock)."""
        for a in self._work.values():
            if a.node_id == node_id and a.state in (
                    WorkState.ASSIGNED, WorkState.RUNNING):
                a.state = WorkState.REASSIGNED
                a.node_id = None
                a.retries += 1
                if a.retries <= a.work.max_retries:
                    node = self._select_node(a.work, exclude={node_id})
                    if node:
                        self._assign(a, node)
                    else:
                        self._enqueue(a.work_id, a.work.priority)
                else:
                    a.state = WorkState.FAILED
                    a.completed_at = time.time()
                    a.error = f"Node {node_id} removed, max retries exceeded"
                    self._fire("work_failed", a)

    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------

    def start_monitor(self) -> None:
        """Start background health monitor thread."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="scan-coord-monitor",
        )
        self._monitor_thread.start()
        log.info("Started coordinator monitor (interval=%.1fs, timeout=%.1fs)",
                 self._heartbeat_interval, self._heartbeat_timeout)

    def stop_monitor(self) -> None:
        """Stop the health monitor."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                self._check_heartbeats()
                self._check_timeouts()
            except Exception as e:
                log.error("Monitor error: %s", e)
            time.sleep(self._heartbeat_interval)

    def _check_heartbeats(self) -> None:
        """Mark nodes offline if heartbeat timed out."""
        now = time.time()
        with self._lock:
            for node in list(self._nodes.values()):
                if node.state == NodeState.ONLINE:
                    elapsed = now - node.last_heartbeat
                    if elapsed > self._heartbeat_timeout:
                        log.warning("Node %s heartbeat timeout (%.0fs)",
                                    node.node_id, elapsed)
                        node.state = NodeState.OFFLINE
                        self._fire("node_offline", node)
                        self._reassign_from_node(node.node_id)

    def _check_timeouts(self) -> None:
        """Fail work items that exceeded their timeout."""
        now = time.time()
        with self._lock:
            for a in list(self._work.values()):
                if a.state == WorkState.RUNNING and a.started_at > 0:
                    elapsed = now - a.started_at
                    if elapsed > a.work.timeout_seconds:
                        log.warning("Work %s timed out after %.0fs",
                                    a.work_id, elapsed)
                        # Free capacity
                        if a.node_id:
                            node = self._nodes.get(a.node_id)
                            if node:
                                node.active_work = max(0, node.active_work - 1)
                        a.error = f"Timeout after {int(elapsed)}s"
                        a.retries += 1
                        if a.retries <= a.work.max_retries:
                            a.state = WorkState.REASSIGNED
                            a.node_id = None
                            node = self._select_node(a.work)
                            if node:
                                self._assign(a, node)
                            else:
                                self._enqueue(a.work_id, a.work.priority)
                        else:
                            a.state = WorkState.FAILED
                            a.completed_at = now
                            self._fire("work_failed", a)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for coordinator events."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _fire(self, event: str, data: Any) -> None:
        """Fire callbacks (best-effort)."""
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                log.error("Callback error on %s: %s", event, e)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return coordinator statistics."""
        with self._lock:
            total = len(self._work)
            by_state = {}
            for a in self._work.values():
                by_state[a.state.value] = by_state.get(a.state.value, 0) + 1

            nodes_online = sum(
                1 for n in self._nodes.values()
                if n.state == NodeState.ONLINE
            )
            total_capacity = sum(n.capacity for n in self._nodes.values())
            used_capacity = sum(n.active_work for n in self._nodes.values())

            return {
                "total_nodes": len(self._nodes),
                "nodes_online": nodes_online,
                "total_capacity": total_capacity,
                "used_capacity": used_capacity,
                "total_work": total,
                "pending": len(self._pending_queue),
                "work_by_state": by_state,
                "strategy": self._strategy.value,
            }


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_coordinator: ScanCoordinator | None = None
_coordinator_lock = threading.Lock()


def get_coordinator(**kwargs: Any) -> ScanCoordinator:
    """Return the global ScanCoordinator singleton."""
    global _coordinator
    if _coordinator is None:
        with _coordinator_lock:
            if _coordinator is None:
                _coordinator = ScanCoordinator(**kwargs)
    return _coordinator
