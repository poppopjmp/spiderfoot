# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp__stor_jsonl
# Purpose:      SpiderFoot plug-in for writing events to a JSONL file.
#
# Author:       SpiderFoot Team
#
# Created:      2026
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""SpiderFoot plug-in module: _stor_jsonl.

Writes every event to a newline-delimited JSON file (JSONL / NDJSON).
Each line is a self-contained JSON object:

    {"generated":1700000000,"type":"IP_ADDRESS","data":"1.2.3.4","module":"sfp_dns",...}
    {"generated":1700000001,"type":"TCP_PORT_OPEN","data":"1.2.3.4:443","module":"sfp_portscan",...}

Useful for:
  - Streaming results to external pipelines (Splunk, Elastic, jq)
  - Archiving scan output as portable flat files
  - Post-processing with standard UNIX tools (grep, wc, sort)
"""

import json
import logging
import os
import threading
from pathlib import Path

from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin

log = logging.getLogger(__name__)


class sfp__stor_jsonl(SpiderFootModernPlugin):
    """Write every scan event to a JSONL file on disk."""

    meta = {
        "name": "JSONL File Output",
        "summary": (
            "Writes scan events to a newline-delimited JSON (.jsonl) file. "
            "Each line is a self-contained JSON object with full event metadata."
        ),
        "flags": [],
    }

    _priority = 0  # storage modules run at highest priority

    opts = {
        "_store": True,
        "output_dir": "logs/scans",
        "include_root": False,
        "max_file_size_mb": 0,  # 0 = unlimited
    }

    optdescs = {
        "output_dir": "Directory to write JSONL files into (one file per scan).",
        "include_root": "Include the ROOT seed event in the output?",
        "max_file_size_mb": (
            "Maximum file size in MB before rotating to a new file (0 = unlimited)."
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self._fh: object | None = None
        self._lock = threading.Lock()
        self._file_index = 0
        self._bytes_written = 0
        self._scan_id: str = ""

    def setup(self, sfc, userOpts: dict | None = None) -> None:
        super().setup(sfc, userOpts or {})
        self._fh = None
        self._file_index = 0
        self._bytes_written = 0

    def watchedEvents(self):
        return ["*"]

    # ── internal helpers ────────────────────────────────────────

    def _open_file(self, scan_id: str) -> None:
        """Open (or rotate) the JSONL output file."""
        out_dir = Path(self.opts.get("output_dir", "logs/scans"))
        out_dir.mkdir(parents=True, exist_ok=True)

        suffix = f".{self._file_index}" if self._file_index > 0 else ""
        filename = out_dir / f"{scan_id}{suffix}.jsonl"

        try:
            self._fh = open(filename, "a", encoding="utf-8")  # noqa: SIM115
            log.info("JSONL output → %s", filename)
        except OSError as exc:
            self.error(f"Cannot open JSONL file {filename}: {exc}")
            self._fh = None

    def _maybe_rotate(self) -> None:
        """Rotate the file if max_file_size_mb is set and exceeded."""
        max_bytes = int(self.opts.get("max_file_size_mb", 0)) * 1024 * 1024
        if max_bytes <= 0:
            return
        if self._bytes_written >= max_bytes:
            if self._fh:
                self._fh.close()
            self._file_index += 1
            self._bytes_written = 0
            self._open_file(self._scan_id)

    # ── event handler ──────────────────────────────────────────

    def handleEvent(self, sfEvent) -> None:
        if not self.opts.get("_store", True):
            return

        if sfEvent.eventType == "ROOT" and not self.opts.get("include_root", False):
            return

        # Lazily open the output file on first event
        if self._fh is None:
            self._scan_id = self.getScanId() or "unknown"
            self._open_file(self._scan_id)
            if self._fh is None:
                return  # file open failed

        record = sfEvent.asDict(full=True)
        line = json.dumps(record, default=str, ensure_ascii=False) + "\n"

        with self._lock:
            try:
                self._fh.write(line)
                self._fh.flush()
                self._bytes_written += len(line.encode("utf-8"))
                self._maybe_rotate()
            except OSError as exc:
                self.error(f"JSONL write failed: {exc}")

    def finish(self) -> None:
        """Close the file handle when the scan is complete."""
        if self._fh:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
        super().finish()
