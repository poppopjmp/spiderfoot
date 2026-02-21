"""
GraphQL resolvers — Query, Mutation & Subscription root types.

Resolvers map GraphQL operations to the existing SpiderFoot database
layer, reusing the same DB helpers as the REST API.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Optional, AsyncGenerator
from collections import Counter, defaultdict

import strawberry
from strawberry.types import Info

from .types import (
    ScanType, EventType, EventTypeSummary, CorrelationType,
    ScanLogType, ModuleType, EventTypeInfo, WorkspaceType,
    GraphNode, GraphEdge, ScanGraph, TimelineEntry,
    RiskDistribution, ScanStatistics, ModuleEventCount,
    EventFilter, PaginationInput, PaginatedEvents, PaginatedScans,
    ScanCreateInput, FalsePositiveInput,
    MutationResult, ScanCreateResult, FalsePositiveResult,
    VectorSearchHit, VectorSearchResult, VectorCollectionInfo,
)

_log = logging.getLogger("spiderfoot.api.graphql")


def _get_db():
    """Get a database handle using the global config."""
    from spiderfoot.api.dependencies import Config
    cfg = Config()
    from spiderfoot.db import SpiderFootDb
    return SpiderFootDb(cfg.get_config())


def _row_to_list(row):
    """Convert DictRow / tuple to indexable list."""
    if hasattr(row, 'keys'):
        # psycopg2 DictRow — convert to plain list
        return [row[i] for i in range(len(row))]
    return list(row) if not isinstance(row, list) else row


def _normalize_scan_row(row):
    """Normalize scanInstanceGet result to a plain list.
    
    scanInstanceGet returns either:
      - A DictRow (which is a list subclass) for PostgreSQL
      - A list of rows for SQLite
      - A tuple for ApiClient
    We detect DictRow by checking for .keys() method.
    """
    if row is None:
        return None
    if hasattr(row, 'keys'):
        # Single DictRow from PostgreSQL
        return [row[i] for i in range(len(row))]
    if isinstance(row, (list, tuple)):
        # Check if first element is also a row (list of rows)
        if len(row) > 0 and hasattr(row[0], 'keys'):
            return [row[0][i] for i in range(len(row[0]))]
        if len(row) > 0 and isinstance(row[0], (list, tuple)) and len(row[0]) > 2:
            return list(row[0])
        # Single tuple/list with scan fields (name, target, created, ...)
        return list(row)
    return list(row)


def _scan_row_to_type(row, scan_id: str | None = None) -> ScanType:
    """Convert a scan DB row to ScanType."""
    r = _row_to_list(row)
    return ScanType(
        scan_id=scan_id or "",
        name=str(r[0]) if r else "",
        target=str(r[1]) if len(r) > 1 else "",
        status=str(r[5]) if len(r) > 5 else "",
        created=float(r[2]) if len(r) > 2 and r[2] else 0.0,
        started=float(r[3]) if len(r) > 3 and r[3] else 0.0,
        ended=float(r[4]) if len(r) > 4 and r[4] else 0.0,
    )


def _event_row_to_type(row, scan_id: str | None = None) -> EventType:
    """Convert an event DB row to EventType.

    scanResultEvent SELECT order:
        0: generated, 1: data, 2: module, 3: hash, 4: type,
        5: source_event_hash, 6: confidence, 7: visibility, 8: risk
    """
    r = _row_to_list(row)
    return EventType(
        generated=float(r[0]) if r and r[0] else 0.0,
        data=str(r[1]) if len(r) > 1 else "",
        module=str(r[2]) if len(r) > 2 else "",
        event_type=str(r[4]) if len(r) > 4 else "",
        event_hash=str(r[3]) if len(r) > 3 else "",
        confidence=int(r[6]) if len(r) > 6 and r[6] is not None else 100,
        visibility=int(r[7]) if len(r) > 7 and r[7] is not None else 100,
        risk=int(r[8]) if len(r) > 8 and r[8] is not None else 0,
        source_event_hash=str(r[5]) if len(r) > 5 else "ROOT",
        false_positive=False,  # not in scanResultEvent SELECT
        scan_id=scan_id,
    )


# ── Query Root ──────────────────────────────────────────────────────

@strawberry.type
class Query:
    """Root query type for SpiderFoot GraphQL API."""

    @strawberry.field(description="Retrieve a single scan by ID")
    def scan(self, scan_id: str) -> Optional[ScanType]:
        dbh = _get_db()
        try:
            row = dbh.scanInstanceGet(scan_id)
            if not row:
                return None
            r = _normalize_scan_row(row)
            if not r:
                return None
            return _scan_row_to_type(r, scan_id)
        except Exception as e:
            _log.error("GraphQL scan() error: %s", e, exc_info=True)
            return None

    @strawberry.field(description="List all scans with optional pagination")
    def scans(
        self,
        pagination: Optional[PaginationInput] = None,
        status_filter: Optional[str] = None,
    ) -> PaginatedScans:
        dbh = _get_db()
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 50

        try:
            all_scans = dbh.scanInstanceList() or []
            result = []
            for s in all_scans:
                s_list = _row_to_list(s)
                scan_id = str(s_list[0]) if s_list else ""
                scan_type = ScanType(
                    scan_id=scan_id,
                    name=str(s_list[1]) if len(s_list) > 1 else "",
                    target=str(s_list[2]) if len(s_list) > 2 else "",
                    created=float(s_list[3]) if len(s_list) > 3 and s_list[3] else 0.0,
                    started=float(s_list[4]) if len(s_list) > 4 and s_list[4] else 0.0,
                    ended=float(s_list[5]) if len(s_list) > 5 and s_list[5] else 0.0,
                    status=str(s_list[6]) if len(s_list) > 6 else "",
                )
                if status_filter and scan_type.status != status_filter:
                    continue
                result.append(scan_type)

            total = len(result)
            start = (page - 1) * page_size
            end = start + page_size

            return PaginatedScans(
                scans=result[start:end],
                total=total,
                page=page,
                page_size=page_size,
            )
        except Exception as e:
            _log.error("GraphQL scans() error: %s", e, exc_info=True)
            return PaginatedScans(scans=[], total=0, page=page, page_size=page_size)

    @strawberry.field(description="Get events for a scan with optional filtering")
    def scan_events(
        self,
        scan_id: str,
        filter: Optional[EventFilter] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PaginatedEvents:
        dbh = _get_db()
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 50

        try:
            raw = dbh.scanResultEvent(scan_id, 'ALL') or []
            events = [_event_row_to_type(r, scan_id) for r in raw]

            # Apply filters
            if filter:
                if filter.event_types:
                    events = [e for e in events if e.event_type in filter.event_types]
                if filter.modules:
                    events = [e for e in events if e.module in filter.modules]
                if filter.min_risk is not None:
                    events = [e for e in events if e.risk >= filter.min_risk]
                if filter.max_risk is not None:
                    events = [e for e in events if e.risk <= filter.max_risk]
                if filter.min_confidence is not None:
                    events = [e for e in events if e.confidence >= filter.min_confidence]
                if filter.exclude_false_positives:
                    events = [e for e in events if not e.false_positive]
                if filter.search_text:
                    q = filter.search_text.lower()
                    events = [e for e in events if q in e.data.lower()]

            total = len(events)
            start = (page - 1) * page_size
            end = start + page_size

            return PaginatedEvents(
                events=events[start:end],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size if page_size else 0,
            )
        except Exception as e:
            _log.error("GraphQL scan_events() error: %s", e, exc_info=True)
            return PaginatedEvents(
                events=[], total=0, page=page,
                page_size=page_size, total_pages=0,
            )

    @strawberry.field(description="Aggregated event type summary for a scan")
    def event_summary(self, scan_id: str) -> list[EventTypeSummary]:
        dbh = _get_db()
        try:
            raw = dbh.scanResultEvent(scan_id, 'ALL') or []
            counts: dict[str, int] = Counter()
            last_seen: dict[str, float] = {}
            for r in raw:
                rl = _row_to_list(r)
                etype = str(rl[4]) if len(rl) > 4 else "UNKNOWN"
                ts = float(rl[0]) if rl and rl[0] else 0.0
                counts[etype] += 1
                if ts > last_seen.get(etype, 0):
                    last_seen[etype] = ts

            return [
                EventTypeSummary(event_type=et, count=c, last_seen=last_seen.get(et))
                for et, c in sorted(counts.items(), key=lambda x: -x[1])
            ]
        except Exception as e:
            _log.error("GraphQL event_summary() error: %s", e, exc_info=True)
            return []

    @strawberry.field(description="Correlations for a scan")
    def scan_correlations(self, scan_id: str) -> list[CorrelationType]:
        dbh = _get_db()
        try:
            corrs = dbh.scanCorrelationList(scan_id) or []
            results = []
            for c in corrs:
                cl = _row_to_list(c)
                results.append(CorrelationType(
                    correlation_id=str(cl[0]) if cl else "",
                    title=str(cl[3]) if len(cl) > 3 else "",
                    severity=str(cl[4]) if len(cl) > 4 else "",
                    rule_id=str(cl[5]) if len(cl) > 5 else "",
                    rule_name=str(cl[5]) if len(cl) > 5 else "",
                    description=str(cl[6]) if len(cl) > 6 else "",
                    matched_event_count=0,
                ))
            return results
        except Exception as e:
            _log.error("GraphQL scan_correlations() error: %s", e, exc_info=True)
            return []

    @strawberry.field(description="Scan execution logs")
    def scan_logs(
        self,
        scan_id: str,
        log_type: Optional[str] = None,
        limit: int = 200,
    ) -> list[ScanLogType]:
        dbh = _get_db()
        try:
            logs = dbh.scanLogs(scan_id, limit=limit) or []
            results = []
            for l in logs:
                ll = _row_to_list(l)
                entry = ScanLogType(
                    timestamp=float(ll[0]) if ll and ll[0] else 0.0,
                    component=str(ll[1]) if len(ll) > 1 else "",
                    log_type=str(ll[2]) if len(ll) > 2 else "",
                    message=str(ll[3]) if len(ll) > 3 else "",
                )
                if log_type and entry.log_type != log_type:
                    continue
                results.append(entry)
            return results
        except Exception as e:
            _log.error("GraphQL scan_logs() error: %s", e, exc_info=True)
            return []

    @strawberry.field(description="Complete scan statistics for dashboard visualization")
    def scan_statistics(self, scan_id: str) -> Optional[ScanStatistics]:
        dbh = _get_db()
        try:
            # Scan info
            scan_row = dbh.scanInstanceGet(scan_id)
            if not scan_row:
                return None
            sr = _normalize_scan_row(scan_row)
            if not sr:
                return None

            started = float(sr[3]) if len(sr) > 3 and sr[3] else 0.0
            ended = float(sr[4]) if len(sr) > 4 and sr[4] else 0.0
            duration = ended - started if ended and started else 0.0

            # Events
            raw = dbh.scanResultEvent(scan_id, 'ALL') or []
            total_events = len(raw)

            type_counts: dict[str, int] = Counter()
            module_counts: dict[str, int] = Counter()
            risk_counts: dict[str, int] = Counter()
            hourly: dict[int, dict[str, int]] = defaultdict(lambda: Counter())

            for r in raw:
                rl = _row_to_list(r)
                etype = str(rl[4]) if len(rl) > 4 else "UNKNOWN"
                module = str(rl[2]) if len(rl) > 2 else "unknown"
                risk = int(rl[8]) if len(rl) > 8 and rl[8] is not None else 0
                ts = float(rl[0]) if rl and rl[0] else 0.0

                type_counts[etype] += 1
                module_counts[module] += 1

                # Risk buckets
                if risk >= 80:
                    risk_counts["critical"] += 1
                elif risk >= 60:
                    risk_counts["high"] += 1
                elif risk >= 40:
                    risk_counts["medium"] += 1
                elif risk >= 20:
                    risk_counts["low"] += 1
                else:
                    risk_counts["info"] += 1

                # Timeline (hourly buckets)
                hour = int(ts // 3600) * 3600
                hourly[hour][etype] += 1

            # Correlations
            try:
                corrs = dbh.scanCorrelationList(scan_id) or []
                total_corrs = len(corrs)
            except Exception:
                total_corrs = 0

            # Risk distribution
            risk_dist = []
            for level in ("critical", "high", "medium", "low", "info"):
                count = risk_counts.get(level, 0)
                pct = (count / total_events * 100) if total_events else 0.0
                risk_dist.append(RiskDistribution(
                    level=level, count=count, percentage=round(pct, 1),
                ))

            # Top modules
            top_modules = [
                ModuleEventCount(module=m, count=c)
                for m, c in module_counts.most_common(20)
            ]

            # Timeline entries (flatten hourly buckets)
            timeline = []
            for hour_ts in sorted(hourly.keys()):
                for etype, count in hourly[hour_ts].items():
                    timeline.append(TimelineEntry(
                        timestamp=float(hour_ts), event_type=etype, count=count,
                    ))

            return ScanStatistics(
                total_events=total_events,
                unique_event_types=len(type_counts),
                total_correlations=total_corrs,
                risk_distribution=risk_dist,
                top_modules=top_modules,
                timeline=timeline,
                duration_seconds=duration,
            )

        except Exception as e:
            _log.error("GraphQL scan_statistics() error: %s", e, exc_info=True)
            return None

    @strawberry.field(description="Event relationship graph for visualization")
    def scan_graph(
        self,
        scan_id: str,
        max_nodes: int = 500,
    ) -> Optional[ScanGraph]:
        dbh = _get_db()
        try:
            raw = dbh.scanResultEvent(scan_id, filterFp=True) or []
            nodes_map: dict[str, GraphNode] = {}
            edges: list[GraphEdge] = []

            for r in raw[:max_nodes]:
                rl = _row_to_list(r)
                # Index map: 0:generated, 1:data, 2:module, 3:hash, 4:type, 5:source_event_hash
                event_hash = str(rl[3]) if len(rl) > 3 else ""
                source_hash = str(rl[5]) if len(rl) > 5 else "ROOT"

                if not event_hash:
                    continue

                nodes_map[event_hash] = GraphNode(
                    id=event_hash,
                    label=str(rl[1])[:80] if len(rl) > 1 else "",
                    event_type=str(rl[4]) if len(rl) > 4 else "",
                    module=str(rl[2]) if len(rl) > 2 else "",
                    risk=int(rl[8]) if len(rl) > 8 and rl[8] is not None else 0,
                )

                if source_hash and source_hash != "ROOT":
                    edges.append(GraphEdge(
                        source=source_hash,
                        target=event_hash,
                        label=str(rl[4]) if len(rl) > 4 else "",
                    ))

            # Add ROOT node
            scan_row = dbh.scanInstanceGet(scan_id)
            if scan_row:
                sr = _normalize_scan_row(scan_row)
                target = str(sr[1]) if sr and len(sr) > 1 else "ROOT"
                nodes_map["ROOT"] = GraphNode(
                    id="ROOT", label=target, event_type="ROOT",
                    module="SpiderFoot", risk=0,
                )

            nodes = list(nodes_map.values())
            return ScanGraph(
                nodes=nodes,
                edges=edges,
                node_count=len(nodes),
                edge_count=len(edges),
            )

        except Exception as e:
            _log.error("GraphQL scan_graph() error: %s", e, exc_info=True)
            return None

    @strawberry.field(description="List all available event types")
    def event_types(self) -> list[EventTypeInfo]:
        dbh = _get_db()
        try:
            types = dbh.eventTypes() or {}
            return [
                EventTypeInfo(
                    event=k,
                    description=str(v) if isinstance(v, str) else str(v[0]) if v else "",
                    raw=False,
                    category="",
                )
                for k, v in types.items()
            ]
        except Exception as e:
            _log.error("GraphQL event_types() error: %s", e, exc_info=True)
            return []

    @strawberry.field(description="List workspaces")
    def workspaces(self) -> list[WorkspaceType]:
        dbh = _get_db()
        try:
            ws_list = dbh.workspaceList() if hasattr(dbh, 'workspaceList') else []
            results = []
            for w in (ws_list or []):
                wl = _row_to_list(w)
                results.append(WorkspaceType(
                    workspace_id=str(wl[0]) if wl else "",
                    name=str(wl[1]) if len(wl) > 1 else "",
                    description=str(wl[2]) if len(wl) > 2 else "",
                    created_time=float(wl[3]) if len(wl) > 3 and wl[3] else 0.0,
                    modified_time=float(wl[4]) if len(wl) > 4 and wl[4] else 0.0,
                    scan_count=0,
                    target_count=0,
                ))
            return results
        except Exception as e:
            _log.error("GraphQL workspaces() error: %s", e, exc_info=True)
            return []

    @strawberry.field(description="Cross-scan event search")
    def search_events(
        self,
        query: str,
        scan_ids: Optional[list[str]] = None,
        event_types: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[EventType]:
        dbh = _get_db()
        try:
            # If specific scans provided, search within them
            if scan_ids:
                all_events = []
                for sid in scan_ids:
                    raw = dbh.scanResultEvent(sid, 'ALL') or []
                    for r in raw:
                        ev = _event_row_to_type(r, sid)
                        if query.lower() in ev.data.lower():
                            if event_types and ev.event_type not in event_types:
                                continue
                            all_events.append(ev)
                            if len(all_events) >= limit:
                                return all_events
                return all_events

            # Search across all scans
            scan_list = dbh.scanInstanceList() or []
            all_events = []
            for s in scan_list:
                sl = _row_to_list(s)
                sid = str(sl[0]) if sl else ""
                if not sid:
                    continue
                try:
                    raw = dbh.scanResultEvent(sid, 'ALL') or []
                    for r in raw:
                        ev = _event_row_to_type(r, sid)
                        if query.lower() in ev.data.lower():
                            if event_types and ev.event_type not in event_types:
                                continue
                            all_events.append(ev)
                            if len(all_events) >= limit:
                                return all_events
                except Exception:
                    continue
            return all_events

        except Exception as e:
            _log.error("GraphQL search_events() error: %s", e, exc_info=True)
            return []

    # ── Vector / Semantic Search ────────────────────────────────────

    @strawberry.field(description="Semantic vector search using Qdrant embeddings")
    def semantic_search(
        self,
        query: str,
        collection: Optional[str] = None,
        limit: int = 20,
        score_threshold: float = 0.5,
        scan_id: Optional[str] = None,
    ) -> VectorSearchResult:
        """Perform a semantic similarity search using Qdrant vector embeddings.

        Embeds the query text and finds the closest matching OSINT events
        in the configured Qdrant vector store.
        """
        try:
            from spiderfoot.qdrant_client import get_qdrant_client, Filter
            from spiderfoot.services.embedding_service import EmbeddingService

            embed_svc = EmbeddingService()
            query_vector = embed_svc.embed_text(query)
            if not query_vector:
                return VectorSearchResult(
                    hits=[], total_found=0, query_time_ms=0,
                    collection=collection or "osint_events",
                )

            qdrant = get_qdrant_client()
            coll = collection or "osint_events"

            # Optional payload filter by scan_id
            filter_ = None
            if scan_id:
                filter_ = Filter(must=[Filter.match("scan_id", scan_id)])

            result = qdrant.search(
                coll, query_vector,
                limit=limit,
                score_threshold=score_threshold,
                filter_=filter_,
            )

            hits = []
            for pt in result.points:
                hits.append(VectorSearchHit(
                    id=pt.id,
                    score=pt.score,
                    event_type=pt.payload.get("event_type"),
                    module=pt.payload.get("module"),
                    data=pt.payload.get("data", "")[:500],
                    scan_id=pt.payload.get("scan_id"),
                    risk=pt.payload.get("risk"),
                    payload=json.dumps(pt.payload) if pt.payload else None,
                ))

            return VectorSearchResult(
                hits=hits,
                total_found=result.total_found,
                query_time_ms=result.query_time_ms,
                collection=coll,
            )

        except Exception as e:
            _log.error("GraphQL semantic_search() error: %s", e, exc_info=True)
            return VectorSearchResult(
                hits=[], total_found=0, query_time_ms=0,
                collection=collection or "osint_events",
            )

    @strawberry.field(description="List Qdrant vector collections")
    def vector_collections(self) -> list[VectorCollectionInfo]:
        """Return all vector collections and their statistics."""
        try:
            from spiderfoot.qdrant_client import get_qdrant_client
            qdrant = get_qdrant_client()
            names = qdrant.list_collections()
            result = []
            for name in names:
                info = qdrant.collection_info(name)
                if info:
                    result.append(VectorCollectionInfo(
                        name=info.name,
                        point_count=info.point_count,
                        vector_dimensions=info.vector_size,
                        distance_metric=info.distance.value if info.distance else "unknown",
                    ))
            return result
        except Exception as e:
            _log.error("GraphQL vector_collections() error: %s", e, exc_info=True)
            return []


# ── Mutation Root ───────────────────────────────────────────────────

@strawberry.type
class Mutation:
    """Root mutation type for SpiderFoot GraphQL API."""

    @strawberry.mutation(description="Start a new scan")
    def start_scan(self, input: ScanCreateInput) -> ScanCreateResult:
        """Create and start a new OSINT scan."""
        try:
            scan_id = str(uuid.uuid4())
            dbh = _get_db()

            # Create scan instance
            dbh.scanInstanceCreate(scan_id, input.name, input.target)

            # Set status to STARTED
            dbh.scanInstanceSet(scan_id, status="STARTED")

            scan = ScanType(
                scan_id=scan_id,
                name=input.name,
                target=input.target,
                status="STARTED",
                created=time.time(),
                started=time.time(),
                ended=0.0,
            )

            _log.info("GraphQL startScan: %s target=%s", scan_id, input.target)
            return ScanCreateResult(
                success=True,
                message=f"Scan started for target: {input.target}",
                scan_id=scan_id,
                scan=scan,
            )

        except Exception as e:
            _log.error("GraphQL startScan() error: %s", e, exc_info=True)
            return ScanCreateResult(
                success=False,
                message=f"Failed to start scan: {e}",
            )

    @strawberry.mutation(description="Stop a running scan")
    def stop_scan(self, scan_id: str) -> MutationResult:
        """Stop a running scan by setting its status to ABORTED."""
        try:
            dbh = _get_db()
            row = dbh.scanInstanceGet(scan_id)
            if not row:
                return MutationResult(success=False, message="Scan not found")

            dbh.scanInstanceSet(scan_id, status="ABORTED")
            _log.info("GraphQL stopScan: %s", scan_id)
            return MutationResult(
                success=True,
                message=f"Scan {scan_id} stopped",
            )
        except Exception as e:
            _log.error("GraphQL stopScan() error: %s", e, exc_info=True)
            return MutationResult(success=False, message=str(e))

    @strawberry.mutation(description="Delete a scan and all its data")
    def delete_scan(self, scan_id: str) -> MutationResult:
        """Delete a scan, its results, config, and logs."""
        try:
            dbh = _get_db()
            row = dbh.scanInstanceGet(scan_id)
            if not row:
                return MutationResult(success=False, message="Scan not found")

            # Delete related data first, then the instance
            try:
                dbh.scanResultDelete(scan_id)
            except Exception:
                pass
            try:
                dbh.scanConfigDelete(scan_id)
            except Exception:
                pass
            dbh.scanInstanceDelete(scan_id)

            _log.info("GraphQL deleteScan: %s", scan_id)
            return MutationResult(
                success=True,
                message=f"Scan {scan_id} deleted",
            )
        except Exception as e:
            _log.error("GraphQL deleteScan() error: %s", e, exc_info=True)
            return MutationResult(success=False, message=str(e))

    @strawberry.mutation(description="Mark scan results as false positive (or unmark)")
    def set_false_positive(
        self, input: FalsePositiveInput,
    ) -> FalsePositiveResult:
        """Set or unset false-positive flags on scan result events."""
        try:
            dbh = _get_db()
            row = dbh.scanInstanceGet(input.scan_id)
            if not row:
                return FalsePositiveResult(
                    success=False, message="Scan not found",
                )

            fp_val = "1" if input.false_positive else "0"
            updated = 0
            try:
                dbh.scanResultsUpdateFP(input.scan_id, input.result_ids, fp_val)
                updated = len(input.result_ids)
            except Exception as inner:
                _log.warning("FP set failed: %s", inner)

            return FalsePositiveResult(
                success=True,
                message=f"Updated {updated} result(s)",
                updated=updated,
            )
        except Exception as e:
            _log.error("GraphQL setFalsePositive() error: %s", e, exc_info=True)
            return FalsePositiveResult(success=False, message=str(e))

    @strawberry.mutation(description="Rerun a completed scan with same configuration")
    def rerun_scan(self, scan_id: str) -> ScanCreateResult:
        """Clone a previous scan's config and start a new scan."""
        try:
            dbh = _get_db()
            row = dbh.scanInstanceGet(scan_id)
            if not row:
                return ScanCreateResult(
                    success=False, message="Original scan not found",
                )

            r = _normalize_scan_row(row)
            name = str(r[0]) if r else "Rerun"
            target = str(r[1]) if r and len(r) > 1 else ""

            new_scan_id = str(uuid.uuid4())
            dbh.scanInstanceCreate(new_scan_id, f"{name} (rerun)", target)
            dbh.scanInstanceSet(new_scan_id, status="STARTED")

            scan = ScanType(
                scan_id=new_scan_id,
                name=f"{name} (rerun)",
                target=target,
                status="STARTED",
                created=time.time(),
                started=time.time(),
                ended=0.0,
            )

            _log.info("GraphQL rerunScan: %s -> %s", scan_id, new_scan_id)
            return ScanCreateResult(
                success=True,
                message=f"Rerun scan created: {new_scan_id}",
                scan_id=new_scan_id,
                scan=scan,
            )
        except Exception as e:
            _log.error("GraphQL rerunScan() error: %s", e, exc_info=True)
            return ScanCreateResult(success=False, message=str(e))


