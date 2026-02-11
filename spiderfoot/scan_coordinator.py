"""Backward-compatibility shim for scan_coordinator.py.

This module re-exports from scan/scan_coordinator.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_coordinator import (
    NodeState,
    WorkState,
    DistributionStrategy,
    ScannerNode,
    ScanWork,
    WorkAssignment,
    ScanCoordinator,
    get_coordinator,
)

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
