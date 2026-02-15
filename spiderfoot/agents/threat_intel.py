"""
Threat Intel Analyzer Agent
=============================
Cross-references scan findings with threat intelligence context.

Analyzes indicators of compromise (IOCs) found during scans against
known threat actor TTPs, malware families, and attack patterns.
"""

import json
import logging
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.threat_intel")

SYSTEM_PROMPT = """You are a threat intelligence analyst. Analyze the provided OSINT findings
and cross-reference them with known threat intelligence patterns.

Identify potential:
- Threat actor associations (APT groups, cybercrime groups)
- Malware family indicators
- Attack pattern matches (MITRE ATT&CK)
- Campaign associations

Respond in JSON format:
{
  "threat_assessment": "overall assessment paragraph",
  "threat_level": "critical" | "high" | "medium" | "low" | "none",
  "confidence": 0.0-1.0,
  "potential_threat_actors": [
    {
      "name": "Actor name or designation",
      "confidence": 0.0-1.0,
      "rationale": "Why this actor is suspected"
    }
  ],
  "mitre_attack_techniques": [
    {
      "technique_id": "T1xxx",
      "technique_name": "",
      "tactic": "",
      "relevance": ""
    }
  ],
  "ioc_enrichment": [
    {
      "ioc": "indicator value",
      "type": "domain|ip|hash|url",
      "assessment": "malicious|suspicious|benign|unknown",
      "context": ""
    }
  ],
  "recommended_actions": ["list of recommended actions"],
  "tags": ["relevant", "tags"]
}"""


class ThreatIntelAnalyzerAgent(BaseAgent):
    """Cross-references findings with threat intelligence context."""

    @property
    def event_types(self) -> List[str]:
        return [
            "MALICIOUS_*",
            "BLACKLISTED_*",
            "DARKNET_*",
            "VULNERABILITY_CVE",
            "IP_ADDRESS",
            "DOMAIN_NAME",
            "AFFILIATE_*",
        ]

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        event_type = event.get("event_type", "UNKNOWN")
        event_data = event.get("data", "")
        target = event.get("target", "")
        source_module = event.get("source_module", "")
        risk = event.get("risk", 0)
        related_events = event.get("related_events", [])

        related_text = ""
        if related_events:
            related_text = "\n**Related Findings:**\n"
            for re_evt in related_events[:10]:
                related_text += (
                    f"- [{re_evt.get('event_type', '?')}] "
                    f"{str(re_evt.get('data', ''))[:150]}\n"
                )

        user_prompt = f"""Analyze this OSINT finding for threat intelligence relevance:

**Event Type:** {event_type}
**Target:** {target}
**Source:** {source_module}
**Risk Score:** {risk}/100
**Finding:**
{event_data[:4000]}
{related_text}

Cross-reference with known threat actor TTPs, malware families, and MITRE ATT&CK patterns."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2048,
            )

            result_data = json.loads(response)
            confidence = float(result_data.get("confidence", 0.5))

            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="threat_intel_analysis",
                data=result_data,
                confidence=confidence,
            )

        except json.JSONDecodeError:
            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="threat_intel_analysis",
                data={"threat_level": "unknown", "raw_response": response[:2000]},
                confidence=0.2,
            )

    @classmethod
    def create(cls) -> "ThreatIntelAnalyzerAgent":
        config = AgentConfig.from_env("threat_intel")
        config.event_types = cls(config).event_types
        return cls(config)
