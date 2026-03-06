# -------------------------------------------------------------------------------
# Name:         waf_bypass
# Purpose:      S-007 — CDN/WAF bypass techniques + header spoofing
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""WAF/CDN Bypass Engine — SOTA S-007 (Cycles 121–140).

Provides techniques to bypass CDN/WAF protections and spoof headers
for stealthier reconnaissance. Integrates with the adaptive stealth
layer (S-005) and scan engine bridge (S-006).

Components
----------
- :class:`BypassTechnique` — Enumeration of known bypass methods.
- :class:`SpoofHeader` — A header key/value with metadata about its
  bypass purpose and compatibility.
- :class:`HeaderSpoofProfile` — A complete set of spoofed headers
  that mimic a specific client type (internal network, CDN node,
  crawler, mobile app, API client).
- :class:`CDNVendor` — Known CDN vendors with specific bypass rules.
- :class:`CDNBypassStrategy` — Per-vendor bypass strategy with
  prioritized techniques.
- :class:`OriginDiscovery` — Techniques to discover the real origin
  server behind a CDN (DNS history, subdomains, cert SANs,
  header leaks, error pages).
- :class:`CacheAnalyzer` — Detect cacheable vs. non-cacheable paths,
  identify cache keys, and find cache-busting opportunities.
- :class:`WAFBypassEngine` — Façade combining all bypass components
  into a unified API.

Usage::

    from spiderfoot.recon.waf_bypass import (
        WAFBypassEngine,
        CDNVendor,
        HeaderSpoofProfile,
    )

    engine = WAFBypassEngine()

    # Get bypass headers for Cloudflare
    headers = engine.get_bypass_headers(CDNVendor.CLOUDFLARE)

    # Get origin discovery hints
    hints = engine.get_origin_hints("example.com", CDNVendor.CLOUDFLARE)

    # Analyze cache behavior
    cache_info = engine.analyze_cache(
        url="https://example.com/api/users",
        response_headers={"Cache-Control": "no-cache", "CF-Cache-Status": "MISS"},
    )
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import random
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.recon.waf_bypass")


# ============================================================================
# Bypass Technique Enumeration (Cycles 121–122)
# ============================================================================


class BypassTechnique(Enum):
    """Known WAF/CDN bypass techniques."""
    # Header-based bypasses
    HEADER_XFF = "x_forwarded_for"               # X-Forwarded-For to appear as internal
    HEADER_X_ORIGINATING_IP = "x_originating_ip"  # X-Originating-IP
    HEADER_X_REAL_IP = "x_real_ip"                # X-Real-IP
    HEADER_X_CLIENT_IP = "x_client_ip"            # X-Client-IP
    HEADER_CF_CONNECTING_IP = "cf_connecting_ip"  # Cloudflare-specific
    HEADER_TRUE_CLIENT_IP = "true_client_ip"      # Akamai True-Client-IP
    HEADER_X_CUSTOM_IP = "x_custom_ip"            # Custom forwarded headers
    HEADER_FORWARDED = "forwarded"                # RFC 7239 Forwarded header
    HEADER_VIA = "via"                            # Via header manipulation

    # Request mutation bypasses
    HOST_OVERRIDE = "host_override"               # Host header manipulation
    PATH_MUTATION = "path_mutation"               # URL path encoding tricks
    METHOD_OVERRIDE = "method_override"           # X-HTTP-Method-Override
    CONTENT_TYPE_BYPASS = "content_type_bypass"   # Content-Type confusion

    # Protocol-level
    HTTP2_DIRECT = "http2_direct"                 # Direct HTTP/2 to origin
    WEBSOCKET_UPGRADE = "websocket_upgrade"       # WebSocket upgrade bypass
    SSL_CLIENT_CERT = "ssl_client_cert"           # Mutual TLS bypass

    # Origin discovery
    DNS_HISTORY = "dns_history"                   # Historical DNS records
    SUBDOMAIN_ENUM = "subdomain_enum"             # Subdomain origin leak
    CERT_TRANSPARENCY = "cert_transparency"       # CT log origin discovery
    ERROR_PAGE_LEAK = "error_page_leak"           # Error pages reveal origin
    MAIL_HEADER_LEAK = "mail_header_leak"         # Email headers leak origin
    SSRF_PROBE = "ssrf_probe"                     # SSRF to discover internal


# ============================================================================
# CDN/WAF Vendor Definitions (Cycles 122–124)
# ============================================================================


class CDNVendor(Enum):
    """Known CDN/WAF vendors with bypass strategy support."""
    UNKNOWN = "unknown"
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    AWS_CLOUDFRONT = "aws_cloudfront"
    AWS_WAF = "aws_waf"
    FASTLY = "fastly"
    IMPERVA = "imperva"
    SUCURI = "sucuri"
    STACKPATH = "stackpath"
    CLOUDFRONT = "cloudfront"
    AZURE_CDN = "azure_cdn"
    GCP_CLOUD_ARMOR = "gcp_cloud_armor"
    DDOS_GUARD = "ddos_guard"
    F5_BIG_IP = "f5_big_ip"
    BARRACUDA = "barracuda"
    GENERIC = "generic"


# ============================================================================
# Spoofed Headers (Cycles 123–126)
# ============================================================================


@dataclass
class SpoofHeader:
    """A single spoofed header with metadata."""
    name: str
    value: str
    technique: BypassTechnique
    description: str = ""
    risk_level: str = "low"   # low / medium / high
    vendor_specific: str = ""  # empty = generic


# Internal IP ranges commonly used in bypass attempts
_INTERNAL_IPS = [
    "127.0.0.1",
    "10.0.0.1",
    "10.10.10.1",
    "172.16.0.1",
    "192.168.1.1",
    "192.168.0.1",
    "::1",
    "fd00::1",
]

_LOCALHOST_VARIANTS = [
    "127.0.0.1",
    "localhost",
    "127.0.0.1:80",
    "127.0.0.1:443",
    "0.0.0.0",
    "0",
    "127.1",
    "127.0.1",
]

