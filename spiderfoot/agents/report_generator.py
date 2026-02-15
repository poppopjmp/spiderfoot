"""
Report Generator Agent
========================
Generates comprehensive scan reports by aggregating findings,
correlations, and agent analysis results.

Uses Qdrant vector DB to retrieve semantically relevant scan data,
enabling rich context-aware report generation regardless of scan size.

Produces structured reports in multiple formats that can be
stored in MinIO and served through the API.
"""

import json
import logging
import os
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.report_generator")

SYSTEM_PROMPT = """You are a cybersecurity report writer specializing in OSINT reconnaissance reports.
Generate a comprehensive, professional security assessment report from the provided scan data.

You will receive rich context from a vector database containing all indexed scan events —
analyse every piece of evidence carefully and produce detailed, data-driven findings.

Structure your report as JSON:
{
  "title": "Report title",
  "executive_summary": "High-level summary for non-technical stakeholders (2-3 paragraphs)",
  "risk_rating": "critical" | "high" | "medium" | "low" | "info",
  "key_findings": [
    {
      "title": "Finding title",
      "severity": "critical|high|medium|low|info",
      "description": "Detailed description",
      "evidence": "Supporting evidence from the scan data",
      "recommendation": "Remediation recommendation"
    }
  ],
  "attack_surface_summary": {
    "domains": 0,
    "hosts": 0,
    "emails": 0,
    "open_ports": 0,
    "technologies": [],
    "exposed_services": []
  },
  "threat_assessment": "Overall threat assessment paragraph",
  "recommendations": [
    {
      "priority": "immediate|short_term|long_term",
      "action": "Recommended action",
      "rationale": "Why this action is important"
    }
  ],
  "methodology": "Brief description of OSINT methodology used",
  "tags": ["relevant", "tags"]
}"""


