#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         scan_profile
# Purpose:      Scan templates and profiles for SpiderFoot.
#               Predefined scan configurations for common use cases,
#               supporting YAML-based profile definitions with module
#               selection, option overrides, and composable presets.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Scan Templates and Profiles

Provides reusable scan configurations::

    from spiderfoot.scan.scan_profile import ProfileManager

    pm = ProfileManager()
    profile = pm.get("quick-recon")
    modules = profile.resolve_modules(all_modules)
    opts = profile.apply_overrides(global_opts)

Built-in profiles:
    - quick-recon: Fast passive scan, no API keys needed
    - full-footprint: Complete active footprinting
    - passive-only: Zero direct target interaction
    - vuln-assessment: Focus on vulnerabilities
    - social-media: Social media presence discovery
    - dark-web: Tor-based deep/dark web scan
    - infrastructure: DNS, ports, hosting analysis
    - api-powered: All modules requiring API keys
    - minimal: Bare minimum modules
    - custom: User-defined template
"""

import copy
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.scan_profile")


class ProfileCategory(str, Enum):
    """Profile categories."""
    RECONNAISSANCE = "reconnaissance"
    VULNERABILITY = "vulnerability"
    SOCIAL = "social"
    INFRASTRUCTURE = "infrastructure"
    DARKWEB = "dark_web"
    CUSTOM = "custom"


@dataclass
class ScanProfile:
    """A reusable scan configuration template."""
    name: str
    display_name: str
    description: str = ""
    category: ProfileCategory = ProfileCategory.RECONNAISSANCE
    version: str = "1.0"

    # Module selection criteria
    use_cases: list[str] = field(default_factory=list)
    include_flags: list[str] = field(default_factory=list)
    exclude_flags: list[str] = field(default_factory=list)
    include_modules: list[str] = field(default_factory=list)
    exclude_modules: list[str] = field(default_factory=list)
    include_categories: list[str] = field(default_factory=list)
    required_event_types: list[str] = field(default_factory=list)

    # Option overrides
    option_overrides: dict[str, Any] = field(default_factory=dict)
    module_options: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Execution settings
    max_threads: int = 0       # 0 = use global default
    timeout_minutes: int = 0   # 0 = no limit
    max_depth: int = 0         # 0 = no limit

    # Metadata
    author: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def resolve_modules(self, all_modules: dict[str, dict]) -> list[str]:
        """Resolve the set of modules to enable based on criteria.

        Args:
            all_modules: Dict of module_name -> module_info where
                module_info has keys: meta, watchedEvents, producedEvents.

        Returns:
            Sorted list of module names to enable.
        """
        selected: set[str] = set()

        # Always exclude deprecated modules unless explicitly included
        effective_exclude_flags = set(self.exclude_flags) | {"deprecated"}

        for mod_name, mod_info in all_modules.items():
            meta = mod_info.get("meta", {})
            flags = set(meta.get("flags", []))
            cases = set(meta.get("useCases", []))
            cats = set(meta.get("categories", []))
            produced = set(mod_info.get("producedEvents", [])
                           if callable(mod_info.get("producedEvents"))
                           is False
                           else mod_info.get("provides", []))

            # Start with use_case matching
            if self.use_cases:
                if not cases.intersection(self.use_cases):
                    continue

            # Include by flags
            if self.include_flags:
                if not flags.intersection(self.include_flags):
                    continue

            # Include by categories
            if self.include_categories:
                if not cats.intersection(self.include_categories):
                    continue

            selected.add(mod_name)

        # Exclude by flags (always excludes deprecated)
        to_remove = set()
        for mod_name in selected:
            meta = all_modules[mod_name].get("meta", {})
            flags = set(meta.get("flags", []))
            if flags.intersection(effective_exclude_flags):
                to_remove.add(mod_name)
        selected -= to_remove

        # Exclude specific modules
        selected -= set(self.exclude_modules)

        # Include specific modules (always added)
        selected.update(self.include_modules)

        # Always include core storage module (sfp__stor_db only, skip deprecated stores)
        for mod_name in all_modules:
            if mod_name == "sfp__stor_db":
                selected.add(mod_name)
                break
        return sorted(selected)

    def apply_overrides(self, global_opts: dict) -> dict:
        """Apply profile option overrides to global config.

        Returns a new dict (does not mutate input).
        """
        opts = copy.deepcopy(global_opts)

        # Global option overrides
        for key, value in self.option_overrides.items():
            opts[key] = value

        # Thread override
        if self.max_threads > 0:
            opts["_maxthreads"] = self.max_threads

        # Module-specific option overrides
        modules_dict = opts.get("__modules__", {})
        for mod_name, mod_opts in self.module_options.items():
            if mod_name in modules_dict:
                mod_config = modules_dict[mod_name].get("opts", {})
                mod_config.update(mod_opts)

        return opts

    def to_dict(self) -> dict:
        """Serialize to dict for JSON/YAML export."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "use_cases": self.use_cases,
            "include_flags": self.include_flags,
            "exclude_flags": self.exclude_flags,
            "include_modules": self.include_modules,
            "exclude_modules": self.exclude_modules,
            "include_categories": self.include_categories,
            "required_event_types": self.required_event_types,
            "option_overrides": self.option_overrides,
            "module_options": self.module_options,
            "max_threads": self.max_threads,
            "timeout_minutes": self.timeout_minutes,
            "max_depth": self.max_depth,
            "author": self.author,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScanProfile":
        """Deserialize from dict."""
        cat = data.get("category", "custom")
        try:
            category = ProfileCategory(cat)
        except ValueError:
            category = ProfileCategory.CUSTOM

        return cls(
            name=data.get("name", "unnamed"),
            display_name=data.get("display_name",
                                  data.get("name", "Unnamed")),
            description=data.get("description", ""),
            category=category,
            version=data.get("version", "1.0"),
            use_cases=data.get("use_cases", []),
            include_flags=data.get("include_flags", []),
            exclude_flags=data.get("exclude_flags", []),
            include_modules=data.get("include_modules", []),
            exclude_modules=data.get("exclude_modules", []),
            include_categories=data.get("include_categories", []),
            required_event_types=data.get("required_event_types", []),
            option_overrides=data.get("option_overrides", {}),
            module_options=data.get("module_options", {}),
            max_threads=data.get("max_threads", 0),
            timeout_minutes=data.get("timeout_minutes", 0),
            max_depth=data.get("max_depth", 0),
            author=data.get("author", ""),
            tags=data.get("tags", []),
        )


