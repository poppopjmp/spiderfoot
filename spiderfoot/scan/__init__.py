"""
SpiderFoot Scan — scan lifecycle, scheduling, coordination, and state management.

This sub-package groups scan-related modules for cleaner imports.

Usage::

    from spiderfoot.scan import ScanStateMachine, ScanState
    from spiderfoot.scan.state import ScanStateMachine
"""

from __future__ import annotations

# Re-export key scan classes for convenience
from spiderfoot.scan_state import ScanState, ScanStateMachine  # noqa: F401
from spiderfoot.scan_state_map import (  # noqa: F401
    db_status_to_state,
    state_to_db_status,
    proto_to_state,
    state_to_proto,
)

__all__ = [
    "ScanState",
    "ScanStateMachine",
    "db_status_to_state",
    "state_to_db_status",
    "proto_to_state",
    "state_to_proto",
    "scan_coordinator",
    "scan_diff",
    "scan_event_bridge",
    "scan_orchestrator",
    "scan_policy",
    "scan_profile",
    "scan_progress",
    "scan_queue",
    "scan_scheduler",
    "scan_service_facade",
    "scan_state",
    "scan_state_map",
    "scan_templates",
    "scan_workflow",
    "scan_delta",
]
