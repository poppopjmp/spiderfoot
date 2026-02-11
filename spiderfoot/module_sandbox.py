"""Backward-compatibility shim for module_sandbox.py.

This module re-exports from plugins/module_sandbox.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_sandbox import (
    ModuleSandbox,
    ResourceLimits,
    ResourceTracker,
    SandboxManager,
    SandboxResult,
    SandboxState,
)

__all__ = [
    "ModuleSandbox",
    "ResourceLimits",
    "ResourceTracker",
    "SandboxManager",
    "SandboxResult",
    "SandboxState",
]
