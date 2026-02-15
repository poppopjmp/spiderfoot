# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Scan Engine Configuration Schema & Loader
# =============================================================================
# Defines the YAML-based scan engine format (inspired by reNgine's approach)
# and provides a loader/validator for scan engine profiles.
#
# A scan engine is a reusable scan configuration that defines:
#   - Which modules to enable
#   - Module-specific settings (intensity, scope)
#   - Target scope rules (in-scope, out-of-scope)
#   - Time/rate limits
#   - Reporting preferences
# =============================================================================

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("spiderfoot.scan_engine")

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ScanIntensity(str, Enum):
    """How aggressively the scan probes targets."""
    PASSIVE = "passive"       # OSINT only, no direct target contact
    LIGHT = "light"           # Minimal direct contact (DNS, WHOIS)
    NORMAL = "normal"         # Standard active scanning
    AGGRESSIVE = "aggressive"  # Full active scan, brute-force enabled


class ScanScope(str, Enum):
    """How far the scan expands from the seed target."""
    TARGET_ONLY = "target_only"       # Only the exact target
    SUBDOMAINS = "subdomains"         # Target + subdomains
    AFFILIATES = "affiliates"         # Target + affiliates + subdomains
    FULL = "full"                     # Everything reachable


class ReportFormat(str, Enum):
    """Report output format."""
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    STIX = "stix"
    SARIF = "sarif"


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ScopeConfig:
    """Target scope configuration."""
    scope: ScanScope = ScanScope.SUBDOMAINS
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    max_depth: int = 3
    follow_redirects: bool = True
    include_ipv6: bool = False


@dataclass
class RateLimitConfig:
    """Rate limiting and timing configuration."""
    max_threads: int = 10
    request_delay_ms: int = 0
    max_requests_per_second: float = 0  # 0 = unlimited
    scan_timeout_minutes: int = 0       # 0 = unlimited
    module_timeout_seconds: int = 300
    dns_timeout_seconds: int = 10
    http_timeout_seconds: int = 15


@dataclass
class ModuleConfig:
    """Configuration for a specific module."""
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1 (highest) to 10 (lowest)


@dataclass
class ReportConfig:
    """Report generation configuration."""
    formats: list[ReportFormat] = field(
        default_factory=lambda: [ReportFormat.HTML]
    )
    auto_generate: bool = False
    include_raw_data: bool = False
    include_executive_summary: bool = True
    include_charts: bool = True
    llm_enhanced: bool = False
    template: str = "default"


@dataclass
class NotificationConfig:
    """Alert/notification configuration."""
    enabled: bool = False
    on_complete: bool = True
    on_high_severity: bool = True
    channels: list[str] = field(default_factory=list)  # webhook, email, slack


