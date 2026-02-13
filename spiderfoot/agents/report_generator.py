"""
Report Generator Agent
========================
Generates comprehensive scan reports by aggregating findings,
correlations, and agent analysis results.

Produces structured reports in multiple formats that can be
stored in MinIO and served through the API.
"""

import json
import logging
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.report_generator")

SYSTEM_PROMPT = """You are a cybersecurity report writer specializing in OSINT reconnaissance reports.
Generate a comprehensive, professional security assessment report from the provided scan data.

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
      "evidence": "Supporting evidence",
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


class ReportGeneratorAgent(BaseAgent):
    """Generates comprehensive scan reports."""

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

        # Build findings summary for the LLM
        findings_text = self._format_findings(findings[:50])  # Cap at 50
        correlations_text = self._format_correlations(correlations[:20])

        user_prompt = f"""Generate a comprehensive OSINT scan report:

**Target:** {target}
**Scan ID:** {scan_id}

**Statistics:**
- Total events: {stats.get('total_events', 'N/A')}
- Unique domains: {stats.get('domains', 'N/A')}
- Unique IPs: {stats.get('ips', 'N/A')}
- Emails found: {stats.get('emails', 'N/A')}
- High-risk findings: {stats.get('high_risk', 'N/A')}

**Key Findings:**
{findings_text}

**Correlations:**
{correlations_text}

**Agent Analysis Results:**
{json.dumps(agent_results[:10], indent=2) if agent_results else 'None available'}

Generate a professional security assessment report."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                model=self.config.llm_model,
                temperature=0.4,
                max_tokens=4096,
            )

            result_data = json.loads(response)

            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=scan_id,
                result_type="scan_report",
                data=result_data,
                confidence=0.85,
            )

        except json.JSONDecodeError:
            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=scan_id,
                result_type="scan_report",
                data={"raw_report": response[:8000]},
                confidence=0.5,
            )

    def _format_findings(self, findings: List[Dict]) -> str:
        if not findings:
            return "No findings available."
        lines = []
        for f in findings:
            risk = f.get("risk", 0)
            lines.append(
                f"- [{f.get('event_type', '?')}] (risk={risk}) "
                f"{str(f.get('data', ''))[:200]}"
            )
        return "\n".join(lines)

    def _format_correlations(self, correlations: List[Dict]) -> str:
        if not correlations:
            return "No correlations found."
        lines = []
        for c in correlations:
            lines.append(
                f"- {c.get('type', '?')}: {c.get('description', '')[:200]}"
            )
        return "\n".join(lines)

    @classmethod
    def create(cls) -> "ReportGeneratorAgent":
        config = AgentConfig.from_env("report_generator")
        config.llm_model = "gpt-4o"  # Use smarter model for reports
        config.event_types = cls(config).event_types
        return cls(config)
