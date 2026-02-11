"""Backward-compatibility shim for module_api_client.py.

This module re-exports from plugins/module_api_client.py for backward compatibility.
"""

from __future__ import annotations

from .plugins.module_api_client import (
    ApiResponse,
    HttpMethod,
    ModuleApiClient,
    RateLimiter,
    RequestConfig,
    RequestRecord,
    ResponseFormat,
)

__all__ = [
    "ApiResponse",
    "HttpMethod",
    "ModuleApiClient",
    "RateLimiter",
    "RequestConfig",
    "RequestRecord",
    "ResponseFormat",
]
