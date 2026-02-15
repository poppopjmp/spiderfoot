"""Scan service package.

Contains :class:`SpiderFootScanner`, the core scan engine that orchestrates
module loading, event dispatching, and scan lifecycle management.
"""

from __future__ import annotations

from spiderfoot.scan_service.scanner import SpiderFootScanner

__all__ = ["SpiderFootScanner"]
