"""Scan service package — DEPRECATED.

This package has been fully merged into :mod:`spiderfoot.scan`.
The re-exports below exist only for backward compatibility;
import directly from ``spiderfoot.scan.scanner`` in new code.

Example migration::

    # old
    from spiderfoot.scan_service.scanner import SpiderFootScanner
    # new
    from spiderfoot.scan.scanner import SpiderFootScanner
"""

from __future__ import annotations

import warnings

warnings.warn(
    "spiderfoot.scan_service is deprecated and will be removed in a future release. "
    "Import from spiderfoot.scan.scanner instead.",
    DeprecationWarning,
    stacklevel=2,
)

from spiderfoot.scan.scanner import SpiderFootScanner, startSpiderFootScanner

__all__ = ["SpiderFootScanner", "startSpiderFootScanner"]