# Common IP source headers that WAFs/proxies trust
_IP_SPOOF_HEADERS: list[tuple[str, BypassTechnique]] = [
    ("X-Forwarded-For", BypassTechnique.HEADER_XFF),
    ("X-Originating-IP", BypassTechnique.HEADER_X_ORIGINATING_IP),
    ("X-Real-IP", BypassTechnique.HEADER_X_REAL_IP),
    ("X-Client-IP", BypassTechnique.HEADER_X_CLIENT_IP),
    ("CF-Connecting-IP", BypassTechnique.HEADER_CF_CONNECTING_IP),
    ("True-Client-IP", BypassTechnique.HEADER_TRUE_CLIENT_IP),
    ("X-Custom-IP-Authorization", BypassTechnique.HEADER_X_CUSTOM_IP),
    ("Forwarded", BypassTechnique.HEADER_FORWARDED),
    ("X-ProxyUser-Ip", BypassTechnique.HEADER_X_CUSTOM_IP),
    ("X-Remote-IP", BypassTechnique.HEADER_X_CUSTOM_IP),
    ("X-Remote-Addr", BypassTechnique.HEADER_X_CUSTOM_IP),
    ("X-Host", BypassTechnique.HEADER_X_CUSTOM_IP),
]


def generate_spoof_headers(ip: str | None = None) -> list[SpoofHeader]:
    """Generate a set of IP-spoofing headers.

    Args:
        ip: IP address to spoof. If None, uses a random internal IP.

    Returns:
        List of SpoofHeader entries.
    """
    if ip is None:
        ip = random.choice(_INTERNAL_IPS)

    headers: list[SpoofHeader] = []
    for header_name, technique in _IP_SPOOF_HEADERS:
        if technique == BypassTechnique.HEADER_FORWARDED:
            value = f"for={ip}"
        else:
            value = ip
        headers.append(SpoofHeader(
            name=header_name,
            value=value,
            technique=technique,
            description=f"Spoof source IP as {ip} via {header_name}",
            risk_level="medium",
        ))
    return headers


# ============================================================================
# Header Spoof Profiles (Cycles 125–128)
# ============================================================================


class ClientType(Enum):
    """Client types for header spoofing profiles."""
    INTERNAL_NETWORK = "internal_network"     # Corporate/internal user
    CDN_NODE = "cdn_node"                     # CDN edge node
    SEARCH_CRAWLER = "search_crawler"         # Search engine crawler
    MOBILE_APP = "mobile_app"                 # Mobile application
    API_CLIENT = "api_client"                 # API/service client
    MONITORING = "monitoring"                 # Uptime monitor
    LOAD_BALANCER = "load_balancer"           # Load balancer health check


@dataclass
class HeaderSpoofProfile:
    """A complete set of headers mimicking a specific client type.

    Provides realistic header combinations that WAFs may whitelist
    or treat with lower suspicion.
    """
    name: str
    client_type: ClientType
    headers: dict[str, str]
    description: str = ""
    risk_level: str = "low"
    effectiveness: float = 0.5   # 0.0–1.0 estimated success rate

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "name": self.name,
            "client_type": self.client_type.value,
            "headers": dict(self.headers),
            "description": self.description,
            "risk_level": self.risk_level,
            "effectiveness": self.effectiveness,
        }


# Pre-built spoof profiles
_DEFAULT_PROFILES: dict[str, HeaderSpoofProfile] = {}


def _build_default_profiles() -> dict[str, HeaderSpoofProfile]:
    """Create the default header spoof profiles."""
    profiles: dict[str, HeaderSpoofProfile] = {}

    # Internal network user — whitelisted by many WAFs
    profiles["internal_user"] = HeaderSpoofProfile(
        name="internal_user",
        client_type=ClientType.INTERNAL_NETWORK,
        headers={
            "X-Forwarded-For": "10.0.0.50",
            "X-Real-IP": "10.0.0.50",
            "X-Originating-IP": "10.0.0.50",
            "X-Internal-Request": "true",
        },
        description="Mimics an internal network user behind corporate proxy",
        risk_level="medium",
        effectiveness=0.65,
    )

    # CDN health check — CDN nodes are whitelisted
    profiles["cdn_health_check"] = HeaderSpoofProfile(
        name="cdn_health_check",
        client_type=ClientType.CDN_NODE,
        headers={
            "X-Forwarded-For": "172.16.0.5",
            "Via": "1.1 cdn-node-42.example.net",
            "X-CDN-Request": "health-check",
            "Accept": "*/*",
            "Connection": "keep-alive",
        },
        description="Mimics a CDN health check probe",
        risk_level="low",
        effectiveness=0.55,
    )

    # Googlebot crawler — often whitelisted for SEO
    profiles["google_crawler"] = HeaderSpoofProfile(
        name="google_crawler",
        client_type=ClientType.SEARCH_CRAWLER,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; Googlebot/2.1; "
                "+http://www.google.com/bot.html)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "From": "googlebot(at)googlebot.com",
        },
        description="Mimics Googlebot — often whitelisted by WAFs",
        risk_level="medium",
        effectiveness=0.70,
    )

    # Bingbot crawler
    profiles["bing_crawler"] = HeaderSpoofProfile(
        name="bing_crawler",
        client_type=ClientType.SEARCH_CRAWLER,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; bingbot/2.0; "
                "+http://www.bing.com/bingbot.htm)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
        },
        description="Mimics Bingbot — frequently whitelisted",
        risk_level="medium",
        effectiveness=0.60,
    )

    # Mobile app user — different WAF rules
    profiles["mobile_ios"] = HeaderSpoofProfile(
        name="mobile_ios",
        client_type=ClientType.MOBILE_APP,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/18.2 Mobile/15E148 Safari/604.1"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "X-Requested-With": "com.apple.mobilesafari",
        },
        description="iOS Safari mobile — different WAF rulesets",
        risk_level="low",
        effectiveness=0.50,
    )

    # API client with service token
    profiles["api_service"] = HeaderSpoofProfile(
        name="api_service",
        client_type=ClientType.API_CLIENT,
        headers={
            "User-Agent": "ServiceClient/2.0 (internal-monitoring)",
            "Accept": "application/json",
            "X-Request-ID": "svc-health-check-001",
            "X-Service-Name": "monitoring-agent",
        },
        description="API service client — bypasses browser-focused WAF rules",
        risk_level="low",
        effectiveness=0.45,
    )

    # Uptime monitor — health checks are whitelisted
    profiles["uptime_monitor"] = HeaderSpoofProfile(
        name="uptime_monitor",
        client_type=ClientType.MONITORING,
        headers={
            "User-Agent": "UptimeRobot/2.0",
            "Accept": "*/*",
            "X-Monitor-Source": "uptime-check",
            "Connection": "close",
        },
        description="Uptime monitor — many WAFs whitelist monitoring services",
        risk_level="low",
        effectiveness=0.55,
    )

    # Load balancer health check
    profiles["lb_health_check"] = HeaderSpoofProfile(
        name="lb_health_check",
        client_type=ClientType.LOAD_BALANCER,
        headers={
            "User-Agent": "ELB-HealthChecker/2.0",
            "X-Forwarded-For": "10.0.0.1",
            "Accept": "*/*",
            "Connection": "keep-alive",
        },
        description="AWS ELB health check — bypasses WAF for internal routes",
        risk_level="low",
        effectiveness=0.60,
    )

    return profiles


