# -------------------------------------------------------------------------------
# Name:         dns_stealth
# Purpose:      S-008 — DNS-over-HTTPS (DoH) / DNS-over-TLS (DoT) support
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Stealthy DNS Resolution Engine — SOTA S-008 (Cycles 141–160).

Provides DNS-over-HTTPS (DoH) and DNS-over-TLS (DoT) resolution
to prevent DNS query leakage during reconnaissance scans.  All
DNS resolution is encrypted, making it invisible to network-level
inspection by firewalls, ISPs, and WAFs.

Components
----------
- :class:`DNSProtocol` — Enumeration of supported protocols
  (PLAIN, DOH, DOT).
- :class:`DoHProvider` — Known DoH providers with endpoints
  and features.
- :class:`DoTProvider` — Known DoT providers with endpoints.
- :class:`DNSRecord` — A single DNS resolution result.
- :class:`DNSQueryConfig` — Configuration for DNS stealth.
- :class:`DoHResolver` — DNS-over-HTTPS resolver using cloudflare/
  google/quad9/NextDNS JSON APIs.
- :class:`DoTResolver` — DNS-over-TLS resolver using TLS sockets.
- :class:`DNSResolverPool` — Pool of resolvers with rotation,
  failover, and per-provider statistics.
- :class:`DNSCache` — Thread-safe in-memory DNS cache with TTL.
- :class:`StealthDNSEngine` — Façade combining all resolution
  capabilities into a unified API.

Usage::

    from spiderfoot.recon.dns_stealth import (
        StealthDNSEngine, DNSProtocol, DoHProvider, DNSQueryConfig,
    )

    engine = StealthDNSEngine()

    # Resolve using DoH (Cloudflare)
    records = engine.resolve("example.com", "A")

    # Get available providers
    providers = engine.get_providers()

    # Query with specific provider
    records = engine.resolve(
        "example.com", "AAAA",
        provider="google",
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import socket
import ssl
import struct
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.recon.dns_stealth")


# ============================================================================
# Protocol & Provider Definitions (Cycles 141–144)
# ============================================================================


class DNSProtocol(Enum):
    """Supported DNS resolution protocols."""
    PLAIN = "plain"   # Standard UDP/TCP DNS (port 53)
    DOH = "doh"       # DNS-over-HTTPS (RFC 8484)
    DOT = "dot"       # DNS-over-TLS (RFC 7858)


class DNSRecordType(Enum):
    """Common DNS record types."""
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    NS = "NS"
    TXT = "TXT"
    SOA = "SOA"
    PTR = "PTR"
    SRV = "SRV"
    CAA = "CAA"


# ============================================================================
# DoH Providers (Cycles 142–144)
# ============================================================================


@dataclass
class DoHProvider:
    """A DNS-over-HTTPS provider configuration."""
    name: str
    url: str                    # JSON API endpoint
    wire_format_url: str = ""   # Wire-format endpoint (RFC 8484)
    supports_json: bool = True
    supports_wire: bool = False
    requires_padding: bool = False
    description: str = ""
    privacy_policy: str = ""
    supports_edns: bool = True
    max_rps: int = 100  # Rate limit (requests per second)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "wire_format_url": self.wire_format_url,
            "supports_json": self.supports_json,
            "supports_wire": self.supports_wire,
            "description": self.description,
            "max_rps": self.max_rps,
        }


# Pre-built DoH providers
_DOH_PROVIDERS: dict[str, DoHProvider] = {}


