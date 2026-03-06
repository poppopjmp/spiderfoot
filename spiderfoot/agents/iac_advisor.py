"""
IaC Advisor Agent
==================
Reviews generated Infrastructure-as-Code (Terraform, Ansible, Docker Compose,
Packer) for security issues, best-practice violations, and hardening gaps.

Processes events of type ``IAC_GENERATED`` (published after the IaC generation
endpoint writes its bundle) and can also be invoked directly via the
``POST /iac/review`` REST endpoint.

Returns per-file analysis plus an aggregate security score (0-100) and a
prioritised issue list with suggested fixes.
"""

import json
import logging
from typing import Any, Dict, List

from .base import AgentConfig, AgentResult, BaseAgent

logger = logging.getLogger("sf.agents.iac_advisor")

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert DevSecOps engineer specialising in \
Infrastructure-as-Code security review for Terraform, Ansible, Docker Compose, \
and Packer configurations.

Your task is to review the provided IaC files and identify:

1. **Security Issues** – hardcoded secrets/credentials, overly-permissive IAM \
policies or security groups, unencrypted storage, missing TLS, world-readable \
permissions, root user containers, privileged mode.
2. **Best-Practice Violations** – missing state backend / remote locking \
(Terraform), unpinned provider/image versions (latest tag), missing \
`become: false` guard (Ansible), exposed ENV secrets (Docker), missing \
resource tagging.
3. **Hardening Gaps** – missing network segmentation, absent logging/monitoring \
config, lack of least-privilege IAM, missing secrets management integration \
(Vault / AWS Secrets Manager / Azure Key Vault).
4. **Optimisation Suggestions** – unused variables, duplicated resource blocks, \
missing lifecycle rules, opportunities to use modules.

Respond ONLY with valid JSON in this exact structure:
{
  "security_score": <integer 0-100, higher is safer>,
  "review_status": "approved" | "needs_changes" | "rejected",
  "summary": "<1-3 sentence plain-language overview>",
  "issues": [
    {
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "category": "security" | "best_practice" | "hardening" | "optimisation",
      "file": "<category/filename>",
      "description": "<clear problem statement>",
      "fix": "<concrete remediation with example snippet where helpful>"
    }
  ],
  "positive_findings": ["<things done well>"],
  "compliance_notes": "<brief note on CIS/SOC2/PCI-DSS relevance if applicable>"
}

Be thorough but concise. Prioritise actionable findings."""

# ── Agent ─────────────────────────────────────────────────────────────────────


class IaCAdvisorAgent(BaseAgent):
    """
    Reviews Infrastructure-as-Code bundles produced by the IaC generation
    endpoint for security, best-practice and hardening issues.
    """

    @property
    def event_types(self) -> List[str]:
        return ["IAC_GENERATED"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_bundle_text(self, bundle: Dict[str, Any], files: Dict[str, Any]) -> str:
        """
        Flatten the IaC bundle into a readable text block for the LLM.
        Includes file-path headings and truncates very large files.
        """
        MAX_FILE_CHARS = 6_000  # keep total prompt manageable
        MAX_TOTAL_CHARS = 40_000

        lines: List[str] = []
        total = 0

        for category, category_files in bundle.items():
            if not isinstance(category_files, dict):
                continue
            for filename, content in category_files.items():
                if not isinstance(content, str):
                    continue
                heading = f"\n{'='*60}\n# {category}/{filename}\n{'='*60}\n"
                snippet = content[:MAX_FILE_CHARS]
                if len(content) > MAX_FILE_CHARS:
                    snippet += f"\n... [{len(content) - MAX_FILE_CHARS} chars truncated]"
                entry = heading + snippet
                total += len(entry)
                if total > MAX_TOTAL_CHARS:
                    lines.append(f"\n[Bundle truncated at {MAX_TOTAL_CHARS} chars to fit context window]")
                    break
                lines.append(entry)

        return "".join(lines) if lines else "(empty bundle)"

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    async def process_event(self, event: Dict[str, Any]) -> AgentResult:
        """Process an IAC_GENERATED event from the event bus."""
        bundle = event.get("bundle", {})
        files = event.get("files", {})
        provider = event.get("provider", "unknown")
        scan_id = event.get("scan_id", "")
        target = event.get("target", "")

        return await self._review(
            bundle=bundle,
            files=files,
            provider=provider,
            scan_id=scan_id,
            target=target,
            event_id=event.get("id", f"iac-{scan_id}"),
        )

    async def review_bundle(
        self,
        *,
        bundle: Dict[str, Any],
        files: Dict[str, Any],
        provider: str,
        scan_id: str = "",
        target: str = "",
    ) -> AgentResult:
        """
        Direct (non-event-bus) entry point, called by the REST endpoint.
        Accepts the raw IaC bundle from the generation API response.
        """
        return await self._review(
            bundle=bundle,
            files=files,
            provider=provider,
            scan_id=scan_id,
            target=target,
            event_id=f"iac-review-{scan_id or 'direct'}",
        )

    async def _review(
        self,
        *,
        bundle: Dict[str, Any],
        files: Dict[str, Any],
        provider: str,
        scan_id: str,
        target: str,
        event_id: str,
    ) -> AgentResult:
        bundle_text = self._build_bundle_text(bundle, files)

        file_list = []
        for cat, fnames in files.items():
            if isinstance(fnames, list):
                for fn in fnames:
                    file_list.append(f"  • {cat}/{fn}")
            elif isinstance(fnames, dict):
                for fn in fnames:
                    file_list.append(f"  • {cat}/{fn}")

        user_prompt = f"""Review this Infrastructure-as-Code bundle generated from a SpiderFoot OSINT scan.

**Cloud Provider:** {provider}
**Scan ID:** {scan_id or 'N/A'}
**Target:** {target or 'N/A'}
**Files included:**
{chr(10).join(file_list) if file_list else '  (none)'}

--- BEGIN IaC BUNDLE ---
{bundle_text}
--- END IaC BUNDLE ---

Perform a thorough security review and return the JSON result."""

        try:
            raw = await self.call_llm(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.15,
                max_tokens=3072,
            )

            # Strip markdown fences if the model adds them
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                cleaned = "\n".join(lines).strip()

            result_data = json.loads(cleaned)

            # Derive confidence from score + issue severity
            score = int(result_data.get("security_score", 50))
            critical_count = sum(
                1 for i in result_data.get("issues", [])
                if i.get("severity") == "critical"
            )
            confidence = min(0.95, 0.5 + (score / 200.0) - (critical_count * 0.05))

            return AgentResult(
                agent_name=self.config.name,
                event_id=event_id,
                scan_id=scan_id,
                result_type="iac_review",
                data=result_data,
                confidence=round(max(0.1, confidence), 3),
            )

        except json.JSONDecodeError:
            logger.warning("IaC Advisor: LLM did not return valid JSON — storing raw response")
            return AgentResult(
                agent_name=self.config.name,
                event_id=event_id,
                scan_id=scan_id,
                result_type="iac_review",
                data={
                    "review_status": "needs_changes",
                    "security_score": 50,
                    "summary": "Review completed but structured parsing failed.",
                    "raw_response": raw[:4000],
                    "issues": [],
                    "positive_findings": [],
                    "compliance_notes": "",
                },
                confidence=0.3,
            )

    @classmethod
    def create(cls) -> "IaCAdvisorAgent":
        config = AgentConfig.from_env("iac_advisor")
        config.event_types = cls(config).event_types
        return cls(config)