# Build defaults on import
_DEFAULT_PROFILES.update(_build_default_profiles())


def get_profile(name: str) -> HeaderSpoofProfile | None:
    """Get a spoof profile by name.

    Args:
        name: Profile name.

    Returns:
        Profile or None if not found.
    """
    return _DEFAULT_PROFILES.get(name)


def get_all_profiles() -> dict[str, HeaderSpoofProfile]:
    """Get all available spoof profiles.

    Returns:
        Dictionary of profile name to HeaderSpoofProfile.
    """
    return dict(_DEFAULT_PROFILES)


def get_profiles_by_client_type(client_type: ClientType) -> list[HeaderSpoofProfile]:
    """Get profiles for a specific client type.

    Args:
        client_type: The client type to filter by.

    Returns:
        List of matching profiles.
    """
    return [
        p for p in _DEFAULT_PROFILES.values()
        if p.client_type == client_type
    ]


# ============================================================================
# CDN-Specific Bypass Strategies (Cycles 127–130)
# ============================================================================


@dataclass
class CDNBypassStrategy:
    """A bypass strategy specific to a CDN/WAF vendor.

    Contains prioritized techniques that are known to work
    against the specific vendor, along with vendor-specific
    headers and configuration.
    """
    vendor: CDNVendor
    techniques: list[BypassTechnique]
    vendor_headers: dict[str, str]
    description: str = ""
    notes: str = ""
    success_rate: float = 0.5

    def get_headers(self, target_ip: str | None = None) -> dict[str, str]:
        """Get bypass headers for this strategy.

        Args:
            target_ip: Optional target IP to include in headers.

        Returns:
            Dict of header name to value.
        """
        headers = dict(self.vendor_headers)

        # Add IP spoof headers if techniques include them
        ip = target_ip or random.choice(_INTERNAL_IPS)
        for tech in self.techniques:
            if tech == BypassTechnique.HEADER_XFF:
                headers["X-Forwarded-For"] = ip
            elif tech == BypassTechnique.HEADER_X_REAL_IP:
                headers["X-Real-IP"] = ip
            elif tech == BypassTechnique.HEADER_X_ORIGINATING_IP:
                headers["X-Originating-IP"] = ip
            elif tech == BypassTechnique.HEADER_CF_CONNECTING_IP:
                headers["CF-Connecting-IP"] = ip
            elif tech == BypassTechnique.HEADER_TRUE_CLIENT_IP:
                headers["True-Client-IP"] = ip
            elif tech == BypassTechnique.HEADER_FORWARDED:
                headers["Forwarded"] = f"for={ip}"

        return headers

    def to_dict(self) -> dict[str, Any]:
        """Serialize strategy to dict."""
        return {
            "vendor": self.vendor.value,
            "techniques": [t.value for t in self.techniques],
            "vendor_headers": dict(self.vendor_headers),
            "description": self.description,
            "notes": self.notes,
            "success_rate": self.success_rate,
        }


# Pre-built CDN bypass strategies
_CDN_STRATEGIES: dict[str, CDNBypassStrategy] = {}


