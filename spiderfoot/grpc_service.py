"""Backward-compatibility shim for grpc_service.py.

This module re-exports from services/grpc_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.grpc_service import (
    ServiceClient,
    ServiceCallError,
    ServiceServer,
    ServiceDirectory,
)

__all__ = [
    "ServiceClient",
    "ServiceCallError",
    "ServiceServer",
    "ServiceDirectory",
]
