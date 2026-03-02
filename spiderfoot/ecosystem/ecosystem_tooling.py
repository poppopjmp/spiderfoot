"""Ecosystem and Community Tooling (Phase 7, Cycles 551-650).

Provides plugin marketplace, module signing, dependency resolution,
versioning/changelog, integration helpers (Burp, Maltego, VSCode,
GitHub Actions), and SDK generation utilities.

Covers:
  - Cycles 551-560: Module submission & validation pipeline
  - Cycles 561-570: Module signing & verification
  - Cycles 571-580: Module dependency resolution
  - Cycles 581-590: Module versioning & changelog
  - Cycles 591-600: Community module index
  - Cycles 601-610: Integration helpers (Burp, Maltego, VSCode, GitHub Actions)
  - Cycles 611-650: SDK generation framework
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.ecosystem")


# ── Module Submission (Cycles 551-560) ────────────────────────────────


class SubmissionStatus(str, Enum):
    """Module submission status."""
    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ModuleSubmission:
    """A community module submission."""
    module_name: str
    author: str
    version: str
    description: str
    source_code: str
    metadata: dict = field(default_factory=dict)
    status: SubmissionStatus = SubmissionStatus.PENDING
    review_notes: str = ""
    submitted_at: float = field(default_factory=time.time)
    submission_id: str = ""


class ModuleSubmissionPipeline:
    """Validates and processes community module submissions.

    Checks: naming convention, required methods, no dangerous imports,
    metadata completeness, and source code quality.
    """

    REQUIRED_METHODS = ["meta", "watchedEvents", "producedEvents",
                        "handleEvent"]
    DANGEROUS_IMPORTS = ["subprocess", "ctypes", "eval", "exec",
                         "__import__"]
    NAME_PATTERN = re.compile(r"^sfp_[a-z][a-z0-9_]{2,30}$")

    def __init__(self) -> None:
        self._submissions: dict[str, ModuleSubmission] = {}
        self._counter = 0

    def submit(self, submission: ModuleSubmission) -> str:
        """Submit a module for review. Returns submission ID."""
        self._counter += 1
        sid = f"sub-{self._counter:04d}"
        submission.submission_id = sid
        submission.status = SubmissionStatus.PENDING
        self._submissions[sid] = submission
        return sid

    def validate(self, submission_id: str) -> dict:
        """Run validation checks on a submission.

        Returns dict with "valid", "errors", "warnings".
        """
        sub = self._submissions.get(submission_id)
        if sub is None:
            return {"valid": False, "errors": ["Submission not found"],
                    "warnings": []}

        errors: list[str] = []
        warnings: list[str] = []

        # Name check
        if not self.NAME_PATTERN.match(sub.module_name):
            errors.append(
                f"Module name '{sub.module_name}' must match "
                f"pattern 'sfp_[a-z][a-z0-9_]{{2,30}}'")

        # Required methods
        for method in self.REQUIRED_METHODS:
            if f"def {method}" not in sub.source_code:
                errors.append(f"Missing required method: {method}")

        # Dangerous imports
        for imp in self.DANGEROUS_IMPORTS:
            if imp in sub.source_code:
                errors.append(f"Dangerous import/usage: {imp}")

        # Metadata
        if not sub.description:
            warnings.append("Missing description")
        if not sub.author:
            errors.append("Missing author")
        if not sub.version:
            errors.append("Missing version")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def approve(self, submission_id: str, notes: str = "") -> bool:
        """Approve a submission."""
        sub = self._submissions.get(submission_id)
        if sub is None:
            return False
        sub.status = SubmissionStatus.APPROVED
        sub.review_notes = notes
        return True

    def reject(self, submission_id: str, notes: str = "") -> bool:
        """Reject a submission."""
        sub = self._submissions.get(submission_id)
        if sub is None:
            return False
        sub.status = SubmissionStatus.REJECTED
        sub.review_notes = notes
        return True

    def get_submission(self, submission_id: str
                       ) -> ModuleSubmission | None:
        return self._submissions.get(submission_id)

    def get_by_status(self, status: SubmissionStatus
                      ) -> list[ModuleSubmission]:
        return [s for s in self._submissions.values()
                if s.status == status]

    @property
    def count(self) -> int:
        return len(self._submissions)


# ── Module Signing (Cycles 561-570) ──────────────────────────────────


@dataclass
class ModuleSignature:
    """A module's verification signature."""
    module_name: str
    version: str
    content_hash: str
    signer: str
    algorithm: str = "sha256"
    signed_at: float = field(default_factory=time.time)


