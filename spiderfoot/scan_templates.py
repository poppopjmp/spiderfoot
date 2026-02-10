"""Scan Templates for SpiderFoot.

Pre-configured scan template library with built-in profiles
for common OSINT use cases. Templates define which modules,
event types, and policies to use for a scan.
"""

import copy
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.scan_templates")


class TemplateCategory(Enum):
    """Template categories."""
    RECONNAISSANCE = "reconnaissance"
    VULNERABILITY = "vulnerability"
    THREAT_INTEL = "threat_intel"
    IDENTITY = "identity"
    INFRASTRUCTURE = "infrastructure"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


@dataclass
class ScanTemplate:
    """A pre-configured scan template."""
    name: str
    description: str = ""
    category: TemplateCategory = TemplateCategory.CUSTOM
    modules: set[str] = field(default_factory=set)
    excluded_modules: set[str] = field(default_factory=set)
    event_types: set[str] = field(default_factory=set)
    options: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)
    author: str = ""
    version: str = "1.0.0"
    created_at: float = field(default_factory=time.time)

    def add_modules(self, *modules: str) -> "ScanTemplate":
        self.modules.update(modules)
        return self

    def exclude_modules(self, *modules: str) -> "ScanTemplate":
        self.excluded_modules.update(modules)
        return self

    def add_event_types(self, *types: str) -> "ScanTemplate":
        self.event_types.update(types)
        return self

    def set_option(self, key: str, value: Any) -> "ScanTemplate":
        self.options[key] = value
        return self

    def get_effective_modules(self) -> set[str]:
        """Get modules minus exclusions."""
        return self.modules - self.excluded_modules

    def clone(self, new_name: str) -> "ScanTemplate":
        """Create a deep copy with a new name."""
        cloned = copy.deepcopy(self)
        cloned.name = new_name
        cloned.created_at = time.time()
        return cloned

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "modules": sorted(self.modules),
            "excluded_modules": sorted(self.excluded_modules),
            "event_types": sorted(self.event_types),
            "options": self.options,
            "tags": sorted(self.tags),
            "author": self.author,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScanTemplate":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            category=TemplateCategory(data.get("category", "custom")),
            modules=set(data.get("modules", [])),
            excluded_modules=set(data.get("excluded_modules", [])),
            event_types=set(data.get("event_types", [])),
            options=data.get("options", {}),
            tags=set(data.get("tags", [])),
            author=data.get("author", ""),
            version=data.get("version", "1.0.0"),
        )


# Built-in templates
def _passive_recon() -> ScanTemplate:
    return ScanTemplate(
        name="passive_recon",
        description="Passive reconnaissance using public sources only",
        category=TemplateCategory.RECONNAISSANCE,
        modules={
            "sfp_dnsresolve", "sfp_dnsbrute", "sfp_whois",
            "sfp_shodan", "sfp_certspotter", "sfp_crt",
            "sfp_hackertarget", "sfp_securitytrails",
        },
        event_types={"IP_ADDRESS", "DOMAIN_NAME", "INTERNET_NAME", "EMAILADDR"},
        tags={"passive", "safe", "external"},
        author="spiderfoot",
    )


def _full_scan() -> ScanTemplate:
    return ScanTemplate(
        name="full_scan",
        description="Comprehensive scan using all available modules",
        category=TemplateCategory.RECONNAISSANCE,
        tags={"comprehensive", "all-modules"},
        author="spiderfoot",
        options={"max_depth": 5},
    )


def _vulnerability_scan() -> ScanTemplate:
    return ScanTemplate(
        name="vulnerability_scan",
        description="Focus on vulnerability discovery",
        category=TemplateCategory.VULNERABILITY,
        modules={
            "sfp_shodan", "sfp_censys", "sfp_vulners",
            "sfp_xforce", "sfp_securitytrails",
        },
        event_types={
            "VULNERABILITY_CVE_CRITICAL", "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_MEDIUM", "VULNERABILITY_CVE_LOW",
            "TCP_PORT_OPEN", "TCP_PORT_OPEN_BANNER",
        },
        tags={"vulnerability", "security"},
        author="spiderfoot",
    )


def _threat_intel() -> ScanTemplate:
    return ScanTemplate(
        name="threat_intel",
        description="Threat intelligence gathering",
        category=TemplateCategory.THREAT_INTEL,
        modules={
            "sfp_virustotal", "sfp_abuseipdb", "sfp_alienvault",
            "sfp_threatcrowd", "sfp_urlhaus",
        },
        event_types={
            "MALICIOUS_IPADDR", "MALICIOUS_INTERNET_NAME",
            "BLACKLISTED_IPADDR", "MALICIOUS_EMAILADDR",
        },
        tags={"threat", "intel", "reputation"},
        author="spiderfoot",
    )


def _identity_search() -> ScanTemplate:
    return ScanTemplate(
        name="identity_search",
        description="Search for identity information (emails, names, accounts)",
        category=TemplateCategory.IDENTITY,
        modules={
            "sfp_haveibeenpwned", "sfp_hunter", "sfp_emailformat",
            "sfp_accounts", "sfp_social",
        },
        event_types={
            "EMAILADDR", "EMAILADDR_COMPROMISED", "HUMAN_NAME",
            "USERNAME", "SOCIAL_MEDIA", "ACCOUNT_EXTERNAL_OWNED",
        },
        tags={"identity", "email", "social"},
        author="spiderfoot",
    )


class TemplateRegistry:
    """Registry of scan templates.

    Usage:
        registry = TemplateRegistry()
        template = registry.get("passive_recon")
        my_scan = template.clone("my_custom_scan")
    """

    def __init__(self, load_defaults: bool = True) -> None:
        self._templates: dict[str, ScanTemplate] = {}
        if load_defaults:
            self._load_defaults()

    def _load_defaults(self) -> None:
        for factory in [_passive_recon, _full_scan, _vulnerability_scan, _threat_intel, _identity_search]:
            t = factory()
            self._templates[t.name] = t

    def register(self, template: ScanTemplate) -> "TemplateRegistry":
        self._templates[template.name] = template
        return self

    def unregister(self, name: str) -> bool:
        return self._templates.pop(name, None) is not None

    def get(self, name: str) -> Optional[ScanTemplate]:
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        return sorted(self._templates.keys())

    def get_by_category(self, category: TemplateCategory) -> list[ScanTemplate]:
        return [t for t in self._templates.values() if t.category == category]

    def search(self, query: str) -> list[ScanTemplate]:
        q = query.lower()
        return [
            t for t in self._templates.values()
            if q in t.name.lower() or q in t.description.lower()
            or any(q in tag for tag in t.tags)
        ]

    def summary(self) -> dict:
        cats: dict[str, int] = {}
        for t in self._templates.values():
            c = t.category.value
            cats[c] = cats.get(c, 0) + 1
        return {
            "total": len(self._templates),
            "categories": cats,
            "templates": self.list_templates(),
        }

    def to_dict(self) -> dict:
        return {
            name: t.to_dict()
            for name, t in sorted(self._templates.items())
        }
