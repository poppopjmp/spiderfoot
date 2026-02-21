"""
Custom Report Templates — user-defined report generation framework.

Provides:
  - Template registry with versioning and categorization
  - Jinja2-based template rendering with scan data context
  - Built-in templates: executive summary, technical detail, compliance
  - Template variables and section definitions
  - Multi-format output: HTML, Markdown, JSON
  - Template sharing and import/export

v5.7.2
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.report_templates")


class TemplateFormat(str, Enum):
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"


class TemplateCategory(str, Enum):
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    COMPLIANCE = "compliance"
    VULNERABILITY = "vulnerability"
    ASSET_INVENTORY = "asset_inventory"
    CHANGE_REPORT = "change_report"
    CUSTOM = "custom"


@dataclass
class TemplateVariable:
    """A variable available in report templates."""
    name: str
    description: str = ""
    var_type: str = "string"     # string, number, boolean, list, dict
    default: Any = None
    required: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TemplateSection:
    """A section within a report template."""
    section_id: str = ""
    title: str = ""
    order: int = 0
    content_template: str = ""    # Jinja2 template string for this section
    condition: str = ""           # Optional: only render if condition is truthy
    subsections: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReportTemplate:
    """A report template definition."""
    template_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: str = TemplateCategory.CUSTOM.value
    output_format: str = TemplateFormat.HTML.value
    author: str = ""
    is_builtin: bool = False
    is_public: bool = False

    # Template content
    header_template: str = ""
    body_template: str = ""       # Main Jinja2 template
    footer_template: str = ""
    css_styles: str = ""          # For HTML output

    # Structure
    sections: list[dict] = field(default_factory=list)
    variables: list[dict] = field(default_factory=list)

    # Metadata
    tags: list[str] = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0
    usage_count: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["section_count"] = len(self.sections)
        d["variable_count"] = len(self.variables)
        return d


@dataclass
class RenderedReport:
    """A rendered report output."""
    report_id: str = ""
    template_id: str = ""
    template_name: str = ""
    scan_id: str = ""
    output_format: str = ""
    content: str = ""
    rendered_at: float = 0.0
    render_time_ms: float = 0.0
    word_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["content_length"] = len(self.content)
        return d


class ReportTemplateManager:
    """Manage custom report templates and rendering.

    Features:
      - Template CRUD with versioning
      - Jinja2-based rendering with scan data context
      - Built-in templates for common report types
      - Template export/import for sharing
      - Render history tracking
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._templates: dict[str, ReportTemplate] = {}
        self._render_history: list[RenderedReport] = []
        self._seed_builtin_templates()

    # ── Template CRUD ─────────────────────────────────────────────────

    def create_template(self, config: dict) -> ReportTemplate:
        """Create a new report template."""
        t = ReportTemplate(**{
            k: v for k, v in config.items()
            if k in ReportTemplate.__dataclass_fields__
        })
        if not t.template_id:
            t.template_id = str(uuid.uuid4())[:12]
        t.created_at = time.time()
        t.updated_at = time.time()

        self._templates[t.template_id] = t
        self._persist(t)
        _log.info("Template created: %s (%s)", t.name, t.template_id)
        return t

    def get_template(self, template_id: str) -> ReportTemplate | None:
        return self._templates.get(template_id)

    def list_templates(
        self,
        category: str | None = None,
        output_format: str | None = None,
        builtin_only: bool = False,
    ) -> list[ReportTemplate]:
        templates = list(self._templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        if output_format:
            templates = [t for t in templates if t.output_format == output_format]
        if builtin_only:
            templates = [t for t in templates if t.is_builtin]
        return sorted(templates, key=lambda t: t.name)

    def update_template(self, template_id: str, updates: dict) -> ReportTemplate | None:
        t = self._templates.get(template_id)
        if not t:
            return None
        if t.is_builtin:
            # Allow updating builtin copies but preserve original
            updates.pop("is_builtin", None)
        updates.pop("template_id", None)
        updates.pop("created_at", None)
        updates["updated_at"] = time.time()

        for k, v in updates.items():
            if hasattr(t, k):
                setattr(t, k, v)
        self._persist(t)
        return t

    def delete_template(self, template_id: str) -> bool:
        t = self._templates.get(template_id)
        if not t:
            return False
        if t.is_builtin:
            return False  # Cannot delete built-in templates
        del self._templates[template_id]
        return True

    def clone_template(self, template_id: str, new_name: str = "") -> ReportTemplate | None:
        """Clone an existing template for customization."""
        original = self._templates.get(template_id)
        if not original:
            return None

        clone_data = asdict(original)
        clone_data["template_id"] = str(uuid.uuid4())[:12]
        clone_data["name"] = new_name or f"{original.name} (Copy)"
        clone_data["is_builtin"] = False
        clone_data["created_at"] = time.time()
        clone_data["updated_at"] = time.time()
        clone_data["usage_count"] = 0

        clone = ReportTemplate(**clone_data)
        self._templates[clone.template_id] = clone
        self._persist(clone)
        return clone

    # ── Rendering ─────────────────────────────────────────────────────

    def render(
        self,
        template_id: str,
        scan_data: dict,
        variables: dict | None = None,
    ) -> RenderedReport:
        """Render a report from a template with scan data.

        Args:
            template_id: Template to use
            scan_data: Scan results/events data
            variables: Additional template variables

        Returns:
            RenderedReport with generated content
        """
        t = self._templates.get(template_id)
        if not t:
            return RenderedReport(
                report_id="error",
                content="Template not found",
                rendered_at=time.time(),
            )

        start = time.time()
        context = self._build_context(scan_data, variables or {})

        try:
            content = self._render_template(t, context)
        except Exception as e:
            _log.error("Template render error: %s", e)
            content = f"Render error: {e}"

        elapsed_ms = (time.time() - start) * 1000

        report = RenderedReport(
            report_id=str(uuid.uuid4())[:12],
            template_id=template_id,
            template_name=t.name,
            scan_id=scan_data.get("scan_id", ""),
            output_format=t.output_format,
            content=content,
            rendered_at=time.time(),
            render_time_ms=round(elapsed_ms, 2),
            word_count=len(content.split()),
            metadata={
                "template_version": t.version,
                "variables_provided": list((variables or {}).keys()),
            },
        )

        t.usage_count += 1
        self._render_history.append(report)
        if len(self._render_history) > 200:
            self._render_history = self._render_history[-200:]

        return report

    def get_render_history(self, limit: int = 20) -> list[RenderedReport]:
        return self._render_history[-limit:]

    # ── Export / Import ───────────────────────────────────────────────

    def export_template(self, template_id: str) -> dict | None:
        """Export a template as a portable dict."""
        t = self._templates.get(template_id)
        if not t:
            return None
        data = asdict(t)
        data["_export_version"] = "1.0"
        data["_exported_at"] = time.time()
        return data

    def import_template(self, data: dict) -> ReportTemplate:
        """Import a template from an exported dict."""
        data.pop("_export_version", None)
        data.pop("_exported_at", None)
        data["template_id"] = str(uuid.uuid4())[:12]
        data["is_builtin"] = False
        data["created_at"] = time.time()
        data["updated_at"] = time.time()
        data["usage_count"] = 0
        return self.create_template(data)

    def get_available_variables(self) -> list[dict]:
        """List all variables available in template context."""
        return [v.to_dict() for v in [
            TemplateVariable("scan_id", "Scan identifier", "string"),
            TemplateVariable("target", "Scan target", "string"),
            TemplateVariable("status", "Scan status", "string"),
            TemplateVariable("started", "Scan start time", "string"),
            TemplateVariable("ended", "Scan end time", "string"),
            TemplateVariable("duration", "Scan duration in seconds", "number"),
            TemplateVariable("total_events", "Total events found", "number"),
            TemplateVariable("event_types", "Count per event type", "dict"),
            TemplateVariable("events", "All scan events", "list"),
            TemplateVariable("modules_used", "Modules that ran", "list"),
            TemplateVariable("hosts_found", "Discovered hosts", "list"),
            TemplateVariable("emails_found", "Discovered emails", "list"),
            TemplateVariable("vulns_found", "Vulnerabilities found", "list"),
            TemplateVariable("ports_found", "Open ports found", "list"),
            TemplateVariable("malicious_count", "Malicious indicators", "number"),
            TemplateVariable("risk_score", "Overall risk score 0-100", "number"),
            TemplateVariable("report_date", "Report generation date", "string"),
            TemplateVariable("company_name", "Company name for branding", "string"),
            TemplateVariable("analyst_name", "Analyst name", "string"),
        ]]

    def get_categories(self) -> list[dict]:
        """List template categories."""
        descriptions = {
            TemplateCategory.EXECUTIVE: "High-level summary for stakeholders",
            TemplateCategory.TECHNICAL: "Detailed technical findings",
            TemplateCategory.COMPLIANCE: "Compliance-oriented assessment",
            TemplateCategory.VULNERABILITY: "Focused vulnerability report",
            TemplateCategory.ASSET_INVENTORY: "Asset discovery inventory",
            TemplateCategory.CHANGE_REPORT: "Attack surface change report",
            TemplateCategory.CUSTOM: "User-defined custom template",
        }
        return [
            {"id": c.value, "name": c.value.replace("_", " ").title(),
             "description": descriptions.get(c, "")}
            for c in TemplateCategory
        ]

    # ── Private helpers ───────────────────────────────────────────────

    def _build_context(self, scan_data: dict, variables: dict) -> dict:
        """Build the template rendering context."""
        events = scan_data.get("events", [])
        event_types: dict[str, int] = {}
        for e in events:
            et = e.get("type", "UNKNOWN")
            event_types[et] = event_types.get(et, 0) + 1

        ctx = {
            "scan_id": scan_data.get("scan_id", ""),
            "target": scan_data.get("target", ""),
            "status": scan_data.get("status", ""),
            "started": scan_data.get("started", ""),
            "ended": scan_data.get("ended", ""),
            "duration": scan_data.get("duration", 0),
            "total_events": len(events),
            "event_types": event_types,
            "events": events,
            "modules_used": scan_data.get("modules", []),
            "hosts_found": [
                e["data"] for e in events
                if e.get("type") in ("INTERNET_NAME", "IP_ADDRESS", "DOMAIN_NAME")
            ],
            "emails_found": [
                e["data"] for e in events if e.get("type") == "EMAILADDR"
            ],
            "vulns_found": [
                e for e in events
                if e.get("type", "").startswith("VULNERABILITY")
            ],
            "ports_found": [
                e["data"] for e in events if e.get("type") == "TCP_PORT_OPEN"
            ],
            "malicious_count": sum(
                1 for e in events if e.get("type", "").startswith("MALICIOUS")
            ),
            "risk_score": scan_data.get("risk_score", 0),
            "report_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        ctx.update(variables)
        return ctx

    def _render_template(self, template: ReportTemplate, context: dict) -> str:
        """Render a template with Jinja2 sandboxed environment or simple string formatting."""
        try:
            from jinja2.sandbox import SandboxedEnvironment
            env = SandboxedEnvironment(autoescape=True)
            tmpl = env.from_string(template.body_template)
            body = tmpl.render(**context)

            parts = []
            if template.header_template:
                h = env.from_string(template.header_template)
                parts.append(h.render(**context))
            parts.append(body)
            if template.footer_template:
                f = env.from_string(template.footer_template)
                parts.append(f.render(**context))

            return "\n\n".join(parts)
        except ImportError:
            # Fallback: simple Python format — only use safe string substitution
            try:
                from string import Template
                return Template(template.body_template).safe_substitute(context)
            except Exception:
                return template.body_template

    def _persist(self, t: ReportTemplate) -> None:
        if self._redis:
            try:
                self._redis.hset("sf:report_templates", t.template_id,
                                 json.dumps(asdict(t)))
            except Exception:
                pass

    def _seed_builtin_templates(self) -> None:
        """Create built-in report templates."""
        now = time.time()

        # Executive Summary
        self._templates["exec-summary"] = ReportTemplate(
            template_id="exec-summary",
            name="Executive Summary",
            description="High-level scan overview for stakeholders with risk assessment",
            version="1.0.0",
            category=TemplateCategory.EXECUTIVE.value,
            output_format=TemplateFormat.HTML.value,
            author="SpiderFoot",
            is_builtin=True,
            is_public=True,
            header_template=(
                "<h1>SpiderFoot Scan Report — Executive Summary</h1>\n"
                "<p><strong>Target:</strong> {{ target }}</p>\n"
                "<p><strong>Date:</strong> {{ report_date }}</p>"
            ),
            body_template=(
                "<h2>Overview</h2>\n"
                "<p>A reconnaissance scan of <strong>{{ target }}</strong> "
                "discovered <strong>{{ total_events }}</strong> findings "
                "across {{ event_types | length }} categories.</p>\n"
                "<h2>Key Metrics</h2>\n"
                "<ul>\n"
                "  <li>Hosts discovered: {{ hosts_found | length }}</li>\n"
                "  <li>Email addresses: {{ emails_found | length }}</li>\n"
                "  <li>Vulnerabilities: {{ vulns_found | length }}</li>\n"
                "  <li>Open ports: {{ ports_found | length }}</li>\n"
                "  <li>Malicious indicators: {{ malicious_count }}</li>\n"
                "</ul>\n"
                "<h2>Risk Assessment</h2>\n"
                "<p>Overall risk score: <strong>{{ risk_score }}/100</strong></p>"
            ),
            footer_template=(
                "<hr>\n<p><em>Generated by SpiderFoot — {{ report_date }}</em></p>"
            ),
            tags=["executive", "summary", "overview"],
            created_at=now,
            updated_at=now,
        )

        # Technical Detail
        self._templates["tech-detail"] = ReportTemplate(
            template_id="tech-detail",
            name="Technical Detail Report",
            description="Comprehensive technical findings with event-level detail",
            version="1.0.0",
            category=TemplateCategory.TECHNICAL.value,
            output_format=TemplateFormat.MARKDOWN.value,
            author="SpiderFoot",
            is_builtin=True,
            is_public=True,
            body_template=(
                "# Technical Scan Report\n\n"
                "**Target:** {{ target }}  \n"
                "**Scan ID:** {{ scan_id }}  \n"
                "**Status:** {{ status }}  \n"
                "**Duration:** {{ duration }}s  \n\n"
                "## Summary\n\n"
                "| Metric | Count |\n|--------|-------|\n"
                "| Total Events | {{ total_events }} |\n"
                "| Hosts | {{ hosts_found | length }} |\n"
                "| Emails | {{ emails_found | length }} |\n"
                "| Vulnerabilities | {{ vulns_found | length }} |\n"
                "| Open Ports | {{ ports_found | length }} |\n"
                "| Malicious | {{ malicious_count }} |\n\n"
                "## Event Type Breakdown\n\n"
                "{% for etype, count in event_types.items() %}"
                "- **{{ etype }}**: {{ count }}\n"
                "{% endfor %}\n\n"
                "## Modules Used\n\n"
                "{% for mod in modules_used %}- {{ mod }}\n{% endfor %}"
            ),
            tags=["technical", "detailed", "events"],
            created_at=now,
            updated_at=now,
        )

        # Vulnerability Report
        self._templates["vuln-report"] = ReportTemplate(
            template_id="vuln-report",
            name="Vulnerability Report",
            description="Focused vulnerability findings with severity breakdown",
            version="1.0.0",
            category=TemplateCategory.VULNERABILITY.value,
            output_format=TemplateFormat.HTML.value,
            author="SpiderFoot",
            is_builtin=True,
            is_public=True,
            header_template=(
                "<h1>Vulnerability Assessment Report</h1>\n"
                "<p>Target: {{ target }} | Date: {{ report_date }}</p>"
            ),
            body_template=(
                "<h2>Vulnerability Summary</h2>\n"
                "<p>Total vulnerabilities found: <strong>{{ vulns_found | length }}</strong></p>\n"
                "<h3>Findings</h3>\n"
                "{% if vulns_found %}"
                "<table><tr><th>Type</th><th>Data</th><th>Module</th></tr>\n"
                "{% for v in vulns_found %}"
                "<tr><td>{{ v.type }}</td><td>{{ v.data }}</td>"
                "<td>{{ v.module }}</td></tr>\n"
                "{% endfor %}</table>\n"
                "{% else %}<p>No vulnerabilities detected.</p>{% endif %}"
            ),
            tags=["vulnerability", "security", "cve"],
            created_at=now,
            updated_at=now,
        )

        # Asset Inventory
        self._templates["asset-inventory"] = ReportTemplate(
            template_id="asset-inventory",
            name="Asset Inventory Report",
            description="Discovered assets: hosts, IPs, domains, emails",
            version="1.0.0",
            category=TemplateCategory.ASSET_INVENTORY.value,
            output_format=TemplateFormat.MARKDOWN.value,
            author="SpiderFoot",
            is_builtin=True,
            is_public=True,
            body_template=(
                "# Asset Inventory — {{ target }}\n\n"
                "Generated: {{ report_date }}\n\n"
                "## Hosts ({{ hosts_found | length }})\n\n"
                "{% for h in hosts_found %}- {{ h }}\n{% endfor %}\n\n"
                "## Email Addresses ({{ emails_found | length }})\n\n"
                "{% for e in emails_found %}- {{ e }}\n{% endfor %}\n\n"
                "## Open Ports ({{ ports_found | length }})\n\n"
                "{% for p in ports_found %}- {{ p }}\n{% endfor %}"
            ),
            tags=["assets", "inventory", "discovery"],
            created_at=now,
            updated_at=now,
        )

        # Compliance Report
        self._templates["compliance"] = ReportTemplate(
            template_id="compliance",
            name="Compliance Assessment",
            description="Compliance-oriented report with control mapping",
            version="1.0.0",
            category=TemplateCategory.COMPLIANCE.value,
            output_format=TemplateFormat.HTML.value,
            author="SpiderFoot",
            is_builtin=True,
            is_public=True,
            body_template=(
                "<h1>Compliance Assessment — {{ target }}</h1>\n"
                "<p>Assessment Date: {{ report_date }}</p>\n"
                "<h2>Findings Summary</h2>\n"
                "<p>Total findings: {{ total_events }}</p>\n"
                "<p>Risk score: {{ risk_score }}/100</p>\n"
                "<h2>Security Controls Assessment</h2>\n"
                "<h3>Network Security</h3>\n"
                "<p>Open ports detected: {{ ports_found | length }}</p>\n"
                "<h3>Data Protection</h3>\n"
                "<p>Email addresses exposed: {{ emails_found | length }}</p>\n"
                "<h3>Vulnerability Management</h3>\n"
                "<p>Vulnerabilities found: {{ vulns_found | length }}</p>\n"
                "<h3>Threat Intelligence</h3>\n"
                "<p>Malicious indicators: {{ malicious_count }}</p>"
            ),
            tags=["compliance", "audit", "controls"],
            created_at=now,
            updated_at=now,
        )