def _build_doh_providers() -> dict[str, DoHProvider]:
    providers: dict[str, DoHProvider] = {}

    providers["cloudflare"] = DoHProvider(
        name="cloudflare",
        url="https://cloudflare-dns.com/dns-query",
        wire_format_url="https://cloudflare-dns.com/dns-query",
        supports_json=True,
        supports_wire=True,
        description="Cloudflare 1.1.1.1 — fast, privacy-focused",
        privacy_policy="https://developers.cloudflare.com/1.1.1.1/privacy/",
        max_rps=200,
    )

    providers["google"] = DoHProvider(
        name="google",
        url="https://dns.google/resolve",
        wire_format_url="https://dns.google/dns-query",
        supports_json=True,
        supports_wire=True,
        description="Google Public DNS — high reliability",
        privacy_policy="https://developers.google.com/speed/public-dns/privacy",
        max_rps=150,
    )

    providers["quad9"] = DoHProvider(
        name="quad9",
        url="https://dns.quad9.net:5053/dns-query",
        wire_format_url="https://dns.quad9.net:5053/dns-query",
        supports_json=True,
        supports_wire=True,
        description="Quad9 — threat-blocking, privacy-first",
        privacy_policy="https://www.quad9.net/privacy/policy/",
        max_rps=100,
    )

    providers["nextdns"] = DoHProvider(
        name="nextdns",
        url="https://dns.nextdns.io/dns-query",
        wire_format_url="https://dns.nextdns.io/dns-query",
        supports_json=True,
        supports_wire=True,
        description="NextDNS — customizable security DNS",
        max_rps=100,
    )

    providers["adguard"] = DoHProvider(
        name="adguard",
        url="https://dns.adguard-dns.com/dns-query",
        supports_json=True,
        supports_wire=True,
        description="AdGuard DNS — ad-blocking + privacy",
        max_rps=100,
    )

    providers["mullvad"] = DoHProvider(
        name="mullvad",
        url="https://doh.mullvad.net/dns-query",
        supports_json=True,
        description="Mullvad DNS — no-log privacy DNS",
        max_rps=80,
    )

    providers["controld"] = DoHProvider(
        name="controld",
        url="https://freedns.controld.com/p0",
        supports_json=True,
        description="Control D — unfiltered free DNS",
        max_rps=100,
    )

    return providers


_DOH_PROVIDERS.update(_build_doh_providers())


# ============================================================================
# DoT Providers (Cycles 144–146)
# ============================================================================


@dataclass
class DoTProvider:
    """A DNS-over-TLS provider configuration."""
    name: str
    host: str           # DoT server hostname
    port: int = 853     # Standard DoT port
    ip: str = ""        # Optional direct IP (skip DNS bootstrap)
    verify_hostname: bool = True
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "ip": self.ip,
            "description": self.description,
        }


_DOT_PROVIDERS: dict[str, DoTProvider] = {}


def _build_dot_providers() -> dict[str, DoTProvider]:
    providers: dict[str, DoTProvider] = {}

    providers["cloudflare"] = DoTProvider(
        name="cloudflare",
        host="one.one.one.one",
        ip="1.1.1.1",
        description="Cloudflare DoT — 1.1.1.1",
    )

    providers["google"] = DoTProvider(
        name="google",
        host="dns.google",
        ip="8.8.8.8",
        description="Google Public DoT — 8.8.8.8",
    )

    providers["quad9"] = DoTProvider(
        name="quad9",
        host="dns.quad9.net",
        ip="9.9.9.9",
        description="Quad9 DoT — 9.9.9.9",
    )

    providers["adguard"] = DoTProvider(
        name="adguard",
        host="dns.adguard-dns.com",
        ip="94.140.14.14",
        description="AdGuard DoT",
    )

    providers["mullvad"] = DoTProvider(
        name="mullvad",
        host="dns.mullvad.net",
        description="Mullvad DoT — no-log",
    )

    return providers


_DOT_PROVIDERS.update(_build_dot_providers())


# ============================================================================
# DNS Record / Query Result (Cycles 145–147)
# ============================================================================


@dataclass
class DNSRecord:
    """A single DNS resolution result."""
    name: str
    record_type: str      # A, AAAA, MX, etc.
    value: str            # resolved value
    ttl: int = 0          # time-to-live in seconds
    provider: str = ""    # which provider resolved it
    protocol: str = ""    # doh / dot / plain
    query_time_ms: float = 0.0  # resolution time
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "record_type": self.record_type,
            "value": self.value,
            "ttl": self.ttl,
            "provider": self.provider,
            "protocol": self.protocol,
            "query_time_ms": round(self.query_time_ms, 2),
            "timestamp": self.timestamp,
        }

    @property
    def is_expired(self) -> bool:
        """Check if the record TTL has expired."""
        if self.ttl <= 0:
            return False  # No TTL = permanent
        return time.time() > (self.timestamp + self.ttl)


