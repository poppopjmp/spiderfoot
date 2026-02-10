"""
Scan metadata and annotation service.

Extracted from ScanServiceFacade to enforce single-responsibility.
Handles metadata CRUD, notes, archiving, and false-positive management.
"""

from __future__ import annotations

import logging
from typing import Any

from spiderfoot.scan_state_map import (
    DB_STATUS_ABORTED,
    DB_STATUS_ERROR_FAILED,
    DB_STATUS_FINISHED,
)

log = logging.getLogger("spiderfoot.scan_metadata_service")


class ScanMetadataService:
    """Manages scan metadata, notes, archives, and false-positive flags.

    This service is extracted from ScanServiceFacade to separate
    metadata/annotation concerns from scan lifecycle management.
    """

    def __init__(self, dbh=None, event_repo=None) -> None:
        """
        Args:
            dbh: Database handle (SpiderFootDb instance).
            event_repo: Optional EventRepository for migrated event operations.
        """
        self._dbh = dbh
        self._event_repo = event_repo

    def set_db_handle(self, dbh) -> None:
        """Set or replace the database handle."""
        self._dbh = dbh

    def _ensure_dbh(self):
        if self._dbh is None:
            raise RuntimeError("No database handle available for ScanMetadataService")
        return self._dbh

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self, scan_id: str) -> dict[str, Any]:
        """Get scan metadata dict."""
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanMetadataGet"):
            return dbh.scanMetadataGet(scan_id) or {}
        return {}

    def set_metadata(self, scan_id: str, metadata: dict[str, Any]) -> None:
        """Set scan metadata dict."""
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanMetadataSet"):
            dbh.scanMetadataSet(scan_id, metadata)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def get_notes(self, scan_id: str) -> str:
        """Get scan notes text."""
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanNotesGet"):
            return dbh.scanNotesGet(scan_id) or ""
        return ""

    def set_notes(self, scan_id: str, notes: str) -> None:
        """Set scan notes text."""
        dbh = self._ensure_dbh()
        if hasattr(dbh, "scanNotesSet"):
            dbh.scanNotesSet(scan_id, notes)

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    def archive(self, scan_id: str) -> None:
        """Mark a scan as archived."""
        meta = self.get_metadata(scan_id)
        meta["archived"] = True
        self.set_metadata(scan_id, meta)

    def unarchive(self, scan_id: str) -> None:
        """Remove archived flag from a scan."""
        meta = self.get_metadata(scan_id)
        meta["archived"] = False
        self.set_metadata(scan_id, meta)

    def is_archived(self, scan_id: str) -> bool:
        """Check if a scan is archived."""
        meta = self.get_metadata(scan_id)
        return bool(meta.get("archived", False))

    # ------------------------------------------------------------------
    # False Positive management
    # ------------------------------------------------------------------

    def set_false_positive(
        self,
        scan_id: str,
        result_ids: list[str],
        fp: str,
    ) -> dict[str, str]:
        """Set/unset false-positive flag on results + children.

        Returns ``{"status": "SUCCESS"|"WARNING"|"ERROR", "message": ...}``.
        """
        dbh = self._ensure_dbh()

        scan_info = dbh.scanInstanceGet(scan_id)
        if not scan_info:
            return {"status": "ERROR", "message": f"Scan not found: {scan_id}"}

        if scan_info[5] not in (DB_STATUS_ABORTED, DB_STATUS_FINISHED, DB_STATUS_ERROR_FAILED):
            return {
                "status": "WARNING",
                "message": "Scan must be in a finished state when setting False Positives.",
            }

        if self._event_repo:
            return self._set_false_positive_via_repo(
                scan_id, result_ids, fp
            )
        return self._set_false_positive_via_dbh(
            dbh, scan_id, result_ids, fp
        )

    def _set_false_positive_via_repo(
        self, scan_id: str, result_ids: list[str], fp: str
    ) -> dict[str, str]:
        """FP management through EventRepository."""
        if fp == "0":
            data = self._event_repo.get_element_sources(
                scan_id, result_ids, recursive=False
            )
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
            scan_id, result_ids, recursive=True
        )
        all_ids = result_ids + childs
        ret = self._event_repo.update_false_positive(scan_id, all_ids, fp)
        if ret:
            return {"status": "SUCCESS", "message": ""}
        return {"status": "ERROR", "message": "Exception encountered."}

    def _set_false_positive_via_dbh(
        self, dbh, scan_id: str, result_ids: list[str], fp: str
    ) -> dict[str, str]:
        """FP management through raw database handle (legacy path)."""
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
    # Results
    # ------------------------------------------------------------------

    def clear_results(self, scan_id: str) -> None:
        """Delete all results/events for scan, keeping the scan entry."""
        dbh = self._ensure_dbh()
        dbh.scanResultDelete(scan_id)

    # ------------------------------------------------------------------
    # Scan config retrieval
    # ------------------------------------------------------------------

    def get_scan_options(
        self, scan_id: str, app_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Return scan options with config descriptions."""
        dbh = self._ensure_dbh()
        meta = dbh.scanInstanceGet(scan_id)
        if not meta:
            return {}

        import time as _time

        started = (
            _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(meta[3]))
            if meta[3] != 0
            else "Not yet"
        )
        finished = (
            _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(meta[4]))
            if meta[4] != 0
            else "Not yet"
        )

        ret: dict[str, Any] = {
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