def _build_cdn_strategies() -> dict[str, CDNBypassStrategy]:
    """Build per-vendor CDN bypass strategies."""
    strategies: dict[str, CDNBypassStrategy] = {}

    # Cloudflare
    strategies["cloudflare"] = CDNBypassStrategy(
        vendor=CDNVendor.CLOUDFLARE,
        techniques=[
            BypassTechnique.HEADER_CF_CONNECTING_IP,
            BypassTechnique.HEADER_TRUE_CLIENT_IP,
            BypassTechnique.HEADER_XFF,
            BypassTechnique.DNS_HISTORY,
            BypassTechnique.SUBDOMAIN_ENUM,
            BypassTechnique.CERT_TRANSPARENCY,
        ],
        vendor_headers={
            "CF-Connecting-IP": "127.0.0.1",
            "X-Forwarded-Proto": "https",
        },
        description=(
            "Cloudflare bypass: CF-Connecting-IP spoofing, DNS history "
            "for origin discovery, subdomain enumeration for leaked origins"
        ),
        notes="Cloudflare validates CF-Connecting-IP in some configurations",
        success_rate=0.40,
    )

    # Akamai
    strategies["akamai"] = CDNBypassStrategy(
        vendor=CDNVendor.AKAMAI,
        techniques=[
            BypassTechnique.HEADER_TRUE_CLIENT_IP,
            BypassTechnique.HEADER_XFF,
            BypassTechnique.HOST_OVERRIDE,
            BypassTechnique.DNS_HISTORY,
            BypassTechnique.ERROR_PAGE_LEAK,
        ],
        vendor_headers={
            "True-Client-IP": "10.0.0.1",
            "Pragma": "akamai-x-get-cache-key",
        },
        description="Akamai bypass: True-Client-IP header, Pragma debug headers",
        notes="The Pragma header may reveal cache keys and origin info",
        success_rate=0.35,
    )

    # AWS CloudFront
    strategies["aws_cloudfront"] = CDNBypassStrategy(
        vendor=CDNVendor.AWS_CLOUDFRONT,
        techniques=[
            BypassTechnique.HEADER_XFF,
            BypassTechnique.HOST_OVERRIDE,
            BypassTechnique.DNS_HISTORY,
            BypassTechnique.CERT_TRANSPARENCY,
            BypassTechnique.ERROR_PAGE_LEAK,
        ],
        vendor_headers={
            "X-Forwarded-For": "10.0.0.1",
            "X-Amz-Cf-Id": "bypass-probe",
        },
        description="CloudFront bypass: XFF trust, direct S3/ALB origin access",
        notes="CloudFront passes XFF to origin; error pages may reveal S3 bucket or ALB",
        success_rate=0.45,
    )

    # Fastly
    strategies["fastly"] = CDNBypassStrategy(
        vendor=CDNVendor.FASTLY,
        techniques=[
            BypassTechnique.HEADER_XFF,
            BypassTechnique.HEADER_X_REAL_IP,
            BypassTechnique.HOST_OVERRIDE,
            BypassTechnique.DNS_HISTORY,
        ],
        vendor_headers={
            "Fastly-Debug": "1",
            "X-Forwarded-For": "127.0.0.1",
        },
        description="Fastly bypass: Debug header for cache info, XFF spoofing",
        notes="Fastly-Debug header reveals cache state and shield POP",
        success_rate=0.40,
    )

    # Imperva / Incapsula
    strategies["imperva"] = CDNBypassStrategy(
        vendor=CDNVendor.IMPERVA,
        techniques=[
            BypassTechnique.HEADER_X_REAL_IP,
            BypassTechnique.HEADER_XFF,
            BypassTechnique.DNS_HISTORY,
            BypassTechnique.SUBDOMAIN_ENUM,
            BypassTechnique.MAIL_HEADER_LEAK,
        ],
        vendor_headers={
            "X-Real-IP": "10.0.0.1",
        },
        description=(
            "Imperva/Incapsula bypass: Origin often discoverable via "
            "DNS history or mail server headers"
        ),
        success_rate=0.50,
    )

    # Sucuri
    strategies["sucuri"] = CDNBypassStrategy(
        vendor=CDNVendor.SUCURI,
        techniques=[
            BypassTechnique.HEADER_XFF,
            BypassTechnique.HEADER_X_REAL_IP,
            BypassTechnique.DNS_HISTORY,
            BypassTechnique.ERROR_PAGE_LEAK,
        ],
        vendor_headers={
            "X-Sucuri-ClientIP": "127.0.0.1",
            "X-Forwarded-For": "10.0.0.1",
        },
        description="Sucuri bypass: X-Sucuri-ClientIP header, DNS history lookup",
        success_rate=0.55,
    )

    # Azure CDN / Front Door
    strategies["azure_cdn"] = CDNBypassStrategy(
        vendor=CDNVendor.AZURE_CDN,
        techniques=[
            BypassTechnique.HEADER_XFF,
            BypassTechnique.HOST_OVERRIDE,
            BypassTechnique.CERT_TRANSPARENCY,
            BypassTechnique.DNS_HISTORY,
        ],
        vendor_headers={
            "X-Azure-ClientIP": "10.0.0.1",
            "X-Forwarded-For": "10.0.0.1",
        },
        description="Azure CDN bypass: XFF spoofing, direct origin via Host header",
        success_rate=0.40,
    )

    # GCP Cloud Armor
    strategies["gcp_cloud_armor"] = CDNBypassStrategy(
        vendor=CDNVendor.GCP_CLOUD_ARMOR,
        techniques=[
            BypassTechnique.HEADER_XFF,
            BypassTechnique.HOST_OVERRIDE,
            BypassTechnique.DNS_HISTORY,
        ],
        vendor_headers={
            "X-Forwarded-For": "10.0.0.1",
            "X-Cloud-Trace-Context": "bypass/0;o=1",
        },
        description="GCP Cloud Armor bypass: XFF chain, trace context header",
        success_rate=0.35,
    )

    # Generic fallback
    strategies["generic"] = CDNBypassStrategy(
        vendor=CDNVendor.GENERIC,
        techniques=[
            BypassTechnique.HEADER_XFF,
            BypassTechnique.HEADER_X_REAL_IP,
            BypassTechnique.HEADER_X_ORIGINATING_IP,
            BypassTechnique.HEADER_X_CLIENT_IP,
            BypassTechnique.HEADER_FORWARDED,
            BypassTechnique.DNS_HISTORY,
        ],
        vendor_headers={
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
        },
        description="Generic bypass: broad IP header spoofing + DNS history",
        success_rate=0.30,
    )

    return strategies


_CDN_STRATEGIES.update(_build_cdn_strategies())


def get_cdn_strategy(vendor: CDNVendor | str) -> CDNBypassStrategy:
    """Get the bypass strategy for a CDN vendor.

    Args:
        vendor: CDN vendor enum or string name.

    Returns:
        CDNBypassStrategy for the vendor, or generic fallback.
    """
    if isinstance(vendor, CDNVendor):
        key = vendor.value
    else:
        key = str(vendor).lower()
    return _CDN_STRATEGIES.get(key, _CDN_STRATEGIES["generic"])


def get_all_strategies() -> dict[str, CDNBypassStrategy]:
    """Return all CDN bypass strategies."""
    return dict(_CDN_STRATEGIES)


