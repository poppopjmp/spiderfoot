"""Backward-compatibility shim for config_schema.py.

This module re-exports from config/config_schema.py for backward compatibility.
"""

from __future__ import annotations

from .config.config_schema import (
    FieldSchema,
    ConfigSchema,
    infer_schema_from_module,
    validate_module_config,
)

__all__ = [
    "FieldSchema",
    "ConfigSchema",
    "infer_schema_from_module",
    "validate_module_config",
]
