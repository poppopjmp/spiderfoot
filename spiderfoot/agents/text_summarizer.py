"""
Text Summarizer Agent
======================
Summarizes large text content found during scans (web pages, documents,
paste sites, etc.) into actionable intelligence summaries.
"""

import json
import logging
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.text_summarizer")

SYSTEM_PROMPT = """You are an OSINT analyst. Summarize the following content found during reconnaissance.
Focus on security-relevant information, exposed data, and actionable intelligence.

Respond in JSON format:
{
  "summary": "Concise summary (2-5 sentences)",
  "key_findings": ["list of key findings"],
  "entities_found": {
    "emails": [],
    "domains": [],
    "ips": [],
    "names": [],
    "organizations": [],
    "technologies": [],
    "credentials": []
  },
  "sentiment": "neutral" | "concerning" | "benign" | "malicious",
  "relevance_score": 0.0-1.0,
  "tags": ["relevant", "tags"]
}"""


class TextSummarizerAgent(BaseAgent):
    """Summarizes large text content into actionable intelligence."""

    @property
    def event_types(self) -> List[str]:
        return [
            "RAW_RIR_DATA",
            "RAW_DNS_RECORDS",
            "RAW_FILE_META_DATA",
            "TARGET_WEB_CONTENT",
            "SEARCH_ENGINE_WEB_CONTENT",
            "PASTE_CONTENT",
            "SOCIAL_MEDIA_*",
            "DOCUMENT_TEXT",
        ]

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        event_type = event.get("event_type", "UNKNOWN")
        event_data = event.get("data", "")
        target = event.get("target", "")
        source_module = event.get("source_module", "")

        # Truncate very large content
        content = event_data[:8000] if len(event_data) > 8000 else event_data
        truncated = len(event_data) > 8000

        user_prompt = f"""Summarize this content found during OSINT reconnaissance:

**Source:** {source_module}
**Event Type:** {event_type}
**Target:** {target}
**Content{'(truncated)' if truncated else ''}:**
{content}

Extract security-relevant information and entities."""

        try:
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )

            result_data = json.loads(response)
            relevance = float(result_data.get("relevance_score", 0.5))

            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="text_summary",
                data=result_data,
                confidence=relevance,
            )

        except json.JSONDecodeError:
            return AgentResult(
                agent_name=self.config.name,
                event_id=event.get("id", ""),
                scan_id=event.get("scan_id", ""),
                result_type="text_summary",
                data={"summary": response[:2000]},
                confidence=0.3,
            )

    @classmethod
    def create(cls) -> "TextSummarizerAgent":
        config = AgentConfig.from_env("text_summarizer")
        config.event_types = cls(config).event_types
        return cls(config)
