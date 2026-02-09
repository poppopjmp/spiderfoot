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
from spiderfoot.db.repositories.event_repository import EventRepository
from spiderfoot.scan_state import (
    InvalidTransitionError,
    ScanState,
    ScanStateMachine,
)
from spiderfoot.scan_state_map import db_status_to_state, state_to_db_status

log = logging.getLogger("spiderfoot.scan_service_facade")


class ScanServiceError(Exception):
    """Raised when a scan operation fails."""


class ScanService:
    """High-level scan lifecycle management.

    Wraps ``ScanRepository`` for persistence and ``ScanStateMachine``
    for state-transition validation.  One ``ScanService`` is created
    per request via the ``get_scan_service()`` Depends provider.
    """

    def __init__(self, repo: ScanRepository, *, dbh=None,
                 event_repo: Optional[EventRepository] = None) -> None:
        self._repo = repo
        self._event_repo = event_repo
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
            # Legacy status string — use centralized mapping
            initial = db_status_to_state(record.status)

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

        # Persist — use centralized DB status mapping
        db_status = state_to_db_status(new_state)
        self._repo.update_status(scan_id, db_status)
        return db_status

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
    # Event / result queries  (Cycle 29 — Phase 2 migration)
    # ------------------------------------------------------------------

    def get_events(self, scan_id: str, event_type: Optional[str] = None,
                   *, filter_fp: bool = False) -> list:
        """Return raw scan result events."""
        if self._event_repo:
            return self._event_repo.get_results(
                scan_id,
                event_type=event_type or "ALL",
                filter_fp=filter_fp,
            ) or []
        dbh = self._ensure_dbh()
        if filter_fp:
            return dbh.scanResultEvent(scan_id, filterFp=True) or []
        return dbh.scanResultEvent(scan_id, event_type) or []

    def search_events(self, scan_id: str, *,
                      event_type: str = "", value: str = "") -> list:
        """Search scan results."""
        if self._event_repo:
            return self._event_repo.search({
                "scan_id": scan_id or "",
                "type": event_type or "",
                "value": value or "",
                "regex": "",
            }) or []
        dbh = self._ensure_dbh()
        return dbh.search({
            "scan_id": scan_id or "",
            "type": event_type or "",
            "value": value or "",
            "regex": "",
        }) or []

    def get_correlations(self, scan_id: str) -> list:
        """Return scan correlation rows."""
        dbh = self._ensure_dbh()
        return dbh.scanCorrelations(scan_id) or []

    def get_scan_logs(self, scan_id: str) -> list:
        """Return raw scan log rows."""
        dbh = self._ensure_dbh()
        return dbh.scanLogs(scan_id) or []

    # ------------------------------------------------------------------
    # Metadata / notes / archive  (Cycle 29)
    # ------------------------------------------------------------------

    def get_metadata(self, scan_id: str) -> Dict[str, Any]:
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanMetadataGet"):
            return dbh.scanMetadataGet(scan_id) or {}
        return {}

    def set_metadata(self, scan_id: str, metadata: Dict[str, Any]) -> None:
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanMetadataSet"):
            dbh.scanMetadataSet(scan_id, metadata)

    def get_notes(self, scan_id: str) -> str:
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanNotesGet"):
            return dbh.scanNotesGet(scan_id) or ""
        return ""

    def set_notes(self, scan_id: str, notes: str) -> None:
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanNotesSet"):
            dbh.scanNotesSet(scan_id, notes)

    def archive(self, scan_id: str) -> None:
        meta = self.get_metadata(scan_id)
        meta["archived"] = True
        self.set_metadata(scan_id, meta)

    def unarchive(self, scan_id: str) -> None:
        meta = self.get_metadata(scan_id)
        meta["archived"] = False
        self.set_metadata(scan_id, meta)

    # ------------------------------------------------------------------
    # Results management  (Cycle 29)
    # ------------------------------------------------------------------

    def clear_results(self, scan_id: str) -> None:
        """Delete all results/events for scan, keeping the scan entry."""
        dbh = self._ensure_dbh()
        dbh.scanResultDelete(scan_id)

    def set_false_positive(self, scan_id: str, result_ids: List[str],
                           fp: str) -> Dict[str, str]:
        """Set/unset false-positive flag on results + children.

        Returns ``{"status": "SUCCESS"|"WARNING"|"ERROR", "message": ...}``.
        """
        dbh = self._ensure_dbh()

        scan_info = dbh.scanInstanceGet(scan_id)
        if not scan_info:
            raise ScanServiceError(f"Scan not found: {scan_id}")

        if scan_info[5] not in ("ABORTED", "FINISHED", "ERROR-FAILED"):
            return {
                "status": "WARNING",
                "message": "Scan must be in a finished state when setting False Positives.",
            }

        if self._event_repo:
            if fp == "0":
                data = self._event_repo.get_element_sources(
                    scan_id, result_ids, recursive=False)
                for row in data:
                    if str(row[14]) == "1":
                        return {
                            "status": "WARNING",
                            "message": (
                                f"Cannot unset element {scan_id} as False Positive "
                                "if a parent element is still False Positive."
                            ),
                        }
            childs = self._event_repo.get_element_children(
                scan_id, result_ids, recursive=True)
            all_ids = result_ids + childs
            ret = self._event_repo.update_false_positive(scan_id, all_ids, fp)
        else:
            if fp == "0":
                data = dbh.scanElementSourcesDirect(scan_id, result_ids)
                for row in data:
                    if str(row[14]) == "1":
                        return {
                            "status": "WARNING",
                            "message": (
                                f"Cannot unset element {scan_id} as False Positive "
                                "if a parent element is still False Positive."
                            ),
                        }
            childs = dbh.scanElementChildrenAll(scan_id, result_ids)
            all_ids = result_ids + childs
            ret = dbh.scanResultsUpdateFP(scan_id, all_ids, fp)

        if ret:
            return {"status": "SUCCESS", "message": ""}
        return {"status": "ERROR", "message": "Exception encountered."}

    # ------------------------------------------------------------------
    # Scan config retrieval  (Cycle 29)
    # ------------------------------------------------------------------

    def get_scan_options(self, scan_id: str,
                        app_config: Dict[str, Any]) -> Dict[str, Any]:
        """Return scan options with config descriptions.

        ``app_config`` is the full application config dict (needed for
        module option descriptions).
        """
        dbh = self._ensure_dbh()
        meta = dbh.scanInstanceGet(scan_id)
        if not meta:
            return {}

        import time as _time

        started = (
            _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(meta[3]))
            if meta[3] != 0 else "Not yet"
        )
        finished = (
            _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(meta[4]))
            if meta[4] != 0 else "Not yet"
        )

        ret: Dict[str, Any] = {
            "meta": [meta[0], meta[1], meta[2], started, finished, meta[5]],
            "config": dbh.scanConfigGet(scan_id),
            "configdesc": {},
        }

        for key in list(ret["config"].keys()):
            if ":" not in key:
                descs = app_config.get("__globaloptdescs__", {})
                if descs:
                    ret["configdesc"][key] = descs.get(key, f"{key} (legacy)")
            else:
                mod_name, mod_opt = key.split(":", 1)
                modules = app_config.get("__modules__", {})
                if mod_name not in modules:
                    continue
                if mod_opt not in modules[mod_name].get("optdescs", {}):
                    continue
                ret["configdesc"][key] = modules[mod_name]["optdescs"][mod_opt]

        return ret

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