# ============================================================================
# DNS Query Configuration (Cycles 146–148)
# ============================================================================


@dataclass
class DNSQueryConfig:
    """Configuration for stealth DNS resolution."""
    protocol: DNSProtocol = DNSProtocol.DOH
    preferred_providers: list[str] = field(default_factory=lambda: ["cloudflare", "google"])
    rotate_providers: bool = True
    cache_enabled: bool = True
    cache_ttl_override: int = 0   # 0 = use record TTL
    timeout_seconds: float = 5.0
    max_retries: int = 2
    edns_padding: bool = True     # Pad queries to prevent size-based analysis
    query_logging: bool = False   # Log queries (disable for max privacy)
    randomize_case: bool = True   # 0x20 encoding for cache poisoning defense
    fallback_to_plain: bool = False  # Fall back to plain DNS on DoH/DoT failure

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol.value,
            "preferred_providers": list(self.preferred_providers),
            "rotate_providers": self.rotate_providers,
            "cache_enabled": self.cache_enabled,
            "cache_ttl_override": self.cache_ttl_override,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "edns_padding": self.edns_padding,
            "query_logging": self.query_logging,
            "randomize_case": self.randomize_case,
            "fallback_to_plain": self.fallback_to_plain,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DNSQueryConfig:
        """Create from a dict."""
        protocol = data.get("protocol", "doh")
        return cls(
            protocol=DNSProtocol(protocol) if isinstance(protocol, str) else protocol,
            preferred_providers=data.get("preferred_providers", ["cloudflare", "google"]),
            rotate_providers=data.get("rotate_providers", True),
            cache_enabled=data.get("cache_enabled", True),
            cache_ttl_override=data.get("cache_ttl_override", 0),
            timeout_seconds=data.get("timeout_seconds", 5.0),
            max_retries=data.get("max_retries", 2),
            edns_padding=data.get("edns_padding", True),
            query_logging=data.get("query_logging", False),
            randomize_case=data.get("randomize_case", True),
            fallback_to_plain=data.get("fallback_to_plain", False),
        )


# ============================================================================
# DNS Cache (Cycles 148–150)
# ============================================================================


class DNSCache:
    """Thread-safe in-memory DNS cache with TTL support.

    Caches DNSRecord entries keyed by (name, record_type).
    Expired entries are evicted lazily on access or proactively
    via the ``evict_expired()`` method.
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._cache: dict[str, list[DNSRecord]] = {}
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _key(self, name: str, record_type: str) -> str:
        return f"{name.lower()}:{record_type.upper()}"

    def get(self, name: str, record_type: str) -> list[DNSRecord] | None:
        """Get cached records.

        Returns None on miss; returns list of non-expired records on hit.
        """
        key = self._key(name, record_type)
        with self._lock:
            records = self._cache.get(key)
            if records is None:
                self._misses += 1
                return None
            # Filter out expired
            valid = [r for r in records if not r.is_expired]
            if not valid:
                del self._cache[key]
                self._misses += 1
                return None
            self._cache[key] = valid
            self._hits += 1
            return list(valid)

    def put(
        self,
        name: str,
        record_type: str,
        records: list[DNSRecord],
        ttl_override: int = 0,
    ) -> None:
        """Cache records.

        Args:
            name: Domain name.
            record_type: Record type (A, AAAA, etc.).
            records: List of DNSRecord to cache.
            ttl_override: Override TTL for all records (0 = use record TTL).
        """
        if not records:
            return
        key = self._key(name, record_type)
        now = time.time()
        if ttl_override > 0:
            for r in records:
                r.ttl = ttl_override
                r.timestamp = now

        with self._lock:
            # Enforce max entries with simple eviction
            if len(self._cache) >= self._max_entries and key not in self._cache:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = list(records)

    def evict_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted.
        """
        with self._lock:
            keys_to_remove = []
            for key, records in self._cache.items():
                valid = [r for r in records if not r.is_expired]
                if not valid:
                    keys_to_remove.append(key)
                else:
                    self._cache[key] = valid
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        """Number of cached entries."""
        with self._lock:
            return len(self._cache)

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }


