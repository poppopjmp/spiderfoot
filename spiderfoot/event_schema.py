#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         event_schema
# Purpose:      Event schema validation for SpiderFoot.
#               Defines schemas for all event types with field-level
#               constraints, enabling runtime validation before storage
#               and schema documentation generation.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Event Schema Validation

Provides declarative schemas for SpiderFoot event types, enabling:

    - Structural validation (type, data format, required fields)
    - Data format constraints (IP addresses, domains, URLs, emails)
    - Confidence/visibility/risk range enforcement
    - Schema documentation generation
    - Schema discovery for tooling

Usage::

    from spiderfoot.event_schema import EventSchemaRegistry, validate_event

    # Validate an event dict
    errors = validate_event({
        "type": "IP_ADDRESS",
        "data": "192.168.1.1",
        "module": "sfp_resolver",
        "confidence": 100,
    })

    # Get schema for a type
    schema = EventSchemaRegistry.get("IP_ADDRESS")
"""

import ipaddress
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.event_schema")

# ---------------------------------------------------------------------------
# Well-known event type categories (mirrors tbl_event_types.event_type)
# ---------------------------------------------------------------------------


class EventCategory(str, Enum):
    """Event type categories."""
    INTERNAL = "INTERNAL"
    ENTITY = "ENTITY"
    DESCRIPTOR = "DESCRIPTOR"
    DATA = "DATA"
    SUBENTITY = "SUBENTITY"


# ---------------------------------------------------------------------------
# Data format validators
# ---------------------------------------------------------------------------

# -- Regex patterns --

_RE_EVENT_TYPE_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_RE_DOMAIN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,63}$"
)
_RE_EMAIL = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
_RE_URL = re.compile(r"^https?://", re.IGNORECASE)
_RE_PHONE = re.compile(r"^[\+\d\s\-\(\)\.]{5,20}$")
_RE_CVE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_RE_BGP_ASN = re.compile(r"^AS\d+", re.IGNORECASE)
_RE_BITCOIN = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{25,}$")
_RE_HASH_MD5 = re.compile(r"^[a-fA-F0-9]{32}$")
_RE_HASH_SHA1 = re.compile(r"^[a-fA-F0-9]{40}$")
_RE_HASH_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


class DataFormat(str, Enum):
    """Supported data format constraints for event data."""
    ANY = "any"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    IP = "ip"      # v4 or v6
    DOMAIN = "domain"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    CVE = "cve"
    ASN = "asn"
    BITCOIN = "bitcoin"
    HASH_MD5 = "hash_md5"
    HASH_SHA1 = "hash_sha1"
    HASH_SHA256 = "hash_sha256"
    NETBLOCK = "netblock"
    NON_EMPTY = "non_empty"
    JSON = "json"


def _validate_format(data: str, fmt: DataFormat) -> Optional[str]:
    """Validate data against a format. Returns error message or None."""
    if fmt == DataFormat.ANY:
        return None

    if fmt == DataFormat.NON_EMPTY:
        if not data or not data.strip():
            return "Data must be non-empty"
        return None

    if fmt == DataFormat.IPV4:
        try:
            ipaddress.IPv4Address(data.strip())
            return None
        except (ValueError, ipaddress.AddressValueError):
            return f"Invalid IPv4 address: {data[:50]}"

    if fmt == DataFormat.IPV6:
        try:
            ipaddress.IPv6Address(data.strip())
            return None
        except (ValueError, ipaddress.AddressValueError):
            return f"Invalid IPv6 address: {data[:50]}"

    if fmt == DataFormat.IP:
        try:
            ipaddress.ip_address(data.strip())
            return None
        except ValueError:
            return f"Invalid IP address: {data[:50]}"

    if fmt == DataFormat.DOMAIN:
        if not _RE_DOMAIN.match(data.strip()):
            return f"Invalid domain name: {data[:50]}"
        return None

    if fmt == DataFormat.EMAIL:
        if not _RE_EMAIL.match(data.strip()):
            return f"Invalid email address: {data[:50]}"
        return None

    if fmt == DataFormat.URL:
        if not _RE_URL.match(data.strip()):
            return f"Invalid URL (must start with http/https): {data[:80]}"
        return None

    if fmt == DataFormat.PHONE:
        if not _RE_PHONE.match(data.strip()):
            return f"Invalid phone number: {data[:30]}"
        return None

    if fmt == DataFormat.CVE:
        if not _RE_CVE.search(data.strip()):
            return f"Data should contain CVE identifier: {data[:50]}"
        return None

    if fmt == DataFormat.ASN:
        if not _RE_BGP_ASN.match(data.strip()):
            return f"Invalid ASN format (expected ASnnnn): {data[:30]}"
        return None

    if fmt == DataFormat.BITCOIN:
        if not _RE_BITCOIN.match(data.strip()):
            return f"Invalid Bitcoin address: {data[:50]}"
        return None

    if fmt == DataFormat.NETBLOCK:
        try:
            ipaddress.ip_network(data.strip(), strict=False)
            return None
        except ValueError:
            return f"Invalid netblock/CIDR: {data[:50]}"

    if fmt == DataFormat.JSON:
        import json
        try:
            json.loads(data)
            return None
        except (json.JSONDecodeError, TypeError):
            return "Data is not valid JSON"

    if fmt in (DataFormat.HASH_MD5, DataFormat.HASH_SHA1, DataFormat.HASH_SHA256):
        patterns = {
            DataFormat.HASH_MD5: _RE_HASH_MD5,
            DataFormat.HASH_SHA1: _RE_HASH_SHA1,
            DataFormat.HASH_SHA256: _RE_HASH_SHA256,
        }
        if not patterns[fmt].match(data.strip()):
            return f"Invalid {fmt.value} hash: {data[:70]}"
        return None

    return None


# ---------------------------------------------------------------------------
# Event Schema definition
# ---------------------------------------------------------------------------


@dataclass
class EventSchema:
    """Schema definition for a single event type."""
    event_type: str
    description: str = ""
    category: EventCategory = EventCategory.ENTITY
    data_format: DataFormat = DataFormat.NON_EMPTY
    is_raw: bool = False
    max_data_length: int = 0     # 0 = no limit
    min_confidence: int = 0
    max_confidence: int = 100
    min_risk: int = 0
    max_risk: int = 100
    deprecated: bool = False
    related_types: List[str] = field(default_factory=list)
    custom_validators: List[Callable[[str], Optional[str]]] = field(
        default_factory=list, repr=False)

    def validate_data(self, data: str) -> List[str]:
        """Validate event data against this schema. Returns errors."""
        errors = []

        if data is None:
            errors.append("Event data cannot be None")
            return errors

        if not isinstance(data, str):
            errors.append(f"Event data must be str, got {type(data).__name__}")
            return errors

        # Format validation
        fmt_err = _validate_format(data, self.data_format)
        if fmt_err:
            errors.append(fmt_err)

        # Length validation
        if self.max_data_length > 0 and len(data) > self.max_data_length:
            errors.append(
                f"Data exceeds maximum length "
                f"({len(data)} > {self.max_data_length})"
            )

        # Custom validators
        for validator in self.custom_validators:
            try:
                err = validator(data)
                if err:
                    errors.append(err)
            except Exception as e:
                errors.append(f"Custom validation error: {e}")

        return errors

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "description": self.description,
            "category": self.category.value,
            "data_format": self.data_format.value,
            "is_raw": self.is_raw,
            "max_data_length": self.max_data_length,
            "deprecated": self.deprecated,
            "related_types": self.related_types,
        }


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of event validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Schema registry
# ---------------------------------------------------------------------------


class EventSchemaRegistry:
    """Registry of all known event type schemas.

    Pre-loaded with schemas for core SpiderFoot event types.
    Extensible via register() for custom modules.
    """

    _schemas: Dict[str, EventSchema] = {}
    _strict: bool = False   # If True, unknown types are errors

    @classmethod
    def register(cls, schema: EventSchema) -> None:
        """Register a schema for an event type."""
        cls._schemas[schema.event_type] = schema

    @classmethod
    def get(cls, event_type: str) -> Optional[EventSchema]:
        """Get schema for an event type."""
        return cls._schemas.get(event_type)

    @classmethod
    def has(cls, event_type: str) -> bool:
        return event_type in cls._schemas

    @classmethod
    def all_types(cls) -> Set[str]:
        return set(cls._schemas.keys())

    @classmethod
    def by_category(cls, category: EventCategory) -> List[EventSchema]:
        return [s for s in cls._schemas.values()
                if s.category == category]

    @classmethod
    def set_strict(cls, strict: bool) -> None:
        cls._strict = strict

    @classmethod
    def validate(cls, event: dict) -> ValidationResult:
        """Validate an event dict against its schema.

        Expected event keys: type, data, module, confidence,
        visibility, risk, source_event_hash.
        """
        errors = []
        warnings = []

        # -- Required fields --
        event_type = event.get("type") or event.get("eventType")
        if not event_type:
            errors.append("Missing required field: type/eventType")
            return ValidationResult(valid=False, errors=errors)

        if not _RE_EVENT_TYPE_NAME.match(event_type):
            errors.append(
                f"Invalid event type name '{event_type}': "
                "must match [A-Z_][A-Z0-9_]*"
            )

        data = event.get("data")
        module = event.get("module")

        if data is None and event_type != "ROOT":
            errors.append("Missing required field: data")

        if not module and event_type != "ROOT":
            errors.append("Missing required field: module")

        # -- Numeric ranges --
        for field_name in ("confidence", "visibility", "risk"):
            val = event.get(field_name)
            if val is not None:
                if not isinstance(val, (int, float)):
                    errors.append(
                        f"{field_name} must be numeric, got "
                        f"{type(val).__name__}"
                    )
                elif not (0 <= val <= 100):
                    errors.append(
                        f"{field_name} must be 0-100, got {val}"
                    )

        # -- Schema-specific validation --
        schema = cls._schemas.get(event_type)
        if schema:
            if schema.deprecated:
                warnings.append(
                    f"Event type '{event_type}' is deprecated"
                )

            if data is not None:
                data_errors = schema.validate_data(str(data))
                errors.extend(data_errors)
        elif cls._strict:
            errors.append(f"Unknown event type: {event_type}")
        else:
            if event_type != "ROOT":
                warnings.append(
                    f"No schema registered for type '{event_type}'"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def reset(cls) -> None:
        """Clear all registered schemas (for testing)."""
        cls._schemas.clear()
        cls._strict = False

    @classmethod
    def generate_docs(cls) -> str:
        """Generate Markdown documentation for all schemas."""
        lines = [
            "# SpiderFoot Event Type Reference",
            "",
            f"Total event types: {len(cls._schemas)}",
            "",
        ]

        by_cat: Dict[str, List[EventSchema]] = {}
        for schema in sorted(cls._schemas.values(),
                             key=lambda s: s.event_type):
            cat = schema.category.value
            by_cat.setdefault(cat, []).append(schema)

        for cat_name in sorted(by_cat.keys()):
            lines.append(f"## {cat_name}")
            lines.append("")
            lines.append(
                "| Event Type | Description | Format | Raw |")
            lines.append(
                "|------------|-------------|--------|-----|")

            for schema in by_cat[cat_name]:
                dep = " *(deprecated)*" if schema.deprecated else ""
                lines.append(
                    f"| `{schema.event_type}` | "
                    f"{schema.description}{dep} | "
                    f"{schema.data_format.value} | "
                    f"{'Y' if schema.is_raw else 'N'} |"
                )
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def validate_event(event: dict) -> List[str]:
    """Validate an event and return error list (empty if valid)."""
    result = EventSchemaRegistry.validate(event)
    return result.errors


# ---------------------------------------------------------------------------
# Built-in schemas for core SpiderFoot event types
# ---------------------------------------------------------------------------

def _register_core_schemas() -> None:
    """Register schemas for all core event types."""
    R = EventSchemaRegistry.register
    S = EventSchema

    # -- INTERNAL --
    R(S("ROOT", "Internal SpiderFoot Root event",
        EventCategory.INTERNAL, DataFormat.ANY))

    # -- ENTITY: Network --
    R(S("IP_ADDRESS", "IPv4 Address",
        EventCategory.ENTITY, DataFormat.IPV4))
    R(S("IPV6_ADDRESS", "IPv6 Address",
        EventCategory.ENTITY, DataFormat.IPV6))
    R(S("INTERNET_NAME", "Internet Name (hostname)",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("INTERNET_NAME_UNRESOLVED", "Unresolved Internet Name",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("DOMAIN_NAME", "Domain Name",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("DOMAIN_NAME_PARENT", "Parent Domain Name",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("AFFILIATE_DOMAIN_NAME", "Affiliate Domain Name",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("CO_HOSTED_SITE", "Co-Hosted Site",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("CO_HOSTED_SITE_DOMAIN", "Co-Hosted Site Domain",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("SIMILARDOMAIN", "Similar Domain",
        EventCategory.ENTITY, DataFormat.DOMAIN))
    R(S("NETBLOCK_OWNER", "Netblock Ownership",
        EventCategory.ENTITY, DataFormat.NETBLOCK))
    R(S("NETBLOCK_MEMBER", "Netblock Membership",
        EventCategory.ENTITY, DataFormat.NETBLOCK))
    R(S("AFFILIATE_IPADDR", "Affiliate IP Address",
        EventCategory.ENTITY, DataFormat.IP))
    R(S("BGP_AS_OWNER", "BGP AS Ownership",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))

    # -- ENTITY: People & Orgs --
    R(S("EMAILADDR", "Email Address",
        EventCategory.ENTITY, DataFormat.EMAIL))
    R(S("EMAILADDR_COMPROMISED", "Compromised Email Address",
        EventCategory.ENTITY, DataFormat.EMAIL))
    R(S("EMAILADDR_GENERIC", "Generic Email Address",
        EventCategory.ENTITY, DataFormat.EMAIL))
    R(S("HUMAN_NAME", "Human Name",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("PHONE_NUMBER", "Phone Number",
        EventCategory.ENTITY, DataFormat.PHONE))
    R(S("USERNAME", "Username",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("COMPANY_NAME", "Company Name",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("PHYSICAL_ADDRESS", "Physical Address",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("COUNTRY_NAME", "Country Name",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("SOCIAL_MEDIA", "Social Media Presence",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))

    # -- ENTITY: Crypto & Identifiers --
    R(S("BITCOIN_ADDRESS", "Bitcoin Address",
        EventCategory.ENTITY, DataFormat.BITCOIN))
    R(S("BITCOIN_BALANCE", "Bitcoin Balance",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("ACCOUNT_EXTERNAL_OWNED", "External Account",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))

    # -- ENTITY: Cloud & Infrastructure --
    R(S("CLOUD_STORAGE_BUCKET", "Cloud Storage Bucket",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("CLOUD_STORAGE_BUCKET_OPEN", "Open Cloud Storage Bucket",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("PROVIDER_DNS", "DNS Provider",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("PROVIDER_HOSTING", "Hosting Provider",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("PROVIDER_MAIL", "Mail Provider",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))

    # -- ENTITY: SSL --
    R(S("SSL_CERTIFICATE_ISSUED", "SSL Certificate - Issued To",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("SSL_CERTIFICATE_ISSUER", "SSL Certificate - Issuer",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("SSL_CERTIFICATE_MISMATCH", "SSL Certificate Mismatch",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))
    R(S("SSL_CERTIFICATE_EXPIRED", "SSL Certificate Expired",
        EventCategory.ENTITY, DataFormat.NON_EMPTY))

    # -- SUBENTITY --
    R(S("TCP_PORT_OPEN", "Open TCP Port",
        EventCategory.SUBENTITY, DataFormat.NON_EMPTY))
    R(S("TCP_PORT_OPEN_BANNER", "Open TCP Port Banner",
        EventCategory.SUBENTITY, DataFormat.NON_EMPTY))
    R(S("UDP_PORT_OPEN", "Open UDP Port",
        EventCategory.SUBENTITY, DataFormat.NON_EMPTY))
    R(S("SOFTWARE_USED", "Software Used",
        EventCategory.SUBENTITY, DataFormat.NON_EMPTY))
    R(S("OPERATING_SYSTEM", "Operating System",
        EventCategory.SUBENTITY, DataFormat.NON_EMPTY))
    R(S("WEBSERVER_BANNER", "Web Server Banner",
        EventCategory.SUBENTITY, DataFormat.NON_EMPTY))
    R(S("WEBSERVER_TECHNOLOGY", "Web Server Technology",
        EventCategory.SUBENTITY, DataFormat.NON_EMPTY))
    R(S("LINKED_URL_INTERNAL", "Linked URL - Internal",
        EventCategory.SUBENTITY, DataFormat.URL))
    R(S("LINKED_URL_EXTERNAL", "Linked URL - External",
        EventCategory.SUBENTITY, DataFormat.URL))

    # -- DESCRIPTOR: Security --
    R(S("MALICIOUS_IPADDR", "Malicious IP Address",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("MALICIOUS_INTERNET_NAME", "Malicious Internet Name",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("MALICIOUS_AFFILIATE_INTERNET_NAME",
        "Malicious Affiliate Internet Name",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("MALICIOUS_AFFILIATE_IPADDR",
        "Malicious Affiliate IP Address",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("MALICIOUS_COHOST", "Malicious Co-Host",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("BLACKLISTED_IPADDR", "Blacklisted IP Address",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("BLACKLISTED_INTERNET_NAME", "Blacklisted Internet Name",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("BLACKLISTED_AFFILIATE_IPADDR",
        "Blacklisted Affiliate IP Address",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))

    # -- DESCRIPTOR: Geolocation --
    R(S("GEOINFO", "Physical Location / GeoIP",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))

    # -- DESCRIPTOR: Vulnerabilities --
    R(S("VULNERABILITY_GENERAL", "Vulnerability - General",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("VULNERABILITY_CVE_CRITICAL",
        "Vulnerability - CVE Critical",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("VULNERABILITY_CVE_HIGH", "Vulnerability - CVE High",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("VULNERABILITY_CVE_MEDIUM", "Vulnerability - CVE Medium",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("VULNERABILITY_CVE_LOW", "Vulnerability - CVE Low",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("VULNERABILITY_DISCLOSURE", "Vulnerability Disclosure",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))

    # -- DESCRIPTOR: Defacement --
    R(S("DEFACED_INTERNET_NAME", "Defaced Internet Name",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("DEFACED_IPADDR", "Defaced IP Address",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))
    R(S("DEFACED_AFFILIATE_INTERNET_NAME",
        "Defaced Affiliate Internet Name",
        EventCategory.DESCRIPTOR, DataFormat.NON_EMPTY))

    # -- DATA --
    R(S("DOMAIN_WHOIS", "Domain Whois",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("NETBLOCK_WHOIS", "Netblock Whois",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("SSL_CERTIFICATE_RAW", "SSL Certificate - Raw Data",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("TARGET_WEB_CONTENT", "Target Web Content",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("TARGET_WEB_CONTENT_TYPE", "Target Web Content Type",
        EventCategory.DATA, DataFormat.NON_EMPTY))
    R(S("RAW_DNS_RECORDS", "Raw DNS Records",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("RAW_RIR_DATA", "Raw RIR Data",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("RAW_FILE_META_DATA", "Raw File Meta Data",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("WEBSERVER_HTTPHEADERS", "HTTP Headers",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("SEARCH_ENGINE_WEB_CONTENT", "Search Engine Web Content",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("LEAKSITE_CONTENT", "Leak Site Content",
        EventCategory.DATA, DataFormat.NON_EMPTY, is_raw=True))
    R(S("LEAKSITE_URL", "Leak Site URL",
        EventCategory.DATA, DataFormat.URL))
    R(S("DNS_TEXT", "DNS TXT Record",
        EventCategory.DATA, DataFormat.NON_EMPTY))
    R(S("DNS_SPF", "DNS SPF Record",
        EventCategory.DATA, DataFormat.NON_EMPTY))

    log.debug("Registered %d core event schemas",
              len(EventSchemaRegistry._schemas))


# Auto-register on import
_register_core_schemas()
