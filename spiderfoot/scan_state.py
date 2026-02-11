"""Backward-compatibility shim for scan_state.py.

This module re-exports from scan/scan_state.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_state import (
    ScanState,
    StateTransition,
    InvalidTransitionError,
    ScanStateMachine,
)

__all__ = [
    "ScanState",
    "StateTransition",
    "InvalidTransitionError",
    "ScanStateMachine",
]
