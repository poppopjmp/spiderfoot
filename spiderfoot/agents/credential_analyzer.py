"""
Credential Analyzer Agent
===========================
Analyzes exposed credentials found during scans for risk assessment.

Processes leaked credential events and produces:
  - Credential type classification
  - Exposure severity assessment
  - Account compromise likelihood
  - Recommended actions
"""

import json
import logging
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.credential_analyzer")

SYSTEM_PROMPT = """You are a cybersecurity analyst specializing in credential exposure analysis.
Analyze exposed credentials found during OSINT reconnaissance.

IMPORTANT: Never reproduce or display the actual credentials in your response.
Focus on the type, context, and risk implications.

Respond in JSON format:
{
  "credential_type": "password" | "api_key" | "token" | "certificate" | "ssh_key" | "database" | "other",
  "exposure_context": "Where/how the credential was found",
  "severity": "critical" | "high" | "medium" | "low",
  "confidence": 0.0-1.0,
  "is_active": true | false | null,
  "affected_services": ["list of potentially affected services"],
  "risk_factors": ["list of risk factors"],
  "recommended_actions": ["list of recommended actions"],
  "tags": ["relevant", "tags"]
}"""


class CredentialAnalyzerAgent(BaseAgent):
    """Analyzes exposed credentials for risk assessment."""

    @property
    def event_types(self) -> List[str]:
        return [
            "LEAKED_CREDENTIALS",
            "PASSWORD_COMPROMISED",
            "CREDENTIAL_*",
            "API_KEY_*",
        ]

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        event_type = event.get("event_type", "UNKNOWN")
        event_data = event.get("data", "")
        source_module = event.get("source_module", "")
        target = event.get("target", "")

        # Redact actual credential values — only analyze context
        user_prompt = f"""Analyze this credential exposure finding:

**Event Type:** {event_type}
**Target Entity:** {target}
**Source Module:** {source_module}
**Context Data (credential values redacted):**
{event_data[:3000]}

Assess the risk and provide recommendations. Do NOT reproduce any credential values."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1024,
            )

            result_data = json.loads(response)
            confidence = float(result_data.get("confidence", 0.5))

            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="credential_analysis",
                data=result_data,
                confidence=confidence,
            )

        except json.JSONDecodeError:
            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="credential_analysis",
                data={"severity": "medium", "raw_response": response[:2000]},
                confidence=0.3,
            )

    @classmethod
    def create(cls) -> "CredentialAnalyzerAgent":
        config = AgentConfig.from_env("credential_analyzer")
        config.event_types = cls(config).event_types
        return cls(config)
