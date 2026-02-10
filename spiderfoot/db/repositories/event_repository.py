"""
EventRepository — Clean interface for event/result operations.

Wraps ``SpiderFootDb`` event methods behind a type-safe facade:
``scanResultEvent``, ``scanResultEventUnique``, ``scanResultSummary``,
``scanEventStore``, ``scanElementSources*``, ``search``, etc.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from spiderfoot.db.repositories.base import AbstractRepository

log = logging.getLogger("spiderfoot.db.repositories.event")


class EventRepository(AbstractRepository):
    """Scan event and result operations."""

    def store_event(
        self,
        scan_id: str,
        event: Any,
        truncate_size: int = 0,
    ) -> None:
        """Persist a SpiderFootEvent to the database."""
        self.dbh.scanEventStore(scan_id, event, truncateSize=truncate_size)

    def get_results(
        self,
        scan_id: str,
        event_type: str = "ALL",
        *,
        source_module: Optional[str] = None,
        filter_fp: bool = False,
    ) -> list[Any]:
        """Get scan result events.

        Args:
            scan_id: Scan instance ID.
            event_type: Filter by event type (or ``"ALL"``).
            source_module: Filter by source module name.
            filter_fp: Exclude false positives.

        Returns:
            List of result rows.
        """
        return self.dbh.scanResultEvent(
            scan_id,
            eventType=event_type,
            srcModule=source_module,
            filterFp=filter_fp,
        )

    def get_unique_results(
        self,
        scan_id: str,
        event_type: str = "ALL",
        *,
        filter_fp: bool = False,
    ) -> list[Any]:
        """Get unique (de-duplicated) scan results."""
        return self.dbh.scanResultEventUnique(
            scan_id,
            eventType=event_type,
            filterFp=filter_fp,
        )

    def get_result_summary(
        self,
        scan_id: str,
        by: str = "type",
    ) -> list[Any]:
        """Get aggregated result summary."""
        return self.dbh.scanResultSummary(scan_id, by=by)

    def get_result_history(self, scan_id: str) -> list[Any]:
        """Get scan result history timeline."""
        return self.dbh.scanResultHistory(scan_id)

    def update_false_positive(
        self,
        scan_id: str,
        result_hashes: list[str],
        fp_flag: int,
    ) -> bool:
        """Mark/unmark results as false positive."""
        return self.dbh.scanResultsUpdateFP(scan_id, result_hashes, fp_flag)

    def get_element_sources(
        self,
        scan_id: str,
        element_ids: list[str],
        *,
        recursive: bool = False,
    ) -> list[Any]:
        """Get source elements for given element IDs.

        Args:
            recursive: If True, walk the full source tree.
        """
        if recursive:
            return self.dbh.scanElementSourcesAll(scan_id, element_ids)
        return self.dbh.scanElementSourcesDirect(scan_id, element_ids)

    def get_element_children(
        self,
        scan_id: str,
        element_ids: list[str],
        *,
        recursive: bool = False,
    ) -> list[Any]:
        """Get child elements for given element IDs."""
        if recursive:
            return self.dbh.scanElementChildrenAll(scan_id, element_ids)
        return self.dbh.scanElementChildrenDirect(scan_id, element_ids)

    def search(
        self,
        criteria: dict[str, Any],
        *,
        filter_fp: bool = False,
    ) -> list[Any]:
        """Search events by criteria dict."""
        return self.dbh.search(criteria, filterFp=filter_fp)

    def log_event(
        self,
        scan_id: str,
        classification: str,
        message: str,
        component: Optional[str] = None,
    ) -> None:
        """Write a single log event."""
        self.dbh.scanLogEvent(scan_id, classification, message, component)

    def log_events_batch(self, batch: list[Any]) -> bool:
        """Write a batch of log events."""
        return self.dbh.scanLogEvents(batch)
