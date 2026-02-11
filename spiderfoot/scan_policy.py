"""Backward-compatibility shim for scan_policy.py.

This module re-exports from scan/scan_policy.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_policy import (
    PolicyAction,
    ViolationSeverity,
    PolicyViolation,
    PolicyCheckResult,
    ScanPolicy,
    PolicyEngine,
)

__all__ = [
    "PolicyAction",
    "ViolationSeverity",
    "PolicyViolation",
    "PolicyCheckResult",
    "ScanPolicy",
    "PolicyEngine",
]
