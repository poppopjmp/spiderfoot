"""Backward-compatibility shim for scan_state_map.py.

This module re-exports from scan/scan_state_map.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_state_map import (
    db_status_to_state,
    state_to_db_status,
    proto_to_state,
    state_to_proto,
    db_status_to_proto,
)

__all__ = [
    "db_status_to_state",
    "state_to_db_status",
    "proto_to_state",
    "state_to_proto",
    "db_status_to_proto",
]