# ============================================================================
# Origin Discovery (Cycles 129–133)
# ============================================================================


@dataclass
class OriginHint:
    """A hint about the origin server behind a CDN.

    Contains a possible origin IP/hostname and the technique
    that would produce it.
    """
    technique: BypassTechnique
    value: str                      # IP or hostname
    confidence: float = 0.0         # 0.0–1.0
    source: str = ""                # where the hint came from
    verified: bool = False          # whether we confirmed it

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "technique": self.technique.value,
            "value": self.value,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "verified": self.verified,
        }


class OriginDiscovery:
    """Generates origin discovery hints for a target behind a CDN.

    Does not perform actual network requests — generates the
    *strategies* and expected data sources for origin discovery.
    Actual resolution is left to the scan modules.
    """

    def __init__(self) -> None:
        self._known_origins: dict[str, list[OriginHint]] = {}

    def get_hints(
        self,
        target: str,
        vendor: CDNVendor | str = CDNVendor.UNKNOWN,
    ) -> list[OriginHint]:
        """Generate origin discovery hints for a target.

        Args:
            target: Domain or hostname.
            vendor: CDN vendor if known.

        Returns:
            List of OriginHint strategies to try.
        """
        hints: list[OriginHint] = []
        strategy = get_cdn_strategy(vendor)

        # DNS history technique
        if BypassTechnique.DNS_HISTORY in strategy.techniques:
            hints.append(OriginHint(
                technique=BypassTechnique.DNS_HISTORY,
                value=target,
                confidence=0.60,
                source="SecurityTrails/ViewDNS historical A records",
            ))

        # Subdomain enumeration
        if BypassTechnique.SUBDOMAIN_ENUM in strategy.techniques:
            common_subs = [
                f"direct.{target}",
                f"origin.{target}",
                f"backend.{target}",
                f"real.{target}",
                f"mail.{target}",
                f"ftp.{target}",
                f"dev.{target}",
                f"staging.{target}",
                f"api.{target}",
                f"internal.{target}",
                f"admin.{target}",
                f"cpanel.{target}",
            ]
            for sub in common_subs:
                hints.append(OriginHint(
                    technique=BypassTechnique.SUBDOMAIN_ENUM,
                    value=sub,
                    confidence=0.35,
                    source=f"Subdomain probe: {sub}",
                ))

        # Certificate transparency logs
        if BypassTechnique.CERT_TRANSPARENCY in strategy.techniques:
            hints.append(OriginHint(
                technique=BypassTechnique.CERT_TRANSPARENCY,
                value=target,
                confidence=0.50,
                source="crt.sh / CT log SAN enumeration",
            ))

        # Error page origin leak
        if BypassTechnique.ERROR_PAGE_LEAK in strategy.techniques:
            hints.append(OriginHint(
                technique=BypassTechnique.ERROR_PAGE_LEAK,
                value=target,
                confidence=0.40,
                source="Trigger error pages (404/500) to leak origin headers",
            ))

        # Mail header leak
        if BypassTechnique.MAIL_HEADER_LEAK in strategy.techniques:
            hints.append(OriginHint(
                technique=BypassTechnique.MAIL_HEADER_LEAK,
                value=f"mail.{target}",
                confidence=0.55,
                source="MX records + email header Received-by analysis",
            ))

        return hints

    def register_origin(self, target: str, hint: OriginHint) -> None:
        """Register a discovered origin for a target.

        Args:
            target: Domain name.
            hint: The origin hint with verified=True if confirmed.
        """
        if target not in self._known_origins:
            self._known_origins[target] = []
        self._known_origins[target].append(hint)

    def get_known_origins(self, target: str) -> list[OriginHint]:
        """Get previously discovered origins for a target.

        Args:
            target: Domain name.

        Returns:
            List of known origin hints.
        """
        return list(self._known_origins.get(target, []))

    def get_best_origin(self, target: str) -> OriginHint | None:
        """Get the highest-confidence origin for a target.

        Args:
            target: Domain name.

        Returns:
            Best origin hint, or None.
        """
        origins = self._known_origins.get(target, [])
        if not origins:
            return None
        # Prefer verified, then highest confidence
        return max(
            origins,
            key=lambda h: (h.verified, h.confidence),
        )

    def clear(self, target: str | None = None) -> None:
        """Clear origin data.

        Args:
            target: If given, clear only that target. Otherwise clear all.
        """
        if target:
            self._known_origins.pop(target, None)
        else:
            self._known_origins.clear()


# ============================================================================
# Cache Analysis (Cycles 133–136)
# ============================================================================


@dataclass
class CacheAnalysis:
    """Result of analyzing cache behavior for a URL/resource.

    Provides intelligence about how the CDN caches the resource,
    useful for finding cache-busting opportunities and understanding
    CDN behavior.
    """
    url: str
    is_cached: bool = False
    cache_status: str = ""              # HIT/MISS/BYPASS/DYNAMIC etc.
    cache_ttl: int = 0                  # seconds
    varies_on: list[str] = field(default_factory=list)  # Vary header values
    cache_key_components: list[str] = field(default_factory=list)
    cdn_vendor: str = ""
    is_dynamic: bool = False            # True if content appears dynamic
    cacheable_path: bool = False        # True if path looks cacheable
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "url": self.url,
            "is_cached": self.is_cached,
            "cache_status": self.cache_status,
            "cache_ttl": self.cache_ttl,
            "varies_on": list(self.varies_on),
            "cache_key_components": list(self.cache_key_components),
            "cdn_vendor": self.cdn_vendor,
            "is_dynamic": self.is_dynamic,
            "cacheable_path": self.cacheable_path,
            "notes": list(self.notes),
        }


