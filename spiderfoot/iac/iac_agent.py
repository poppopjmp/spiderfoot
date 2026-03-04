# -*- coding: utf-8 -*-
"""LLM-backed IaC validation and repair agent.

Repair cycle
------------
For every file that fails validation the agent runs up to MAX_REPAIR_CYCLES
(3) validate → LLM-repair → re-validate iterations::

    iteration 1: validate → errors found → LLM repair prompt → re-validate
    iteration 2: still errors → LLM repair (with remaining errors) → re-validate
    iteration 3: still errors → LLM repair (final attempt) → re-validate
    if still invalid → record in ``unresolved_errors`` for the caller

Errors that survive all three cycles are surfaced in :attr:`AgentResult.unresolved_errors`
so the user can inspect and fix them manually.

Best-practice rules are embedded in the system prompt and enforced by
:mod:`spiderfoot.iac.hcl_validator` before each repair attempt.

Public API
----------
``IaCAgent(llm_client, max_iterations=3)``
``IaCAgent.validate_and_repair(bundle, profile) -> AgentResult``
``IaCAgent.improve(bundle, profile) -> AgentResult``
"""
from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field
from typing import Any

from spiderfoot.iac.hcl_validator import (
    HCLValidationResult,
    audit_terraform_bundle,
    validate_hcl,
    validate_hcl_bundle,
)
from spiderfoot.iac.schema_validation import (
    SchemaValidationResult,
    validate_ansible_playbook,
    validate_docker_compose,
)

_log = logging.getLogger("spiderfoot.iac.iac_agent")

