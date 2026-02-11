"""Backward-compatibility shim for scan_profile.py.

This module re-exports from scan/scan_profile.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_profile import (
    ProfileCategory,
    ScanProfile,
    ProfileManager,
    get_profile_manager,
)

__all__ = [
    "ProfileCategory",
    "ScanProfile",
    "ProfileManager",
    "get_profile_manager",
]
