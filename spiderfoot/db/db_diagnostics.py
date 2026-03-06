# -------------------------------------------------------------------------------
# Name:         SpiderFoot DB Diagnostics
# Purpose:      EXPLAIN ANALYZE utilities for auditing query performance.
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2025-07-16
# Copyright:    (c) Agostino Panico 2025
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Database query diagnostics and EXPLAIN ANALYZE utilities for SpiderFoot.

Provides functions to analyse the 5 most common query patterns used
by the application.  Each function returns the EXPLAIN ANALYZE output
as a list of plan rows and a summary dict with estimated cost, rows,
and whether a sequential scan is present.

Usage (diagnostic / DBA shell):

    from spiderfoot.db.db_diagnostics import QueryDiagnostics
    diag = QueryDiagnostics(conn)
    report = diag.explain_all("some-scan-guid")
    for name, result in report.items():
        print(name, result["summary"])

Cycle 71 — Phase 2 Performance.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class ExplainResult:
    """Parsed EXPLAIN ANALYZE result."""

    query_name: str
    plan_rows: list[str] = field(default_factory=list)
    total_cost: float = 0.0
    estimated_rows: int = 0
    actual_time_ms: float = 0.0
    has_seq_scan: bool = False
    has_index_scan: bool = False
    planning_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_name": self.query_name,
            "total_cost": self.total_cost,
            "estimated_rows": self.estimated_rows,
            "actual_time_ms": self.actual_time_ms,
            "has_seq_scan": self.has_seq_scan,
            "has_index_scan": self.has_index_scan,
            "planning_time_ms": self.planning_time_ms,
            "execution_time_ms": self.execution_time_ms,
            "warnings": self.warnings,
            "plan_rows": self.plan_rows,
        }


def _parse_explain_output(query_name: str, rows: list[str]) -> ExplainResult:
    """Parse raw EXPLAIN ANALYZE text rows into an ExplainResult."""
    result = ExplainResult(query_name=query_name, plan_rows=rows)
    for row in rows:
        text = row if isinstance(row, str) else str(row[0]) if row else ""
        lower = text.lower()

        # Detect scan types
        if "seq scan" in lower:
            result.has_seq_scan = True
        if "index scan" in lower or "index only scan" in lower or "bitmap index scan" in lower:
            result.has_index_scan = True

        # Parse cost
        cost_match = re.search(r"cost=[\d.]+\.\.([\d.]+)", text)
        if cost_match:
            cost = float(cost_match.group(1))
            if cost > result.total_cost:
                result.total_cost = cost

        # Parse estimated rows
        rows_match = re.search(r"rows=(\d+)", text)
        if rows_match:
            est = int(rows_match.group(1))
            if est > result.estimated_rows:
                result.estimated_rows = est

        # Parse actual time
        actual_match = re.search(r"actual time=[\d.]+\.\.([\d.]+)", text)
        if actual_match:
            actual = float(actual_match.group(1))
            if actual > result.actual_time_ms:
                result.actual_time_ms = actual

        # Parse planning time
        planning_match = re.search(r"Planning [Tt]ime:\s*([\d.]+)\s*ms", text)
        if planning_match:
            result.planning_time_ms = float(planning_match.group(1))

        # Parse execution time
        exec_match = re.search(r"Execution [Tt]ime:\s*([\d.]+)\s*ms", text)
        if exec_match:
            result.execution_time_ms = float(exec_match.group(1))

    # Warnings
    if result.has_seq_scan and not result.has_index_scan:
        result.warnings.append("Query uses only sequential scan — consider adding an index")
    if result.total_cost > 10000:
        result.warnings.append(f"High estimated cost ({result.total_cost:.1f})")
    if result.execution_time_ms > 1000:
        result.warnings.append(f"Slow execution ({result.execution_time_ms:.1f}ms)")

    return result