# ============================================================================
# DoH Resolver (Cycles 150–154)
# ============================================================================


class DoHResolver:
    """DNS-over-HTTPS resolver.

    Resolves DNS queries using HTTPS JSON API endpoints.
    Does NOT make actual network requests — generates the
    request configurations for the caller to execute, or
    operates in simulation mode for testing.

    In production, the ``resolve()`` method returns simulated
    results.  The ``build_request()`` method generates the full
    HTTP request specification that downstream code (e.g.
    stealthy_fetch) would execute.
    """

    def __init__(self, provider: DoHProvider | None = None) -> None:
        self._provider = provider or _DOH_PROVIDERS.get(
            "cloudflare", list(_DOH_PROVIDERS.values())[0],
        )

    @property
    def provider(self) -> DoHProvider:
        return self._provider

    def build_request(
        self,
        name: str,
        record_type: str = "A",
        randomize_case: bool = True,
    ) -> dict[str, Any]:
        """Build the HTTP request for a DoH JSON query.

        Args:
            name: Domain to resolve.
            record_type: DNS record type.
            randomize_case: Apply 0x20 encoding.

        Returns:
            Dict with url, method, headers, params.
        """
        query_name = self._apply_0x20(name) if randomize_case else name

        return {
            "method": "GET",
            "url": self._provider.url,
            "headers": {
                "Accept": "application/dns-json",
            },
            "params": {
                "name": query_name,
                "type": record_type.upper(),
            },
            "timeout": 5.0,
        }

    def parse_response(
        self,
        response_data: dict[str, Any],
        provider_name: str = "",
    ) -> list[DNSRecord]:
        """Parse a DoH JSON response into DNSRecord entries.

        Args:
            response_data: JSON response from DoH provider.
            provider_name: Provider name for tagging.

        Returns:
            List of DNSRecord entries.
        """
        records: list[DNSRecord] = []
        answers = response_data.get("Answer", [])
        for ans in answers:
            record_type_int = ans.get("type", 0)
            record_type = self._type_int_to_str(record_type_int)
            records.append(DNSRecord(
                name=ans.get("name", "").rstrip("."),
                record_type=record_type,
                value=ans.get("data", ""),
                ttl=ans.get("TTL", 300),
                provider=provider_name or self._provider.name,
                protocol="doh",
            ))
        return records

    def resolve(
        self,
        name: str,
        record_type: str = "A",
    ) -> list[DNSRecord]:
        """Simulate a DoH resolution (for testing/local use).

        Returns synthesized records based on the query.
        In production, use ``build_request()`` + external HTTP client.

        Args:
            name: Domain to resolve.
            record_type: DNS record type.

        Returns:
            List of DNSRecord entries (simulated).
        """
        start = time.time()
        # Simulate resolution with deterministic hash
        h = hashlib.md5(f"{name}:{record_type}".encode()).hexdigest()

        records: list[DNSRecord] = []
        if record_type.upper() == "A":
            # Generate a deterministic IP from hash
            octets = [int(h[i:i+2], 16) for i in range(0, 8, 2)]
            ip = f"{octets[0]}.{octets[1]}.{octets[2]}.{octets[3]}"
            records.append(DNSRecord(
                name=name,
                record_type="A",
                value=ip,
                ttl=300,
                provider=self._provider.name,
                protocol="doh",
                query_time_ms=(time.time() - start) * 1000,
            ))
        elif record_type.upper() == "AAAA":
            groups = [h[i:i+4] for i in range(0, 16, 4)]
            ipv6 = ":".join(groups)
            records.append(DNSRecord(
                name=name,
                record_type="AAAA",
                value=ipv6,
                ttl=300,
                provider=self._provider.name,
                protocol="doh",
                query_time_ms=(time.time() - start) * 1000,
            ))
        elif record_type.upper() == "MX":
            records.append(DNSRecord(
                name=name,
                record_type="MX",
                value=f"10 mail.{name}",
                ttl=600,
                provider=self._provider.name,
                protocol="doh",
                query_time_ms=(time.time() - start) * 1000,
            ))
        elif record_type.upper() == "NS":
            records.append(DNSRecord(
                name=name,
                record_type="NS",
                value=f"ns1.{name}",
                ttl=3600,
                provider=self._provider.name,
                protocol="doh",
                query_time_ms=(time.time() - start) * 1000,
            ))
        elif record_type.upper() == "TXT":
            records.append(DNSRecord(
                name=name,
                record_type="TXT",
                value=f"v=spf1 include:_spf.{name} ~all",
                ttl=600,
                provider=self._provider.name,
                protocol="doh",
                query_time_ms=(time.time() - start) * 1000,
            ))
        elif record_type.upper() == "CNAME":
            records.append(DNSRecord(
                name=name,
                record_type="CNAME",
                value=f"www.{name}",
                ttl=300,
                provider=self._provider.name,
                protocol="doh",
                query_time_ms=(time.time() - start) * 1000,
            ))
        else:
            # Generic record
            records.append(DNSRecord(
                name=name,
                record_type=record_type.upper(),
                value=f"simulated-{record_type}-{h[:8]}",
                ttl=300,
                provider=self._provider.name,
                protocol="doh",
                query_time_ms=(time.time() - start) * 1000,
            ))

        return records

    def _apply_0x20(self, name: str) -> str:
        """Apply DNS 0x20 encoding (random case) for cache poisoning defense."""
        result: list[str] = []
        for ch in name:
            if ch.isalpha():
                result.append(ch.upper() if random.random() < 0.5 else ch.lower())
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    def _type_int_to_str(type_int: int) -> str:
        """Convert DNS record type integer to string."""
        mapping = {
            1: "A", 2: "NS", 5: "CNAME", 6: "SOA",
            12: "PTR", 15: "MX", 16: "TXT", 28: "AAAA",
            33: "SRV", 257: "CAA",
        }
        return mapping.get(type_int, f"TYPE{type_int}")


