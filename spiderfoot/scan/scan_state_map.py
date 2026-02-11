"""
Unified scan state mapping — single source of truth.

Maps between the three representations of scan state:
1. Python ``ScanState`` enum (canonical)
2. Protobuf ``ScanState`` enum (wire format)
3. Legacy DB status strings (backward compat)

All mappings are defined here and nowhere else. Other modules should
import from this module instead of doing ad-hoc string comparisons.

Usage::

    from spiderfoot.scan_state_map import (
        db_status_to_state,
        state_to_db_status,
        proto_to_state,
        state_to_proto,
    )

    state = db_status_to_state("FINISHED")   # -> ScanState.COMPLETED
    db_str = state_to_db_status(ScanState.COMPLETED)  # -> "FINISHED"
"""

from __future__ import annotations

import logging
from typing import Final

from .scan_state import ScanState

log = logging.getLogger("spiderfoot.scan_state_map")

__all__ = [
    "DB_STATUS_CREATED",
    "DB_STATUS_QUEUED",
    "DB_STATUS_STARTING",
    "DB_STATUS_RUNNING",
    "DB_STATUS_STARTED",
    "DB_STATUS_PAUSED",
    "DB_STATUS_ABORT_REQUESTED",
    "DB_STATUS_ABORTED",
    "DB_STATUS_FINISHED",
    "DB_STATUS_ERROR_FAILED",
    "db_status_to_state",
    "state_to_db_status",
    "proto_to_state",
    "state_to_proto",
    "db_status_to_proto",
    "proto_to_db_status",
]

# ── Legacy DB status string ↔ Python ScanState enum ──────────────────────────

_DB_TO_STATE = {
    "CREATED": ScanState.CREATED,
    "QUEUED": ScanState.QUEUED,
    "STARTING": ScanState.STARTING,
    "RUNNING": ScanState.RUNNING,
    "STARTED": ScanState.RUNNING,          # legacy alias
    "PAUSED": ScanState.PAUSED,
    "ABORT-REQUESTED": ScanState.STOPPING,
    "ABORTED": ScanState.CANCELLED,
    "FINISHED": ScanState.COMPLETED,
    "ERROR-FAILED": ScanState.FAILED,
    "FAILED": ScanState.FAILED,            # normalized alias
    "COMPLETED": ScanState.COMPLETED,      # normalized alias
    "CANCELLED": ScanState.CANCELLED,      # normalized alias
    "STOPPING": ScanState.STOPPING,        # normalized alias
}

# ── Named constants for legacy DB status strings ─────────────────────────────
# Use these instead of bare string literals like "FINISHED" or "ABORTED".
DB_STATUS_CREATED: Final[str] = "CREATED"
DB_STATUS_QUEUED: Final[str] = "QUEUED"
DB_STATUS_STARTING: Final[str] = "STARTING"
DB_STATUS_RUNNING: Final[str] = "RUNNING"
DB_STATUS_STARTED: Final[str] = "STARTED"
DB_STATUS_PAUSED: Final[str] = "PAUSED"
DB_STATUS_ABORT_REQUESTED: Final[str] = "ABORT-REQUESTED"
DB_STATUS_ABORTED: Final[str] = "ABORTED"
DB_STATUS_FINISHED: Final[str] = "FINISHED"
DB_STATUS_ERROR_FAILED: Final[str] = "ERROR-FAILED"

_STATE_TO_DB = {
    ScanState.CREATED: "CREATED",
    ScanState.QUEUED: "QUEUED",
    ScanState.STARTING: "STARTING",
    ScanState.RUNNING: "RUNNING",
    ScanState.PAUSED: "PAUSED",
    ScanState.STOPPING: "ABORT-REQUESTED",
    ScanState.COMPLETED: "FINISHED",
    ScanState.FAILED: "ERROR-FAILED",
    ScanState.CANCELLED: "ABORTED",
}