# Cache status header names used by various CDNs
_CACHE_STATUS_HEADERS = [
    "CF-Cache-Status",        # Cloudflare
    "X-Cache",                # CloudFront, Fastly, generic
    "X-Cache-Status",         # Nginx
    "X-Drupal-Cache",         # Drupal
    "X-Varnish",              # Varnish
    "X-Proxy-Cache",          # Squid
    "Akamai-Cache-Status",    # Akamai
    "X-Fastly-Request-ID",    # Fastly (presence = CDN)
    "X-Served-By",            # Fastly
    "X-CDN",                  # Generic CDN indicator
    "X-Edge-Cache",           # Edge caches
    "Age",                    # RFC — indicates cached response
]

# Patterns indicating the resource was served from cache
_CACHE_HIT_PATTERNS = re.compile(
    r"\b(HIT|hit|STALE|stale|REVALIDATED)\b", re.IGNORECASE,
)
_CACHE_MISS_PATTERNS = re.compile(
    r"\b(MISS|miss|BYPASS|bypass|EXPIRED|expired|DYNAMIC|dynamic)\b",
    re.IGNORECASE,
)

# File extensions that are typically cached by CDNs
_CACHEABLE_EXTENSIONS = {
    ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".webp", ".avif", ".mp4",
    ".webm", ".pdf", ".zip", ".gz",
}


class CacheAnalyzer:
    """Analyze cache behavior from response headers.

    Inspects CDN cache status headers to understand caching behavior
    and identify opportunities for cache-busting or bypassing.
    """

    def analyze(
        self,
        url: str,
        response_headers: dict[str, str],
        status_code: int = 200,
    ) -> CacheAnalysis:
        """Analyze cache behavior for a response.

        Args:
            url: The requested URL.
            response_headers: Response headers (case-insensitive lookup).
            status_code: HTTP status code.

        Returns:
            CacheAnalysis with detected cache behavior.
        """
        # Normalize headers to case-insensitive
        headers = {k.lower(): v for k, v in response_headers.items()}
        result = CacheAnalysis(url=url)

        # Detect CDN vendor from headers
        result.cdn_vendor = self._detect_cdn(headers)

        # Extract cache status
        for h in _CACHE_STATUS_HEADERS:
            val = headers.get(h.lower(), "")
            if val:
                result.cache_status = val
                if _CACHE_HIT_PATTERNS.search(val):
                    result.is_cached = True
                elif _CACHE_MISS_PATTERNS.search(val):
                    result.is_cached = False
                break

        # Check Age header — presence implies caching
        age = headers.get("age", "")
        if age and age.isdigit():
            age_sec = int(age)
            if age_sec > 0:
                result.is_cached = True
                result.cache_ttl = max(result.cache_ttl, age_sec)
                result.notes.append(f"Age header indicates {age_sec}s since cache fill")

        # Parse Cache-Control
        cc = headers.get("cache-control", "")
        if cc:
            result.cache_key_components.append(f"Cache-Control: {cc}")
            if "no-cache" in cc or "no-store" in cc or "private" in cc:
                result.is_dynamic = True
                result.notes.append("Cache-Control prevents caching")
            elif "max-age=" in cc:
                match = re.search(r"max-age=(\d+)", cc)
                if match:
                    result.cache_ttl = int(match.group(1))

        # Parse Vary header
        vary = headers.get("vary", "")
        if vary:
            result.varies_on = [v.strip() for v in vary.split(",") if v.strip()]
            result.cache_key_components.append(f"Vary: {vary}")

        # Check if path looks cacheable (static asset extensions)
        path = url.rsplit("?", 1)[0]  # strip query string
        ext = ""
        if "." in path.rsplit("/", 1)[-1]:
            ext = "." + path.rsplit(".", 1)[-1].lower()
        result.cacheable_path = ext in _CACHEABLE_EXTENSIONS

        # Dynamic content indicators
        if status_code in (301, 302, 303, 307, 308):
            result.is_dynamic = True
            result.notes.append("Redirect response — typically not cached")
        if status_code >= 400:
            result.notes.append(f"Error status {status_code} — CDN may cache or pass through")

        # Set-Cookie implies dynamic
        if "set-cookie" in headers:
            result.is_dynamic = True
            result.notes.append("Set-Cookie present — response is user-specific")

        return result

    def _detect_cdn(self, headers: dict[str, str]) -> str:
        """Detect CDN vendor from response headers."""
        # Cloudflare
        if "cf-ray" in headers or "cf-cache-status" in headers:
            return "cloudflare"
        # Akamai
        if any(k.startswith("x-akamai") for k in headers):
            return "akamai"
        # CloudFront
        if "x-amz-cf-id" in headers or "x-amz-cf-pop" in headers:
            return "cloudfront"
        # Fastly
        if "x-fastly-request-id" in headers or "fastly-debug" in headers:
            return "fastly"
        # Varnish
        if "x-varnish" in headers:
            return "varnish"
        # StackPath / MaxCDN
        if "x-cdn" in headers and "stackpath" in headers.get("x-cdn", "").lower():
            return "stackpath"
        # Generic
        server = headers.get("server", "").lower()
        if "cloudflare" in server:
            return "cloudflare"
        if "akamaighost" in server:
            return "akamai"

        return ""


# ============================================================================
# Path Mutation / URL Encoding Bypass (Cycles 135–137)
# ============================================================================


@dataclass
class PathMutation:
    """A URL path mutation for WAF rule bypassing."""
    original: str
    mutated: str
    technique: str  # description of the mutation
    risk_level: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "mutated": self.mutated,
            "technique": self.technique,
            "risk_level": self.risk_level,
        }