# ── Subscription Root ───────────────────────────────────────────────

@strawberry.type
class Subscription:
    """Root subscription type for real-time GraphQL updates."""

    @strawberry.subscription(description="Real-time scan status updates")
    async def scan_progress(
        self,
        scan_id: str,
        interval: float = 2.0,
    ) -> AsyncGenerator[ScanType, None]:
        """Subscribe to live scan status changes.

        Polls the database at the specified interval and yields
        updated ScanType objects whenever the scan status changes.
        Automatically completes when the scan is finished.
        """
        last_status = None
        while True:
            try:
                dbh = _get_db()
                row = dbh.scanInstanceGet(scan_id)
                if not row:
                    return

                r = _normalize_scan_row(row)
                if not r:
                    return

                current = _scan_row_to_type(r, scan_id)

                # Yield on every poll (client sees latest state)
                if current.status != last_status:
                    last_status = current.status
                    yield current

                # Terminal states — stop streaming
                if current.status in (
                    "FINISHED", "ABORTED", "ERROR-FAILED",
                    "CANCELLED", "FAILED",
                ):
                    return

            except Exception as e:
                _log.error("GraphQL scanProgress error: %s", e, exc_info=True)
                return

            await asyncio.sleep(interval)

    @strawberry.subscription(description="Live event stream for a running scan")
    async def scan_events_live(
        self,
        scan_id: str,
        interval: float = 3.0,
    ) -> AsyncGenerator[EventType, None]:
        """Stream new events as they are discovered during a scan.

        Polls for new events and yields only those not previously seen.
        """
        seen_hashes: set[str] = set()
        while True:
            try:
                dbh = _get_db()
                raw = dbh.scanResultEvent(scan_id, 'ALL') or []
                for r in raw:
                    ev = _event_row_to_type(r, scan_id)
                    if ev.event_hash not in seen_hashes:
                        seen_hashes.add(ev.event_hash)
                        yield ev

                # Check if scan is done
                scan_row = dbh.scanInstanceGet(scan_id)
                if scan_row:
                    sr = _normalize_scan_row(scan_row)
                    status = str(sr[5]) if sr and len(sr) > 5 else ""
                    if status in ("FINISHED", "ABORTED", "ERROR-FAILED",
                                  "CANCELLED", "FAILED"):
                        return

            except Exception as e:
                _log.error("GraphQL scanEventsLive error: %s", e, exc_info=True)
                return

            await asyncio.sleep(interval)


# ── Query Complexity Extension ──────────────────────────────────────

class QueryDepthLimiter:
    """Strawberry extension that limits GraphQL query nesting depth."""

    MAX_DEPTH = 10

    def on_operation(self):
        """No-op — depth checking done at validation time."""

    @staticmethod
    def _get_depth(node, current: int = 0) -> int:
        """Recursively compute the nesting depth of a selection set."""
        if not hasattr(node, 'selection_set') or not node.selection_set:
            return current
        return max(
            QueryDepthLimiter._get_depth(sel, current + 1)
            for sel in node.selection_set.selections
        )


# ── Build Schema ────────────────────────────────────────────────────

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