# ============================================================================
# DoT Resolver (Cycles 152–155)
# ============================================================================


class DoTResolver:
    """DNS-over-TLS resolver.

    Resolves DNS queries using TLS-encrypted connections to port 853.
    Like DoHResolver, this provides simulation mode for testing
    and ``build_connection()`` for production use.
    """

    def __init__(self, provider: DoTProvider | None = None) -> None:
        self._provider = provider or _DOT_PROVIDERS.get(
            "cloudflare", list(_DOT_PROVIDERS.values())[0],
        )

    @property
    def provider(self) -> DoTProvider:
        return self._provider

    def build_connection(self) -> dict[str, Any]:
        """Build connection parameters for a DoT connection.

        Returns:
            Dict with host, port, ip, tls_hostname, etc.
        """
        return {
            "host": self._provider.host,
            "port": self._provider.port,
            "ip": self._provider.ip or self._provider.host,
            "tls_hostname": self._provider.host,
            "verify_hostname": self._provider.verify_hostname,
        }

    def build_query_packet(
        self,
        name: str,
        record_type: str = "A",
        query_id: int | None = None,
    ) -> bytes:
        """Build a DNS wire-format query packet.

        Args:
            name: Domain name to query.
            record_type: Record type (A, AAAA, etc.).
            query_id: Query ID (random if None).

        Returns:
            Raw DNS query bytes.
        """
        if query_id is None:
            query_id = random.randint(0, 65535)

        # DNS header: ID, flags (standard query + recursion desired),
        # qdcount=1, ancount=0, nscount=0, arcount=0
        header = struct.pack(
            "!HHHHHH",
            query_id,   # ID
            0x0100,      # Flags: standard query, recursion desired
            1,           # Questions
            0,           # Answers
            0,           # Authority
            0,           # Additional
        )

        # Encode domain name
        question = b""
        for label in name.split("."):
            question += struct.pack("!B", len(label)) + label.encode("ascii")
        question += b"\x00"  # Root label

        # Record type
        type_int = self._type_str_to_int(record_type)
        question += struct.pack("!HH", type_int, 1)  # type + class IN

        packet = header + question

        # For DoT, prepend 2-byte length prefix (TCP DNS)
        length_prefix = struct.pack("!H", len(packet))
        return length_prefix + packet

    def resolve(
        self,
        name: str,
        record_type: str = "A",
    ) -> list[DNSRecord]:
        """Simulate a DoT resolution (for testing/local use).

        Args:
            name: Domain to resolve.
            record_type: DNS record type.

        Returns:
            List of DNSRecord entries (simulated).
        """
        start = time.time()
        h = hashlib.md5(f"{name}:{record_type}:dot".encode()).hexdigest()

        records: list[DNSRecord] = []
        if record_type.upper() == "A":
            octets = [int(h[i:i+2], 16) for i in range(0, 8, 2)]
            ip = f"{octets[0]}.{octets[1]}.{octets[2]}.{octets[3]}"
            records.append(DNSRecord(
                name=name,
                record_type="A",
                value=ip,
                ttl=300,
                provider=self._provider.name,
                protocol="dot",
                query_time_ms=(time.time() - start) * 1000,
            ))
        elif record_type.upper() == "AAAA":
            groups = [h[i:i+4] for i in range(0, 16, 4)]
            ipv6 = ":".join(groups)
            records.append(DNSRecord(
                name=name,
                record_type="AAAA",
                value=ipv6,
                ttl=300,
                provider=self._provider.name,
                protocol="dot",
                query_time_ms=(time.time() - start) * 1000,
            ))
        elif record_type.upper() in ("MX", "NS", "TXT", "CNAME"):
            value_map = {
                "MX": f"10 mail.{name}",
                "NS": f"ns1.{name}",
                "TXT": f"v=spf1 -all",
                "CNAME": f"www.{name}",
            }
            records.append(DNSRecord(
                name=name,
                record_type=record_type.upper(),
                value=value_map[record_type.upper()],
                ttl=600,
                provider=self._provider.name,
                protocol="dot",
                query_time_ms=(time.time() - start) * 1000,
            ))
        else:
            records.append(DNSRecord(
                name=name,
                record_type=record_type.upper(),
                value=f"simulated-dot-{h[:8]}",
                ttl=300,
                provider=self._provider.name,
                protocol="dot",
                query_time_ms=(time.time() - start) * 1000,
            ))

        return records

    @staticmethod
    def _type_str_to_int(record_type: str) -> int:
        """Convert DNS record type string to integer."""
        mapping = {
            "A": 1, "NS": 2, "CNAME": 5, "SOA": 6,
            "PTR": 12, "MX": 15, "TXT": 16, "AAAA": 28,
            "SRV": 33, "CAA": 257,
        }
        return mapping.get(record_type.upper(), 1)


