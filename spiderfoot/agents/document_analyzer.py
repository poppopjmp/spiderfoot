"""
Document Analyzer Agent
========================
Analyzes user-uploaded documents and reports for OSINT relevance.

Supports:
  - PDF text extraction analysis
  - Report parsing and entity extraction
  - Cross-referencing document content with scan data
  - User-supplied intelligence integration
"""

import json
import logging
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.document_analyzer")

SYSTEM_PROMPT = """You are an OSINT analyst specializing in document intelligence.
Analyze the provided document content for security-relevant information that could
enhance an OSINT investigation.

Extract all identifiable entities and assess their relevance to the investigation target.

Respond in JSON format:
{
  "document_type": "report" | "email" | "log" | "configuration" | "code" | "intelligence_report" | "other",
  "summary": "Brief document summary",
  "entities": {
    "domains": [{"value": "", "context": ""}],
    "ip_addresses": [{"value": "", "context": ""}],
    "email_addresses": [{"value": "", "context": ""}],
    "urls": [{"value": "", "context": ""}],
    "phone_numbers": [{"value": "", "context": ""}],
    "person_names": [{"value": "", "context": ""}],
    "organization_names": [{"value": "", "context": ""}],
    "technologies": [{"value": "", "context": ""}],
    "file_hashes": [{"value": "", "context": ""}],
    "credentials": [{"type": "", "context": ""}],
    "crypto_addresses": [{"value": "", "context": ""}]
  },
  "iocs": [
    {
      "type": "domain|ip|hash|url|email",
      "value": "",
      "confidence": 0.0-1.0,
      "context": ""
    }
  ],
  "suggested_scan_targets": ["entities worth investigating further"],
  "relevance_score": 0.0-1.0,
  "classification": "public" | "internal" | "confidential" | "unknown",
  "tags": ["relevant", "tags"]
}"""


class DocumentAnalyzerAgent(BaseAgent):
    """Analyzes uploaded documents for OSINT-relevant entities and IOCs."""

    @property
    def event_types(self) -> List[str]:
        return [
            "DOCUMENT_UPLOAD",
            "USER_DOCUMENT",
            "REPORT_UPLOAD",
            "USER_INPUT_DATA",
        ]

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        document_text = event.get("data", "")
        document_name = event.get("filename", "unknown")
        document_type = event.get("content_type", "text/plain")
        target = event.get("target", "")
        scan_id = event.get("scan_id", "")

        # Handle large documents by chunking
        chunks = self._chunk_text(document_text, max_chars=8000)
        all_results = []

        for i, chunk in enumerate(chunks):
            user_prompt = f"""Analyze this document content for OSINT-relevant information:

**Document:** {document_name}
**Content Type:** {document_type}
**Investigation Target:** {target}
**Chunk:** {i + 1}/{len(chunks)}

**Content:**
{chunk}

Extract all security-relevant entities, IOCs, and potential scan targets."""

            try:
                response = await self.call_llm(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=2048,
                )
                chunk_result = json.loads(response)
                all_results.append(chunk_result)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning("Error analyzing chunk %d: %s", i, exc)

        # Merge results from all chunks
        merged = self._merge_chunk_results(all_results)
        merged["document_name"] = document_name
        merged["total_chunks"] = len(chunks)

        return AgentResult(
            agent_name=self.config.name,
            event_id=event.get("id", ""),
            scan_id=scan_id,
            result_type="document_analysis",
            data=merged,
            confidence=float(merged.get("relevance_score", 0.5)),
        )

    def _chunk_text(self, text: str, max_chars: int = 8000) -> List[str]:
        """Split text into chunks, preferring paragraph boundaries."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_chars:
                chunks.append(text)
                break

            # Find a good break point (paragraph or sentence)
            break_point = text.rfind("\n\n", 0, max_chars)
            if break_point == -1:
                break_point = text.rfind(". ", 0, max_chars)
            if break_point == -1:
                break_point = max_chars

            chunks.append(text[: break_point + 1])
            text = text[break_point + 1 :]

        return chunks

    def _merge_chunk_results(self, results: List[Dict]) -> Dict:
        """Merge analysis results from multiple chunks."""
        if not results:
            return {"summary": "No analysis results", "relevance_score": 0.0}

        if len(results) == 1:
            return results[0]

        merged = {
            "document_type": results[0].get("document_type", "other"),
            "summary": " ".join(r.get("summary", "") for r in results),
            "entities": {},
            "iocs": [],
            "suggested_scan_targets": [],
            "relevance_score": max(
                float(r.get("relevance_score", 0)) for r in results
            ),
            "tags": [],
        }

        # Merge entity lists
        entity_keys = [
            "domains", "ip_addresses", "email_addresses", "urls",
            "phone_numbers", "person_names", "organization_names",
            "technologies", "file_hashes", "credentials", "crypto_addresses",
        ]
        for key in entity_keys:
            seen = set()
            merged_list = []
            for r in results:
                entities = r.get("entities", {}).get(key, [])
                for e in entities:
                    val = e.get("value", "") if isinstance(e, dict) else str(e)
                    if val and val not in seen:
                        seen.add(val)
                        merged_list.append(e)
            merged["entities"][key] = merged_list

        # Merge IOCs (deduplicate by value)
        ioc_seen = set()
        for r in results:
            for ioc in r.get("iocs", []):
                val = ioc.get("value", "")
                if val and val not in ioc_seen:
                    ioc_seen.add(val)
                    merged["iocs"].append(ioc)

        # Merge scan targets
        target_set = set()
        for r in results:
            for t in r.get("suggested_scan_targets", []):
                if t not in target_set:
                    target_set.add(t)
                    merged["suggested_scan_targets"].append(t)

        # Merge tags
        tag_set = set()
        for r in results:
            for t in r.get("tags", []):
                tag_set.add(t)
        merged["tags"] = list(tag_set)

        return merged

    @classmethod
    def create(cls) -> "DocumentAnalyzerAgent":
        config = AgentConfig.from_env("document_analyzer")
        config.event_types = cls(config).event_types
        return cls(config)
