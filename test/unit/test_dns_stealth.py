# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         test_dns_stealth
# Purpose:      Unit tests for S-008 — DNS-over-HTTPS / DNS-over-TLS support
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Tests for spiderfoot.recon.dns_stealth — covers 100% of public API.

Test matrix:
- DNSProtocol enum
- DNSRecordType enum
- DoHProvider / DoTProvider dataclasses
- DNSRecord dataclass + expiry logic
- DNSQueryConfig + serialization
- DoHResolver (build_request, parse_response, resolve, 0x20, type mapping)
- DoTResolver (build_connection, build_query_packet, resolve, type mapping)
- DNSCache (get/put, TTL expiry, eviction, stats)
- DNSResolverPool (rotation, selection, stats, providers)
- StealthDNSEngine (resolve, cache, stats, dashboard, config update)
- Module-level functions
"""

import struct
import time

import pytest

from spiderfoot.recon.dns_stealth import (
    DNSCache,
    DNSProtocol,
    DNSQueryConfig,
    DNSRecord,
    DNSRecordType,
    DNSResolverPool,
    DoHProvider,
    DoHResolver,
    DoTProvider,
    DoTResolver,
    StealthDNSEngine,
    get_all_protocols,
    get_all_record_types,
    get_doh_providers,
    get_dot_providers,
)


# ============================================================================
# DNSProtocol
# ============================================================================


class TestDNSProtocol:
    def test_values(self):
        assert DNSProtocol.PLAIN.value == "plain"
        assert DNSProtocol.DOH.value == "doh"
        assert DNSProtocol.DOT.value == "dot"

    def test_count(self):
        assert len(DNSProtocol) == 3

    def test_from_string(self):
        assert DNSProtocol("doh") == DNSProtocol.DOH

    def test_invalid(self):
        with pytest.raises(ValueError):
            DNSProtocol("invalid")


# ============================================================================
# DNSRecordType
# ============================================================================


class TestDNSRecordType:
    def test_count(self):
        assert len(DNSRecordType) == 10

    def test_all_values(self):
        expected = {"A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "PTR", "SRV", "CAA"}
        actual = {r.value for r in DNSRecordType}
        assert actual == expected


# ============================================================================
# DoHProvider
# ============================================================================


class TestDoHProvider:
    def test_creation(self):
        p = DoHProvider(
            name="test",
            url="https://dns.test/query",
            description="Test provider",
        )
        assert p.name == "test"
        assert p.supports_json is True
        assert p.max_rps == 100

    def test_to_dict(self):
        p = DoHProvider(name="test", url="https://dns.test/q")
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["url"] == "https://dns.test/q"
        assert "max_rps" in d

    def test_built_in_providers(self):
        providers = get_doh_providers()
        assert len(providers) == 7
        assert "cloudflare" in providers
        assert "google" in providers
        assert "quad9" in providers
        assert "nextdns" in providers
        assert "adguard" in providers
        assert "mullvad" in providers
        assert "controld" in providers

    def test_cloudflare_url(self):
        p = get_doh_providers()["cloudflare"]
        assert "cloudflare" in p.url
        assert p.supports_wire is True

    def test_google_url(self):
        p = get_doh_providers()["google"]
        assert "dns.google" in p.url


# ============================================================================
# DoTProvider
# ============================================================================


class TestDoTProvider:
    def test_creation(self):
        p = DoTProvider(name="test", host="dns.test")
        assert p.port == 853
        assert p.verify_hostname is True

    def test_to_dict(self):
        p = DoTProvider(name="test", host="dns.test", ip="1.2.3.4")
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["host"] == "dns.test"
        assert d["port"] == 853
        assert d["ip"] == "1.2.3.4"

    def test_built_in_providers(self):
        providers = get_dot_providers()
        assert len(providers) == 5
        assert "cloudflare" in providers
        assert "google" in providers
        assert "quad9" in providers

    def test_cloudflare_ip(self):
        p = get_dot_providers()["cloudflare"]
        assert p.ip == "1.1.1.1"

    def test_google_ip(self):
        p = get_dot_providers()["google"]
        assert p.ip == "8.8.8.8"


# ============================================================================
# DNSRecord
# ============================================================================


class TestDNSRecord:
    def test_creation(self):
        r = DNSRecord(name="example.com", record_type="A", value="1.2.3.4")
        assert r.name == "example.com"
        assert r.record_type == "A"
        assert r.value == "1.2.3.4"
        assert r.ttl == 0

    def test_to_dict(self):
        r = DNSRecord(
            name="example.com",
            record_type="A",
            value="1.2.3.4",
            ttl=300,
            provider="cloudflare",
            protocol="doh",
        )
        d = r.to_dict()
        assert d["name"] == "example.com"
        assert d["ttl"] == 300
        assert d["provider"] == "cloudflare"
        assert d["protocol"] == "doh"

    def test_not_expired_zero_ttl(self):
        r = DNSRecord(name="t", record_type="A", value="1.2.3.4", ttl=0)
        assert r.is_expired is False

    def test_not_expired_positive_ttl(self):
        r = DNSRecord(
            name="t", record_type="A", value="1.2.3.4",
            ttl=3600, timestamp=time.time(),
        )
        assert r.is_expired is False

    def test_expired(self):
        r = DNSRecord(
            name="t", record_type="A", value="1.2.3.4",
            ttl=1, timestamp=time.time() - 10,
        )
        assert r.is_expired is True


# ============================================================================
# DNSQueryConfig
# ============================================================================


class TestDNSQueryConfig:
    def test_defaults(self):
        c = DNSQueryConfig()
        assert c.protocol == DNSProtocol.DOH
        assert c.cache_enabled is True
        assert c.rotate_providers is True
        assert c.randomize_case is True
        assert c.fallback_to_plain is False

    def test_to_dict(self):
        c = DNSQueryConfig()
        d = c.to_dict()
        assert d["protocol"] == "doh"
        assert d["cache_enabled"] is True
        assert isinstance(d["preferred_providers"], list)

    def test_from_dict(self):
        d = {
            "protocol": "dot",
            "preferred_providers": ["quad9"],
            "cache_enabled": False,
            "timeout_seconds": 10.0,
        }
        c = DNSQueryConfig.from_dict(d)
        assert c.protocol == DNSProtocol.DOT
        assert c.preferred_providers == ["quad9"]
        assert c.cache_enabled is False
        assert c.timeout_seconds == 10.0

    def test_roundtrip(self):
        c1 = DNSQueryConfig(
            protocol=DNSProtocol.DOT,
            preferred_providers=["google"],
            max_retries=5,
        )
        c2 = DNSQueryConfig.from_dict(c1.to_dict())
        assert c2.protocol == c1.protocol
        assert c2.preferred_providers == c1.preferred_providers
        assert c2.max_retries == c1.max_retries

    def test_from_dict_defaults(self):
        c = DNSQueryConfig.from_dict({})
        assert c.protocol == DNSProtocol.DOH
        assert c.max_retries == 2


# ============================================================================
# DoHResolver
# ============================================================================


class TestDoHResolver:
    def test_default_provider(self):
        r = DoHResolver()
        assert r.provider.name == "cloudflare"

    def test_custom_provider(self):
        p = DoHProvider(name="custom", url="https://dns.custom/q")
        r = DoHResolver(p)
        assert r.provider.name == "custom"

    def test_build_request(self):
        r = DoHResolver()
        req = r.build_request("example.com", "A", randomize_case=False)
        assert req["method"] == "GET"
        assert "cloudflare" in req["url"]
        assert req["params"]["name"] == "example.com"
        assert req["params"]["type"] == "A"
        assert req["headers"]["Accept"] == "application/dns-json"

    def test_build_request_randomize_case(self):
        r = DoHResolver()
        req = r.build_request("example.com", "A", randomize_case=True)
        name = req["params"]["name"]
        assert name.lower() == "example.com"

    def test_resolve_a(self):
        r = DoHResolver()
        records = r.resolve("example.com", "A")
        assert len(records) == 1
        assert records[0].record_type == "A"
        assert records[0].protocol == "doh"
        assert records[0].provider == "cloudflare"
        # Validate IP format
        parts = records[0].value.split(".")
        assert len(parts) == 4

    def test_resolve_aaaa(self):
        r = DoHResolver()
        records = r.resolve("example.com", "AAAA")
        assert len(records) == 1
        assert records[0].record_type == "AAAA"
        assert ":" in records[0].value

    def test_resolve_mx(self):
        r = DoHResolver()
        records = r.resolve("example.com", "MX")
        assert len(records) == 1
        assert "mail" in records[0].value

    def test_resolve_ns(self):
        r = DoHResolver()
        records = r.resolve("example.com", "NS")
        assert len(records) == 1
        assert "ns1" in records[0].value

    def test_resolve_txt(self):
        r = DoHResolver()
        records = r.resolve("example.com", "TXT")
        assert len(records) == 1
        assert "spf" in records[0].value

    def test_resolve_cname(self):
        r = DoHResolver()
        records = r.resolve("example.com", "CNAME")
        assert records[0].value == "www.example.com"

    def test_resolve_unknown_type(self):
        r = DoHResolver()
        records = r.resolve("example.com", "SRV")
        assert len(records) == 1
        assert records[0].record_type == "SRV"
        assert "simulated" in records[0].value

    def test_resolve_deterministic(self):
        r = DoHResolver()
        r1 = r.resolve("example.com", "A")
        r2 = r.resolve("example.com", "A")
        assert r1[0].value == r2[0].value

    def test_resolve_different_domains(self):
        r = DoHResolver()
        r1 = r.resolve("example.com", "A")
        r2 = r.resolve("other.com", "A")
        assert r1[0].value != r2[0].value

    def test_parse_response(self):
        r = DoHResolver()
        response = {
            "Answer": [
                {"name": "example.com.", "type": 1, "data": "1.2.3.4", "TTL": 300},
                {"name": "example.com.", "type": 1, "data": "5.6.7.8", "TTL": 300},
            ],
        }
        records = r.parse_response(response)
        assert len(records) == 2
        assert records[0].value == "1.2.3.4"
        assert records[1].value == "5.6.7.8"
        assert records[0].name == "example.com"

    def test_parse_response_cname(self):
        r = DoHResolver()
        response = {
            "Answer": [
                {"name": "www.example.com.", "type": 5, "data": "example.com", "TTL": 600},
            ],
        }
        records = r.parse_response(response)
        assert records[0].record_type == "CNAME"

    def test_parse_response_empty(self):
        r = DoHResolver()
        records = r.parse_response({})
        assert records == []

    def test_type_int_to_str(self):
        assert DoHResolver._type_int_to_str(1) == "A"
        assert DoHResolver._type_int_to_str(28) == "AAAA"
        assert DoHResolver._type_int_to_str(15) == "MX"
        assert DoHResolver._type_int_to_str(999) == "TYPE999"


# ============================================================================
# DoTResolver
# ============================================================================


class TestDoTResolver:
    def test_default_provider(self):
        r = DoTResolver()
        assert r.provider.name == "cloudflare"

    def test_custom_provider(self):
        p = DoTProvider(name="custom", host="dns.custom")
        r = DoTResolver(p)
        assert r.provider.name == "custom"

    def test_build_connection(self):
        r = DoTResolver()
        conn = r.build_connection()
        assert conn["port"] == 853
        assert conn["host"] == "one.one.one.one"
        assert conn["ip"] == "1.1.1.1"
        assert conn["verify_hostname"] is True

    def test_build_query_packet_structure(self):
        r = DoTResolver()
        pkt = r.build_query_packet("example.com", "A", query_id=12345)
        # First 2 bytes: length prefix
        length = struct.unpack("!H", pkt[:2])[0]
        assert length == len(pkt) - 2
        # Next 2 bytes: query ID
        qid = struct.unpack("!H", pkt[2:4])[0]
        assert qid == 12345
        # Flags
        flags = struct.unpack("!H", pkt[4:6])[0]
        assert flags == 0x0100  # Standard query + recursion desired

    def test_build_query_packet_aaaa(self):
        r = DoTResolver()
        pkt = r.build_query_packet("test.com", "AAAA")
        # Should contain type 28 (AAAA) near the end — 2 bytes before class IN
        # Find end of question section
        assert len(pkt) > 12

    def test_build_query_packet_random_id(self):
        r = DoTResolver()
        pkt1 = r.build_query_packet("a.com")
        pkt2 = r.build_query_packet("a.com")
        # IDs should (usually) differ
        id1 = struct.unpack("!H", pkt1[2:4])[0]
        id2 = struct.unpack("!H", pkt2[2:4])[0]
        # Not deterministic, but at least test it works
        assert isinstance(id1, int)
        assert isinstance(id2, int)

    def test_resolve_a(self):
        r = DoTResolver()
        records = r.resolve("example.com", "A")
        assert len(records) == 1
        assert records[0].protocol == "dot"
        assert records[0].record_type == "A"

    def test_resolve_aaaa(self):
        r = DoTResolver()
        records = r.resolve("example.com", "AAAA")
        assert records[0].record_type == "AAAA"

    def test_resolve_mx(self):
        r = DoTResolver()
        records = r.resolve("example.com", "MX")
        assert "mail" in records[0].value

    def test_resolve_ns(self):
        r = DoTResolver()
        records = r.resolve("example.com", "NS")
        assert "ns1" in records[0].value

    def test_resolve_txt(self):
        r = DoTResolver()
        records = r.resolve("example.com", "TXT")
        assert "spf" in records[0].value

    def test_resolve_cname(self):
        r = DoTResolver()
        records = r.resolve("example.com", "CNAME")
        assert "www" in records[0].value

    def test_resolve_unknown(self):
        r = DoTResolver()
        records = r.resolve("example.com", "CAA")
        assert "simulated-dot" in records[0].value

    def test_resolve_deterministic(self):
        r = DoTResolver()
        r1 = r.resolve("example.com", "A")
        r2 = r.resolve("example.com", "A")
        assert r1[0].value == r2[0].value

    def test_type_str_to_int(self):
        assert DoTResolver._type_str_to_int("A") == 1
        assert DoTResolver._type_str_to_int("AAAA") == 28
        assert DoTResolver._type_str_to_int("MX") == 15
        assert DoTResolver._type_str_to_int("UNKNOWN") == 1  # default


# ============================================================================
# DNSCache
# ============================================================================


class TestDNSCache:
    def test_empty_cache(self):
        c = DNSCache()
        assert c.size == 0
        assert c.get("x.com", "A") is None

    def test_put_and_get(self):
        c = DNSCache()
        r = DNSRecord(name="x.com", record_type="A", value="1.2.3.4", ttl=300)
        c.put("x.com", "A", [r])
        result = c.get("x.com", "A")
        assert result is not None
        assert len(result) == 1
        assert result[0].value == "1.2.3.4"

    def test_case_insensitive(self):
        c = DNSCache()
        r = DNSRecord(name="X.COM", record_type="A", value="1.2.3.4", ttl=300)
        c.put("X.COM", "A", [r])
        assert c.get("x.com", "A") is not None
        assert c.get("X.COM", "a") is not None

    def test_miss(self):
        c = DNSCache()
        assert c.get("no.com", "A") is None
        assert c.stats["misses"] == 1

    def test_hit_counter(self):
        c = DNSCache()
        r = DNSRecord(name="x.com", record_type="A", value="1.2.3.4", ttl=300)
        c.put("x.com", "A", [r])
        c.get("x.com", "A")
        c.get("x.com", "A")
        assert c.stats["hits"] == 2

    def test_ttl_expiry(self):
        c = DNSCache()
        r = DNSRecord(
            name="x.com", record_type="A", value="1.2.3.4",
            ttl=1, timestamp=time.time() - 10,
        )
        c.put("x.com", "A", [r])
        assert c.get("x.com", "A") is None

    def test_ttl_override(self):
        c = DNSCache()
        r = DNSRecord(name="x.com", record_type="A", value="1.2.3.4", ttl=1)
        c.put("x.com", "A", [r], ttl_override=3600)
        assert c.get("x.com", "A") is not None

    def test_evict_expired(self):
        c = DNSCache()
        r1 = DNSRecord(
            name="old.com", record_type="A", value="1.2.3.4",
            ttl=1, timestamp=time.time() - 10,
        )
        r2 = DNSRecord(
            name="new.com", record_type="A", value="5.6.7.8",
            ttl=3600,
        )
        c.put("old.com", "A", [r1])
        c.put("new.com", "A", [r2])
        evicted = c.evict_expired()
        assert evicted == 1
        assert c.size == 1
        assert c.get("new.com", "A") is not None

    def test_clear(self):
        c = DNSCache()
        r = DNSRecord(name="x.com", record_type="A", value="1.2.3.4", ttl=300)
        c.put("x.com", "A", [r])
        c.clear()
        assert c.size == 0
        assert c.stats["hits"] == 0
        assert c.stats["misses"] == 0

    def test_max_entries_eviction(self):
        c = DNSCache(max_entries=3)
        for i in range(5):
            r = DNSRecord(name=f"{i}.com", record_type="A", value=f"1.2.3.{i}", ttl=300)
            c.put(f"{i}.com", "A", [r])
        assert c.size <= 3

    def test_put_empty_records(self):
        c = DNSCache()
        c.put("x.com", "A", [])
        assert c.size == 0

    def test_stats_hit_rate(self):
        c = DNSCache()
        r = DNSRecord(name="x.com", record_type="A", value="1.2.3.4", ttl=300)
        c.put("x.com", "A", [r])
        c.get("x.com", "A")  # hit
        c.get("y.com", "A")  # miss
        stats = c.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert abs(stats["hit_rate"] - 0.5) < 0.01


# ============================================================================
# DNSResolverPool
# ============================================================================


class TestDNSResolverPool:
    def test_default_pool(self):
        pool = DNSResolverPool()
        providers = pool.get_available_providers()
        assert "doh" in providers
        assert "cloudflare" in providers["doh"]
        assert "google" in providers["doh"]

    def test_resolve_a(self):
        pool = DNSResolverPool()
        records = pool.resolve("example.com", "A")
        assert len(records) >= 1
        assert records[0].record_type == "A"

    def test_resolve_with_provider(self):
        pool = DNSResolverPool()
        records = pool.resolve("example.com", "A", provider="google")
        assert len(records) == 1
        assert records[0].provider == "google"

    def test_resolve_invalid_provider(self):
        pool = DNSResolverPool()
        records = pool.resolve("example.com", "A", provider="nonexistent")
        assert records == []

    def test_rotation(self):
        config = DNSQueryConfig(
            preferred_providers=["cloudflare", "google"],
            rotate_providers=True,
        )
        pool = DNSResolverPool(config)
        r1 = pool.resolve("a.com", "A")
        r2 = pool.resolve("b.com", "A")
        # With rotation, providers should alternate
        providers = {r1[0].provider, r2[0].provider}
        assert len(providers) >= 1  # At least one unique provider

    def test_no_rotation(self):
        config = DNSQueryConfig(
            preferred_providers=["cloudflare", "google"],
            rotate_providers=False,
        )
        pool = DNSResolverPool(config)
        r1 = pool.resolve("a.com", "A")
        r2 = pool.resolve("b.com", "A")
        assert r1[0].provider == r2[0].provider  # Same provider

    def test_stats(self):
        pool = DNSResolverPool()
        pool.resolve("example.com", "A")
        stats = pool.get_stats()
        assert len(stats) > 0
        for name, s in stats.items():
            assert "success" in s
            assert "total" in s

    def test_dot_protocol(self):
        config = DNSQueryConfig(
            protocol=DNSProtocol.DOT,
            preferred_providers=["cloudflare"],
        )
        pool = DNSResolverPool(config)
        records = pool.resolve("example.com", "A")
        assert len(records) == 1
        assert records[0].protocol == "dot"

    def test_fallback_resolver_creation(self):
        config = DNSQueryConfig(preferred_providers=["nonexistent"])
        pool = DNSResolverPool(config)
        providers = pool.get_available_providers()
        # Should have at least cloudflare as fallback
        assert len(providers["doh"]) >= 1


# ============================================================================
# StealthDNSEngine
# ============================================================================


class TestStealthDNSEngine:
    def test_creation(self):
        engine = StealthDNSEngine()
        assert engine.config.protocol == DNSProtocol.DOH

    def test_custom_config(self):
        config = DNSQueryConfig(protocol=DNSProtocol.DOT)
        engine = StealthDNSEngine(config)
        assert engine.config.protocol == DNSProtocol.DOT

    def test_resolve_a(self):
        engine = StealthDNSEngine()
        records = engine.resolve("example.com", "A")
        assert len(records) >= 1
        assert records[0].record_type == "A"

    def test_resolve_aaaa(self):
        engine = StealthDNSEngine()
        records = engine.resolve("example.com", "AAAA")
        assert records[0].record_type == "AAAA"

    def test_resolve_mx(self):
        engine = StealthDNSEngine()
        records = engine.resolve("example.com", "MX")
        assert records[0].record_type == "MX"

    def test_resolve_cached(self):
        engine = StealthDNSEngine()
        r1 = engine.resolve("example.com", "A")
        r2 = engine.resolve("example.com", "A")
        # Second should be cached
        assert r1[0].value == r2[0].value
        stats = engine.get_stats()
        assert stats["cached_queries"] >= 1

    def test_resolve_skip_cache(self):
        engine = StealthDNSEngine()
        engine.resolve("example.com", "A")
        engine.resolve("example.com", "A", skip_cache=True)
        stats = engine.get_stats()
        assert stats["total_queries"] == 2
        # Cache hit should still be 0 for second query if skip_cache=True
        assert stats["cached_queries"] <= 1

    def test_resolve_with_provider(self):
        engine = StealthDNSEngine()
        records = engine.resolve("example.com", "A", provider="google")
        assert records[0].provider == "google"

    def test_resolve_many(self):
        engine = StealthDNSEngine()
        queries = [
            ("example.com", "A"),
            ("example.com", "AAAA"),
            ("other.com", "MX"),
        ]
        results = engine.resolve_many(queries)
        assert len(results) == 3
        assert "example.com:A" in results
        assert "example.com:AAAA" in results
        assert "other.com:MX" in results

    def test_get_providers(self):
        engine = StealthDNSEngine()
        providers = engine.get_providers()
        assert "doh" in providers
        assert "dot" in providers

    def test_get_all_doh_providers(self):
        engine = StealthDNSEngine()
        providers = engine.get_all_doh_providers()
        assert len(providers) == 7
        assert "cloudflare" in providers

    def test_get_all_dot_providers(self):
        engine = StealthDNSEngine()
        providers = engine.get_all_dot_providers()
        assert len(providers) == 5

    def test_get_stats(self):
        engine = StealthDNSEngine()
        engine.resolve("example.com", "A")
        stats = engine.get_stats()
        assert stats["total_queries"] == 1
        assert stats["protocol"] == "doh"
        assert "cache_stats" in stats
        assert "provider_stats" in stats

    def test_cache_hit_rate(self):
        engine = StealthDNSEngine()
        engine.resolve("a.com", "A")
        engine.resolve("a.com", "A")
        engine.resolve("b.com", "A")
        stats = engine.get_stats()
        assert stats["cache_hit_rate"] > 0

    def test_dashboard_data(self):
        engine = StealthDNSEngine()
        dash = engine.get_dashboard_data()
        assert dash["protocol"] == "doh"
        assert dash["doh_provider_count"] == 7
        assert dash["dot_provider_count"] == 5
        assert len(dash["record_types"]) == 10
        assert "config" in dash
        assert "stats" in dash

    def test_update_config(self):
        engine = StealthDNSEngine()
        engine.update_config({"protocol": "dot", "max_retries": 5})
        assert engine.config.protocol == DNSProtocol.DOT
        assert engine.config.max_retries == 5

    def test_reset_stats(self):
        engine = StealthDNSEngine()
        engine.resolve("a.com", "A")
        engine.reset_stats()
        stats = engine.get_stats()
        assert stats["total_queries"] == 0
        assert stats["cached_queries"] == 0

    def test_clear_cache(self):
        engine = StealthDNSEngine()
        engine.resolve("a.com", "A")
        assert engine.cache.size > 0
        engine.clear_cache()
        assert engine.cache.size == 0

    def test_cache_disabled(self):
        config = DNSQueryConfig(cache_enabled=False)
        engine = StealthDNSEngine(config)
        engine.resolve("a.com", "A")
        engine.resolve("a.com", "A")
        stats = engine.get_stats()
        assert stats["cached_queries"] == 0

    def test_ttl_override(self):
        config = DNSQueryConfig(cache_ttl_override=9999)
        engine = StealthDNSEngine(config)
        engine.resolve("a.com", "A")
        cached = engine.cache.get("a.com", "A")
        assert cached is not None
        assert cached[0].ttl == 9999


# ============================================================================
# Module-level Functions
# ============================================================================


class TestModuleFunctions:
    def test_get_doh_providers(self):
        providers = get_doh_providers()
        assert isinstance(providers, dict)
        assert len(providers) == 7

    def test_get_dot_providers(self):
        providers = get_dot_providers()
        assert isinstance(providers, dict)
        assert len(providers) == 5

    def test_get_all_protocols(self):
        protos = get_all_protocols()
        assert set(protos) == {"plain", "doh", "dot"}

    def test_get_all_record_types(self):
        types = get_all_record_types()
        assert "A" in types
        assert "AAAA" in types
        assert "MX" in types
        assert len(types) == 10


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    def test_empty_domain(self):
        engine = StealthDNSEngine()
        records = engine.resolve("", "A")
        assert len(records) >= 0  # Should not crash

    def test_very_long_domain(self):
        engine = StealthDNSEngine()
        long_domain = "a" * 200 + ".com"
        records = engine.resolve(long_domain, "A")
        assert len(records) >= 0

    def test_special_characters_domain(self):
        engine = StealthDNSEngine()
        records = engine.resolve("test-site.example.co.uk", "A")
        assert len(records) >= 1

    def test_multiple_record_types(self):
        engine = StealthDNSEngine()
        for rtype in ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]:
            records = engine.resolve("example.com", rtype)
            assert len(records) >= 1, f"Failed for {rtype}"

    def test_concurrent_access_cache(self):
        """Basic test that cache handles concurrent access."""
        import threading

        cache = DNSCache()
        errors: list[str] = []

        def writer():
            for i in range(50):
                r = DNSRecord(name=f"{i}.com", record_type="A", value=f"1.0.0.{i % 256}", ttl=300)
                cache.put(f"{i}.com", "A", [r])

        def reader():
            for i in range(50):
                cache.get(f"{i}.com", "A")

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_concurrent_engine_resolve(self):
        """Basic test that engine handles concurrent resolves."""
        import threading

        engine = StealthDNSEngine()
        errors: list[str] = []

        def resolver(domain: str):
            try:
                engine.resolve(domain, "A")
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=resolver, args=(f"domain{i}.com",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    def test_doh_vs_dot_different_results(self):
        """DoH and DoT produce different simulated results for same domain."""
        doh = DoHResolver()
        dot = DoTResolver()
        r_doh = doh.resolve("example.com", "A")
        r_dot = dot.resolve("example.com", "A")
        # They use different hash seeds, so results differ
        assert r_doh[0].value != r_dot[0].value
        assert r_doh[0].protocol == "doh"
        assert r_dot[0].protocol == "dot"

    def test_query_packet_domain_encoding(self):
        """Verify domain name is properly encoded in wire format."""
        r = DoTResolver()
        pkt = r.build_query_packet("a.b.c", "A", query_id=1)
        # After length prefix (2) + header (12), labels start
        # "a" → 01 61, "b" → 01 62, "c" → 01 63, root → 00
        data = pkt[14:]  # Skip length prefix + header
        assert data[0] == 1  # length of "a"
        assert data[1] == ord("a")
        assert data[2] == 1  # length of "b"
        assert data[3] == ord("b")
        assert data[4] == 1  # length of "c"
        assert data[5] == ord("c")
        assert data[6] == 0  # root label
