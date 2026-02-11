"""Backward-compatibility shim for correlation_service.py.

This module re-exports from services/correlation_service.py for backward compatibility.
"""

from __future__ import annotations

from .services.correlation_service import (
    CorrelationTrigger,
    CorrelationServiceConfig,
    CorrelationResult,
    CorrelationService,
    get_correlation_service,
)

__all__ = [
    "CorrelationTrigger",
    "CorrelationServiceConfig",
    "CorrelationResult",
    "CorrelationService",
    "get_correlation_service",
]
