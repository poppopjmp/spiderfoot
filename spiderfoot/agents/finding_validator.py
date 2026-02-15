"""
Finding Validator Agent
========================
Validates high-risk findings using LLM analysis to reduce false positives.

Processes events with risk >= 60 and produces:
  - Validation verdict (confirmed / likely_false_positive / needs_review)
  - Confidence score
  - Reasoning explanation
  - Remediation suggestions
"""

import json
import logging
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.finding_validator")

SYSTEM_PROMPT = """You are a cybersecurity analyst specializing in OSINT findings validation.
Given a scan finding, analyze whether it represents a genuine security concern or a false positive.

Respond in JSON format:
{
  "verdict": "confirmed" | "likely_false_positive" | "needs_review",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your analysis",
  "severity": "critical" | "high" | "medium" | "low" | "info",
  "remediation": "Suggested remediation steps if confirmed",
  "tags": ["list", "of", "relevant", "tags"]
}"""


class FindingValidatorAgent(BaseAgent):
    """Validates scan findings to reduce false positives."""

    @property
    def event_types(self) -> List[str]:
        return [
            "MALICIOUS_*",
            "VULNERABILITY_*",
            "BLACKLISTED_*",
            "LEAKED_*",
            "DARKNET_*",
        ]

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        event_type = event.get("event_type", "UNKNOWN")
        event_data = event.get("data", "")
        source_module = event.get("source_module", "")
        target = event.get("target", "")
        risk = event.get("risk", 0)

        user_prompt = f"""Analyze this OSINT finding:

**Event Type:** {event_type}
**Target:** {target}
**Source Module:** {source_module}
**Risk Score:** {risk}/100
**Finding Data:**
{event_data[:4000]}

Validate whether this is a genuine security finding or a false positive."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
            )

            # Parse JSON response
            result_data = json.loads(response)
            confidence = float(result_data.get("confidence", 0.5))

            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="finding_validation",
                data=result_data,
                confidence=confidence,
            )

        except json.JSONDecodeError:
            # LLM didn't return valid JSON — store raw response
            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="finding_validation",
                data={"verdict": "needs_review", "raw_response": response[:2000]},
                confidence=0.3,
            )

    @classmethod
    def create(cls) -> "FindingValidatorAgent":
        config = AgentConfig.from_env("finding_validator")
        config.event_types = cls(config).event_types
        return cls(config)