# Hard limit — users can pass a lower value but never higher
MAX_REPAIR_CYCLES = 3


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    """Outcome of an agent repair/improve run."""

    bundle: dict[str, dict[str, str]]
    """The (potentially repaired) IaC bundle.  Same structure as the input."""

    validation_results: list[HCLValidationResult | SchemaValidationResult] = field(default_factory=list)
    """Final validation results after the last iteration."""

    iterations: int = 0
    """Number of repair iterations that were performed."""

    repaired: bool = False
    """True if the agent made at least one successful repair."""

    notes: list[str] = field(default_factory=list)
    """Human-readable notes produced during the run."""

    all_valid: bool = True
    """True when all files pass validation after the run."""

    unresolved_errors: dict[str, list[str]] = field(default_factory=dict)
    """Errors that survived all repair cycles, keyed by filename.

    When non-empty the caller should present these to the user with a
    recommendation to fix them manually.  The agent cannot resolve them
    automatically.
    """

    def to_dict(self) -> dict[str, Any]:
        results_out = []
        for r in self.validation_results:
            if hasattr(r, "to_dict"):
                results_out.append(r.to_dict())
            else:
                results_out.append({"valid": getattr(r, "valid", None), "errors": getattr(r, "errors", [])})
        return {
            "iterations": self.iterations,
            "repaired": self.repaired,
            "all_valid": self.all_valid,
            "notes": self.notes,
            "validation_results": results_out,
            "unresolved_errors": self.unresolved_errors,
            "requires_manual_fix": bool(self.unresolved_errors),
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class IaCAgent:
    """LLM-backed agent that validates and repairs IaC bundles.

    Args:
        llm_client: An initialised :class:`~spiderfoot.ai.llm_client.LLMClient`.
        max_iterations: Maximum number of repair attempts per file (default 3).
        temperature: LLM temperature for repair prompts (default 0.1 for
                     determinism).
    """

    # ------------------------------------------------------------------ #
    # System prompt — corrections + Terraform/Ansible best practices      #
    # ------------------------------------------------------------------ #
    _SYSTEM_PROMPT = textwrap.dedent("""\
        You are a senior Infrastructure-as-Code engineer specialising in
        Terraform (HCL), Ansible, and Docker Compose.  You must produce
        production-quality, best-practice IaC.

        You will receive:
        1. A summary of the recon target (OS, open ports, detected services).
        2. One or more VALIDATION ERRORS found in the file.
        3. The full content of the file to repair.

        Return ONLY the corrected file content — no markdown fences, no
        explanations, no commentary.  The output is saved directly as a
        .tf / .yml file.

        ═══════════════════════════════════════════════════════════
        TERRAFORM BEST PRACTICES (must be met in every .tf file)
        ═══════════════════════════════════════════════════════════
        SYNTAX
        - Use '=' for attribute assignment — never ':'.
        - Every { must have a matching }; heredoc <<TAG must close with TAG.
        - ${...} interpolation inside strings; never ${{ or }} outside strings.
        - Every var.X reference needs a variable "X" {} block.
        - Every resource_type.label.attr reference needs the resource declared.
        - Provider block required; pin version with ~> (e.g. "~> 5.0").

        STRUCTURE
        - terraform {} block with required_providers and a backend stub.
        - Separate variable declarations into variables.tf; outputs into outputs.tf.
        - Use locals {} for any computed or derived value.
        - Group related resources with a blank line between blocks.
        - Add a # comment above every resource explaining its purpose.

        VARIABLES
        - Every variable block must have: description, type, and default (or
          mark sensitive = true for secrets).
        - Never hard-code IP addresses, regions, or credentials — always var.*.
        - Use validation {} blocks for variables with constrained values.

        SECURITY
        - Security group / firewall rules must restrict source CIDR; avoid
          0.0.0.0/0 for anything except HTTP/HTTPS.
        - Mark sensitive variables sensitive = true.
        - Do NOT embed passwords, API keys, or tokens in any attribute.

        TAGGING
        - AWS resources: include a tags block with at minimum Name and
          Environment = var.environment.
        - Azure resources: include a tags block.
        - GCP resources: include labels.

        ═══════════════════════════════════════════════════════════
        ANSIBLE BEST PRACTICES (must be met in every playbook)
        ═══════════════════════════════════════════════════════════
        STRUCTURE
        - Top level must be a YAML list starting with - hosts: ...
        - Set gather_facts: true or false explicitly.
        - Group tasks logically using block: with a comment name.
        - Use handlers: for service restarts triggered with notify:.

        IDEMPOTENCY
        - Every task must be idempotent (state: present/absent, creates:, etc.).
        - Prefer ansible.builtin.* fully-qualified module names.
        - Use when: conditions instead of shell tests where possible.

        PRIVILEGE
        - Set become: true at play or task level when root is required.
        - Do not use raw: or shell: when a module covers the use-case.

        VARIABLES
        - Use {{ variable }} syntax; do not mix Jinja2 strings with bare values
          without quotes.
        - Define defaults in vars: or group_vars, not inline literals.

        ERROR HANDLING
        - Use block: / rescue: / always: for cleanup on failure.
        - Set ignore_errors: true only with a comment explaining why.
    """)

    def __init__(self, llm_client: Any, max_iterations: int = MAX_REPAIR_CYCLES, temperature: float = 0.1) -> None:
        # Never exceed the hard cap regardless of what the caller requests
        self._max_iter = max(1, min(max_iterations, MAX_REPAIR_CYCLES))
        self._llm = llm_client
        self._temperature = temperature

    # ---------------------------------------------------------------------
    # Public interface
    # ---------------------------------------------------------------------

    def validate_and_repair(
        self,
        bundle: dict[str, dict[str, str]],
        profile: Any | None = None,
    ) -> AgentResult:
        """Validate all files in *bundle* and repair any that have errors.

        Args:
            bundle: ``{"terraform": {"main.tf": "<hcl>"}, "ansible": {...}, ...}``
            profile: Optional :class:`~spiderfoot.iac.target_replication.TargetProfile`.
                     Used to add context to repair prompts.

        Returns:
            :class:`AgentResult` with the (repaired) bundle and validation summary.
        """
        # Deep-copy the bundle so we don't mutate the caller's data
        bundle = {sec: dict(files) for sec, files in bundle.items()}

        all_results: list[HCLValidationResult | SchemaValidationResult] = []
        notes: list[str] = []
        iterations_total = 0
        repaired_any = False
        profile_summary = _profile_summary(profile)

        unresolved: dict[str, list[str]] = {}

        # --- Terraform (.tf) -----------------------------------------------
        tf_files = bundle.get("terraform", {})
        for fname, content in list(tf_files.items()):
            if not fname.endswith(".tf"):
                continue
            res, new_content, iters, fixed = self._repair_loop(
                filename=fname,
                content=content,
                profile_summary=profile_summary,
                validator=lambda fn, ct: validate_hcl(fn, ct),  # noqa: B023
            )
            tf_files[fname] = new_content
            all_results.append(res)
            iterations_total += iters
            if fixed:
                repaired_any = True
                notes.append(f"Repaired {fname} after {iters} iteration(s)")
            if not res.valid and res.errors:
                unresolved[fname] = list(res.errors)
                notes.append(
                    f"{fname}: {len(res.errors)} error(s) unresolved after "
                    f"{iters} repair cycle(s) — manual fix required"
                )
                _log.warning(
                    "Unresolved IaC errors in %s after %d cycle(s): %s",
                    fname, iters, res.errors,
                )

        # Cross-file bundle audit
        bundle_issues = audit_terraform_bundle(tf_files)
        if bundle_issues:
            notes.append("Cross-file audit issues:")
            notes.extend(f"  {i}" for i in bundle_issues)

        # --- Ansible (.yml / .yaml) ----------------------------------------
        ansible_files = bundle.get("ansible", {})
        for fname, content in list(ansible_files.items()):
            if not fname.endswith((".yml", ".yaml")):
                continue
            res_yaml = validate_ansible_playbook(content)
            if not res_yaml.valid:
                content, iters, fixed = self._repair_yaml_loop(
                    filename=fname,
                    content=content,
                    errors=res_yaml.errors,
                    profile_summary=profile_summary,
                    filetype="Ansible playbook",
                )
                ansible_files[fname] = content
                iterations_total += iters
                if fixed:
                    repaired_any = True
                    notes.append(f"Repaired {fname} after {iters} iteration(s)")
                # Re-validate to record the final state
                res_yaml = validate_ansible_playbook(content)
                if not res_yaml.valid and res_yaml.errors:
                    unresolved[fname] = list(res_yaml.errors)
                    notes.append(
                        f"{fname}: {len(res_yaml.errors)} error(s) unresolved after "
                        f"{iters} repair cycle(s) — manual fix required"
                    )
                    _log.warning(
                        "Unresolved IaC errors in %s after %d cycle(s): %s",
                        fname, iters, res_yaml.errors,
                    )
            all_results.append(res_yaml)

        # --- Docker Compose ------------------------------------------------
        docker_files = bundle.get("docker", {})
        for fname, content in list(docker_files.items()):
            if "docker-compose" not in fname and fname not in ("docker-compose.yml", "docker-compose.yaml"):
                continue
            res_dc = validate_docker_compose(content)
            if not res_dc.valid:
                content, iters, fixed = self._repair_yaml_loop(
                    filename=fname,
                    content=content,
                    errors=res_dc.errors,
                    profile_summary=profile_summary,
                    filetype="Docker Compose",
                )
                docker_files[fname] = content
                iterations_total += iters
                if fixed:
                    repaired_any = True
                    notes.append(f"Repaired {fname} after {iters} iteration(s)")
                res_dc = validate_docker_compose(content)
                if not res_dc.valid and res_dc.errors:
                    unresolved[fname] = list(res_dc.errors)
                    notes.append(
                        f"{fname}: {len(res_dc.errors)} error(s) unresolved after "
                        f"{iters} repair cycle(s) — manual fix required"
                    )
                    _log.warning(
                        "Unresolved IaC errors in %s after %d cycle(s): %s",
                        fname, iters, res_dc.errors,
                    )
            all_results.append(res_dc)

        all_valid = not unresolved and all(getattr(r, "valid", True) for r in all_results)
        return AgentResult(
            bundle=bundle,
            validation_results=all_results,
            iterations=iterations_total,
            repaired=repaired_any,
            notes=notes,
            all_valid=all_valid,
            unresolved_errors=unresolved,
        )

    # ------------------------------------------------------------------
    # Internal repair loops
    # ------------------------------------------------------------------

    def _repair_loop(
        self,
        filename: str,
        content: str,
        profile_summary: str,
        validator: Any,
    ) -> tuple[HCLValidationResult, str, int, bool]:
        """Validate → LLM repair → re-validate, up to MAX_REPAIR_CYCLES times.

        Returns ``(final_result, final_content, iterations, was_repaired)``.
        If errors remain after all cycles the caller is responsible for
        recording them in ``unresolved_errors``.
        """
        result = validator(filename, content)
        if result.valid:
            return result, content, 0, False

        iterations = 0
        repaired = False
        prev_error_count = len(result.errors)

        for cycle in range(1, self._max_iter + 1):
            iterations = cycle
            _log.debug(
                "Repair cycle %d/%d for %s — %d error(s) remaining",
                cycle, self._max_iter, filename, len(result.errors),
            )

            repaired_content = self._call_llm_repair(
                filename=filename,
                content=content,
                errors=result.errors,
                warnings=result.warnings,
                profile_summary=profile_summary,
                filetype="Terraform HCL",
                cycle=cycle,
                max_cycles=self._max_iter,
            )
            if not repaired_content or repaired_content.strip() == content.strip():
                _log.debug("LLM returned unchanged content on cycle %d for %s", cycle, filename)
                break

            new_result = validator(filename, repaired_content)
            content = repaired_content
            result = new_result

            if result.valid:
                repaired = True
                _log.info("Repaired %s cleanly on cycle %d/%d", filename, cycle, self._max_iter)
                break
            if len(result.errors) >= prev_error_count:
                # Not making progress — stop early rather than burn cycles
                _log.debug(
                    "No error reduction on cycle %d for %s (%d → %d), stopping early",
                    cycle, filename, prev_error_count, len(result.errors),
                )
                break
            prev_error_count = len(result.errors)

        return result, content, iterations, repaired

    def _repair_yaml_loop(
        self,
        filename: str,
        content: str,
        errors: list[str],
        profile_summary: str,
        filetype: str,
    ) -> tuple[str, int, bool]:
        """Validate → LLM repair → re-validate loop for YAML files (Ansible / Docker Compose).

        Mirrors the HCL repair loop: up to MAX_REPAIR_CYCLES cycles with
        re-validation after each attempt so the caller always gets current
        error state.  Returns ``(final_content, iterations, was_repaired)``.
        """
        repaired = False
        iterations = 0
        prev_error_count = len(errors)

        for cycle in range(1, self._max_iter + 1):
            iterations = cycle
            _log.debug(
                "YAML repair cycle %d/%d for %s — %d error(s)",
                cycle, self._max_iter, filename, len(errors),
            )
            repaired_content = self._call_llm_repair(
                filename=filename,
                content=content,
                errors=errors,
                warnings=[],
                profile_summary=profile_summary,
                filetype=filetype,
                cycle=cycle,
                max_cycles=self._max_iter,
            )
            if not repaired_content or repaired_content.strip() == content.strip():
                _log.debug("LLM returned unchanged YAML on cycle %d for %s", cycle, filename)
                break

            content = repaired_content
            repaired = True

            # Re-validate to check if we're done
            from spiderfoot.iac.schema_validation import (
                validate_ansible_playbook as _vap,
                validate_docker_compose as _vdc,
            )
            if "ansible" in filetype.lower() or filetype.lower().endswith(".yml"):
                interim = _vap(content)
            else:
                interim = _vdc(content)

            if interim.valid:
                _log.info("Repaired %s cleanly on YAML cycle %d/%d", filename, cycle, self._max_iter)
                break
            errors = interim.errors
            if len(errors) >= prev_error_count:
                _log.debug(
                    "No YAML error reduction on cycle %d for %s, stopping early", cycle, filename
                )
                break
            prev_error_count = len(errors)

        return content, iterations, repaired

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _call_llm_repair(
        self,
        filename: str,
        content: str,
        errors: list[str],
        warnings: list[str],
        profile_summary: str,
        filetype: str,
        cycle: int = 1,
        max_cycles: int = MAX_REPAIR_CYCLES,
    ) -> str:
        """Call the LLM to repair *content* and return the corrected text.

        Returns empty string on any error so callers can skip gracefully.
        """
        error_lines = "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(errors[:25]))
        warn_lines = ("\n".join(f"  - {w}" for w in warnings[:10])) if warnings else "  (none)"
        content_snippet = content[:8000] if len(content) > 8000 else content

        cycle_note = (
            f"This is repair cycle {cycle} of {max_cycles}. "
            + ("This is the FINAL attempt — fix all remaining errors." if cycle == max_cycles else
               "Focus on the numbered errors; minimise changes elsewhere.")
        )

        user_prompt = textwrap.dedent(f"""\
            {cycle_note}

            TARGET SUMMARY:
            {profile_summary}

            ERRORS TO FIX in {filename} ({filetype}) — {len(errors)} error(s):
            {error_lines}

            WARNINGS (best-practice issues to address if possible):
            {warn_lines}

            FILE CONTENT ({filename}):
            {content_snippet}

            Return the complete corrected file content only.
        """)

        try:
            response = self._llm.chat_messages(
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self._temperature,
            )
            text = getattr(response, "content", "") or ""
            # Strip markdown code fences if model adds them anyway
            text = _strip_markdown_fences(text)
            return text
        except Exception as exc:
            _log.warning("LLM repair call failed for %s: %s", filename, exc)
            return ""

    # ------------------------------------------------------------------
    # Improvement mode (re-generate from profile)
    # ------------------------------------------------------------------

    def improve(
        self,
        bundle: dict[str, dict[str, str]],
        profile: Any | None = None,
        targets: list[str] | None = None,
    ) -> AgentResult:
        """Use the LLM to improve (re-generate) selected files from the profile.

        This goes beyond repair — the LLM rewrites the file from scratch using
        the TargetProfile as context, then validates the result.

        Args:
            bundle:  Current bundle (files not in *targets* are passed through).
            profile: :class:`~spiderfoot.iac.target_replication.TargetProfile`.
            targets: List of filenames to improve (e.g. ``["main.tf"]``).
                     If None, all ``.tf`` files are improved.

        Returns:
            :class:`AgentResult` similar to ``validate_and_repair``.
        """
        bundle = {sec: dict(files) for sec, files in bundle.items()}
        notes: list[str] = []
        all_results: list[HCLValidationResult] = []
        profile_summary = _profile_summary(profile)

        tf_files = bundle.get("terraform", {})
        for fname in list(tf_files.keys()):
            if not fname.endswith(".tf"):
                continue
            if targets is not None and fname not in targets:
                continue
            improved = self._call_llm_improve(fname, tf_files[fname], profile_summary)
            if improved:
                tf_files[fname] = improved
                notes.append(f"LLM-improved {fname}")
            res = validate_hcl(fname, tf_files[fname])
            all_results.append(res)

        return AgentResult(
            bundle=bundle,
            validation_results=all_results,
            notes=notes,
            all_valid=all(r.valid for r in all_results),
        )

    def _call_llm_improve(self, filename: str, current: str, profile_summary: str) -> str:
        """Ask the LLM to rewrite *filename* with improved IaC quality."""
        system = (
            "You are an expert Terraform HCL engineer. "
            "Rewrite the given file to be clean, idiomatic, well-commented HCL. "
            "Return ONLY the file content — no markdown fences, no commentary."
        )
        user = textwrap.dedent(f"""\
            TARGET SUMMARY:
            {profile_summary}

            CURRENT {filename}:
            {current[:8000]}

            Return the improved complete file content.
        """)
        try:
            response = self._llm.chat_messages(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
            )
            text = getattr(response, "content", "") or ""
            return _strip_markdown_fences(text)
        except Exception as exc:
            _log.warning("LLM improve call failed for %s: %s", filename, exc)
            return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile_summary(profile: Any | None) -> str:
    """Create a concise text summary of a TargetProfile."""
    if profile is None:
        return "No target profile available."
    try:
        lines = [f"Target: {profile.target}"]
        if profile.operating_system:
            lines.append(f"OS: {profile.operating_system}")
        if profile.open_ports:
            port_list = ", ".join(str(p.port) for p in profile.open_ports[:20])
            lines.append(f"Open ports: {port_list}")
        if profile.web_server:
            lines.append(f"Web server: {profile.web_server} {profile.web_server_version}".strip())
        if profile.services:
            svc_list = ", ".join(f"{s.name} {s.version}".strip() for s in profile.services[:10])
            lines.append(f"Services: {svc_list}")
        if profile.cloud_provider:
            lines.append(f"Cloud provider hint: {profile.cloud_provider}")
        return "\n".join(lines)
    except Exception:
        return "Target profile available (parse error)."


def _strip_markdown_fences(text: str) -> str:
    """Remove triple-backtick code fences from LLM output."""
    lines = text.splitlines()
    # Drop first line if it's a fence opener
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    # Drop last line if it's a fence closer
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