class PathMutator:
    """Generate URL path mutations to bypass WAF rules.

    WAFs often match URL patterns with regex — encoding tricks
    can bypass overly-specific rules.
    """

    def mutate(self, path: str) -> list[PathMutation]:
        """Generate mutations for a path.

        Args:
            path: Original URL path (e.g. /admin/login).

        Returns:
            List of PathMutation alternatives.
        """
        mutations: list[PathMutation] = []

        # 1. Double URL encoding
        double_encoded = self._double_encode(path)
        if double_encoded != path:
            mutations.append(PathMutation(
                original=path,
                mutated=double_encoded,
                technique="double_url_encode",
            ))

        # 2. Path traversal normalization
        # /admin → /./admin, /../admin/../admin
        mutations.append(PathMutation(
            original=path,
            mutated=f"/.{path}",
            technique="dot_prefix",
        ))

        # 3. Case variation (for case-insensitive servers)
        case_var = self._randomize_case(path)
        if case_var != path:
            mutations.append(PathMutation(
                original=path,
                mutated=case_var,
                technique="case_variation",
            ))

        # 4. Trailing dot / slash
        mutations.append(PathMutation(
            original=path,
            mutated=path + "/",
            technique="trailing_slash",
        ))
        mutations.append(PathMutation(
            original=path,
            mutated=path + "/.",
            technique="trailing_dot_slash",
        ))

        # 5. Null byte (legacy bypass — rarely works on modern systems)
        mutations.append(PathMutation(
            original=path,
            mutated=path + "%00",
            technique="null_byte",
            risk_level="high",
        ))

        # 6. Unicode normalization
        unicode_path = self._unicode_normalize(path)
        if unicode_path != path:
            mutations.append(PathMutation(
                original=path,
                mutated=unicode_path,
                technique="unicode_normalization",
            ))

        # 7. Semicolon path parameter
        if "/" in path and len(path) > 1:
            parts = path.rsplit("/", 1)
            mutations.append(PathMutation(
                original=path,
                mutated=f"{parts[0]};bypass=1/{parts[1]}",
                technique="semicolon_parameter",
            ))

        # 8. Fragment injection
        mutations.append(PathMutation(
            original=path,
            mutated=path + "#",
            technique="fragment_injection",
        ))

        return mutations

    def _double_encode(self, path: str) -> str:
        """Double URL-encode special characters."""
        result: list[str] = []
        for ch in path:
            if ch == "/":
                result.append("%252F")
            elif ch == " ":
                result.append("%2520")
            elif ch == ".":
                result.append("%252E")
            else:
                result.append(ch)
        return "".join(result)

    def _randomize_case(self, path: str) -> str:
        """Randomly change case of alphabetic characters."""
        result: list[str] = []
        for i, ch in enumerate(path):
            if ch.isalpha() and i % 3 == 0:
                result.append(ch.upper() if ch.islower() else ch.lower())
            else:
                result.append(ch)
        return "".join(result)

    def _unicode_normalize(self, path: str) -> str:
        """Replace characters with Unicode equivalents."""
        replacements = {
            "/": "\uff0f",  # Fullwidth solidus
            ".": "\uff0e",  # Fullwidth full stop
            "-": "\u2010",  # Hyphen
        }
        result: list[str] = []
        for ch in path:
            if ch in replacements and random.random() < 0.3:
                result.append(replacements[ch])
            else:
                result.append(ch)
        return "".join(result)


# ============================================================================
# Method Override Bypass (Cycles 137–138)
# ============================================================================


@dataclass
class MethodOverride:
    """An HTTP method override to bypass method-based WAF rules."""
    original_method: str
    override_method: str
    headers: dict[str, str]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_method": self.original_method,
            "override_method": self.override_method,
            "headers": dict(self.headers),
            "description": self.description,
        }


def generate_method_overrides(
    target_method: str = "GET",
) -> list[MethodOverride]:
    """Generate method override combinations.

    Some WAFs only inspect GET/POST — using method override headers
    can bypass method-specific rules.

    Args:
        target_method: The HTTP method you want executed.

    Returns:
        List of MethodOverride alternatives.
    """
    overrides: list[MethodOverride] = []

    # X-HTTP-Method-Override
    overrides.append(MethodOverride(
        original_method="POST",
        override_method=target_method,
        headers={"X-HTTP-Method-Override": target_method},
        description=f"POST with X-HTTP-Method-Override: {target_method}",
    ))

    # X-Method-Override
    overrides.append(MethodOverride(
        original_method="POST",
        override_method=target_method,
        headers={"X-Method-Override": target_method},
        description=f"POST with X-Method-Override: {target_method}",
    ))

    # X-HTTP-Method
    overrides.append(MethodOverride(
        original_method="POST",
        override_method=target_method,
        headers={"X-HTTP-Method": target_method},
        description=f"POST with X-HTTP-Method: {target_method}",
    ))

    # _method parameter (Rails/Laravel convention)
    overrides.append(MethodOverride(
        original_method="POST",
        override_method=target_method,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        description=f"POST with _method={target_method} body parameter",
    ))

    return overrides


# ============================================================================
# WAF Bypass Engine — Façade (Cycles 138–140)
# ============================================================================


