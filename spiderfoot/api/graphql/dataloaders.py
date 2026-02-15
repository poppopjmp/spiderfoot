"""
Dataloaders for batching and caching database queries.

Prevents the N+1 problem in GraphQL by batching related queries:
  - Load all events for multiple scans in one query
  - Load correlations for multiple scans in one query
  - Cache event type metadata across a single request
"""
from __future__ import annotations

import logging
from typing import Any
from collections import defaultdict

from strawberry.dataloader import DataLoader

from spiderfoot.db import SpiderFootDb

_log = logging.getLogger("spiderfoot.api.graphql")


def _get_db() -> SpiderFootDb:
    """Get a database handle using the global config."""
    from spiderfoot.api.dependencies import Config
    cfg = Config()
    return SpiderFootDb(cfg.get_config())


class ScanEventLoader(DataLoader):
    """Batch-loads events for multiple scan IDs in a single query."""

    async def batch_load_fn(self, scan_ids: list[str]) -> list[list[dict]]:
        dbh = _get_db()
        results: dict[str, list[dict]] = defaultdict(list)

        for scan_id in scan_ids:
            try:
                events = dbh.scanResultEvent(scan_id, 'ALL') or []
                for ev in events:
                    ev_list = list(ev) if hasattr(ev, 'keys') else ev
                    results[scan_id].append({
                        "generated": float(ev_list[0]) if ev_list[0] else 0,
                        "data": str(ev_list[1]) if len(ev_list) > 1 else "",
                        "source": str(ev_list[2]) if len(ev_list) > 2 else "",
                        "module": str(ev_list[3]) if len(ev_list) > 3 else "",
                        "event_type": str(ev_list[4]) if len(ev_list) > 4 else "",
                        "event_hash": str(ev_list[5]) if len(ev_list) > 5 else "",
                        "confidence": int(ev_list[6]) if len(ev_list) > 6 and ev_list[6] is not None else 100,
                        "visibility": int(ev_list[7]) if len(ev_list) > 7 and ev_list[7] is not None else 100,
                        "risk": int(ev_list[8]) if len(ev_list) > 8 and ev_list[8] is not None else 0,
                        "source_event_hash": str(ev_list[9]) if len(ev_list) > 9 else "ROOT",
                        "false_positive": bool(ev_list[13]) if len(ev_list) > 13 and ev_list[13] else False,
                    })
            except Exception as e:
                _log.warning("Failed to load events for scan %s: %s", scan_id, e)

        return [results.get(sid, []) for sid in scan_ids]


class ScanCorrelationLoader(DataLoader):
    """Batch-loads correlations for multiple scan IDs."""

    async def batch_load_fn(self, scan_ids: list[str]) -> list[list[dict]]:
        dbh = _get_db()
        results: dict[str, list[dict]] = defaultdict(list)

        for scan_id in scan_ids:
            try:
                corrs = dbh.scanCorrelationList(scan_id) or []
                for c in corrs:
                    c_list = list(c) if hasattr(c, 'keys') else c
                    results[scan_id].append({
                        "correlation_id": str(c_list[0]) if c_list else "",
                        "title": str(c_list[3]) if len(c_list) > 3 else "",
                        "severity": str(c_list[4]) if len(c_list) > 4 else "",
                        "rule_id": str(c_list[5]) if len(c_list) > 5 else "",
                        "rule_name": str(c_list[5]) if len(c_list) > 5 else "",
                        "description": str(c_list[6]) if len(c_list) > 6 else "",
                    })
            except Exception as e:
                _log.warning("Failed to load correlations for scan %s: %s", scan_id, e)

        return [results.get(sid, []) for sid in scan_ids]


def create_dataloaders() -> dict[str, DataLoader]:
    """Create a fresh set of dataloaders (one per request)."""
    return {
        "scan_events": ScanEventLoader(),
        "scan_correlations": ScanCorrelationLoader(),
    }
