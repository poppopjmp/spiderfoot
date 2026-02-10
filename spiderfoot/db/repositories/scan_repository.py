"""
ScanRepository — Clean interface for scan instance operations.

Wraps ``SpiderFootDb`` scan methods (``scanInstanceCreate``,
``scanInstanceGet``, ``scanInstanceList``, ``scanInstanceDelete``,
``scanConfigSet``, ``scanConfigGet``) behind a type-safe facade.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from spiderfoot.db.repositories.base import AbstractRepository

log = logging.getLogger("spiderfoot.db.repositories.scan")


@dataclass
class ScanRecord:
    """Typed representation of a scan instance."""

    scan_id: str
    name: str
    target: str
    status: str
    created: float = 0.0
    started: float = 0.0
    ended: float = 0.0

    @classmethod
    def from_row(cls, row: tuple) -> "ScanRecord":
        """Build from a DB row tuple (guid, name, target, created, started, ended, status)."""
        if not row or len(row) < 7:
            raise ValueError(f"Invalid scan row: {row}")
        return cls(
            scan_id=str(row[0]),
            name=str(row[1]),
            target=str(row[2]),
            created=float(row[3] or 0),
            started=float(row[4] or 0),
            ended=float(row[5] or 0),
            status=str(row[6]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation."""
        return {
            "scan_id": self.scan_id,
            "name": self.name,
            "target": self.target,
            "status": self.status,
            "created": self.created,
            "started": self.started,
            "ended": self.ended,
        }


class ScanRepository(AbstractRepository):
    """Scan lifecycle operations."""

    def create_scan(
        self,
        scan_id: str,
        name: str,
        target: str,
    ) -> None:
        """Create a new scan instance."""
        self.dbh.scanInstanceCreate(scan_id, name, target)
        log.debug("Created scan %s (%s)", scan_id, name)

    def get_scan(self, scan_id: str) -> ScanRecord | None:
        """Get a single scan by ID.

        Returns:
            ``ScanRecord`` or None if not found.
        """
        row = self.dbh.scanInstanceGet(scan_id)
        if not row:
            return None
        try:
            return ScanRecord.from_row(row)
        except (ValueError, IndexError):
            return None

    def list_scans(self) -> list[ScanRecord]:
        """List all scan instances."""
        rows = self.dbh.scanInstanceList()
        results = []
        for row in (rows or []):
            try:
                results.append(ScanRecord.from_row(row))
            except (ValueError, IndexError):
                continue
        return results

    def update_status(
        self,
        scan_id: str,
        status: str,
        *,
        started: float | None = None,
        ended: float | None = None,
    ) -> None:
        """Update scan status and optional timestamps."""
        self.dbh.scanInstanceSet(scan_id, started=started, ended=ended, status=status)

    def delete_scan(self, scan_id: str) -> bool:
        """Delete a scan and all associated data.

        Returns:
            True if deleted, False otherwise.
        """
        return self.dbh.scanInstanceDelete(scan_id)

    def set_config(self, scan_id: str, config_data: str) -> None:
        """Store serialized scan configuration."""
        self.dbh.scanConfigSet(scan_id, config_data)

    def get_config(self, scan_id: str) -> dict[str, Any] | None:
        """Retrieve scan configuration."""
        return self.dbh.scanConfigGet(scan_id)

    def get_scan_log(
        self,
        scan_id: str,
        limit: int | None = None,
        from_row: int = 0,
        reverse: bool = False,
    ) -> list[Any]:
        """Retrieve scan log entries."""
        return self.dbh.scanLogs(scan_id, limit=limit, fromRowId=from_row, reverse=reverse)

    def get_scan_errors(self, scan_id: str, limit: int = 0) -> list[Any]:
        """Retrieve scan error entries."""
        return self.dbh.scanErrors(scan_id, limit=limit)