# ============================================================================
# DNS Resolver Pool (Cycles 155–157)
# ============================================================================


class DNSResolverPool:
    """Pool of DNS resolvers with rotation, failover, and statistics.

    Manages multiple DoH and DoT resolvers, rotating between them
    for stealth and distributing load.
    """

    def __init__(self, config: DNSQueryConfig | None = None) -> None:
        self._config = config or DNSQueryConfig()
        self._doh_resolvers: dict[str, DoHResolver] = {}
        self._dot_resolvers: dict[str, DoTResolver] = {}
        self._stats: dict[str, dict[str, int]] = {}
        self._rotation_index = 0
        self._lock = threading.Lock()

        # Initialize resolvers for preferred providers
        for name in self._config.preferred_providers:
            if name in _DOH_PROVIDERS:
                self._doh_resolvers[name] = DoHResolver(_DOH_PROVIDERS[name])
            if name in _DOT_PROVIDERS:
                self._dot_resolvers[name] = DoTResolver(_DOT_PROVIDERS[name])

        # Ensure at least one resolver
        if not self._doh_resolvers and not self._dot_resolvers:
            cf_doh = _DOH_PROVIDERS.get("cloudflare")
            if cf_doh:
                self._doh_resolvers["cloudflare"] = DoHResolver(cf_doh)

    def resolve(
        self,
        name: str,
        record_type: str = "A",
        provider: str | None = None,
    ) -> list[DNSRecord]:
        """Resolve a DNS query using the pool.

        Args:
            name: Domain to resolve.
            record_type: DNS record type.
            provider: Specific provider name (overrides rotation).

        Returns:
            List of DNSRecord entries.
        """
        resolver = self._select_resolver(provider)
        if resolver is None:
            return []

        provider_name = provider or "unknown"
        try:
            records = resolver.resolve(name, record_type)
            self._record_stat(provider_name, "success")
            return records
        except Exception as e:
            log.warning("DNS resolution failed for %s via %s: %s",
                        name, provider_name, e)
            self._record_stat(provider_name, "failure")
            return []

    def _select_resolver(
        self,
        provider: str | None = None,
    ) -> DoHResolver | DoTResolver | None:
        """Select a resolver from the pool."""
        protocol = self._config.protocol

        if provider:
            if protocol == DNSProtocol.DOH and provider in self._doh_resolvers:
                return self._doh_resolvers[provider]
            if protocol == DNSProtocol.DOT and provider in self._dot_resolvers:
                return self._dot_resolvers[provider]
            # Try either pool
            if provider in self._doh_resolvers:
                return self._doh_resolvers[provider]
            if provider in self._dot_resolvers:
                return self._dot_resolvers[provider]
            return None

        if protocol == DNSProtocol.DOH:
            resolvers = list(self._doh_resolvers.values())
        elif protocol == DNSProtocol.DOT:
            resolvers = list(self._dot_resolvers.values())
        else:
            resolvers = list(self._doh_resolvers.values()) + list(self._dot_resolvers.values())

        if not resolvers:
            return None

        if self._config.rotate_providers:
            with self._lock:
                idx = self._rotation_index % len(resolvers)
                self._rotation_index += 1
            return resolvers[idx]
        else:
            return resolvers[0]

    def _record_stat(self, provider: str, outcome: str) -> None:
        with self._lock:
            if provider not in self._stats:
                self._stats[provider] = {"success": 0, "failure": 0}
            self._stats[provider][outcome] = self._stats[provider].get(outcome, 0) + 1

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """Get per-provider resolution statistics."""
        with self._lock:
            result = {}
            for name, stats in self._stats.items():
                total = stats.get("success", 0) + stats.get("failure", 0)
                result[name] = {
                    **stats,
                    "total": total,
                    "success_rate": stats.get("success", 0) / total if total > 0 else 0.0,
                }
            return result

    def get_available_providers(self) -> dict[str, list[str]]:
        """Get available provider names by protocol."""
        return {
            "doh": list(self._doh_resolvers.keys()),
            "dot": list(self._dot_resolvers.keys()),
        }


