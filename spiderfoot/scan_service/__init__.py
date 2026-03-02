"""Scan service package — DEPRECATED.

This package has been merged into :mod:`spiderfoot.scan`.
These re-exports exist only for backward compatibility.
Import from ``spiderfoot.scan.scanner`` instead.
"""

from __future__ import annotations

from spiderfoot.scan.scanner import SpiderFootScanner, startSpiderFootScanner

__all__ = ["SpiderFootScanner", "startSpiderFootScanner"]