class ModuleSigner:
    """Signs and verifies module content integrity.

    Uses SHA-256 content hashing (not cryptographic signing —
    that would require a PKI which is out of scope for dev tooling).
    """

    def __init__(self) -> None:
        self._signatures: dict[str, ModuleSignature] = {}

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA-256 hash of module content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def sign(self, module_name: str, version: str,
             content: str, signer: str) -> ModuleSignature:
        """Sign a module's content."""
        content_hash = self.compute_hash(content)
        sig = ModuleSignature(
            module_name=module_name,
            version=version,
            content_hash=content_hash,
            signer=signer,
        )
        key = f"{module_name}:{version}"
        self._signatures[key] = sig
        return sig

    def verify(self, module_name: str, version: str,
               content: str) -> dict:
        """Verify a module's content against its signature.

        Returns dict with "verified", "signer", "details".
        """
        key = f"{module_name}:{version}"
        sig = self._signatures.get(key)
        if sig is None:
            return {"verified": False, "signer": None,
                    "details": "No signature found"}

        current_hash = self.compute_hash(content)
        if current_hash == sig.content_hash:
            return {"verified": True, "signer": sig.signer,
                    "details": "Content matches signature"}
        else:
            return {"verified": False, "signer": sig.signer,
                    "details": "Content has been modified"}

    @property
    def signature_count(self) -> int:
        return len(self._signatures)


# ── Module Dependency Resolution (Cycles 571-580) ────────────────────


@dataclass
class ModuleDependency:
    """A module dependency declaration."""
    module_name: str
    depends_on: list[str] = field(default_factory=list)
    optional_deps: list[str] = field(default_factory=list)
    conflicts_with: list[str] = field(default_factory=list)


class DependencyResolver:
    """Resolves module dependencies with cycle detection.

    Performs topological sort and detects circular dependencies.
    """

    def __init__(self) -> None:
        self._deps: dict[str, ModuleDependency] = {}

    def register(self, dep: ModuleDependency) -> None:
        """Register a module's dependencies."""
        self._deps[dep.module_name] = dep

    def resolve(self, module_name: str) -> dict:
        """Resolve dependencies for a module.

        Returns dict with "order" (topological), "missing", "conflicts".
        """
        if module_name not in self._deps:
            return {"order": [module_name], "missing": [], "conflicts": []}

        visited: set[str] = set()
        order: list[str] = []
        missing: list[str] = []
        path: set[str] = set()
        cycle_found = False

        def dfs(name: str) -> None:
            nonlocal cycle_found
            if name in path:
                cycle_found = True
                return
            if name in visited:
                return
            path.add(name)
            visited.add(name)

            dep = self._deps.get(name)
            if dep:
                for req in dep.depends_on:
                    if req not in self._deps:
                        missing.append(req)
                    else:
                        dfs(req)
            order.append(name)
            path.discard(name)

        dfs(module_name)

        conflicts = []
        dep = self._deps.get(module_name)
        if dep:
            for c in dep.conflicts_with:
                if c in visited:
                    conflicts.append(c)

        return {
            "order": order if not cycle_found else [],
            "missing": list(dict.fromkeys(missing)),
            "conflicts": conflicts,
            "cycle_detected": cycle_found,
        }

    def check_conflicts(self, modules: list[str]) -> list[str]:
        """Check for conflicts among a set of modules."""
        conflicts = []
        module_set = set(modules)
        for name in modules:
            dep = self._deps.get(name)
            if dep:
                for c in dep.conflicts_with:
                    if c in module_set:
                        pair = tuple(sorted([name, c]))
                        if f"{pair[0]} <-> {pair[1]}" not in conflicts:
                            conflicts.append(f"{pair[0]} <-> {pair[1]}")
        return conflicts

    @property
    def module_count(self) -> int:
        return len(self._deps)


# ── Module Versioning (Cycles 581-590) ────────────────────────────────


@dataclass
class ModuleVersion:
    """A module version entry."""
    module_name: str
    version: str
    changelog: str = ""
    released_at: float = field(default_factory=time.time)
    compatible_sf_versions: list[str] = field(default_factory=list)


