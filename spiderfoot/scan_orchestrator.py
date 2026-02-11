"""Backward-compatibility shim for scan_orchestrator.py.

This module re-exports from scan/scan_orchestrator.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_orchestrator import (
    ScanPhase,
    PhaseResult,
    ModuleSchedule,
    ScanOrchestrator,
)

__all__ = [
    "ScanPhase",
    "PhaseResult",
    "ModuleSchedule",
    "ScanOrchestrator",
]