@dataclass
class ScanEngine:
    """Complete scan engine configuration.

    This is the top-level object that represents a scan engine profile.
    Scan engines can be stored as YAML files and loaded via the ScanEngineLoader.
    """
    # Identity
    name: str = "Default"
    description: str = ""
    version: str = "1.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)

    # Scan behavior
    intensity: ScanIntensity = ScanIntensity.NORMAL
    scope: ScopeConfig = field(default_factory=ScopeConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Module selection
    modules: dict[str, ModuleConfig] = field(default_factory=dict)
    module_groups: list[str] = field(default_factory=list)  # e.g., ["dns", "web", "email"]
    exclude_modules: list[str] = field(default_factory=list)

    # Output
    report: ReportConfig = field(default_factory=ReportConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_enabled_modules(self) -> list[str]:
        """Return list of explicitly enabled module names."""
        return [
            name for name, cfg in self.modules.items()
            if cfg.enabled
        ]

    def get_module_options(self, module_name: str) -> dict[str, Any]:
        """Get options for a specific module."""
        mod = self.modules.get(module_name)
        return mod.options if mod else {}

    def to_sf_config(self, base_config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Convert to SpiderFoot's internal config format.

        Merges engine settings with the base SpiderFoot config,
        applying module options, threading, and scope settings.
        """
        config = dict(base_config or {})

        # Threading / rate limits
        config["_maxthreads"] = self.rate_limit.max_threads
        config["_fetchtimeout"] = self.rate_limit.http_timeout_seconds
        config["_dnstimeout"] = self.rate_limit.dns_timeout_seconds

        if self.rate_limit.request_delay_ms > 0:
            config["_delay"] = self.rate_limit.request_delay_ms

        # Scope
        config["_internettlds_wildcard"] = (
            self.scope.scope in (ScanScope.AFFILIATES, ScanScope.FULL)
        )

        # Per-module options
        for mod_name, mod_cfg in self.modules.items():
            if mod_cfg.options:
                for key, value in mod_cfg.options.items():
                    config[f"{mod_name}:{key}"] = value

        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (for YAML/JSON export)."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "intensity": self.intensity.value,
            "scope": {
                "scope": self.scope.scope.value,
                "include_patterns": self.scope.include_patterns,
                "exclude_patterns": self.scope.exclude_patterns,
                "max_depth": self.scope.max_depth,
                "follow_redirects": self.scope.follow_redirects,
                "include_ipv6": self.scope.include_ipv6,
            },
            "rate_limit": {
                "max_threads": self.rate_limit.max_threads,
                "request_delay_ms": self.rate_limit.request_delay_ms,
                "max_requests_per_second": self.rate_limit.max_requests_per_second,
                "scan_timeout_minutes": self.rate_limit.scan_timeout_minutes,
                "module_timeout_seconds": self.rate_limit.module_timeout_seconds,
                "dns_timeout_seconds": self.rate_limit.dns_timeout_seconds,
                "http_timeout_seconds": self.rate_limit.http_timeout_seconds,
            },
            "modules": {
                name: {
                    "enabled": cfg.enabled,
                    "options": cfg.options,
                    "priority": cfg.priority,
                }
                for name, cfg in self.modules.items()
            },
            "module_groups": self.module_groups,
            "exclude_modules": self.exclude_modules,
            "report": {
                "formats": [f.value for f in self.report.formats],
                "auto_generate": self.report.auto_generate,
                "include_raw_data": self.report.include_raw_data,
                "include_executive_summary": self.report.include_executive_summary,
                "include_charts": self.report.include_charts,
                "llm_enhanced": self.report.llm_enhanced,
                "template": self.report.template,
            },
            "notification": {
                "enabled": self.notification.enabled,
                "on_complete": self.notification.on_complete,
                "on_high_severity": self.notification.on_high_severity,
                "channels": self.notification.channels,
            },
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Loader / Validator
# ---------------------------------------------------------------------------


class ScanEngineError(Exception):
    """Raised when a scan engine configuration is invalid."""


class ScanEngineLoader:
    """Load and validate scan engine YAML profiles.

    Usage::

        loader = ScanEngineLoader("config/engines/")
        engine = loader.load("passive_recon")
        modules = engine.get_enabled_modules()
        sf_config = engine.to_sf_config(base_config)
    """

    DEFAULT_DIR = "config/engines"

    def __init__(self, engines_dir: str | Path | None = None) -> None:
        self.engines_dir = Path(engines_dir or self.DEFAULT_DIR)
        self._cache: dict[str, ScanEngine] = {}

    def load(self, name: str) -> ScanEngine:
        """Load a scan engine by name from the engines directory.

        The name corresponds to the YAML filename (without extension).
        """
        if name in self._cache:
            return self._cache[name]

        path = self.engines_dir / f"{name}.yaml"
        if not path.exists():
            path = self.engines_dir / f"{name}.yml"
        if not path.exists():
            raise ScanEngineError(f"Scan engine '{name}' not found in {self.engines_dir}")

        return self.load_file(path)

    def load_file(self, path: str | Path) -> ScanEngine:
        """Load a scan engine from a specific YAML file."""
        path = Path(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ScanEngineError(f"Invalid YAML in {path}: {e}")

        if not isinstance(data, dict):
            raise ScanEngineError(f"Expected dict in {path}, got {type(data).__name__}")

        engine = self._parse_engine(data)
        self._cache[engine.name] = engine
        log.info("Loaded scan engine '%s' from %s", engine.name, path)
        return engine

    def load_from_dict(self, data: dict[str, Any]) -> ScanEngine:
        """Load a scan engine from a dictionary (e.g. from API request)."""
        return self._parse_engine(data)

    def list_engines(self) -> list[dict[str, str]]:
        """List available scan engines in the engines directory."""
        engines = []
        if not self.engines_dir.exists():
            return engines

        for path in sorted(self.engines_dir.glob("*.y*ml")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    engines.append({
                        "name": data.get("name", path.stem),
                        "description": data.get("description", ""),
                        "file": path.name,
                        "intensity": data.get("intensity", "normal"),
                        "tags": data.get("tags", []),
                    })
            except Exception:
                log.warning("Skipping invalid engine file: %s", path)

        return engines

    def save(self, engine: ScanEngine, name: str | None = None) -> Path:
        """Save a scan engine to a YAML file."""
        fname = name or engine.name.lower().replace(" ", "_")
        self.engines_dir.mkdir(parents=True, exist_ok=True)
        path = self.engines_dir / f"{fname}.yaml"

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                engine.to_dict(),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        log.info("Saved scan engine '%s' to %s", engine.name, path)
        return path

    # -----------------------------------------------------------------
    # Parsing
    # -----------------------------------------------------------------

    def _parse_engine(self, data: dict[str, Any]) -> ScanEngine:
        """Parse a raw dict into a ScanEngine dataclass."""
        engine = ScanEngine(
            name=data.get("name", "Unnamed"),
            description=data.get("description", ""),
            version=str(data.get("version", "1.0")),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            intensity=ScanIntensity(data.get("intensity", "normal")),
            module_groups=data.get("module_groups", []),
            exclude_modules=data.get("exclude_modules", []),
            metadata=data.get("metadata", {}),
        )

        # Scope
        scope_data = data.get("scope", {})
        if isinstance(scope_data, dict):
            engine.scope = ScopeConfig(
                scope=ScanScope(scope_data.get("scope", "subdomains")),
                include_patterns=scope_data.get("include_patterns", []),
                exclude_patterns=scope_data.get("exclude_patterns", []),
                max_depth=scope_data.get("max_depth", 3),
                follow_redirects=scope_data.get("follow_redirects", True),
                include_ipv6=scope_data.get("include_ipv6", False),
            )

        # Rate limits
        rl_data = data.get("rate_limit", {})
        if isinstance(rl_data, dict):
            engine.rate_limit = RateLimitConfig(
                max_threads=rl_data.get("max_threads", 10),
                request_delay_ms=rl_data.get("request_delay_ms", 0),
                max_requests_per_second=rl_data.get("max_requests_per_second", 0),
                scan_timeout_minutes=rl_data.get("scan_timeout_minutes", 0),
                module_timeout_seconds=rl_data.get("module_timeout_seconds", 300),
                dns_timeout_seconds=rl_data.get("dns_timeout_seconds", 10),
                http_timeout_seconds=rl_data.get("http_timeout_seconds", 15),
            )

        # Modules
        modules_data = data.get("modules", {})
        if isinstance(modules_data, dict):
            for mod_name, mod_data in modules_data.items():
                if isinstance(mod_data, dict):
                    engine.modules[mod_name] = ModuleConfig(
                        enabled=mod_data.get("enabled", True),
                        options=mod_data.get("options", {}),
                        priority=mod_data.get("priority", 5),
                    )
                elif isinstance(mod_data, bool):
                    engine.modules[mod_name] = ModuleConfig(enabled=mod_data)
        elif isinstance(modules_data, list):
            for mod_name in modules_data:
                engine.modules[str(mod_name)] = ModuleConfig(enabled=True)

        # Report
        report_data = data.get("report", {})
        if isinstance(report_data, dict):
            formats = []
            for fmt in report_data.get("formats", ["html"]):
                try:
                    formats.append(ReportFormat(fmt))
                except ValueError:
                    log.warning("Unknown report format: %s", fmt)
            engine.report = ReportConfig(
                formats=formats or [ReportFormat.HTML],
                auto_generate=report_data.get("auto_generate", False),
                include_raw_data=report_data.get("include_raw_data", False),
                include_executive_summary=report_data.get("include_executive_summary", True),
                include_charts=report_data.get("include_charts", True),
                llm_enhanced=report_data.get("llm_enhanced", False),
                template=report_data.get("template", "default"),
            )

        # Notification
        notif_data = data.get("notification", {})
        if isinstance(notif_data, dict):
            engine.notification = NotificationConfig(
                enabled=notif_data.get("enabled", False),
                on_complete=notif_data.get("on_complete", True),
                on_high_severity=notif_data.get("on_high_severity", True),
                channels=notif_data.get("channels", []),
            )

        return engine
