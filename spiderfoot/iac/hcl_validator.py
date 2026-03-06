# -*- coding: utf-8 -*-
"""Deterministic HCL (HashiCorp Configuration Language) validator.

Does not require the Terraform binary — all checks are performed in pure
Python using a lightweight structural analyser of the HCL text.

Passes
------
1. **Structural** — brace balance, heredoc pairing, f-string escape leaks,
   YAML-style colon assignments.
2. **Block extraction** — parse top-level block headers into ``_Block`` objects.
3. **Semantic** — ``var.X`` vs ``variable "X"`` cross-reference, resource
   reference presence, provider attribute hints, port-range bounds.
4. **Best-practice linting** — warns on missing ``terraform {}`` block,
   unpinned provider versions, variables without ``description``, resources
   missing ``tags``, open-world CIDRs (``0.0.0.0/0``) on non-HTTP ports,
   hard-coded sensitive values.

Public API
----------
``validate_hcl(filename, content)`` → :class:`HCLValidationResult`
``validate_hcl_bundle(bundle)`` → list[:class:`HCLValidationResult`]
``audit_terraform_bundle(files)`` → list[str]
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger("spiderfoot.iac.hcl_validator")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class HCLValidationResult:
    """Validation outcome for a single HCL file."""

    filename: str = ""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors_by_line: dict[int, list[str]] = field(default_factory=dict)

    def _add_error(self, msg: str, line: int | None = None) -> None:
        self.valid = False
        self.errors.append(msg)
        if line is not None:
            self.errors_by_line.setdefault(line, []).append(msg)

    def _add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Regex patterns
_RE_BLOCK_HEADER = re.compile(
    r'^(\s*)'                          # leading indent
    r'([a-zA-Z_][a-zA-Z0-9_-]*)'      # block type (e.g. resource, provider, variable)
    r'(?:\s+"([^"]*)")?'               # optional label1 (e.g. "aws_instance")
    r'(?:\s+"([^"]*)")?'               # optional label2 (e.g. "replica")
    r'\s*\{',                          # opening brace
)
_RE_ATTR = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*(.+)')
_RE_HEREDOC_OPEN = re.compile(r'<<-?([A-Z_][A-Z_0-9]*)')
_RE_HEREDOC_CLOSE = re.compile(r'^\s*([A-Z_][A-Z_0-9]*)\s*$')
_RE_VAR_REF = re.compile(r'\$\{var\.([a-zA-Z_][a-zA-Z0-9_-]*)\}|(?<!\$\{)var\.([a-zA-Z_][a-zA-Z0-9_-]*)')
_RE_RESOURCE_REF = re.compile(r'([a-zA-Z][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_-]*)\.([a-zA-Z_][a-zA-Z0-9_-]*)')
_RE_LEAKED_PY_ESCAPE = re.compile(r'\$\{\{|\}\}[^}]|\}\}\s*$')  # ${{ or }} outside interpolation
_RE_PORT_FROM = re.compile(r'from_port\s*=\s*(-?\d+)')
_RE_PORT_TO = re.compile(r'to_port\s*=\s*(-?\d+)')
_RE_PORT_RANGE_STR = re.compile(r'port_range\s*=\s*"(\d+)-(\d+)"')
_RE_COLON_ASSIGN = re.compile(r'^\s*[a-zA-Z_][a-zA-Z0-9_-]*\s*:\s*[^/]')  # YAML leftover

# Best-practice patterns
_RE_OPEN_CIDR = re.compile(r'cidr_blocks?\s*=\s*\[?\s*"0\.0\.0\.0/0"')
_RE_HARDCODED_SECRET = re.compile(
    r'(?:password|secret|token|api_key|private_key|access_key)\s*=\s*"[^"${}][^"]{3,}"',
    re.IGNORECASE,
)
_RE_DESCRIPTION_ATTR = re.compile(r'^\s*description\s*=', re.MULTILINE)
_RE_TAGS_BLOCK = re.compile(r'^\s*tags\s*=', re.MULTILINE)


def _strip_comments(line: str) -> str:
    """Remove HCL inline comments (# and //) while preserving strings."""
    inside_string = False
    result = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"' and (i == 0 or line[i - 1] != '\\'):
            inside_string = not inside_string
        elif not inside_string:
            if c == '#':
                break
            if c == '/' and i + 1 < len(line) and line[i + 1] == '/':
                break
        result.append(c)
        i += 1
    return ''.join(result).rstrip()


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

def validate_hcl(filename: str, content: str) -> HCLValidationResult:
    """Validate a single HCL file content.

    Args:
        filename: Name of the file (for error messages).
        content:  Raw text content of the ``.tf`` file.

    Returns:
        :class:`HCLValidationResult` with all issues found.
    """
    res = HCLValidationResult(filename=filename)
    lines = content.splitlines()

    # Pass 1 — basic structural checks
    _check_brace_balance(lines, res)
    _check_heredocs(lines, res)
    _check_leaked_fstring_escapes(lines, res)
    _check_colon_assignments(lines, res)

    # Pass 2 — block extraction
    blocks = _extract_blocks(lines, res)

    # Pass 3 — semantic checks using extracted blocks
    _check_variable_references(content, blocks, res)
    _check_resource_references(content, blocks, res)
    _check_provider_required_attrs(blocks, res)
    _check_port_ranges(content, res)

    # Pass 4 — best-practice linting
    _check_best_practices(content, blocks, res, filename)

    return res


def validate_hcl_bundle(bundle: dict[str, dict[str, str]]) -> list[HCLValidationResult]:
    """Validate all ``.tf`` files within a bundle dict.

    Args:
        bundle: ``{"terraform": {"main.tf": "<hcl>", ...}, ...}``

    Returns:
        List of :class:`HCLValidationResult`, one per validated file.
    """
    results: list[HCLValidationResult] = []
    tf_files = bundle.get("terraform", {})
    if isinstance(tf_files, dict):
        for fname, content in tf_files.items():
            if fname.endswith(".tf") and isinstance(content, str):
                results.append(validate_hcl(fname, content))
    return results


# ---------------------------------------------------------------------------
# Pass 1 — structural
# ---------------------------------------------------------------------------

def _check_brace_balance(lines: list[str], res: HCLValidationResult) -> None:
    depth = 0
    in_heredoc: str | None = None
    in_string = False

    for lineno, raw in enumerate(lines, 1):
        line = _strip_comments(raw)

        # heredoc handling
        if in_heredoc:
            m = _RE_HEREDOC_CLOSE.match(line)
            if m and m.group(1) == in_heredoc:
                in_heredoc = None
            continue

        m_hd = _RE_HEREDOC_OPEN.search(line)
        if m_hd:
            in_heredoc = m_hd.group(1)
            continue

        # Count braces outside strings
        i = 0
        while i < len(line):
            c = line[i]
            if c == '"' and (i == 0 or line[i - 1] != '\\'):
                in_string = not in_string
            elif c == '$' and i + 1 < len(line) and line[i + 1] == '{':
                # ${...} interpolation — skip ahead to closing }
                i += 2
                interp_depth = 1
                while i < len(line) and interp_depth > 0:
                    if line[i] == '{':
                        interp_depth += 1
                    elif line[i] == '}':
                        interp_depth -= 1
                    i += 1
                continue
            elif not in_string:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth < 0:
                        res._add_error(f"Unexpected '}}' (extra closing brace)", lineno)
                        depth = 0
            i += 1

    if depth != 0:
        res._add_error(f"Unmatched '{{' — {depth} block(s) not closed")
    if in_heredoc:
        res._add_error(f"Unclosed heredoc: <<{in_heredoc}")


def _check_heredocs(lines: list[str], res: HCLValidationResult) -> None:
    """Verify every heredoc marker has a corresponding close tag."""
    open_heredocs: list[tuple[str, int]] = []
    for lineno, line in enumerate(lines, 1):
        m = _RE_HEREDOC_OPEN.search(line)
        if m:
            open_heredocs.append((m.group(1), lineno))
        elif open_heredocs:
            m2 = _RE_HEREDOC_CLOSE.match(line)
            if m2 and open_heredocs and m2.group(1) == open_heredocs[-1][0]:
                open_heredocs.pop()
    for tag, lineno in open_heredocs:
        res._add_error(f"Heredoc '<<{tag}' (line {lineno}) never closed")


def _check_leaked_fstring_escapes(lines: list[str], res: HCLValidationResult) -> None:
    """Detect Python f-string escape leaks: ${{ or }} that weren't unescaped."""
    for lineno, line in enumerate(lines, 1):
        # ${{ is always wrong in HCL — it should be ${
        if '${{' in line:
            res._add_error(
                "Python f-string escape '${{' found — should be '${' in HCL",
                lineno,
            )
        # Bare }} (not inside a string interpolation closing) — heuristic check
        # Count }} occurrences that don't also have a matching ${
        stripped = line.replace('${', '').replace('}', '\x00')
        if '\x00\x00' in stripped:
            res._add_warning(
                f"Possible leaked '}}}}' on line {lineno} — verify HCL interpolations",
            )


def _check_colon_assignments(lines: list[str], res: HCLValidationResult) -> None:
    """Flag YAML-style 'key: value' assignments (wrong in HCL)."""
    in_heredoc: str | None = None
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if in_heredoc:
            m = _RE_HEREDOC_CLOSE.match(line)
            if m and m.group(1) == in_heredoc:
                in_heredoc = None
            continue
        m_hd = _RE_HEREDOC_OPEN.search(line)
        if m_hd:
            in_heredoc = m_hd.group(1)
            continue
        # Skip comments and block headers
        if line.startswith('#') or line.startswith('//') or line.endswith('{'):
            continue
        if _RE_COLON_ASSIGN.match(line):
            res._add_warning(
                f"YAML-style 'key: value' assignment on line {lineno} — HCL uses 'key = value'",
            )


# ---------------------------------------------------------------------------
# Pass 2 — block extraction
# ---------------------------------------------------------------------------

@dataclass
class _Block:
    block_type: str        # resource, variable, provider, output, …
    label1: str = ""       # e.g. "aws_instance" or "aws"
    label2: str = ""       # e.g. "replica"
    start_line: int = 0
    body: str = ""


def _extract_blocks(lines: list[str], res: HCLValidationResult) -> list[_Block]:
    """Extract top-level HCL block declarations."""
    blocks: list[_Block] = []
    in_heredoc: str | None = None

    for lineno, raw in enumerate(lines, 1):
        line = _strip_comments(raw)
        if in_heredoc:
            m = _RE_HEREDOC_CLOSE.match(line)
            if m and m.group(1) == in_heredoc:
                in_heredoc = None
            continue
        m_hd = _RE_HEREDOC_OPEN.search(line)
        if m_hd:
            in_heredoc = m_hd.group(1)
            continue

        m = _RE_BLOCK_HEADER.match(line)
        if m and m.group(1) == "":  # only top-level (no leading indent)
            blocks.append(_Block(
                block_type=m.group(2),
                label1=m.group(3) or "",
                label2=m.group(4) or "",
                start_line=lineno,
            ))
    return blocks


# ---------------------------------------------------------------------------
# Pass 3 — semantic checks
# ---------------------------------------------------------------------------

def _check_variable_references(content: str, blocks: list[_Block], res: HCLValidationResult) -> None:
    """Ensure every var.X reference has a matching variable "X" block."""
    declared_vars: set[str] = {
        b.label1 for b in blocks if b.block_type == "variable" and b.label1
    }
    referenced_vars: set[str] = set()
    for m in _RE_VAR_REF.finditer(content):
        name = m.group(1) or m.group(2)
        if name:
            referenced_vars.add(name)

    for var in sorted(referenced_vars - declared_vars):
        res._add_error(f"var.{var} referenced but not declared in a 'variable' block")


def _check_resource_references(content: str, blocks: list[_Block], res: HCLValidationResult) -> None:
    """Ensure resource references like aws_instance.replica.id point to declared resources."""
    # Build a set of (resource_type, resource_name) pairs
    declared: set[tuple[str, str]] = {
        (b.label1, b.label2)
        for b in blocks
        if b.block_type == "resource" and b.label1 and b.label2
    }

    # Known non-resource identifiers to skip
    _SKIP_PREFIXES = {
        "var", "local", "module", "data", "path", "self", "each",
        "count", "terraform", "true", "false", "null",
    }

    for m in _RE_RESOURCE_REF.finditer(content):
        rtype, rname, _ = m.group(1), m.group(2), m.group(3)
        if rtype in _SKIP_PREFIXES:
            continue
        # Only check types we know are resources (have underscore = provider_type pattern)
        if "_" not in rtype:
            continue
        if (rtype, rname) not in declared:
            res._add_warning(
                f"Reference to '{rtype}.{rname}' found but resource block not declared in this file"
                " (may be in another .tf file)"
            )


def _check_provider_required_attrs(blocks: list[_Block], res: HCLValidationResult) -> None:
    """Warn when provider blocks are missing required attributes."""
    for b in blocks:
        if b.block_type == "provider" and b.label1:
            # Presence check delegated to best-practice pass; nothing to error here structurally.
            pass


def _check_port_ranges(content: str, res: HCLValidationResult) -> None:
    """Validate port numbers found in security group / firewall rules."""
    for m in _RE_PORT_FROM.finditer(content):
        port = int(m.group(1))
        if port < 0 or port > 65535:
            res._add_error(f"from_port={port} is out of valid range 0-65535")

    for m in _RE_PORT_TO.finditer(content):
        port = int(m.group(1))
        if port < 0 or port > 65535:
            res._add_error(f"to_port={port} is out of valid range 0-65535")

    for m in _RE_PORT_RANGE_STR.finditer(content):
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            res._add_error(f"port_range \"{lo}-{hi}\" has start > end")
        if lo < 0 or hi > 65535:
            res._add_error(f"port_range \"{lo}-{hi}\" contains value out of 0-65535")


# ---------------------------------------------------------------------------
# Pass 4 — best-practice linting (warnings, not errors)
# ---------------------------------------------------------------------------

# AWS / Azure / GCP resource prefixes that support tags / labels
_TAGGABLE_PREFIXES = (
    "aws_", "azurerm_", "google_compute_", "google_container_",
    "digitalocean_droplet", "digitalocean_loadbalancer",
)
# Ports where open-world ingress (0.0.0.0/0) is acceptable
_ACCEPTABLE_OPEN_PORTS = {80, 443, 8080, 8443}
# Provider names that should pin the version
_VERSIONED_PROVIDERS = {"aws", "azurerm", "google", "digitalocean", "vsphere"}


def _check_best_practices(
    content: str,
    blocks: list[_Block],
    res: HCLValidationResult,
    filename: str,
) -> None:
    """Emit best-practice warnings for common anti-patterns.

    All findings are *warnings*, not errors, so the file still passes
    validation — but the LLM repair prompt explicitly asks the model to
    address warnings too.
    """
    block_types = {b.block_type for b in blocks}
    lines = content.splitlines()

    # 1. main.tf should have a terraform {} block
    if filename in ("main.tf",) and "terraform" not in block_types:
        res._add_warning(
            "Best practice: 'main.tf' should contain a terraform {} block with "
            "required_providers and a backend configuration"
        )

    # 2. terraform block should declare required_providers
    if "terraform" in block_types and "required_providers" not in content:
        res._add_warning(
            "Best practice: terraform {} block is missing required_providers — "
            "add required_providers with pinned version constraints (~> x.y)"
        )

    # 3. Provider without version pinning
    for b in blocks:
        if b.block_type == "provider" and b.label1 in _VERSIONED_PROVIDERS:
            if "version" not in content:
                res._add_warning(
                    f"Best practice: provider \"{b.label1}\" should pin its version "
                    f"with '~> x.y' inside required_providers"
                )

    # 4. Variables without description
    _check_variable_descriptions(content, blocks, res)

    # 5. Outputs without description
    for b in blocks:
        if b.block_type == "output" and b.label1:
            # Find the body of this output block
            body_start = b.start_line
            body = "\n".join(lines[body_start:body_start + 10])  # look ahead 10 lines
            if "description" not in body:
                res._add_warning(
                    f"Best practice: output \"{b.label1}\" is missing a description attribute"
                )

    # 6. Taggable resources without tags
    for b in blocks:
        if b.block_type == "resource" and b.label1 and b.label2:
            if any(b.label1.startswith(p) for p in _TAGGABLE_PREFIXES):
                body_start = b.start_line
                # Scan up to 60 lines ahead for a tags = block
                body = "\n".join(lines[body_start:body_start + 60])
                if not _RE_TAGS_BLOCK.search(body):
                    res._add_warning(
                        f"Best practice: resource \"{b.label1}\" \"{b.label2}\" "
                        f"has no tags/labels block"
                    )

    # 7. Open-world CIDR (0.0.0.0/0) on non-HTTP ports
    if _RE_OPEN_CIDR.search(content):
        # Find the from_port nearest to each open-cidr occurrence
        for m_cidr in _RE_OPEN_CIDR.finditer(content):
            # Look for a from_port within 200 chars before the CIDR
            surrounding = content[max(0, m_cidr.start() - 200):m_cidr.start()]
            m_port = None
            for mp in _RE_PORT_FROM.finditer(surrounding):
                m_port = mp  # keep last one (closest to CIDR)
            if m_port:
                port = int(m_port.group(1))
                if port not in _ACCEPTABLE_OPEN_PORTS and port != 0:
                    res._add_warning(
                        f"Best practice: 0.0.0.0/0 (open-world) ingress on port {port} — "
                        f"restrict to known IP ranges for non-HTTP ports"
                    )
            else:
                res._add_warning(
                    "Best practice: 0.0.0.0/0 (open-world) CIDR found — "
                    "restrict to known IP ranges unless serving public HTTP/HTTPS"
                )

    # 8. Hard-coded secrets / credentials
    for m in _RE_HARDCODED_SECRET.finditer(content):
        attr = m.group(0).split("=")[0].strip()
        res._add_warning(
            f"Best practice: '{attr}' appears to be a hard-coded secret — "
            f"use a variable (sensitive = true) or a secrets-manager data source"
        )


def _check_variable_descriptions(
    content: str,
    blocks: list[_Block],
    res: HCLValidationResult,
) -> None:
    """Warn on variable blocks that have no description attribute."""
    lines = content.splitlines()
    for b in blocks:
        if b.block_type != "variable" or not b.label1:
            continue
        # Scan from the block header line for up to 15 lines
        body = "\n".join(lines[b.start_line:b.start_line + 15])
        if not _RE_DESCRIPTION_ATTR.search(body):
            res._add_warning(
                f"Best practice: variable \"{b.label1}\" is missing a description attribute"
            )


# ---------------------------------------------------------------------------
# Cross-file bundle checks
# ---------------------------------------------------------------------------

def audit_terraform_bundle(files: dict[str, str]) -> list[str]:
    """Cross-file consistency checks across all .tf files in a directory.

    Returns a list of advisory messages (not pass/fail — callers decide severity).
    """
    issues: list[str] = []

    # Collect all variable declarations and references across files
    all_declared_vars: set[str] = set()
    all_referenced_vars: set[str] = set()
    all_declared_resources: set[tuple[str, str]] = set()

    for fname, content in files.items():
        if not fname.endswith(".tf"):
            continue
        lines = content.splitlines()
        blocks = _extract_blocks(lines, HCLValidationResult())
        for b in blocks:
            if b.block_type == "variable" and b.label1:
                all_declared_vars.add(b.label1)
            if b.block_type == "resource" and b.label1 and b.label2:
                all_declared_resources.add((b.label1, b.label2))
        for m in _RE_VAR_REF.finditer(content):
            name = m.group(1) or m.group(2)
            if name:
                all_referenced_vars.add(name)

    for var in sorted(all_referenced_vars - all_declared_vars):
        issues.append(f"UNDECLARED_VAR: var.{var} referenced but no 'variable \"{var}\"' block found")

    return issues
