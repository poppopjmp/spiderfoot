"""
Visualization Service — data aggregation for scan visualizations.

Encapsulates scan data retrieval via ``ScanRepository`` and
``EventRepository`` (Cycle 23), providing pre-processed payloads
for graph, summary, timeline, and heatmap endpoints.

Cycle 28 — eliminates raw ``SpiderFootDb`` from the visualization
router.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

log = logging.getLogger("spiderfoot.visualization_service")


class VisualizationServiceError(Exception):
    """Raised when a visualization operation fails."""


class VisualizationService:
    """Scan data aggregation for visualization endpoints.

    Composed from ``ScanRepository`` (scan existence checks) and
    a raw ``dbh`` for result queries (``scanResultEvent``,
    ``scanResultSummary``) until those are migrated to EventRepository.
    """

    def __init__(self, *, scan_repo=None, dbh=None) -> None:
        """Initialize the VisualizationService."""
        self._scan_repo = scan_repo
        self._dbh = dbh

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_scan(self, scan_id: str) -> dict[str, Any]:
        """Return scan info dict or raise 404-able error."""
        if self._scan_repo is not None:
            record = self._scan_repo.get_scan(scan_id)
            if record is None:
                raise VisualizationServiceError(f"Scan not found: {scan_id}")
            return record.to_dict()
        # Fallback to raw dbh
        if self._dbh is not None:
            row = self._dbh.scanInstanceGet(scan_id)
            if not row:
                raise VisualizationServiceError(f"Scan not found: {scan_id}")
            return {
                "name": row[0], "target": row[1],
                "status": row[5] if len(row) > 5 else "Unknown",
            }
        raise VisualizationServiceError("No data source configured")

    def _get_results(self, scan_id: str, event_type=None):
        """Get raw scan result events."""
        if self._dbh is None:
            return []
        return self._dbh.scanResultEvent(scan_id, event_type) or []

    def _get_summary(self, scan_id: str, group_by: str = "type"):
        if self._dbh is None:
            return []
        return self._dbh.scanResultSummary(scan_id, group_by) or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_graph_data(
        self,
        scan_id: str,
        *,
        event_type: str | None = None,
    ) -> tuple[dict[str, Any], list]:
        """Return (scan_info, results) for graph rendering.

        Returns:
            Tuple of (scan_info_dict, raw_result_rows).
        """
        info = self._require_scan(scan_id)
        results = self._get_results(scan_id, event_type)
        return info, results

    def get_multi_scan_graph_data(
        self,
        scan_ids: list[str],
        *,
        event_type: str | None = None,
    ) -> tuple[list[str], list]:
        """Return (valid_scan_ids, merged_results) for multi-scan graph.

        Skips invalid scan IDs with a warning.
        """
        valid_ids: list[str] = []
        all_results: list = []
        for sid in scan_ids:
            try:
                self._require_scan(sid)
                valid_ids.append(sid)
                all_results.extend(self._get_results(sid, event_type))
            except VisualizationServiceError:
                log.warning("Scan %s not found, skipping", sid)
        return valid_ids, all_results

    def get_summary_data(
        self,
        scan_id: str,
        *,
        group_by: str = "type",
    ) -> dict[str, Any]:
        """Return chart-ready summary data."""
        info = self._require_scan(scan_id)
        summary_rows = self._get_summary(scan_id, group_by)

        labels: list[str] = []
        values: list[int] = []
        total = 0

        for item in summary_rows:
            if group_by == "type":
                label = item[0] if len(item) > 0 else "Unknown"
                value = item[4] if len(item) > 4 else 1
            elif group_by == "module":
                label = item[1] if len(item) > 1 else "Unknown"
                value = item[4] if len(item) > 4 else 1
            else:
                label = item[3] if len(item) > 3 else "Unknown"
                value = item[4] if len(item) > 4 else 1

            labels.append(str(label))
            values.append(int(value))
            total += int(value)

        return {
            "scan_id": scan_id,
            "group_by": group_by,
            "data": {"labels": labels, "values": values, "total": total},
            "scan_info": info,
        }

    def get_timeline_data(
        self,
        scan_id: str,
        *,
        interval: str = "hour",
        event_type: str | None = None,
    ) -> dict[str, Any]:
        """Return timeline aggregation."""
        info = self._require_scan(scan_id)
        results = self._get_results(scan_id, event_type)

        buckets: dict[str, int] = defaultdict(int)
        for row in results:
            ts = row[0] if row else None
            if ts is None:
                continue
            # ts may be a float epoch or a datetime
            try:
                if isinstance(ts, (int, float)):
                    import time as _time
                    from datetime import datetime
                    dt = datetime.fromtimestamp(float(ts))
                elif hasattr(ts, "strftime"):
                    dt = ts
                else:
                    continue

                if interval == "day":
                    key = dt.strftime("%Y-%m-%d")
                elif interval == "week":
                    from datetime import timedelta
                    start = dt - timedelta(days=dt.weekday())
                    key = start.strftime("%Y-%m-%d")
                else:
                    key = dt.strftime("%Y-%m-%d %H:00")
            except Exception as e:
                continue
            buckets[key] += 1

        sorted_items = sorted(buckets.items())
        return {
            "scan_id": scan_id,
            "interval": interval,
            "timeline": {
                "timestamps": [t for t, _ in sorted_items],
                "counts": [c for _, c in sorted_items],
            },
            "total_events": sum(buckets.values()),
            "scan_info": info,
        }

    def get_heatmap_data(
        self,
        scan_id: str,
        *,
        dimension_x: str = "module",
        dimension_y: str = "type",
    ) -> dict[str, Any]:
        """Return heatmap matrix data."""
        info = self._require_scan(scan_id)
        results = self._get_results(scan_id)

        matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        x_labels: set = set()
        y_labels: set = set()

        dim_index = {"module": 2, "type": 3}

        for row in results:
            x_idx = dim_index.get(dimension_x, 2)
            y_idx = dim_index.get(dimension_y, 3)
            x_val = str(row[x_idx]) if len(row) > x_idx else "Unknown"
            y_val = str(row[y_idx]) if len(row) > y_idx else "Unknown"

            x_labels.add(x_val)
            y_labels.add(y_val)
            matrix[x_val][y_val] += 1

        x_sorted = sorted(x_labels)
        y_sorted = sorted(y_labels)
        grid = [
            [matrix.get(x, {}).get(y, 0) for x in x_sorted]
            for y in y_sorted
        ]

        return {
            "scan_id": scan_id,
            "dimensions": {"x": dimension_x, "y": dimension_y},
            "heatmap": {
                "x_labels": x_sorted,
                "y_labels": y_sorted,
                "matrix": grid,
            },
            "scan_info": info,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release resources held by the service."""
        if self._scan_repo is not None and hasattr(self._scan_repo, "close"):
            self._scan_repo.close()
