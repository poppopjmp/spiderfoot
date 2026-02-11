"""Backward-compatibility shim for cli_service.py.

This module re-exports from services/cli_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.cli_service import (
    cmd_version,
    cmd_status,
    cmd_metrics,
    cmd_config_get,
    cmd_config_set,
)

__all__ = [
    "cmd_version",
    "cmd_status",
    "cmd_metrics",
    "cmd_config_get",
    "cmd_config_set",
]
