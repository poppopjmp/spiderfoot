"""Backward-compatibility shim for http_service.py.

This module re-exports from services/http_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.http_service import (
    HttpServiceConfig,
    HttpService,
)

__all__ = [
    "HttpServiceConfig",
    "HttpService",
]