class WAFBypassEngine:
    """Unified WAF/CDN bypass engine combining all S-007 components.

    Provides a single entry point for:
    - Header spoofing profiles
    - CDN-specific bypass strategies
    - Origin discovery hints
    - Cache behavior analysis
    - Path mutation
    - Method override generation

    Usage::

        engine = WAFBypassEngine()

        # Get bypass headers for Cloudflare
        headers = engine.get_bypass_headers(CDNVendor.CLOUDFLARE)

        # Discover origin behind CDN
        hints = engine.get_origin_hints("example.com", CDNVendor.CLOUDFLARE)
    """

    def __init__(self) -> None:
        self._origin_discovery = OriginDiscovery()
        self._cache_analyzer = CacheAnalyzer()
        self._path_mutator = PathMutator()
        self._bypass_stats: dict[str, dict[str, int]] = {}
        self._lock = threading.Lock()

    @property
    def origin_discovery(self) -> OriginDiscovery:
        """Access the origin discovery component."""
        return self._origin_discovery

    @property
    def cache_analyzer(self) -> CacheAnalyzer:
        """Access the cache analyzer component."""
        return self._cache_analyzer

    @property
    def path_mutator(self) -> PathMutator:
        """Access the path mutator component."""
        return self._path_mutator

    # ── Header Operations ────────────────────────────────────

    def get_bypass_headers(
        self,
        vendor: CDNVendor | str = CDNVendor.GENERIC,
        target_ip: str | None = None,
    ) -> dict[str, str]:
        """Get bypass headers for a CDN vendor.

        Args:
            vendor: CDN vendor enum or string.
            target_ip: Optional IP to include in headers.

        Returns:
            Dict of header name→value for bypass.
        """
        strategy = get_cdn_strategy(vendor)
        return strategy.get_headers(target_ip)

    def get_all_spoof_headers(
        self,
        ip: str | None = None,
    ) -> list[SpoofHeader]:
        """Get all IP-spoofing headers.

        Args:
            ip: IP to use in headers. If None, random internal IP.

        Returns:
            List of SpoofHeader entries.
        """
        return generate_spoof_headers(ip)

    def get_spoof_profile(self, name: str) -> HeaderSpoofProfile | None:
        """Get a header spoof profile by name.

        Args:
            name: Profile name (e.g. "google_crawler").

        Returns:
            HeaderSpoofProfile or None.
        """
        return get_profile(name)

    def get_all_profiles(self) -> dict[str, HeaderSpoofProfile]:
        """Get all available spoof profiles."""
        return get_all_profiles()

    def get_profiles_by_type(
        self,
        client_type: ClientType,
    ) -> list[HeaderSpoofProfile]:
        """Get spoof profiles for a client type."""
        return get_profiles_by_client_type(client_type)

    # ── CDN Strategy ─────────────────────────────────────────

    def get_cdn_strategy(
        self,
        vendor: CDNVendor | str,
    ) -> CDNBypassStrategy:
        """Get bypass strategy for a CDN vendor."""
        return get_cdn_strategy(vendor)

    def get_all_strategies(self) -> dict[str, CDNBypassStrategy]:
        """Get all CDN bypass strategies."""
        return get_all_strategies()

    # ── Origin Discovery ──────────────────────────────────────

    def get_origin_hints(
        self,
        target: str,
        vendor: CDNVendor | str = CDNVendor.UNKNOWN,
    ) -> list[OriginHint]:
        """Get origin discovery hints for a target."""
        return self._origin_discovery.get_hints(target, vendor)

    def register_origin(self, target: str, hint: OriginHint) -> None:
        """Register a discovered origin."""
        self._origin_discovery.register_origin(target, hint)

    def get_known_origins(self, target: str) -> list[OriginHint]:
        """Get known origins for a target."""
        return self._origin_discovery.get_known_origins(target)

    def get_best_origin(self, target: str) -> OriginHint | None:
        """Get the best known origin for a target."""
        return self._origin_discovery.get_best_origin(target)

    # ── Cache Analysis ────────────────────────────────────────

    def analyze_cache(
        self,
        url: str,
        response_headers: dict[str, str],
        status_code: int = 200,
    ) -> CacheAnalysis:
        """Analyze cache behavior from response headers."""
        return self._cache_analyzer.analyze(url, response_headers, status_code)

    # ── Path Mutation ─────────────────────────────────────────

    def mutate_path(self, path: str) -> list[PathMutation]:
        """Generate path mutations for WAF bypass."""
        return self._path_mutator.mutate(path)

    # ── Method Override ───────────────────────────────────────

    def get_method_overrides(
        self,
        target_method: str = "GET",
    ) -> list[MethodOverride]:
        """Generate HTTP method override combinations."""
        return generate_method_overrides(target_method)

    # ── Statistics ────────────────────────────────────────────

    def record_bypass_attempt(
        self,
        vendor: str,
        technique: str,
        success: bool,
    ) -> None:
        """Record a bypass attempt result.

        Args:
            vendor: CDN vendor name.
            technique: Technique used.
            success: Whether the bypass worked.
        """
        with self._lock:
            key = f"{vendor}:{technique}"
            if key not in self._bypass_stats:
                self._bypass_stats[key] = {"attempts": 0, "successes": 0}
            self._bypass_stats[key]["attempts"] += 1
            if success:
                self._bypass_stats[key]["successes"] += 1

    def get_bypass_stats(self) -> dict[str, dict[str, Any]]:
        """Get bypass attempt statistics.

        Returns:
            Dict of "vendor:technique" → {attempts, successes, success_rate}.
        """
        with self._lock:
            result: dict[str, dict[str, Any]] = {}
            for key, stats in self._bypass_stats.items():
                attempts = stats["attempts"]
                successes = stats["successes"]
                result[key] = {
                    "attempts": attempts,
                    "successes": successes,
                    "success_rate": successes / attempts if attempts > 0 else 0.0,
                }
            return result

    def get_vendor_success_rates(self) -> dict[str, float]:
        """Get per-vendor success rates.

        Returns:
            Dict of vendor → success_rate.
        """
        with self._lock:
            vendor_stats: dict[str, dict[str, int]] = {}
            for key, stats in self._bypass_stats.items():
                vendor = key.split(":")[0]
                if vendor not in vendor_stats:
                    vendor_stats[vendor] = {"attempts": 0, "successes": 0}
                vendor_stats[vendor]["attempts"] += stats["attempts"]
                vendor_stats[vendor]["successes"] += stats["successes"]

            return {
                v: s["successes"] / s["attempts"] if s["attempts"] > 0 else 0.0
                for v, s in vendor_stats.items()
            }

    def reset_stats(self) -> None:
        """Clear all bypass statistics."""
        with self._lock:
            self._bypass_stats.clear()

    # ── Dashboard / Summary ───────────────────────────────────

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get dashboard-ready summary of bypass capabilities.

        Returns:
            Dict with bypass statistics, strategies, and profile counts.
        """
        return {
            "strategies_count": len(_CDN_STRATEGIES),
            "profiles_count": len(_DEFAULT_PROFILES),
            "techniques_count": len(BypassTechnique),
            "bypass_stats": self.get_bypass_stats(),
            "vendor_success_rates": self.get_vendor_success_rates(),
            "available_strategies": list(_CDN_STRATEGIES.keys()),
            "available_profiles": list(_DEFAULT_PROFILES.keys()),
        }