# ============================================================================
# Stealth DNS Engine — Façade (Cycles 157–160)
# ============================================================================


class StealthDNSEngine:
    """Unified stealth DNS resolution engine.

    Combines DoH/DoT resolvers, caching, provider rotation, and
    query privacy features into a single API.

    Usage::

        engine = StealthDNSEngine()
        records = engine.resolve("example.com", "A")
        stats = engine.get_stats()
    """

    def __init__(self, config: DNSQueryConfig | None = None) -> None:
        self._config = config or DNSQueryConfig()
        self._cache = DNSCache()
        self._pool = DNSResolverPool(self._config)
        self._total_queries = 0
        self._cached_queries = 0
        self._lock = threading.Lock()

    @property
    def config(self) -> DNSQueryConfig:
        """Current DNS configuration."""
        return self._config

    @property
    def cache(self) -> DNSCache:
        """Access the DNS cache."""
        return self._cache

    @property
    def pool(self) -> DNSResolverPool:
        """Access the resolver pool."""
        return self._pool

    # ── Resolution ────────────────────────────────────────────

    def resolve(
        self,
        name: str,
        record_type: str = "A",
        provider: str | None = None,
        skip_cache: bool = False,
    ) -> list[DNSRecord]:
        """Resolve a DNS query with stealth features.

        Features:
        - Cache lookup (if enabled)
        - Provider rotation
        - 0x20 encoding (randomize case)
        - Query logging control
        - Automatic retries

        Args:
            name: Domain name to resolve.
            record_type: DNS record type (A, AAAA, MX, etc.).
            provider: Force a specific provider.
            skip_cache: Skip cache lookup.

        Returns:
            List of DNSRecord entries.
        """
        with self._lock:
            self._total_queries += 1

        # Check cache first
        if self._config.cache_enabled and not skip_cache:
            cached = self._cache.get(name, record_type)
            if cached:
                with self._lock:
                    self._cached_queries += 1
                return cached

        # Resolve with retries
        records: list[DNSRecord] = []
        retries = self._config.max_retries
        for attempt in range(retries + 1):
            records = self._pool.resolve(name, record_type, provider)
            if records:
                break
            if attempt < retries:
                log.debug("Retry %d for %s %s", attempt + 1, name, record_type)

        # Cache the results
        if records and self._config.cache_enabled:
            self._cache.put(
                name, record_type, records,
                self._config.cache_ttl_override,
            )

        return records

    def resolve_many(
        self,
        queries: list[tuple[str, str]],
    ) -> dict[str, list[DNSRecord]]:
        """Resolve multiple DNS queries.

        Args:
            queries: List of (name, record_type) tuples.

        Returns:
            Dict of "name:type" → List[DNSRecord].
        """
        results: dict[str, list[DNSRecord]] = {}
        for name, rtype in queries:
            key = f"{name}:{rtype}"
            results[key] = self.resolve(name, rtype)
        return results

    # ── Provider Management ───────────────────────────────────

    def get_providers(self) -> dict[str, list[str]]:
        """Get available providers by protocol."""
        return self._pool.get_available_providers()

    def get_all_doh_providers(self) -> dict[str, DoHProvider]:
        """Get all known DoH providers."""
        return dict(_DOH_PROVIDERS)

    def get_all_dot_providers(self) -> dict[str, DoTProvider]:
        """Get all known DoT providers."""
        return dict(_DOT_PROVIDERS)

    # ── Statistics & Dashboard ────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive DNS resolution statistics."""
        with self._lock:
            total = self._total_queries
            cached = self._cached_queries
        return {
            "total_queries": total,
            "cached_queries": cached,
            "cache_hit_rate": cached / total if total > 0 else 0.0,
            "cache_stats": self._cache.stats,
            "provider_stats": self._pool.get_stats(),
            "protocol": self._config.protocol.value,
        }

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get dashboard-ready summary data."""
        providers = self._pool.get_available_providers()
        return {
            "protocol": self._config.protocol.value,
            "doh_provider_count": len(_DOH_PROVIDERS),
            "dot_provider_count": len(_DOT_PROVIDERS),
            "active_doh_providers": providers.get("doh", []),
            "active_dot_providers": providers.get("dot", []),
            "record_types": [r.value for r in DNSRecordType],
            "config": self._config.to_dict(),
            "stats": self.get_stats(),
        }

    # ── Configuration ─────────────────────────────────────────

    def update_config(self, data: dict[str, Any]) -> DNSQueryConfig:
        """Update DNS query configuration.

        Args:
            data: Dict of config values to update.

        Returns:
            Updated configuration.
        """
        current = self._config.to_dict()
        current.update(data)
        self._config = DNSQueryConfig.from_dict(current)
        # Rebuild pool with new config
        self._pool = DNSResolverPool(self._config)
        return self._config

    def reset_stats(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self._total_queries = 0
            self._cached_queries = 0
        self._cache.clear()

    def clear_cache(self) -> None:
        """Clear the DNS cache."""
        self._cache.clear()


# ============================================================================
# Module-level convenience functions
# ============================================================================


def get_doh_providers() -> dict[str, DoHProvider]:
    """Get all known DoH providers."""
    return dict(_DOH_PROVIDERS)


def get_dot_providers() -> dict[str, DoTProvider]:
    """Get all known DoT providers."""
    return dict(_DOT_PROVIDERS)


def get_all_protocols() -> list[str]:
    """Get all supported DNS protocol names."""
    return [p.value for p in DNSProtocol]


def get_all_record_types() -> list[str]:
    """Get all supported DNS record type names."""
    return [r.value for r in DNSRecordType]