def db_status_to_state(status: str) -> ScanState:
    """Convert a legacy DB status string to a ``ScanState`` enum.

    Args:
        status: DB status string (e.g. ``"FINISHED"``, ``"ABORTED"``).

    Returns:
        Corresponding ``ScanState``.

    Raises:
        ValueError: If the status string is not recognized.
    """
    result = _DB_TO_STATE.get(status)
    if result is None:
        # Try case-insensitive
        result = _DB_TO_STATE.get(status.upper())
    if result is None:
        log.warning("Unknown DB status string: %r — defaulting to CREATED", status)
        return ScanState.CREATED
    return result


def state_to_db_status(state: ScanState) -> str:
    """Convert a ``ScanState`` enum to its legacy DB status string.

    Args:
        state: The ``ScanState`` enum value.

    Returns:
        Legacy DB status string (e.g. ``"FINISHED"``).
    """
    return _STATE_TO_DB.get(state, state.value)


# ── Protobuf ScanState ↔ Python ScanState enum ──────────────────────────────

# Proto enum values (from spiderfoot.v1.ScanState in spiderfoot.proto)
_PROTO_TO_STATE = {
    0: ScanState.CREATED,      # SCAN_STATE_UNKNOWN -> CREATED
    1: ScanState.CREATED,      # SCAN_STATE_CREATED
    2: ScanState.STARTING,     # SCAN_STATE_STARTING
    3: ScanState.RUNNING,      # SCAN_STATE_RUNNING
    4: ScanState.PAUSED,       # SCAN_STATE_PAUSED
    5: ScanState.STOPPING,     # SCAN_STATE_ABORT_REQUESTED
    6: ScanState.CANCELLED,    # SCAN_STATE_ABORTED
    7: ScanState.COMPLETED,    # SCAN_STATE_FINISHED
    8: ScanState.FAILED,       # SCAN_STATE_ERROR
}

_STATE_TO_PROTO = {
    ScanState.CREATED: 1,      # SCAN_STATE_CREATED
    ScanState.QUEUED: 1,       # No QUEUED in proto → map to CREATED
    ScanState.STARTING: 2,     # SCAN_STATE_STARTING
    ScanState.RUNNING: 3,      # SCAN_STATE_RUNNING
    ScanState.PAUSED: 4,       # SCAN_STATE_PAUSED
    ScanState.STOPPING: 5,     # SCAN_STATE_ABORT_REQUESTED
    ScanState.COMPLETED: 7,    # SCAN_STATE_FINISHED
    ScanState.FAILED: 8,       # SCAN_STATE_ERROR
    ScanState.CANCELLED: 6,    # SCAN_STATE_ABORTED
}


def proto_to_state(proto_value: int) -> ScanState:
    """Convert a protobuf ``ScanState`` enum value to Python ``ScanState``.

    Args:
        proto_value: Integer value from the proto ``ScanState`` enum.

    Returns:
        Corresponding ``ScanState``.
    """
    result = _PROTO_TO_STATE.get(proto_value)
    if result is None:
        log.warning("Unknown proto ScanState value: %d — defaulting to CREATED",
                    proto_value)
        return ScanState.CREATED
    return result


def state_to_proto(state: ScanState) -> int:
    """Convert a Python ``ScanState`` to its protobuf enum integer value.

    Args:
        state: The ``ScanState`` enum value.

    Returns:
        Integer proto enum value.
    """
    return _STATE_TO_PROTO.get(state, 0)


# ── Convenience: DB ↔ Proto (via ScanState) ──────────────────────────────────

def db_status_to_proto(status: str) -> int:
    """Convert a legacy DB status string directly to proto enum value."""
    return state_to_proto(db_status_to_state(status))


def proto_to_db_status(proto_value: int) -> str:
    """Convert a proto enum value directly to legacy DB status string."""
    return state_to_db_status(proto_to_state(proto_value))
