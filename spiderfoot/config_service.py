"""Backward-compatibility shim for config_service.py.

This module re-exports from services/config_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.config_service import (
    ConfigValidator,
    ConfigService,
    get_config_service,
    reset_config_service,
)

__all__ = [
    "ConfigValidator",
    "ConfigService",
    "get_config_service",
    "reset_config_service",
]