class ModuleRegistry:
    """Community module registry with versioning.

    Tracks module versions, changelogs, and compatibility.
    """

    def __init__(self) -> None:
        self._modules: dict[str, list[ModuleVersion]] = defaultdict(list)

    def register(self, version: ModuleVersion) -> None:
        """Register a new module version."""
        self._modules[version.module_name].append(version)

    def get_versions(self, module_name: str) -> list[ModuleVersion]:
        """Get all versions of a module."""
        return list(self._modules.get(module_name, []))

    def get_latest(self, module_name: str) -> ModuleVersion | None:
        """Get the latest version of a module."""
        versions = self._modules.get(module_name, [])
        if not versions:
            return None
        return max(versions, key=lambda v: v.released_at)

    def search(self, query: str) -> list[str]:
        """Search modules by name."""
        query_lower = query.lower()
        return [name for name in self._modules
                if query_lower in name.lower()]

    def get_changelog(self, module_name: str) -> str:
        """Get combined changelog for a module."""
        versions = self.get_versions(module_name)
        lines = []
        for v in sorted(versions, key=lambda x: x.released_at,
                        reverse=True):
            lines.append(f"## {v.version}")
            if v.changelog:
                lines.append(v.changelog)
            lines.append("")
        return "\n".join(lines)

    @property
    def module_count(self) -> int:
        return len(self._modules)

    @property
    def total_versions(self) -> int:
        return sum(len(v) for v in self._modules.values())


# ── Integration Helpers (Cycles 601-610) ──────────────────────────────


class IntegrationTemplate:
    """Generates integration templates for external tools."""

    @staticmethod
    def burp_extension(api_url: str = "http://localhost:5001") -> str:
        """Generate Burp Suite extension template."""
        return f"""# SpiderFoot Burp Extension Template
# Register in Burp: Extender > Add > Python
# Requires: Jython

from burp import IBurpExtender, IContextMenuFactory
from javax.swing import JMenuItem
import java.net.URL as URL
import json

class BurpExtender(IBurpExtender, IContextMenuFactory):
    API_URL = "{api_url}"

    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        callbacks.setExtensionName("SpiderFoot Integration")
        callbacks.registerContextMenuFactory(self)

    def createMenuItems(self, invocation):
        menu = JMenuItem("Send to SpiderFoot")
        menu.addActionListener(lambda e: self.send_to_sf(invocation))
        return [menu]

    def send_to_sf(self, invocation):
        messages = invocation.getSelectedMessages()
        for msg in messages:
            url = str(msg.getUrl())
            # POST to SpiderFoot API
            data = json.dumps({{"target": url, "modules": []}})
            # ... HTTP POST to self.API_URL + "/api/v1/scans"
"""

    @staticmethod
    def maltego_transform() -> str:
        """Generate Maltego transform template."""
        return """# SpiderFoot Maltego Transform Template
# Maltego TRX API

from maltego_trx.maltego import UIM_TYPES
from maltego_trx.transform import DiscoverableTransform

class SpiderFootLookup(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request, response):
        target = request.Value
        # Call SpiderFoot API
        # results = sf_api.scan(target)
        # for result in results:
        #     entity = response.addEntity("maltego.Domain", result["data"])
        #     entity.addProperty("source", value="SpiderFoot")
        response.addUIMessage("SpiderFoot lookup complete", UIM_TYPES["Inform"])
"""

    @staticmethod
    def github_actions_workflow() -> str:
        """Generate GitHub Actions workflow template."""
        return """# .github/workflows/spiderfoot-scan.yml
name: SpiderFoot Security Scan

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday
  workflow_dispatch:

jobs:
  scan:
    runs-on: ubuntu-latest
    services:
      spiderfoot:
        image: ghcr.io/spiderfoot/spiderfoot:latest
        ports:
          - 5001:5001
    steps:
      - name: Wait for SpiderFoot
        run: |
          for i in $(seq 1 30); do
            curl -s http://localhost:5001/api/v1/health && break
            sleep 2
          done

      - name: Run Scan
        run: |
          curl -X POST http://localhost:5001/api/v1/scans \\
            -H 'Content-Type: application/json' \\
            -d '{"target": "${{ github.event.inputs.target }}", "modules": []}'

      - name: Collect Results
        run: |
          curl http://localhost:5001/api/v1/scans/latest/results > results.json

      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: spiderfoot-results
          path: results.json
"""

    @staticmethod
    def vscode_extension_manifest() -> dict:
        """Generate VS Code extension package.json template."""
        return {
            "name": "spiderfoot-module-dev",
            "displayName": "SpiderFoot Module Development",
            "version": "0.1.0",
            "engines": {"vscode": "^1.85.0"},
            "categories": ["Snippets", "Testing"],
            "activationEvents": ["onLanguage:python"],
            "contributes": {
                "snippets": [
                    {"language": "python", "path": "./snippets.json"}
                ],
                "commands": [
                    {
                        "command": "spiderfoot.scaffoldModule",
                        "title": "SpiderFoot: Scaffold New Module",
                    },
                    {
                        "command": "spiderfoot.validateModule",
                        "title": "SpiderFoot: Validate Module",
                    },
                ],
            },
        }


