"""Backward-compatibility shim for visualization_service.py.

This module re-exports from reporting/visualization_service.py for backward compatibility.
"""

from __future__ import annotations

from .reporting.visualization_service import (
    VisualizationServiceError,
    VisualizationService,
)

__all__ = [
    "VisualizationServiceError",
    "VisualizationService",
]
