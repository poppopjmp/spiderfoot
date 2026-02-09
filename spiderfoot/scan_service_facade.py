"""
Scan Service Facade — Unified scan lifecycle management.

Combines ``ScanRepository`` (Cycle 23) with ``ScanStateMachine``
for formal state transition enforcement.  Provides a clean API
for the scan router to consume via FastAPI ``Depends()``.

Cycle 27 — wires two previously-unwired components together.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from spiderfoot.db.repositories.scan_repository import ScanRecord, ScanRepository
from spiderfoot.scan_state import (
    InvalidTransitionError,
    ScanState,
    ScanStateMachine,
)

log = logging.getLogger("spiderfoot.scan_service_facade")


class ScanServiceError(Exception):
    """Raised when a scan operation fails."""


class ScanService:
    """High-level scan lifecycle management.

    Wraps ``ScanRepository`` for persistence and ``ScanStateMachine``
    for state-transition validation.  One ``ScanService`` is created
    per request via the ``get_scan_service()`` Depends provider.
    """

    def __init__(self, repo: ScanRepository, *, dbh=None) -> None:
        self._repo = repo
        self._dbh = dbh  # fallback raw dbh for methods not yet on repo
        self._machines: Dict[str, ScanStateMachine] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Scan CRUD (delegates to repository)
    # ------------------------------------------------------------------

    def list_scans(self) -> List[ScanRecord]:
        """Return all scan records."""
        return self._repo.list_scans()

    def get_scan(self, scan_id: str) -> Optional[ScanRecord]:
        """Get a single scan record or ``None``."""
        return self._repo.get_scan(scan_id)

    def create_scan(self, scan_id: str, name: str, target: str) -> None:
        """Create a new scan instance in the DB."""
        self._repo.create_scan(scan_id, name, target)
        # Bootstrap the state machine for this scan
        sm = ScanStateMachine(scan_id, initial_state=ScanState.CREATED)
        with self._lock:
            self._machines[scan_id] = sm

    def delete_scan(self, scan_id: str) -> bool:
        """Delete a scan instance."""
        result = self._repo.delete_scan(scan_id)
        with self._lock:
            self._machines.pop(scan_id, None)
        return result

    def delete_scan_full(self, scan_id: str) -> None:
        """Delete a scan and ALL related data (results, config, logs)."""
        dbh = self._ensure_dbh()
        dbh.scanResultDelete(scan_id)
        dbh.scanConfigDelete(scan_id)
        dbh.scanInstanceDelete(scan_id)
        with self._lock:
            self._machines.pop(scan_id, None)

    # ------------------------------------------------------------------
    # State management  (ScanStateMachine)
    # ------------------------------------------------------------------

    def _get_machine(self, scan_id: str) -> ScanStateMachine:
        """Get or lazily create a state machine for *scan_id*."""
        with self._lock:
            if scan_id in self._machines:
                return self._machines[scan_id]

        # Bootstrap from the DB status
        record = self._repo.get_scan(scan_id)
        if record is None:
            raise ScanServiceError(f"Scan not found: {scan_id}")

        try:
            initial = ScanState(record.status)
        except ValueError:
            # Legacy status string — map to closest state
            status_map = {
                "FINISHED": ScanState.COMPLETED,
                "ERROR-FAILED": ScanState.FAILED,
                "ABORTED": ScanState.CANCELLED,
                "ABORT-REQUESTED": ScanState.STOPPING,
            }
            initial = status_map.get(record.status, ScanState.CREATED)

        sm = ScanStateMachine(scan_id, initial_state=initial)
        with self._lock:
            self._machines.setdefault(scan_id, sm)
            return self._machines[scan_id]

    def stop_scan(self, scan_id: str) -> str:
        """Request a scan abort with state validation.

        Transitions the state machine to STOPPING/CANCELLED and
        persists the ``ABORTED`` status in the DB.

        Returns:
            The new status string written to the DB.
        """
        sm = self._get_machine(scan_id)

        # Try STOPPING first (from RUNNING), then CANCELLED (from others)
        new_state = None
        for target in (ScanState.STOPPING, ScanState.CANCELLED):
            if sm.can_transition(target):
                new_state = sm.transition(target, reason="User abort via API")
                break

        if new_state is None:
            raise ScanServiceError(
                f"Cannot stop scan {scan_id} in state {sm.state.value}"
            )

        # Persist — the DB column uses "ABORTED", not the enum value
        self._repo.update_status(scan_id, "ABORTED")
        return "ABORTED"

    def get_scan_state(self, scan_id: str) -> Dict[str, Any]:
        """Return state machine info for a scan."""
        sm = self._get_machine(scan_id)
        return sm.to_dict()

    # ------------------------------------------------------------------
    # Config / logs  (delegate to repo)
    # ------------------------------------------------------------------

    def get_config(self, scan_id: str) -> Optional[Dict[str, Any]]:
        return self._repo.get_config(scan_id)

    def set_config(self, scan_id: str, config_data: str) -> None:
        self._repo.set_config(scan_id, config_data)

    def get_scan_log(self, scan_id: str, **kw) -> List[Any]:
        return self._repo.get_scan_log(scan_id, **kw)

    def get_scan_errors(self, scan_id: str, limit: int = 0) -> List[Any]:
        return self._repo.get_scan_errors(scan_id, limit=limit)

    # ------------------------------------------------------------------
    # Raw DB access  (transitional — for endpoints not yet migrated)
    # ------------------------------------------------------------------

    def _ensure_dbh(self):
        """Return the raw DB handle for methods not yet in the repo."""
        if self._dbh is not None:
            return self._dbh
        if hasattr(self._repo, "_dbh") and self._repo._dbh is not None:
            return self._repo._dbh
        raise ScanServiceError("No database handle available")

    @property
    def dbh(self):
        """Expose raw DB handle for un-migrated endpoints."""
        return self._ensure_dbh()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying repository."""
        self._repo.close()
