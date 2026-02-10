"""Event Type Taxonomy for SpiderFoot.

Hierarchical event type classification system providing
categories, relationships, risk scoring defaults, and
validation for the 172+ SpiderFoot event types.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.event_taxonomy")


class EventCategory(Enum):
    """Top-level event categories."""
    NETWORK = "network"
    IDENTITY = "identity"
    INFRASTRUCTURE = "infrastructure"
    VULNERABILITY = "vulnerability"
    REPUTATION = "reputation"
    DATA_LEAK = "data_leak"
    GEOLOCATION = "geo"
    SOCIAL = "social"
    WEB = "web"
    CRYPTO = "crypto"
    INTERNAL = "internal"
    OTHER = "other"


class RiskLevel(Enum):
    """Risk classification levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NONE = "none"


@dataclass
class EventTypeInfo:
    """Metadata about a single event type."""
    name: str
    description: str = ""
    category: EventCategory = EventCategory.OTHER
    risk_level: RiskLevel = RiskLevel.INFO
    is_raw: bool = False
    parent_type: str | None = None
    related_types: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "is_raw": self.is_raw,
            "parent_type": self.parent_type,
            "related_types": sorted(self.related_types),
            "tags": sorted(self.tags),
        }


# Default taxonomy mappings
_DEFAULT_TAXONOMY: dict[str, dict[str, Any]] = {
    # Network
    "IP_ADDRESS": {"cat": EventCategory.NETWORK, "risk": RiskLevel.INFO, "desc": "IPv4/IPv6 address"},
    "IPV6_ADDRESS": {
        "cat": EventCategory.NETWORK, "risk": RiskLevel.INFO,
        "desc": "IPv6 address", "parent": "IP_ADDRESS",
    },
    "NETBLOCK_MEMBER": {"cat": EventCategory.NETWORK, "risk": RiskLevel.INFO, "desc": "Netblock member"},
    "NETBLOCK_OWNER": {"cat": EventCategory.NETWORK, "risk": RiskLevel.INFO, "desc": "Netblock owner"},
    "BGP_AS_MEMBER": {"cat": EventCategory.NETWORK, "risk": RiskLevel.INFO, "desc": "BGP AS membership"},
    "BGP_AS_OWNER": {"cat": EventCategory.NETWORK, "risk": RiskLevel.INFO, "desc": "BGP AS owner"},
    "TCP_PORT_OPEN": {"cat": EventCategory.NETWORK, "risk": RiskLevel.LOW, "desc": "Open TCP port"},
    "UDP_PORT_OPEN": {"cat": EventCategory.NETWORK, "risk": RiskLevel.LOW, "desc": "Open UDP port"},
    "TCP_PORT_OPEN_BANNER": {
        "cat": EventCategory.NETWORK, "risk": RiskLevel.INFO,
        "desc": "TCP port banner", "parent": "TCP_PORT_OPEN",
    },

    # DNS / Infrastructure
    "INTERNET_NAME": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "Hostname/FQDN"},
    "DOMAIN_NAME": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "Domain name"},
    "DOMAIN_NAME_PARENT": {
        "cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO,
        "desc": "Parent domain", "parent": "DOMAIN_NAME",
    },
    "AFFILIATE_DOMAIN_NAME": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "Affiliated domain"},
    "CO_HOSTED_SITE": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "Co-hosted site"},
    "SIMILARDOMAIN": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.LOW, "desc": "Similar domain"},
    "DNS_TEXT": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "DNS TXT record"},
    "DNS_SPF": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "DNS SPF record"},
    "DNS_SRV": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "DNS SRV record"},
    "PROVIDER_DNS": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "DNS provider"},
    "PROVIDER_HOSTING": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "Hosting provider"},
    "PROVIDER_MAIL": {"cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO, "desc": "Mail provider"},
    "WEBSERVER_BANNER": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "Web server banner"},
    "WEBSERVER_HTTPHEADERS": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "HTTP headers"},
    "WEBSERVER_TECHNOLOGY": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "Web technology"},

    # Identity
    "EMAILADDR": {"cat": EventCategory.IDENTITY, "risk": RiskLevel.INFO, "desc": "Email address"},
    "EMAILADDR_COMPROMISED": {
        "cat": EventCategory.IDENTITY, "risk": RiskLevel.HIGH,
        "desc": "Compromised email", "parent": "EMAILADDR",
    },
    "EMAILADDR_GENERIC": {
        "cat": EventCategory.IDENTITY, "risk": RiskLevel.INFO,
        "desc": "Generic email", "parent": "EMAILADDR",
    },
    "PHONE_NUMBER": {"cat": EventCategory.IDENTITY, "risk": RiskLevel.LOW, "desc": "Phone number"},
    "HUMAN_NAME": {"cat": EventCategory.IDENTITY, "risk": RiskLevel.INFO, "desc": "Person name"},
    "USERNAME": {"cat": EventCategory.IDENTITY, "risk": RiskLevel.INFO, "desc": "Username"},
    "ACCOUNT_EXTERNAL_OWNED": {"cat": EventCategory.IDENTITY, "risk": RiskLevel.INFO, "desc": "External account owned"},
    "SOCIAL_MEDIA": {"cat": EventCategory.SOCIAL, "risk": RiskLevel.INFO, "desc": "Social media profile"},

    # SSL/TLS
    "SSL_CERTIFICATE_ISSUED": {
        "cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO,
        "desc": "SSL certificate issued",
    },
    "SSL_CERTIFICATE_EXPIRED": {
        "cat": EventCategory.VULNERABILITY, "risk": RiskLevel.MEDIUM,
        "desc": "Expired SSL certificate",
    },
    "SSL_CERTIFICATE_MISMATCH": {
        "cat": EventCategory.VULNERABILITY, "risk": RiskLevel.MEDIUM,
        "desc": "SSL certificate mismatch",
    },
    "SSL_CERTIFICATE_RAW": {
        "cat": EventCategory.INFRASTRUCTURE, "risk": RiskLevel.INFO,
        "desc": "Raw SSL cert data", "raw": True,
    },

    # Vulnerabilities
    "VULNERABILITY_CVE_CRITICAL": {
        "cat": EventCategory.VULNERABILITY, "risk": RiskLevel.CRITICAL,
        "desc": "Critical CVE",
    },
    "VULNERABILITY_CVE_HIGH": {"cat": EventCategory.VULNERABILITY, "risk": RiskLevel.HIGH, "desc": "High CVE"},
    "VULNERABILITY_CVE_MEDIUM": {"cat": EventCategory.VULNERABILITY, "risk": RiskLevel.MEDIUM, "desc": "Medium CVE"},
    "VULNERABILITY_CVE_LOW": {"cat": EventCategory.VULNERABILITY, "risk": RiskLevel.LOW, "desc": "Low CVE"},
    "VULNERABILITY_GENERAL": {
        "cat": EventCategory.VULNERABILITY, "risk": RiskLevel.MEDIUM,
        "desc": "General vulnerability",
    },

    # Reputation / threat intel
    "MALICIOUS_IPADDR": {"cat": EventCategory.REPUTATION, "risk": RiskLevel.HIGH, "desc": "Malicious IP"},
    "MALICIOUS_INTERNET_NAME": {"cat": EventCategory.REPUTATION, "risk": RiskLevel.HIGH, "desc": "Malicious hostname"},
    "MALICIOUS_AFFILIATE_IPADDR": {
        "cat": EventCategory.REPUTATION, "risk": RiskLevel.MEDIUM,
        "desc": "Malicious affiliate IP",
    },
    "MALICIOUS_EMAILADDR": {"cat": EventCategory.REPUTATION, "risk": RiskLevel.HIGH, "desc": "Malicious email"},
    "MALICIOUS_SUBNET": {"cat": EventCategory.REPUTATION, "risk": RiskLevel.MEDIUM, "desc": "Malicious subnet"},
    "BLACKLISTED_IPADDR": {"cat": EventCategory.REPUTATION, "risk": RiskLevel.HIGH, "desc": "Blacklisted IP"},
    "BLACKLISTED_AFFILIATE_IPADDR": {
        "cat": EventCategory.REPUTATION, "risk": RiskLevel.MEDIUM,
        "desc": "Blacklisted affiliate IP",
    },

    # Data leaks
    "LEAKSITE_CONTENT": {"cat": EventCategory.DATA_LEAK, "risk": RiskLevel.HIGH, "desc": "Leak site content"},
    "LEAKSITE_URL": {"cat": EventCategory.DATA_LEAK, "risk": RiskLevel.HIGH, "desc": "Leak site URL"},
    "DARKNET_MENTION_CONTENT": {"cat": EventCategory.DATA_LEAK, "risk": RiskLevel.HIGH, "desc": "Dark web mention"},
    "DARKNET_MENTION_URL": {"cat": EventCategory.DATA_LEAK, "risk": RiskLevel.HIGH, "desc": "Dark web URL"},
    "PASSWORD_COMPROMISED": {
        "cat": EventCategory.DATA_LEAK, "risk": RiskLevel.CRITICAL,
        "desc": "Compromised password",
    },
    "HASH_COMPROMISED": {"cat": EventCategory.DATA_LEAK, "risk": RiskLevel.HIGH, "desc": "Compromised hash"},

    # Geo
    "GEOINFO": {"cat": EventCategory.GEOLOCATION, "risk": RiskLevel.INFO, "desc": "Geolocation data"},
    "PHYSICAL_ADDRESS": {"cat": EventCategory.GEOLOCATION, "risk": RiskLevel.LOW, "desc": "Physical address"},
    "PHYSICAL_COORDINATES": {"cat": EventCategory.GEOLOCATION, "risk": RiskLevel.INFO, "desc": "GPS coordinates"},
    "COUNTRY_NAME": {"cat": EventCategory.GEOLOCATION, "risk": RiskLevel.INFO, "desc": "Country"},

    # Web
    "LINKED_URL_INTERNAL": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "Internal URL"},
    "LINKED_URL_EXTERNAL": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "External URL"},
    "URL_FORM": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "Web form URL"},
    "URL_UPLOAD": {"cat": EventCategory.WEB, "risk": RiskLevel.LOW, "desc": "Upload URL"},
    "URL_JAVASCRIPT": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "JavaScript URL"},
    "URL_WEB_FRAMEWORK": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "Web framework URL"},
    "HTTP_CODE": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "HTTP status code"},
    "BASE64_DATA": {"cat": EventCategory.WEB, "risk": RiskLevel.LOW, "desc": "Base64 encoded data"},
    "SEARCH_ENGINE_WEB_CONTENT": {"cat": EventCategory.WEB, "risk": RiskLevel.INFO, "desc": "Search engine content"},

    # Crypto / blockchain
    "BITCOIN_ADDRESS": {"cat": EventCategory.CRYPTO, "risk": RiskLevel.LOW, "desc": "Bitcoin address"},
    "BITCOIN_BALANCE": {"cat": EventCategory.CRYPTO, "risk": RiskLevel.INFO, "desc": "Bitcoin balance"},
    "ETHEREUM_ADDRESS": {"cat": EventCategory.CRYPTO, "risk": RiskLevel.LOW, "desc": "Ethereum address"},

    # Internal
    "ROOT": {"cat": EventCategory.INTERNAL, "risk": RiskLevel.NONE, "desc": "Root/seed event"},
    "INITIAL_TARGET": {"cat": EventCategory.INTERNAL, "risk": RiskLevel.NONE, "desc": "Initial target"},
}