# ---------------------------------------------------------------------------
# Profile Manager
# ---------------------------------------------------------------------------


class ProfileManager:
    """Manages scan profiles — built-in and user-defined.

    Profiles can be loaded from JSON files, registered programmatically,
    or used via the built-in presets.
    """

    def __init__(self) -> None:
        """Initialize the ProfileManager."""
        self._profiles: dict[str, ScanProfile] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Register built-in scan profiles."""

        self.register(ScanProfile(
            name="quick-recon",
            display_name="Quick Reconnaissance",
            description=(
                "Fast passive scan using only modules that don't "
                "require API keys and are not slow or invasive."
            ),
            category=ProfileCategory.RECONNAISSANCE,
            use_cases=["Passive"],
            exclude_flags=["apikey", "slow", "invasive", "tool", "tor"],
            max_threads=5,
            timeout_minutes=30,
            tags=["quick", "passive", "no-api"],
        ))

        self.register(ScanProfile(
            name="full-footprint",
            display_name="Full Footprint",
            description=(
                "Comprehensive active footprinting using all available "
                "modules including invasive ones. Excludes Tor modules."
            ),
            category=ProfileCategory.RECONNAISSANCE,
            use_cases=["Footprint"],
            exclude_flags=["tor", "errorprone"],
            max_threads=3,
            tags=["comprehensive", "active"],
        ))

        self.register(ScanProfile(
            name="passive-only",
            display_name="Passive Only",
            description=(
                "Strictly passive modules — no direct interaction with "
                "the target. Safe for stealth reconnaissance."
            ),
            category=ProfileCategory.RECONNAISSANCE,
            use_cases=["Passive"],
            exclude_flags=["invasive", "tool"],
            tags=["passive", "stealth", "safe"],
        ))

        self.register(ScanProfile(
            name="vuln-assessment",
            display_name="Vulnerability Assessment",
            description=(
                "Focus on discovering vulnerabilities, exposed services, "
                "and security issues."
            ),
            category=ProfileCategory.VULNERABILITY,
            required_event_types=[
                "VULNERABILITY_CVE_CRITICAL",
                "VULNERABILITY_CVE_HIGH",
                "VULNERABILITY_CVE_MEDIUM",
                "VULNERABILITY_CVE_LOW",
                "VULNERABILITY_GENERAL",
                "VULNERABILITY_DISCLOSURE",
                "TCP_PORT_OPEN",
                "TCP_PORT_OPEN_BANNER",
            ],
            include_categories=[
                "Crawling and Scanning",
                "Reputation Systems",
            ],
            exclude_flags=["tor", "errorprone"],
            max_threads=3,
            tags=["security", "vulnerability", "assessment"],
        ))

        self.register(ScanProfile(
            name="social-media",
            display_name="Social Media Discovery",
            description=(
                "Discover social media profiles, usernames, and "
                "public presence across platforms."
            ),
            category=ProfileCategory.SOCIAL,
            include_categories=["Social Media", "Secondary Networks"],
            exclude_flags=["tor", "invasive"],
            tags=["social", "osint", "profiles"],
        ))

        self.register(ScanProfile(
            name="dark-web",
            display_name="Dark Web Scan",
            description=(
                "Search dark web / Tor hidden services for mentions "
                "of the target. Requires Tor proxy configuration."
            ),
            category=ProfileCategory.DARKWEB,
            include_flags=["tor"],
            option_overrides={
                "_socks1type": "TOR",
                "_socks2addr": "127.0.0.1",
                "_socks3port": "9050",
            },
            max_threads=2,
            tags=["darkweb", "tor", "deep-web"],
        ))

        self.register(ScanProfile(
            name="infrastructure",
            display_name="Infrastructure Analysis",
            description=(
                "Focus on DNS, ports, hosting, SSL certificates, "
                "and network infrastructure mapping."
            ),
            category=ProfileCategory.INFRASTRUCTURE,
            include_categories=["DNS", "Passive DNS"],
            required_event_types=[
                "IP_ADDRESS",
                "INTERNET_NAME",
                "TCP_PORT_OPEN",
                "NETBLOCK_OWNER",
                "BGP_AS_OWNER",
                "SSL_CERTIFICATE_ISSUED",
                "PROVIDER_DNS",
                "PROVIDER_HOSTING",
            ],
            exclude_flags=["tor", "errorprone"],
            tags=["infrastructure", "dns", "network"],
        ))

        self.register(ScanProfile(
            name="api-powered",
            display_name="API-Powered Scan",
            description=(
                "Only modules requiring API keys — comprehensive "
                "results from premium data sources."
            ),
            category=ProfileCategory.RECONNAISSANCE,
            include_flags=["apikey"],
            exclude_flags=["tor", "errorprone"],
            tags=["api", "premium", "comprehensive"],
        ))

        self.register(ScanProfile(
            name="minimal",
            display_name="Minimal Scan",
            description=(
                "Bare minimum modules for quick validation. "
                "DNS resolution and basic web checks only."
            ),
            category=ProfileCategory.RECONNAISSANCE,
            include_modules=[
                "sfp_dnsresolve",
                "sfp_spider",
                "sfp_webframework",
            ],
            max_threads=2,
            timeout_minutes=10,
            tags=["minimal", "quick", "test"],
        ))

        self.register(ScanProfile(
            name="investigate",
            display_name="Investigation Mode",
            description=(
                "Targeted investigation — all Investigate-tagged "
                "modules for deep analysis of specific entities."
            ),
            category=ProfileCategory.RECONNAISSANCE,
            use_cases=["Investigate"],
            exclude_flags=["errorprone"],
            tags=["investigate", "targeted", "deep"],
        ))

        self.register(ScanProfile(
            name="tools-only",
            display_name="External Tools Only",
            description=(
                "Run all external recon tools against the target. "
                "Includes both pre-installed tools (nmap, nuclei, "
                "testssl.sh, whatweb, dnstwist, etc.) and active "
                "scan tools (httpx, subfinder, amass, dnsx, naabu, "
                "gobuster, katana, nikto, gitleaks, and more). "
                "Requires the active scan worker container."
            ),
            category=ProfileCategory.RECONNAISSANCE,
            include_flags=["tool"],
            include_modules=[
                # ── Pre-installed base-image tools ──
                "sfp_tool_cmseek",
                "sfp_tool_dnstwist",
                "sfp_tool_gobuster",
                "sfp_tool_nbtscan",
                "sfp_tool_onesixtyone",
                "sfp_tool_phoneinfoga",
                "sfp_tool_retirejs",
                "sfp_tool_snallygaster",
                "sfp_tool_testsslsh",
                "sfp_tool_trufflehog",
                "sfp_tool_wafw00f",
                "sfp_tool_wappalyzer",
                "sfp_tool_whatweb",
                # ── Pre-existing modules (no tool_ prefix) ──
                "sfp_httpx",
                "sfp_nuclei",
                "sfp_subfinder",
                # ── Active worker DNS & subdomain tools ──
                "sfp_tool_amass",
                "sfp_tool_dnsx",
                "sfp_tool_massdns",
                # ── Active worker URL / crawling tools ──
                "sfp_tool_gau",
                "sfp_tool_waybackurls",
                "sfp_tool_gospider",
                "sfp_tool_hakrawler",
                "sfp_tool_katana",
                # ── Active worker fuzzing / parameter tools ──
                "sfp_tool_ffuf",
                "sfp_tool_arjun",
                # ── Active worker screenshots ──
                "sfp_tool_gowitness",
                # ── Active worker vulnerability scanning ──
                "sfp_tool_nikto",
                "sfp_tool_dalfox",
                # ── Active worker secret/JS analysis ──
                "sfp_tool_gitleaks",
                "sfp_tool_linkfinder",
                # ── Active worker port scanning ──
                "sfp_tool_naabu",
                "sfp_tool_masscan",
                # ── Active worker SSL/TLS ──
                "sfp_tool_tlsx",
                "sfp_tool_sslyze",
                "sfp_tool_sslscan",
                # ── Core helpers (DNS resolution to feed tools) ──
                "sfp_dnsresolve",
                "sfp_spider",
            ],
            exclude_flags=["errorprone"],
            max_threads=4,
            timeout_minutes=120,
            tags=["tools", "active", "recon", "external", "comprehensive"],
        ))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, profile: ScanProfile) -> None:
        """Register or update a profile."""
        self._profiles[profile.name] = profile

    def get(self, name: str) -> ScanProfile | None:
        """Get a profile by name."""
        return self._profiles.get(name)

    def delete(self, name: str) -> bool:
        """Delete a profile. Returns True if found."""
        return self._profiles.pop(name, None) is not None

    def list_profiles(self, category: ProfileCategory | None = None
                      ) -> list[ScanProfile]:
        """List all profiles, optionally filtered by category."""
        profiles = self._profiles.values()
        if category:
            profiles = [p for p in profiles
                        if p.category == category]
        return sorted(profiles, key=lambda p: p.name)

    def list_names(self) -> list[str]:
        """List all profile names."""
        return sorted(self._profiles.keys())

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def save_to_file(self, name: str, filepath: str) -> bool:
        """Save a profile to a JSON file."""
        profile = self.get(name)
        if not profile:
            return False

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, indent=2)
            return True
        except (TypeError, OSError) as e:
            log.error("Failed to save profile %s: %s", name, e)
            return False

    def load_from_file(self, filepath: str) -> ScanProfile | None:
        """Load a profile from a JSON file."""
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            profile = ScanProfile.from_dict(data)
            self.register(profile)
            return profile
        except (json.JSONDecodeError, OSError, ValueError) as e:
            log.error("Failed to load profile from %s: %s",
                      filepath, e)
            return None

    def load_directory(self, dir_path: str) -> int:
        """Load all .json profile files from a directory.

        Returns number of profiles loaded.
        """
        if not os.path.isdir(dir_path):
            return 0

        count = 0
        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                filepath = os.path.join(dir_path, filename)
                if self.load_from_file(filepath):
                    count += 1

        log.info("Loaded %d profiles from %s", count, dir_path)
        return count

    def export_all(self) -> list[dict]:
        """Export all profiles as dicts."""
        return [p.to_dict() for p in self.list_profiles()]


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    """Get or create the global ProfileManager singleton."""
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