class QueryDiagnostics:
    """Run EXPLAIN ANALYZE on the 5 most common SpiderFoot query patterns.

    The diagnostics object accepts a raw psycopg2 connection and does
    NOT modify any data (all queries are wrapped in a rolled-back
    transaction for safety).
    """

    # The 5 canonical query patterns that dominate DB load
    QUERY_PATTERNS = {
        "scan_result_listing": (
            "EXPLAIN ANALYZE "
            "SELECT ROUND(c.generated) AS generated, c.data, c.module, c.hash, "
            "c.type, c.source_event_hash, c.confidence, c.visibility, c.risk "
            "FROM tbl_scan_results c "
            "WHERE c.scan_instance_id = %s "
            "ORDER BY c.data"
        ),
        "event_type_count": (
            "EXPLAIN ANALYZE "
            "SELECT r.type, e.event_descr, MAX(ROUND(generated)) AS last_in, "
            "count(*) AS total, count(DISTINCT r.data) AS utotal "
            "FROM tbl_scan_results r, tbl_event_types e "
            "WHERE e.event = r.type AND r.scan_instance_id = %s "
            "GROUP BY r.type, e.event_descr "
            "ORDER BY e.event_descr"
        ),
        "correlation_lookup": (
            "EXPLAIN ANALYZE "
            "SELECT cr.id, cr.title, cr.rule_risk, cr.rule_id, cr.rule_name "
            "FROM tbl_scan_correlation_results cr "
            "WHERE cr.scan_instance_id = %s"
        ),
        "event_children_direct": (
            "EXPLAIN ANALYZE "
            "SELECT ROUND(c.generated) AS generated, c.data, s.data AS source_data, "
            "c.module, c.type, c.confidence, c.visibility, c.risk, c.hash, "
            "c.source_event_hash "
            "FROM tbl_scan_results c, tbl_scan_results s "
            "WHERE c.scan_instance_id = %s "
            "AND c.source_event_hash = s.hash "
            "AND s.scan_instance_id = c.scan_instance_id "
            "AND s.hash = %s"
        ),
        "unique_results": (
            "EXPLAIN ANALYZE "
            "SELECT DISTINCT data, type, COUNT(*) "
            "FROM tbl_scan_results "
            "WHERE scan_instance_id = %s "
            "GROUP BY type, data "
            "ORDER BY COUNT(*)"
        ),
    }

    def __init__(self, conn: Any) -> None:
        """Initialize with a psycopg2 connection.

        Args:
            conn: A live psycopg2 connection object.
        """
        if conn is None:
            raise ValueError("conn must be a valid database connection")
        self.conn = conn

    def _run_explain(self, query_name: str, query: str, params: tuple) -> ExplainResult:
        """Run a single EXPLAIN ANALYZE query safely inside a savepoint."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("SAVEPOINT diag_sp")
            cursor.execute(query, params)
            raw_rows = cursor.fetchall()
            cursor.execute("RELEASE SAVEPOINT diag_sp")
            rows = [str(r[0]) if r else "" for r in raw_rows]
            return _parse_explain_output(query_name, rows)
        except Exception as e:
            log.warning("EXPLAIN failed for %s: %s", query_name, e)
            try:
                cursor.execute("ROLLBACK TO SAVEPOINT diag_sp")
            except Exception:
                pass
            result = ExplainResult(query_name=query_name)
            result.warnings.append(f"Query failed: {e}")
            return result
        finally:
            cursor.close()

    def explain_scan_result_listing(self, scan_id: str) -> ExplainResult:
        """EXPLAIN ANALYZE the scan result listing query."""
        return self._run_explain(
            "scan_result_listing",
            self.QUERY_PATTERNS["scan_result_listing"],
            (scan_id,),
        )

    def explain_event_type_count(self, scan_id: str) -> ExplainResult:
        """EXPLAIN ANALYZE the event type count/summary query."""
        return self._run_explain(
            "event_type_count",
            self.QUERY_PATTERNS["event_type_count"],
            (scan_id,),
        )

    def explain_correlation_lookup(self, scan_id: str) -> ExplainResult:
        """EXPLAIN ANALYZE the correlation results lookup."""
        return self._run_explain(
            "correlation_lookup",
            self.QUERY_PATTERNS["correlation_lookup"],
            (scan_id,),
        )

    def explain_event_children_direct(self, scan_id: str, event_hash: str = "ROOT") -> ExplainResult:
        """EXPLAIN ANALYZE the direct child event lookup."""
        return self._run_explain(
            "event_children_direct",
            self.QUERY_PATTERNS["event_children_direct"],
            (scan_id, event_hash),
        )

    def explain_unique_results(self, scan_id: str) -> ExplainResult:
        """EXPLAIN ANALYZE the unique results query."""
        return self._run_explain(
            "unique_results",
            self.QUERY_PATTERNS["unique_results"],
            (scan_id,),
        )

    def explain_all(self, scan_id: str, event_hash: str = "ROOT") -> dict[str, ExplainResult]:
        """Run EXPLAIN ANALYZE on all 5 canonical query patterns.

        Args:
            scan_id: A valid scan_instance_id (GUID).
            event_hash: An event hash for the child-lookup query (defaults to ROOT).

        Returns:
            dict mapping query name to ExplainResult.
        """
        return {
            "scan_result_listing": self.explain_scan_result_listing(scan_id),
            "event_type_count": self.explain_event_type_count(scan_id),
            "correlation_lookup": self.explain_correlation_lookup(scan_id),
            "event_children_direct": self.explain_event_children_direct(scan_id, event_hash),
            "unique_results": self.explain_unique_results(scan_id),
        }

    def explain_custom(self, query_name: str, query: str, params: tuple) -> ExplainResult:
        """Run EXPLAIN ANALYZE on an arbitrary query.

        The query string MUST already be prefixed with ``EXPLAIN ANALYZE``.
        """
        if not query.strip().upper().startswith("EXPLAIN"):
            query = f"EXPLAIN ANALYZE {query}"
        return self._run_explain(query_name, query, params)

    def health_check(self, scan_id: str) -> dict[str, Any]:
        """Run all diagnostics and return a summary health report.

        Returns a dict with:
        - ``status``: "healthy" | "warning" | "critical"
        - ``queries``: dict of query summaries
        - ``recommendations``: list of actionable recommendations
        """
        results = self.explain_all(scan_id)
        recommendations: list[str] = []
        worst_status = "healthy"

        summaries = {}
        for name, result in results.items():
            summaries[name] = result.to_dict()
            if result.warnings:
                if worst_status == "healthy":
                    worst_status = "warning"
            if result.execution_time_ms > 5000:
                worst_status = "critical"
                recommendations.append(
                    f"[CRITICAL] {name} took {result.execution_time_ms:.0f}ms — requires immediate optimisation"
                )
            elif result.has_seq_scan and not result.has_index_scan:
                recommendations.append(
                    f"[WARNING] {name} uses sequential scan — add appropriate index"
                )

        return {
            "status": worst_status,
            "queries": summaries,
            "recommendations": recommendations,
        }