# ── SDK Generation (Cycles 611-650) ──────────────────────────────────


@dataclass
class SDKEndpoint:
    """An API endpoint for SDK generation."""
    method: str
    path: str
    operation_id: str
    description: str = ""
    request_body: str = ""  # type hint
    response_type: str = "dict"


class SDKGenerator:
    """Generates client SDK code from API endpoint definitions.

    Supports Python, Go, and JavaScript clients.
    """

    DEFAULT_ENDPOINTS = [
        SDKEndpoint("GET", "/api/v1/health", "get_health",
                    "Health check"),
        SDKEndpoint("GET", "/api/v1/scans", "list_scans",
                    "List all scans", response_type="list[dict]"),
        SDKEndpoint("POST", "/api/v1/scans", "create_scan",
                    "Create a new scan", request_body="dict"),
        SDKEndpoint("GET", "/api/v1/scans/{scan_id}", "get_scan",
                    "Get scan details"),
        SDKEndpoint("DELETE", "/api/v1/scans/{scan_id}", "delete_scan",
                    "Delete a scan"),
        SDKEndpoint("GET", "/api/v1/scans/{scan_id}/results",
                    "get_scan_results", "Get scan results",
                    response_type="list[dict]"),
        SDKEndpoint("GET", "/api/v1/modules", "list_modules",
                    "List available modules",
                    response_type="list[dict]"),
    ]

    def __init__(self, base_url: str = "http://localhost:5001",
                 endpoints: list[SDKEndpoint] | None = None) -> None:
        self.base_url = base_url
        self._endpoints = endpoints or list(self.DEFAULT_ENDPOINTS)

    def generate_python(self) -> str:
        """Generate Python SDK client."""
        lines = [
            '"""SpiderFoot Python SDK Client (auto-generated)."""',
            "",
            "import httpx",
            "from typing import Any",
            "",
            "",
            "class SpiderFootClient:",
            '    """SpiderFoot API client."""',
            "",
            "    def __init__(self, base_url: str = "
            f'"{self.base_url}",',
            "                 api_key: str = \"\") -> None:",
            "        self.base_url = base_url.rstrip(\"/\")",
            "        self._headers = {}",
            "        if api_key:",
            '            self._headers["Authorization"] = f"Bearer {api_key}"',
            "",
        ]

        for ep in self._endpoints:
            method_lower = ep.method.lower()
            path_params = re.findall(r"\{(\w+)\}", ep.path)
            params = ", ".join(f"{p}: str" for p in path_params)
            if ep.request_body:
                if params:
                    params += ", "
                params += "data: dict"

            sig = f"    def {ep.operation_id}(self"
            if params:
                sig += f", {params}"
            sig += ") -> Any:"
            lines.append(sig)
            lines.append(f'        """{ep.description}."""')

            path_expr = ep.path
            for p in path_params:
                path_expr = path_expr.replace(f"{{{p}}}", f"{{{p}}}")

            lines.append(f'        url = f"{{self.base_url}}{path_expr}"')

            if ep.request_body:
                lines.append(
                    f"        resp = httpx.{method_lower}"
                    f"(url, json=data, headers=self._headers)"
                )
            else:
                lines.append(
                    f"        resp = httpx.{method_lower}"
                    f"(url, headers=self._headers)"
                )

            lines.append("        resp.raise_for_status()")
            lines.append("        return resp.json()")
            lines.append("")

        return "\n".join(lines)

    def generate_javascript(self) -> str:
        """Generate JavaScript SDK client."""
        lines = [
            "// SpiderFoot JavaScript SDK Client (auto-generated)",
            "",
            "class SpiderFootClient {",
            "  constructor(baseUrl, apiKey) {",
            f'    this.baseUrl = baseUrl || "{self.base_url}";',
            "    this.headers = {};",
            "    if (apiKey) {",
            '      this.headers["Authorization"] = `Bearer ${apiKey}`;',
            "    }",
            "  }",
            "",
        ]

        for ep in self._endpoints:
            method_lower = ep.method.lower()
            path_params = re.findall(r"\{(\w+)\}", ep.path)
            params = list(path_params)
            if ep.request_body:
                params.append("data")

            js_path = re.sub(r"\{(\w+)\}", r"${\1}", ep.path)

            lines.append(f"  async {ep.operation_id}("
                         f"{', '.join(params)}) {{")
            lines.append(f"    // {ep.description}")
            lines.append(f"    const url = `${{this.baseUrl}}"
                         f"{js_path}`;")

            if ep.request_body:
                lines.append("    const resp = await fetch(url, {")
                lines.append(f'      method: "{ep.method}",')
                lines.append("      headers: { ...this.headers, "
                             "'Content-Type': 'application/json' },")
                lines.append("      body: JSON.stringify(data),")
                lines.append("    });")
            else:
                lines.append("    const resp = await fetch(url, {")
                lines.append(f'      method: "{ep.method}",')
                lines.append("      headers: this.headers,")
                lines.append("    });")

            lines.append("    return resp.json();")
            lines.append("  }")
            lines.append("")

        lines.append("}")
        lines.append("")
        lines.append("module.exports = { SpiderFootClient };")
        return "\n".join(lines)

    def generate_go(self) -> str:
        """Generate Go SDK client."""
        lines = [
            "// SpiderFoot Go SDK Client (auto-generated)",
            "package spiderfoot",
            "",
            "import (",
            '\t"encoding/json"',
            '\t"fmt"',
            '\t"io"',
            '\t"net/http"',
            '\t"bytes"',
            ")",
            "",
            "type Client struct {",
            "\tBaseURL string",
            "\tAPIKey  string",
            "\tHTTP    *http.Client",
            "}",
            "",
            "func NewClient(baseURL, apiKey string) *Client {",
            "\treturn &Client{",
            "\t\tBaseURL: baseURL,",
            "\t\tAPIKey:  apiKey,",
            "\t\tHTTP:    &http.Client{},",
            "\t}",
            "}",
            "",
        ]

        for ep in self._endpoints:
            func_name = "".join(word.capitalize()
                                for word in ep.operation_id.split("_"))
            path_params = re.findall(r"\{(\w+)\}", ep.path)
            go_params = ["c *Client"]
            for p in path_params:
                go_params.append(f"{p} string")
            if ep.request_body:
                go_params.append("data interface{}")

            lines.append(f"func ({', '.join(go_params)}) "
                         f"{func_name}() (map[string]interface{{}}, error) {{")

            go_path = ep.path
            for p in path_params:
                go_path = go_path.replace(f"{{{p}}}", f"%s")

            if path_params:
                format_args = ", ".join(path_params)
                lines.append(f'\turl := fmt.Sprintf("%s{go_path}", '
                             f'c.BaseURL, {format_args})')
            else:
                lines.append(f'\turl := c.BaseURL + "{ep.path}"')

            if ep.request_body:
                lines.append("\tbody, _ := json.Marshal(data)")
                lines.append(f'\treq, _ := http.NewRequest("{ep.method}",'
                             f' url, bytes.NewBuffer(body))')
            else:
                lines.append(f'\treq, _ := http.NewRequest("{ep.method}",'
                             f' url, nil)')

            lines.append('\treq.Header.Set("Authorization", '
                         '"Bearer "+c.APIKey)')
            lines.append("\tresp, err := c.HTTP.Do(req)")
            lines.append("\tif err != nil { return nil, err }")
            lines.append("\tdefer resp.Body.Close()")
            lines.append("\tresBody, _ := io.ReadAll(resp.Body)")
            lines.append("\tvar result map[string]interface{}")
            lines.append("\tjson.Unmarshal(resBody, &result)")
            lines.append("\treturn result, nil")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    @property
    def endpoint_count(self) -> int:
        return len(self._endpoints)