class EventTaxonomy:
    """Hierarchical event type classification system.

    Usage:
        taxonomy = EventTaxonomy()
        info = taxonomy.get("IP_ADDRESS")
        types = taxonomy.get_by_category(EventCategory.NETWORK)
        children = taxonomy.get_children("IP_ADDRESS")
    """

    def __init__(self, load_defaults: bool = True) -> None:
        self._types: dict[str, EventTypeInfo] = {}
        if load_defaults:
            self._load_defaults()

    def _load_defaults(self) -> None:
        for name, meta in _DEFAULT_TAXONOMY.items():
            info = EventTypeInfo(
                name=name,
                description=meta.get("desc", ""),
                category=meta.get("cat", EventCategory.OTHER),
                risk_level=meta.get("risk", RiskLevel.INFO),
                is_raw=meta.get("raw", False),
                parent_type=meta.get("parent"),
            )
            self._types[name] = info

    def register(self, info: EventTypeInfo) -> "EventTaxonomy":
        """Register a new event type (chainable)."""
        self._types[info.name] = info
        return self

    def unregister(self, name: str) -> bool:
        return self._types.pop(name, None) is not None

    def get(self, name: str) -> EventTypeInfo | None:
        return self._types.get(name)

    def exists(self, name: str) -> bool:
        return name in self._types

    def get_category(self, name: str) -> EventCategory | None:
        info = self._types.get(name)
        return info.category if info else None

    def get_risk(self, name: str) -> RiskLevel | None:
        info = self._types.get(name)
        return info.risk_level if info else None

    def get_by_category(self, category: EventCategory) -> list[EventTypeInfo]:
        return [t for t in self._types.values() if t.category == category]

    def get_by_risk(self, risk: RiskLevel) -> list[EventTypeInfo]:
        return [t for t in self._types.values() if t.risk_level == risk]

    def get_children(self, parent_name: str) -> list[EventTypeInfo]:
        return [t for t in self._types.values() if t.parent_type == parent_name]

    def get_ancestors(self, name: str) -> list[str]:
        """Get the ancestor chain (parent, grandparent, ...)."""
        ancestors = []
        current = name
        visited = set()
        while current and current not in visited:
            visited.add(current)
            info = self._types.get(current)
            if info and info.parent_type:
                ancestors.append(info.parent_type)
                current = info.parent_type
            else:
                break
        return ancestors

    def is_descendant(self, child: str, ancestor: str) -> bool:
        return ancestor in self.get_ancestors(child)

    @property
    def all_types(self) -> list[str]:
        return sorted(self._types.keys())

    @property
    def categories(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self._types.values():
            c = t.category.value
            counts[c] = counts.get(c, 0) + 1
        return counts

    @property
    def risk_distribution(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self._types.values():
            r = t.risk_level.value
            counts[r] = counts.get(r, 0) + 1
        return counts

    def validate_type(self, name: str) -> bool:
        return name in self._types

    def search(self, query: str) -> list[EventTypeInfo]:
        """Search types by name or description substring."""
        q = query.lower()
        return [
            t for t in self._types.values()
            if q in t.name.lower() or q in t.description.lower()
        ]

    def summary(self) -> dict:
        return {
            "total_types": len(self._types),
            "categories": self.categories,
            "risk_distribution": self.risk_distribution,
        }

    def to_dict(self) -> dict:
        return {
            name: info.to_dict()
            for name, info in sorted(self._types.items())
        }
