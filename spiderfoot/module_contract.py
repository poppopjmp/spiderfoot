"""Backward-compatibility shim for module_contract.py.

This module re-exports from plugins/module_contract.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_contract import (
    DataSourceModel,
    ModuleMeta,
    ModuleValidationResult,
    SpiderFootModuleProtocol,
    validate_module,
    validate_module_batch,
)

__all__ = [
    "DataSourceModel",
    "ModuleMeta",
    "ModuleValidationResult",
    "SpiderFootModuleProtocol",
    "validate_module",
    "validate_module_batch",
]
