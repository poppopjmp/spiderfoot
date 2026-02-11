"""Backward-compatibility shim for scan_templates.py.

This module re-exports from scan/scan_templates.py for backward compatibility.
"""

from __future__ import annotations

from .scan.scan_templates import (
    TemplateCategory,
    ScanTemplate,
    TemplateRegistry,
)

__all__ = [
    "TemplateCategory",
    "ScanTemplate",
    "TemplateRegistry",
]
