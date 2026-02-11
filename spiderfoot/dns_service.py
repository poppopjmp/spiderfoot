"""Backward-compatibility shim for dns_service.py.

This module re-exports from services/dns_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.dns_service import (
    DnsServiceConfig,
    DnsService,
)

__all__ = [
    "DnsServiceConfig",
    "DnsService",
]