def _get_qdrant_context(scan_id: str, target: str, max_events: int = 200) -> dict:
    """Retrieve semantically relevant context from Qdrant vector DB.

    This function queries Qdrant in two ways:
    1. Scrolls all indexed events for this scan (up to max_events)
    2. Runs semantic similarity search for the target to find
       the most relevant events

    Returns a dict with 'scan_events', 'semantic_hits', and 'event_stats'.
    """
    context: Dict[str, Any] = {
        "scan_events": [],
        "semantic_hits": [],
        "infra_hits": [],
        "event_stats": {},
        "available": False,
    }

    try:
        from spiderfoot.qdrant_client import get_qdrant_client, Filter
        from spiderfoot.services.embedding_service import get_embedding_service
        from spiderfoot.vector_correlation import (
            VectorCorrelationEngine, VectorCorrelationConfig,
            CorrelationStrategy,
        )

        qdrant = get_qdrant_client()
        embeddings = get_embedding_service()
        config = VectorCorrelationConfig()

        # 1. Scroll all events for this scan from Qdrant
        scan_filter = Filter(must=[Filter.match("scan_id", scan_id)])
        all_events: list = []
        offset = None
        batch_limit = 100
        while len(all_events) < max_events:
            remaining = max_events - len(all_events)
            fetch = min(batch_limit, remaining)
            points, next_offset = qdrant.scroll(
                config.collection_name,
                limit=fetch,
                offset=offset,
                filter_=scan_filter,
            )
            if not points:
                break
            all_events.extend(points)
            offset = next_offset
            if not next_offset:
                break

        # Build event type statistics
        type_counts: Dict[str, int] = {}
        risk_counts: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        for pt in all_events:
            et = pt.payload.get("event_type", "UNKNOWN")
            type_counts[et] = type_counts.get(et, 0) + 1
            r = pt.payload.get("risk", 0)
            if isinstance(r, int) and 0 <= r <= 4:
                risk_counts[r] = risk_counts.get(r, 0) + 1

        context["event_stats"] = {
            "total_indexed": len(all_events),
            "type_breakdown": dict(
                sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "risk_breakdown": {
                "info": risk_counts.get(0, 0),
                "low": risk_counts.get(1, 0),
                "medium": risk_counts.get(2, 0),
                "high": risk_counts.get(3, 0),
                "critical": risk_counts.get(4, 0),
            },
        }

        # Format scan events as structured data for the prompt
        # Group by event type for readability and cap per type
        by_type: Dict[str, list] = {}
        for pt in all_events:
            et = pt.payload.get("event_type", "UNKNOWN")
            if et not in by_type:
                by_type[et] = []
            if len(by_type[et]) < 15:  # cap per type
                by_type[et].append({
                    "data": str(pt.payload.get("data", ""))[:500],
                    "source": pt.payload.get("source_module", ""),
                    "risk": pt.payload.get("risk", 0),
                    "confidence": pt.payload.get("confidence", 100),
                })
        context["scan_events"] = by_type

        # 2. Semantic similarity search for the target
        engine = VectorCorrelationEngine(
            qdrant=qdrant,
            embeddings=embeddings,
            config=config,
        )

        sim_result = engine.correlate(
            f"security assessment for {target}",
            strategy=CorrelationStrategy.SIMILARITY,
            scan_id=scan_id,
        )
        context["semantic_hits"] = [
            {
                "type": h.event.event_type,
                "data": h.event.data[:300],
                "source": h.event.source_module,
                "risk": h.event.risk,
                "score": round(h.score, 3),
            }
            for h in sim_result.hits[:30]
        ]

        # 3. Infrastructure-focused search
        infra_result = engine.correlate(
            f"infrastructure services ports for {target}",
            strategy=CorrelationStrategy.INFRASTRUCTURE,
            scan_id=scan_id,
        )
        context["infra_hits"] = [
            {
                "type": h.event.event_type,
                "data": h.event.data[:300],
                "source": h.event.source_module,
                "score": round(h.score, 3),
            }
            for h in infra_result.hits[:20]
        ]

        context["available"] = True
        logger.info(
            "Qdrant context retrieved for scan %s: %d events, %d types, "
            "%d semantic hits, %d infra hits",
            scan_id, len(all_events), len(type_counts),
            len(context["semantic_hits"]), len(context["infra_hits"]),
        )

    except ImportError as e:
        logger.warning("Qdrant/embedding dependencies not available: %s", e)
    except Exception as e:
        logger.warning("Failed to retrieve Qdrant context: %s", e)

    return context


class ReportGeneratorAgent(BaseAgent):
    """Generates comprehensive scan reports using Qdrant vector context."""

    @property
    def event_types(self) -> List[str]:
        return ["SCAN_COMPLETE", "REPORT_REQUEST"]

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        scan_id = event.get("scan_id", "")
        target = event.get("target", "")
        findings = event.get("findings", [])
        correlations = event.get("correlations", [])
        stats = event.get("stats", {})
        agent_results = event.get("agent_results", [])

        # ── Retrieve rich context from Qdrant vector DB ──
        qdrant_ctx = _get_qdrant_context(scan_id, target)

        # Build the comprehensive prompt
        findings_text = self._format_findings(findings[:50])
        correlations_text = self._format_correlations(correlations[:20])
        qdrant_section = self._format_qdrant_context(qdrant_ctx)

        user_prompt = f"""Generate a comprehensive OSINT scan report:

**Target:** {target}
**Scan ID:** {scan_id}

**Statistics:**
- Total events: {stats.get('total_events', 'N/A')}
- Unique domains: {stats.get('domains', 'N/A')}
- Unique IPs: {stats.get('ips', 'N/A')}
- Emails found: {stats.get('emails', 'N/A')}
- High-risk findings: {stats.get('high_risk', 'N/A')}

{qdrant_section}

**Summary Findings from Scan:**
{findings_text}

**Correlations:**
{correlations_text}

**Agent Analysis Results:**
{json.dumps(agent_results[:10], indent=2) if agent_results else 'None available'}

Generate a professional security assessment report. Use ALL the evidence from the
Vector DB Context section above to provide detailed, data-driven analysis.
Every finding should reference specific evidence from the scan data."""

        last_error = None
        for attempt in range(3):
            try:
                response = await self.call_llm(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self.config.llm_model,
                    temperature=0.4,
                    max_tokens=8192,
                )

                result_data = self._parse_json_response(response)

                return AgentResult(
                    agent_name=self.config.name,
                    event_id=event.get("id", ""),
                    scan_id=scan_id,
                    result_type="scan_report",
                    data=result_data,
                    confidence=0.9 if qdrant_ctx["available"] else 0.7,
                )

            except json.JSONDecodeError:
                return AgentResult(
                    agent_name=self.config.name,
                    event_id=event.get("id", ""),
                    scan_id=scan_id,
                    result_type="scan_report",
                    data={"raw_report": response[:12000]},
                    confidence=0.5,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Report generation attempt %d/3 failed: %s", attempt + 1, e
                )
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)

        return AgentResult(
            agent_name=self.config.name,
            event_id=event.get("id", ""),
            scan_id=scan_id,
            result_type="error",
            data={},
            confidence=0,
            error=str(last_error) if last_error else "Unknown error",
        )

    def _format_qdrant_context(self, ctx: dict) -> str:
        """Format Qdrant vector DB context into a rich prompt section."""
        if not ctx.get("available"):
            return "**Vector DB Context:** Not available — using summary data only."

        lines = ["=" * 60]
        lines.append("VECTOR DATABASE CONTEXT (Qdrant — Full Scan Intelligence)")
        lines.append("=" * 60)

        # Event statistics
        stats = ctx.get("event_stats", {})
        lines.append(f"\n📊 **Indexed Events:** {stats.get('total_indexed', 0)}")

        risk = stats.get("risk_breakdown", {})
        if risk:
            lines.append(f"  Risk breakdown: Critical={risk.get('critical', 0)}, "
                         f"High={risk.get('high', 0)}, Medium={risk.get('medium', 0)}, "
                         f"Low={risk.get('low', 0)}, Info={risk.get('info', 0)}")

        # Type breakdown
        types = stats.get("type_breakdown", {})
        if types:
            lines.append("\n📋 **Data Types Found:**")
            for et, count in list(types.items())[:25]:
                lines.append(f"  - {et}: {count} events")

        # All scan events by type
        scan_events = ctx.get("scan_events", {})
        if scan_events:
            lines.append(f"\n🔍 **Detailed Scan Events ({sum(len(v) for v in scan_events.values())} items):**")
            for event_type, events in scan_events.items():
                lines.append(f"\n  [{event_type}] ({len(events)} events)")
                for e in events:
                    risk_label = {0: "", 1: "⚠", 2: "⚠⚠", 3: "🔴", 4: "🔴🔴"}.get(e.get("risk", 0), "")
                    lines.append(f"    {risk_label} {e['data'][:300]}  (src: {e['source']})")

        # Semantically relevant hits
        semantic = ctx.get("semantic_hits", [])
        if semantic:
            lines.append(f"\n🎯 **Top Semantic Matches (relevance-ranked):**")
            for h in semantic:
                lines.append(f"  [{h['type']}] (score={h['score']}, risk={h['risk']}) {h['data'][:250]}")

        # Infrastructure hits
        infra = ctx.get("infra_hits", [])
        if infra:
            lines.append(f"\n🏗️ **Infrastructure Intelligence:**")
            for h in infra:
                lines.append(f"  [{h['type']}] (score={h['score']}) {h['data'][:250]}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def _format_findings(self, findings: List[Dict]) -> str:
        if not findings:
            return "No findings available."
        lines = []
        for f in findings:
            risk = f.get("risk", 0)
            lines.append(
                f"- [{f.get('event_type', f.get('type', '?'))}] (risk={risk}) "
                f"{str(f.get('data', f.get('description', '')))[:200]}"
            )
        return "\n".join(lines)

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response, stripping markdown fences if present."""
        text = response.strip()
        # Strip ```json ... ``` or ``` ... ```
        if text.startswith("```"):
            # Remove opening fence
            first_nl = text.index("\n") if "\n" in text else 3
            text = text[first_nl + 1:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)

    def _format_correlations(self, correlations: List[Dict]) -> str:
        if not correlations:
            return "No correlations found."
        lines = []
        for c in correlations:
            lines.append(
                f"- {c.get('type', c.get('rule_name', '?'))}: "
                f"{c.get('description', c.get('rule_descr', ''))[:200]}"
            )
        return "\n".join(lines)

    @classmethod
    def create(cls) -> "ReportGeneratorAgent":
        config = AgentConfig.from_env("report_generator")
        config.llm_model = "gpt-4o"  # Use smarter model for reports
        config.event_types = cls(config).event_types
        return cls(config)
