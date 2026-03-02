"""API Developer Experience Tooling for SpiderFoot.

Implements Phase 4 Cycles 271-290:

Cycle 271: Enhanced OpenAPI spec examples for all endpoint types
Cycle 272: API changelog with semver history
Cycle 273: API introspection — event types, module categories, rule IDs
Cycle 274-275: SDK stub generation and documentation helpers
Cycles 276-290: Missing API schemas — bulk scan, templates, module config,
               real-time correlation streaming
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence


# ── API Changelog (Cycle 272) ─────────────────────────────────────────


class ChangeType(str, Enum):
    """Type of API change."""
    ADDED = "added"
    CHANGED = "changed"
    DEPRECATED = "deprecated"
    REMOVED = "removed"
    FIXED = "fixed"
    SECURITY = "security"


@dataclass(frozen=True)
class ChangelogEntry:
    """A single changelog entry."""
    version: str
    change_type: ChangeType
    description: str
    endpoint: str = ""
    breaking: bool = False
    date: str = ""


class APIChangelog:
    """API changelog with semver history.

    Usage:
        changelog = APIChangelog()
        changelog.add("6.0.0", ChangeType.ADDED, "Initial v6 API release")
        changelog.add("6.0.0", ChangeType.ADDED, "GraphQL endpoint", "/api/graphql")
        history = changelog.get_history()
        breaking = changelog.get_breaking_changes()
    """

    def __init__(self) -> None:
        self._entries: list[ChangelogEntry] = []
        self._load_builtin()

    def _load_builtin(self) -> None:
        """Load built-in changelog entries for SpiderFoot v6."""
        builtin = [
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "REST API with FastAPI framework",
                           "/api/v1", date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "GraphQL endpoint with subscriptions",
                           "/api/graphql", date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "Scan management endpoints",
                           "/api/v1/scans", date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "Module configuration endpoints",
                           "/api/v1/modules", date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "Correlation analysis endpoints",
                           "/api/v1/correlations", date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "Event streaming via WebSocket",
                           "/api/v1/ws/events", date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.CHANGED,
                           "PostgreSQL-only database backend",
                           breaking=True, date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.REMOVED,
                           "Legacy CherryPy web interface",
                           breaking=True, date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "JWT/OAuth2 authentication",
                           "/api/v1/auth", date="2025-01-01"),
            ChangelogEntry("6.0.0", ChangeType.ADDED,
                           "Workspace multi-tenancy",
                           "/api/v1/workspaces", date="2025-01-01"),
            ChangelogEntry("6.1.0", ChangeType.ADDED,
                           "Bulk scan submission endpoint",
                           "/api/v1/scans/bulk", date="2025-06-01"),
            ChangelogEntry("6.1.0", ChangeType.ADDED,
                           "Scan templates CRUD",
                           "/api/v1/templates", date="2025-06-01"),
            ChangelogEntry("6.1.0", ChangeType.ADDED,
                           "Module enable/disable per scan",
                           "/api/v1/scans/{id}/modules", date="2025-06-01"),
            ChangelogEntry("6.1.0", ChangeType.ADDED,
                           "Real-time correlation streaming",
                           "/api/v1/ws/correlations", date="2025-06-01"),
            ChangelogEntry("6.2.0", ChangeType.ADDED,
                           "API introspection endpoint",
                           "/api/v1/introspect", date="2025-12-01"),
            ChangelogEntry("6.2.0", ChangeType.ADDED,
                           "Event type catalog endpoint",
                           "/api/v1/event-types", date="2025-12-01"),
        ]
        self._entries.extend(builtin)

    def add(
        self,
        version: str,
        change_type: ChangeType,
        description: str,
        endpoint: str = "",
        breaking: bool = False,
        date: str = "",
    ) -> None:
        """Add a changelog entry."""
        self._entries.append(ChangelogEntry(
            version=version,
            change_type=change_type,
            description=description,
            endpoint=endpoint,
            breaking=breaking,
            date=date or time.strftime("%Y-%m-%d"),
        ))

    def get_history(
        self,
        version: str | None = None,
        change_type: ChangeType | None = None,
    ) -> list[ChangelogEntry]:
        """Get changelog entries, optionally filtered."""
        entries = self._entries
        if version:
            entries = [e for e in entries if e.version == version]
        if change_type:
            entries = [e for e in entries if e.change_type == change_type]
        return sorted(entries, key=lambda e: e.version, reverse=True)

    def get_breaking_changes(self) -> list[ChangelogEntry]:
        """Get all breaking changes."""
        return [e for e in self._entries if e.breaking]

    def get_versions(self) -> list[str]:
        """Get all unique versions in order."""
        versions = sorted({e.version for e in self._entries}, reverse=True)
        return versions

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def to_markdown(self) -> str:
        """Render changelog as Markdown."""
        lines = ["# API Changelog\n"]
        by_version: dict[str, list[ChangelogEntry]] = defaultdict(list)
        for entry in self._entries:
            by_version[entry.version].append(entry)

        for version in sorted(by_version.keys(), reverse=True):
            entries = by_version[version]
            date = entries[0].date if entries[0].date else ""
            lines.append(f"## [{version}] — {date}\n")

            by_type: dict[str, list[ChangelogEntry]] = defaultdict(list)
            for e in entries:
                by_type[e.change_type.value].append(e)

            for ct in ["added", "changed", "deprecated", "removed", "fixed", "security"]:
                if ct in by_type:
                    lines.append(f"### {ct.capitalize()}\n")
                    for e in by_type[ct]:
                        breaking = " **BREAKING**" if e.breaking else ""
                        endpoint = f" (`{e.endpoint}`)" if e.endpoint else ""
                        lines.append(f"- {e.description}{endpoint}{breaking}")
                    lines.append("")

        return "\n".join(lines)


# ── API Introspection (Cycle 273) ─────────────────────────────────────


# Standard SpiderFoot event types
STANDARD_EVENT_TYPES: dict[str, str] = {
    "AFFILIATE_DOMAIN_NAME": "Domain associated with the target organization",
    "AFFILIATE_INTERNET_NAME": "Internet hostname associated with the target",
    "AFFILIATE_IPADDR": "IP address associated with an affiliate",
    "BGP_AS_MEMBER": "IP network belonging to a BGP AS",
    "BGP_AS_OWNER": "Organization owning a BGP AS",
    "BGP_AS_PEER": "BGP AS peering relationship",
    "BLACKLISTED_AFFILIATE_IPADDR": "Blacklisted affiliate IP address",
    "BLACKLISTED_IPADDR": "Blacklisted IP address",
    "BLACKLISTED_NETBLOCK": "Blacklisted network block",
    "BLACKLISTED_SUBNET": "Blacklisted subnet",
    "CO_HOSTED_SITE": "Website co-hosted on the same IP",
    "CO_HOSTED_SITE_DOMAIN": "Domain of a co-hosted site",
    "COMPANY_NAME": "Company or organization name",
    "COUNTRY_NAME": "Country associated with IP/domain",
    "DARKNET_MENTION_CONTENT": "Content mentioning target on dark web",
    "DARKNET_MENTION_URL": "Dark web URL mentioning target",
    "DNS_SPF": "SPF DNS record",
    "DNS_TEXT": "TXT DNS record",
    "DOMAIN_NAME": "Registered domain name",
    "DOMAIN_REGISTRAR": "Domain registrar",
    "DOMAIN_WHOIS": "Domain WHOIS data",
    "EMAILADDR": "Email address",
    "EMAILADDR_COMPROMISED": "Email found in breach database",
    "GEOINFO": "Geographic location data",
    "HUMAN_NAME": "Person's name",
    "INTERNET_NAME": "Internet hostname (FQDN)",
    "INTERNET_NAME_UNRESOLVED": "Unresolved internet hostname",
    "IP_ADDRESS": "IPv4 or IPv6 address",
    "LINKED_URL_EXTERNAL": "External URL linked from target",
    "LINKED_URL_INTERNAL": "Internal URL linked from target",
    "MALICIOUS_AFFILIATE_IPADDR": "Malicious affiliate IP",
    "MALICIOUS_IPADDR": "Malicious IP address",
    "MALICIOUS_INTERNET_NAME": "Malicious hostname",
    "NETBLOCK_MEMBER": "IP network block membership",
    "NETBLOCK_OWNER": "Network block owner",
    "OPERATING_SYSTEM": "Operating system detected",
    "PHONE_NUMBER": "Telephone number",
    "PHYSICAL_ADDRESS": "Physical/postal address",
    "PHYSICAL_COORDINATES": "GPS coordinates",
    "PROVIDER_DNS": "DNS provider",
    "PROVIDER_HOSTING": "Hosting provider",
    "PROVIDER_MAIL": "Email provider",
    "RAW_RIR_DATA": "Raw Regional Internet Registry data",
    "SOCIAL_MEDIA": "Social media profile",
    "SOFTWARE_USED": "Software/technology detected",
    "SSL_CERTIFICATE_EXPIRED": "Expired SSL certificate",
    "SSL_CERTIFICATE_ISSUED": "SSL certificate details",
    "SSL_CERTIFICATE_ISSUER": "SSL certificate issuer",
    "SSL_CERTIFICATE_MISMATCH": "SSL certificate hostname mismatch",
    "SSL_CERTIFICATE_RAW": "Raw SSL certificate data",
    "TCP_PORT_OPEN": "Open TCP port",
    "TCP_PORT_OPEN_BANNER": "Banner from open TCP port",
    "URL_FORM": "Form URL found on target",
    "URL_JAVASCRIPT": "JavaScript URL found",
    "URL_STATIC": "Static resource URL",
    "URL_WEB_FRAMEWORK": "Web framework URL pattern",
    "VULNERABILITY_CVE_CRITICAL": "Critical CVE vulnerability",
    "VULNERABILITY_CVE_HIGH": "High severity CVE",
    "VULNERABILITY_CVE_LOW": "Low severity CVE",
    "VULNERABILITY_CVE_MEDIUM": "Medium severity CVE",
    "VULNERABILITY_GENERAL": "General vulnerability",
    "WEBSERVER_BANNER": "Web server banner",
    "WEBSERVER_HTTPHEADERS": "HTTP response headers",
    "WEBSERVER_TECHNOLOGY": "Web server technology",
    "WIKI_URL": "Wiki URL mentioning target",
}

# Standard module categories
STANDARD_MODULE_CATEGORIES: dict[str, str] = {
    "Content Analysis": "Modules that analyze web content and extract data",
    "Crawling and Scanning": "Active scanning and crawling modules",
    "DNS": "DNS resolution and analysis modules",
    "Leaks, Dumps and Breaches": "Modules checking breach databases",
    "Passive DNS": "Passive DNS lookup modules",
    "Public Registries": "WHOIS, RIR, and public registry modules",
    "Real World": "Physical world data (geo, addresses, etc.)",
    "Reputation Systems": "IP/domain reputation checking modules",
    "Search Engines": "Search engine based modules",
    "Secondary Networks": "Alternative network modules (Tor, I2P, etc.)",
    "Social Media": "Social media profile modules",
}


class APIIntrospector:
    """API introspection service.

    Provides programmatic access to event types, module categories,
    correlation rules, and API endpoint metadata.

    Usage:
        introspector = APIIntrospector()
        event_types = introspector.get_event_types()
        categories = introspector.get_module_categories()
        summary = introspector.get_api_summary()
    """

    def __init__(self) -> None:
        self._custom_event_types: dict[str, str] = {}
        self._custom_categories: dict[str, str] = {}
        self._endpoints: list[EndpointInfo] = []
        self._load_default_endpoints()

    def get_event_types(
        self,
        pattern: str | None = None,
    ) -> dict[str, str]:
        """Get all known event types with descriptions.

        Args:
            pattern: Optional regex to filter event type names.
        """
        all_types = {**STANDARD_EVENT_TYPES, **self._custom_event_types}
        if pattern:
            regex = re.compile(pattern, re.IGNORECASE)
            all_types = {k: v for k, v in all_types.items() if regex.search(k)}
        return all_types

    def get_module_categories(self) -> dict[str, str]:
        """Get all module categories with descriptions."""
        return {**STANDARD_MODULE_CATEGORIES, **self._custom_categories}

    def register_event_type(self, name: str, description: str) -> None:
        """Register a custom event type."""
        self._custom_event_types[name] = description

    def register_category(self, name: str, description: str) -> None:
        """Register a custom module category."""
        self._custom_categories[name] = description

    def get_api_summary(self) -> dict[str, Any]:
        """Get API summary information."""
        return {
            "event_type_count": len(STANDARD_EVENT_TYPES) + len(self._custom_event_types),
            "category_count": len(STANDARD_MODULE_CATEGORIES) + len(self._custom_categories),
            "endpoint_count": len(self._endpoints),
            "endpoints_by_method": self._endpoints_by_method(),
            "endpoints_by_tag": self._endpoints_by_tag(),
        }

    def get_endpoints(
        self,
        method: str | None = None,
        tag: str | None = None,
    ) -> list["EndpointInfo"]:
        """Get API endpoints, optionally filtered."""
        endpoints = self._endpoints
        if method:
            endpoints = [e for e in endpoints if e.method.upper() == method.upper()]
        if tag:
            endpoints = [e for e in endpoints if tag in e.tags]
        return endpoints

    def add_endpoint(self, endpoint: "EndpointInfo") -> None:
        """Register an API endpoint."""
        self._endpoints.append(endpoint)

    def _endpoints_by_method(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for e in self._endpoints:
            counts[e.method.upper()] += 1
        return dict(counts)

    def _endpoints_by_tag(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for e in self._endpoints:
            for tag in e.tags:
                counts[tag] += 1
        return dict(counts)

    def _load_default_endpoints(self) -> None:
        """Load default API endpoints."""
        defaults = [
            EndpointInfo("GET", "/api/v1/scans", "List all scans",
                         tags=["Scans"]),
            EndpointInfo("POST", "/api/v1/scans", "Create a new scan",
                         tags=["Scans"]),
            EndpointInfo("GET", "/api/v1/scans/{id}", "Get scan details",
                         tags=["Scans"]),
            EndpointInfo("DELETE", "/api/v1/scans/{id}", "Delete a scan",
                         tags=["Scans"]),
            EndpointInfo("POST", "/api/v1/scans/bulk", "Submit multiple scans",
                         tags=["Scans"]),
            EndpointInfo("GET", "/api/v1/scans/{id}/events", "Get scan events",
                         tags=["Scans", "Events"]),
            EndpointInfo("GET", "/api/v1/modules", "List all modules",
                         tags=["Modules"]),
            EndpointInfo("GET", "/api/v1/modules/{name}", "Get module details",
                         tags=["Modules"]),
            EndpointInfo("PUT", "/api/v1/modules/{name}/config", "Update module config",
                         tags=["Modules", "Config"]),
            EndpointInfo("GET", "/api/v1/event-types", "List event types",
                         tags=["Introspection"]),
            EndpointInfo("GET", "/api/v1/correlations", "List correlations",
                         tags=["Correlations"]),
            EndpointInfo("POST", "/api/v1/correlations/analyze", "Run correlation",
                         tags=["Correlations"]),
            EndpointInfo("GET", "/api/v1/introspect", "API introspection",
                         tags=["Introspection"]),
            EndpointInfo("GET", "/api/v1/changelog", "API changelog",
                         tags=["Introspection"]),
            EndpointInfo("GET", "/api/v1/templates", "List scan templates",
                         tags=["Templates"]),
            EndpointInfo("POST", "/api/v1/templates", "Create scan template",
                         tags=["Templates"]),
            EndpointInfo("GET", "/api/v1/workspaces", "List workspaces",
                         tags=["Workspaces"]),
            EndpointInfo("POST", "/api/v1/auth/login", "Authenticate",
                         tags=["Auth"]),
        ]
        self._endpoints.extend(defaults)


@dataclass
class EndpointInfo:
    """Metadata about an API endpoint."""
    method: str
    path: str
    description: str
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False
    auth_required: bool = True

    @property
    def operation_id(self) -> str:
        """Generate an operation ID from method and path."""
        clean = self.path.replace("/api/v1/", "").replace("/", "_").replace("{", "").replace("}", "")
        return f"{self.method.lower()}_{clean}"


# ── OpenAPI Example Generator (Cycle 271) ─────────────────────────────


class OpenAPIExampleGenerator:
    """Generate example requests/responses for OpenAPI spec.

    Usage:
        gen = OpenAPIExampleGenerator()
        examples = gen.generate_all()
        scan_examples = gen.for_endpoint("POST", "/api/v1/scans")
    """

    def __init__(self) -> None:
        self._examples: dict[str, dict[str, Any]] = {}
        self._build_examples()

    def _build_examples(self) -> None:
        """Build example request/response pairs."""
        self._examples = {
            "POST /api/v1/scans": {
                "request": {
                    "target": "example.com",
                    "name": "Example scan",
                    "modules": ["sfp_dnsresolve", "sfp_whois"],
                    "options": {"_useragent": "SpiderFoot/6.0"},
                },
                "response": {
                    "scan_id": "abc-123-def-456",
                    "status": "QUEUED",
                    "target": "example.com",
                    "created_at": "2025-01-01T00:00:00Z",
                },
            },
            "GET /api/v1/scans": {
                "response": [
                    {
                        "scan_id": "abc-123",
                        "target": "example.com",
                        "status": "FINISHED",
                        "events_count": 1234,
                    },
                ],
            },
            "GET /api/v1/scans/{id}": {
                "response": {
                    "scan_id": "abc-123",
                    "target": "example.com",
                    "status": "FINISHED",
                    "started_at": "2025-01-01T00:00:00Z",
                    "finished_at": "2025-01-01T01:23:45Z",
                    "events_count": 1234,
                    "modules_used": ["sfp_dnsresolve", "sfp_whois"],
                },
            },
            "POST /api/v1/scans/bulk": {
                "request": {
                    "targets": ["example.com", "test.org", "192.168.1.0/24"],
                    "modules": ["sfp_dnsresolve"],
                    "options": {},
                },
                "response": {
                    "scans": [
                        {"scan_id": "bulk-001", "target": "example.com", "status": "QUEUED"},
                        {"scan_id": "bulk-002", "target": "test.org", "status": "QUEUED"},
                        {"scan_id": "bulk-003", "target": "192.168.1.0/24", "status": "QUEUED"},
                    ],
                    "total": 3,
                },
            },
            "GET /api/v1/modules": {
                "response": [
                    {
                        "name": "sfp_dnsresolve",
                        "display_name": "DNS Resolver",
                        "category": "DNS",
                        "enabled": True,
                        "watched_events": ["DOMAIN_NAME", "INTERNET_NAME"],
                        "produced_events": ["IP_ADDRESS", "AFFILIATE_IPADDR"],
                    },
                ],
            },
            "GET /api/v1/event-types": {
                "response": {
                    "event_types": [
                        {"name": "DOMAIN_NAME", "description": "Registered domain name"},
                        {"name": "IP_ADDRESS", "description": "IPv4 or IPv6 address"},
                    ],
                    "total": 68,
                },
            },
            "GET /api/v1/correlations": {
                "response": [
                    {
                        "rule_id": "shared_hosting",
                        "severity": "medium",
                        "matches": 3,
                        "description": "Multiple domains sharing the same IP",
                    },
                ],
            },
            "POST /api/v1/templates": {
                "request": {
                    "name": "Quick DNS scan",
                    "description": "Fast DNS-only scan template",
                    "modules": ["sfp_dnsresolve", "sfp_dnsbrute"],
                    "options": {"_maxthreads": 10},
                },
                "response": {
                    "template_id": "tmpl-001",
                    "name": "Quick DNS scan",
                    "created_at": "2025-01-01T00:00:00Z",
                },
            },
            "GET /api/v1/introspect": {
                "response": {
                    "event_type_count": 68,
                    "category_count": 11,
                    "endpoint_count": 18,
                    "api_version": "6.2.0",
                },
            },
            "GET /api/v1/changelog": {
                "response": {
                    "versions": ["6.2.0", "6.1.0", "6.0.0"],
                    "entries": [
                        {
                            "version": "6.2.0",
                            "type": "added",
                            "description": "API introspection endpoint",
                        },
                    ],
                },
            },
        }

    def generate_all(self) -> dict[str, dict[str, Any]]:
        """Get all examples."""
        return dict(self._examples)

    def for_endpoint(self, method: str, path: str) -> dict[str, Any] | None:
        """Get examples for a specific endpoint."""
        key = f"{method.upper()} {path}"
        return self._examples.get(key)

    def add_example(
        self,
        method: str,
        path: str,
        request: dict[str, Any] | None = None,
        response: Any = None,
    ) -> None:
        """Add a custom example."""
        key = f"{method.upper()} {path}"
        example: dict[str, Any] = {}
        if request is not None:
            example["request"] = request
        if response is not None:
            example["response"] = response
        self._examples[key] = example

    @property
    def endpoint_count(self) -> int:
        return len(self._examples)


# ── SDK Stub Generator (Cycle 275) ────────────────────────────────────


class SDKStubGenerator:
    """Generate SDK client stubs from endpoint metadata.

    Usage:
        gen = SDKStubGenerator()
        python_stub = gen.generate_python(endpoints)
        go_stub = gen.generate_go(endpoints)
    """

    def generate_python(self, endpoints: list[EndpointInfo]) -> str:
        """Generate a Python SDK client stub."""
        lines = [
            '"""SpiderFoot API Client (auto-generated)."""',
            "",
            "from __future__ import annotations",
            "",
            "import httpx",
            "",
            "",
            "class SpiderFootClient:",
            '    """SpiderFoot API client."""',
            "",
            '    def __init__(self, base_url: str = "http://localhost:5001", api_key: str = "") -> None:',
            "        self.base_url = base_url.rstrip('/')",
            "        self.api_key = api_key",
            "        self._client = httpx.Client(",
            '            base_url=self.base_url,',
            '            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},',
            "        )",
            "",
        ]

        for ep in endpoints:
            method_name = ep.operation_id
            has_path_params = "{" in ep.path
            params = []

            if has_path_params:
                # Extract path params
                path_params = re.findall(r'\{(\w+)\}', ep.path)
                params.extend(f"{p}: str" for p in path_params)

            if ep.method.upper() in ("POST", "PUT", "PATCH"):
                params.append("data: dict | None = None")

            param_str = ", ".join(["self"] + params)
            lines.append(f"    def {method_name}({param_str}) -> dict:")
            lines.append(f'        """{ep.description}."""')

            path = ep.path
            if has_path_params:
                path_params = re.findall(r'\{(\w+)\}', ep.path)
                for p in path_params:
                    path = path.replace(f"{{{p}}}", f"{{{p}}}")
                lines.append(f'        url = f"{path}"')
            else:
                lines.append(f'        url = "{path}"')

            if ep.method.upper() == "GET":
                lines.append("        resp = self._client.get(url)")
            elif ep.method.upper() == "POST":
                lines.append("        resp = self._client.post(url, json=data)")
            elif ep.method.upper() == "PUT":
                lines.append("        resp = self._client.put(url, json=data)")
            elif ep.method.upper() == "DELETE":
                lines.append("        resp = self._client.delete(url)")
            else:
                lines.append(f"        resp = self._client.request('{ep.method}', url)")

            lines.append("        resp.raise_for_status()")
            lines.append("        return resp.json()")
            lines.append("")

        return "\n".join(lines)

    def generate_go(self, endpoints: list[EndpointInfo]) -> str:
        """Generate a Go SDK client stub."""
        lines = [
            "// SpiderFoot API Client (auto-generated)",
            "package spiderfoot",
            "",
            'import (',
            '    "bytes"',
            '    "encoding/json"',
            '    "fmt"',
            '    "net/http"',
            ')',
            "",
            "type Client struct {",
            "    BaseURL string",
            "    APIKey  string",
            "    HTTP    *http.Client",
            "}",
            "",
            'func NewClient(baseURL, apiKey string) *Client {',
            "    return &Client{",
            "        BaseURL: baseURL,",
            "        APIKey:  apiKey,",
            "        HTTP:    &http.Client{},",
            "    }",
            "}",
            "",
        ]

        for ep in endpoints:
            func_name = self._go_func_name(ep)
            lines.append(f"// {func_name} — {ep.description}")

            path_params = re.findall(r'\{(\w+)\}', ep.path)
            go_params = [f"{p} string" for p in path_params]

            if ep.method.upper() in ("POST", "PUT", "PATCH"):
                go_params.append("body interface{}")

            param_str = ", ".join(go_params)
            lines.append(f"func (c *Client) {func_name}({param_str}) (map[string]interface{{}}, error) {{")

            path = ep.path
            if path_params:
                for p in path_params:
                    path = path.replace(f"{{{p}}}", f"%s")
                format_args = ", ".join(path_params)
                lines.append(f'    url := fmt.Sprintf("%s{path}", c.BaseURL, {format_args})')
            else:
                lines.append(f'    url := c.BaseURL + "{path}"')

            if ep.method.upper() in ("POST", "PUT", "PATCH"):
                lines.append("    data, _ := json.Marshal(body)")
                lines.append(f'    req, _ := http.NewRequest("{ep.method}", url, bytes.NewReader(data))')
            else:
                lines.append(f'    req, _ := http.NewRequest("{ep.method}", url, nil)')

            lines.append('    req.Header.Set("Authorization", "Bearer "+c.APIKey)')
            lines.append("    resp, err := c.HTTP.Do(req)")
            lines.append("    if err != nil {")
            lines.append("        return nil, err")
            lines.append("    }")
            lines.append("    defer resp.Body.Close()")
            lines.append("    var result map[string]interface{}")
            lines.append("    json.NewDecoder(resp.Body).Decode(&result)")
            lines.append("    return result, nil")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def _go_func_name(self, ep: EndpointInfo) -> str:
        """Convert endpoint to Go function name."""
        method = ep.method.capitalize()
        path = ep.path.replace("/api/v1/", "")
        parts = re.split(r'[/{}]', path)
        parts = [p.capitalize() for p in parts if p]
        return method + "".join(parts)


# ── Bulk Scan Schema (Cycle 276) ──────────────────────────────────────


@dataclass
class BulkScanRequest:
    """Request schema for bulk scan submission."""
    targets: list[str]
    modules: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    template_id: str | None = None
    name_prefix: str = ""

    def validate(self) -> list[str]:
        """Validate the request."""
        errors = []
        if not self.targets:
            errors.append("At least one target is required")
        if len(self.targets) > 100:
            errors.append("Maximum 100 targets per bulk request")
        for t in self.targets:
            if not t or not t.strip():
                errors.append("Empty target value")
        return errors


@dataclass
class BulkScanResponse:
    """Response schema for bulk scan submission."""
    scans: list[dict[str, str]] = field(default_factory=list)
    total: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.scans)


# ── Scan Template Schema (Cycle 276) ──────────────────────────────────


@dataclass
class ScanTemplate:
    """Scan template for reusable scan configurations."""
    template_id: str = ""
    name: str = ""
    description: str = ""
    modules: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def validate(self) -> list[str]:
        """Validate the template."""
        errors = []
        if not self.name:
            errors.append("Template name is required")
        if not self.modules:
            errors.append("At least one module is required")
        return errors


class ScanTemplateStore:
    """In-memory scan template store for development/testing.

    Usage:
        store = ScanTemplateStore()
        template = ScanTemplate(name="Quick DNS", modules=["sfp_dnsresolve"])
        store.create(template)
        found = store.get(template.template_id)
    """

    def __init__(self) -> None:
        self._templates: dict[str, ScanTemplate] = {}
        self._counter = 0

    def create(self, template: ScanTemplate) -> ScanTemplate:
        """Create a new template."""
        self._counter += 1
        template.template_id = f"tmpl-{self._counter:04d}"
        template.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        template.updated_at = template.created_at
        self._templates[template.template_id] = template
        return template

    def get(self, template_id: str) -> ScanTemplate | None:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def list(self) -> list[ScanTemplate]:
        """List all templates."""
        return list(self._templates.values())

    def update(self, template_id: str, **kwargs: Any) -> ScanTemplate | None:
        """Update a template."""
        tmpl = self._templates.get(template_id)
        if not tmpl:
            return None
        for k, v in kwargs.items():
            if hasattr(tmpl, k) and k != "template_id":
                setattr(tmpl, k, v)
        tmpl.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        return tmpl

    def delete(self, template_id: str) -> bool:
        """Delete a template."""
        if template_id in self._templates:
            del self._templates[template_id]
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._templates)
