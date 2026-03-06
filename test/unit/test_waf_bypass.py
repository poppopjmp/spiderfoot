# -------------------------------------------------------------------------------
# Name:         test_waf_bypass
# Purpose:      Tests for S-007 — CDN/WAF bypass techniques + header spoofing
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Comprehensive test suite for spiderfoot.recon.waf_bypass (S-007).

Covers:
- BypassTechnique enumeration
- CDNVendor enumeration
- SpoofHeader generation
- HeaderSpoofProfile system
- CDNBypassStrategy per-vendor strategies
- OriginDiscovery hints + registration
- CacheAnalyzer header analysis
- PathMutator URL mutations
- MethodOverride generation
- WAFBypassEngine façade (all methods)
- Statistics tracking + dashboard
"""

import pytest

from spiderfoot.recon.waf_bypass import (
    BypassTechnique,
    CacheAnalysis,
    CacheAnalyzer,
    CDNBypassStrategy,
    CDNVendor,
    ClientType,
    HeaderSpoofProfile,
    MethodOverride,
    OriginDiscovery,
    OriginHint,
    PathMutation,
    PathMutator,
    SpoofHeader,
    WAFBypassEngine,
    generate_method_overrides,
    generate_spoof_headers,
    get_all_profiles,
    get_all_strategies,
    get_cdn_strategy,
    get_profile,
    get_profiles_by_client_type,
)


# ============================================================================
# BypassTechnique Enumeration Tests
# ============================================================================


class TestBypassTechnique:
    """Tests for the BypassTechnique enum."""

    def test_technique_count(self):
        assert len(BypassTechnique) == 22

    def test_header_techniques_exist(self):
        assert BypassTechnique.HEADER_XFF.value == "x_forwarded_for"
        assert BypassTechnique.HEADER_X_ORIGINATING_IP.value == "x_originating_ip"
        assert BypassTechnique.HEADER_X_REAL_IP.value == "x_real_ip"
        assert BypassTechnique.HEADER_X_CLIENT_IP.value == "x_client_ip"
        assert BypassTechnique.HEADER_CF_CONNECTING_IP.value == "cf_connecting_ip"
        assert BypassTechnique.HEADER_TRUE_CLIENT_IP.value == "true_client_ip"

    def test_request_mutation_techniques(self):
        assert BypassTechnique.HOST_OVERRIDE.value == "host_override"
        assert BypassTechnique.PATH_MUTATION.value == "path_mutation"
        assert BypassTechnique.METHOD_OVERRIDE.value == "method_override"
        assert BypassTechnique.CONTENT_TYPE_BYPASS.value == "content_type_bypass"

    def test_protocol_techniques(self):
        assert BypassTechnique.HTTP2_DIRECT.value == "http2_direct"
        assert BypassTechnique.WEBSOCKET_UPGRADE.value == "websocket_upgrade"
        assert BypassTechnique.SSL_CLIENT_CERT.value == "ssl_client_cert"

    def test_origin_discovery_techniques(self):
        assert BypassTechnique.DNS_HISTORY.value == "dns_history"
        assert BypassTechnique.SUBDOMAIN_ENUM.value == "subdomain_enum"
        assert BypassTechnique.CERT_TRANSPARENCY.value == "cert_transparency"
        assert BypassTechnique.ERROR_PAGE_LEAK.value == "error_page_leak"
        assert BypassTechnique.MAIL_HEADER_LEAK.value == "mail_header_leak"

    def test_all_values_unique(self):
        values = [t.value for t in BypassTechnique]
        assert len(values) == len(set(values))


# ============================================================================
# CDNVendor Enumeration Tests
# ============================================================================


class TestCDNVendor:
    """Tests for the CDNVendor enum."""

    def test_vendor_count(self):
        assert len(CDNVendor) == 16

    def test_major_vendors_exist(self):
        assert CDNVendor.CLOUDFLARE.value == "cloudflare"
        assert CDNVendor.AKAMAI.value == "akamai"
        assert CDNVendor.AWS_CLOUDFRONT.value == "aws_cloudfront"
        assert CDNVendor.FASTLY.value == "fastly"
        assert CDNVendor.IMPERVA.value == "imperva"
        assert CDNVendor.SUCURI.value == "sucuri"
        assert CDNVendor.AZURE_CDN.value == "azure_cdn"

    def test_special_vendors(self):
        assert CDNVendor.UNKNOWN.value == "unknown"
        assert CDNVendor.GENERIC.value == "generic"

    def test_all_values_unique(self):
        values = [v.value for v in CDNVendor]
        assert len(values) == len(set(values))


# ============================================================================
# SpoofHeader Tests
# ============================================================================


class TestSpoofHeader:
    """Tests for SpoofHeader dataclass."""

    def test_basic_creation(self):
        h = SpoofHeader(
            name="X-Forwarded-For",
            value="10.0.0.1",
            technique=BypassTechnique.HEADER_XFF,
        )
        assert h.name == "X-Forwarded-For"
        assert h.value == "10.0.0.1"
        assert h.technique == BypassTechnique.HEADER_XFF
        assert h.risk_level == "low"

    def test_with_metadata(self):
        h = SpoofHeader(
            name="CF-Connecting-IP",
            value="127.0.0.1",
            technique=BypassTechnique.HEADER_CF_CONNECTING_IP,
            description="Cloudflare IP spoofing",
            risk_level="high",
            vendor_specific="cloudflare",
        )
        assert h.description == "Cloudflare IP spoofing"
        assert h.risk_level == "high"
        assert h.vendor_specific == "cloudflare"


class TestGenerateSpoofHeaders:
    """Tests for generate_spoof_headers()."""

    def test_default_internal_ip(self):
        headers = generate_spoof_headers()
        assert len(headers) > 0
        # All should have IP values from internal pool
        for h in headers:
            assert isinstance(h, SpoofHeader)
            assert h.name
            assert h.value

    def test_specific_ip(self):
        headers = generate_spoof_headers("192.168.1.100")
        for h in headers:
            if h.technique == BypassTechnique.HEADER_FORWARDED:
                assert "192.168.1.100" in h.value
            else:
                assert h.value == "192.168.1.100"

    def test_header_count(self):
        # Should generate one header per IP_SPOOF_HEADERS entry
        headers = generate_spoof_headers("10.0.0.1")
        assert len(headers) == 12  # 12 IP spoof header types

    def test_xff_included(self):
        headers = generate_spoof_headers("10.0.0.1")
        names = [h.name for h in headers]
        assert "X-Forwarded-For" in names
        assert "X-Real-IP" in names
        assert "CF-Connecting-IP" in names

    def test_forwarded_header_format(self):
        """RFC 7239 Forwarded header uses for= format."""
        headers = generate_spoof_headers("10.10.10.1")
        forwarded = [h for h in headers if h.name == "Forwarded"]
        assert len(forwarded) == 1
        assert forwarded[0].value == "for=10.10.10.1"

    def test_risk_level(self):
        headers = generate_spoof_headers()
        for h in headers:
            assert h.risk_level == "medium"

    def test_description_includes_ip(self):
        headers = generate_spoof_headers("172.16.0.1")
        for h in headers:
            assert "172.16.0.1" in h.description


# ============================================================================
# HeaderSpoofProfile Tests
# ============================================================================


class TestHeaderSpoofProfile:
    """Tests for HeaderSpoofProfile and profile retrieval."""

    def test_profile_creation(self):
        p = HeaderSpoofProfile(
            name="test",
            client_type=ClientType.INTERNAL_NETWORK,
            headers={"X-Test": "value"},
        )
        assert p.name == "test"
        assert p.effectiveness == 0.5

    def test_to_dict(self):
        p = HeaderSpoofProfile(
            name="test",
            client_type=ClientType.CDN_NODE,
            headers={"Via": "1.1 node"},
            effectiveness=0.7,
        )
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["client_type"] == "cdn_node"
        assert d["headers"]["Via"] == "1.1 node"
        assert d["effectiveness"] == 0.7

    def test_get_profile_exists(self):
        p = get_profile("google_crawler")
        assert p is not None
        assert p.client_type == ClientType.SEARCH_CRAWLER
        assert "Googlebot" in p.headers["User-Agent"]

    def test_get_profile_not_found(self):
        assert get_profile("nonexistent") is None

    def test_get_all_profiles(self):
        profiles = get_all_profiles()
        assert len(profiles) >= 8
        assert "internal_user" in profiles
        assert "google_crawler" in profiles
        assert "mobile_ios" in profiles
        assert "api_service" in profiles

    def test_profiles_by_client_type_crawler(self):
        crawlers = get_profiles_by_client_type(ClientType.SEARCH_CRAWLER)
        assert len(crawlers) >= 2  # google + bing
        for p in crawlers:
            assert p.client_type == ClientType.SEARCH_CRAWLER

    def test_profiles_by_client_type_internal(self):
        internal = get_profiles_by_client_type(ClientType.INTERNAL_NETWORK)
        assert len(internal) >= 1

    def test_profiles_by_client_type_monitoring(self):
        monitors = get_profiles_by_client_type(ClientType.MONITORING)
        assert len(monitors) >= 1

    def test_lb_health_check_profile(self):
        p = get_profile("lb_health_check")
        assert p is not None
        assert p.client_type == ClientType.LOAD_BALANCER
        assert "ELB" in p.headers["User-Agent"]

    def test_cdn_health_check_profile(self):
        p = get_profile("cdn_health_check")
        assert p is not None
        assert "Via" in p.headers

    def test_uptime_monitor_profile(self):
        p = get_profile("uptime_monitor")
        assert p is not None
        assert "UptimeRobot" in p.headers["User-Agent"]


# ============================================================================
# ClientType Tests
# ============================================================================


class TestClientType:
    """Tests for ClientType enum."""

    def test_all_types(self):
        assert len(ClientType) == 7
        assert ClientType.INTERNAL_NETWORK.value == "internal_network"
        assert ClientType.CDN_NODE.value == "cdn_node"
        assert ClientType.SEARCH_CRAWLER.value == "search_crawler"
        assert ClientType.MOBILE_APP.value == "mobile_app"
        assert ClientType.API_CLIENT.value == "api_client"
        assert ClientType.MONITORING.value == "monitoring"
        assert ClientType.LOAD_BALANCER.value == "load_balancer"


# ============================================================================
# CDNBypassStrategy Tests
# ============================================================================


class TestCDNBypassStrategy:
    """Tests for CDNBypassStrategy and per-vendor strategies."""

    def test_strategy_creation(self):
        strategy = CDNBypassStrategy(
            vendor=CDNVendor.CLOUDFLARE,
            techniques=[BypassTechnique.HEADER_CF_CONNECTING_IP],
            vendor_headers={"CF-Connecting-IP": "127.0.0.1"},
        )
        assert strategy.vendor == CDNVendor.CLOUDFLARE
        assert len(strategy.techniques) == 1

    def test_get_headers_default_ip(self):
        strategy = CDNBypassStrategy(
            vendor=CDNVendor.GENERIC,
            techniques=[BypassTechnique.HEADER_XFF, BypassTechnique.HEADER_X_REAL_IP],
            vendor_headers={"Accept": "*/*"},
        )
        headers = strategy.get_headers()
        assert "X-Forwarded-For" in headers
        assert "X-Real-IP" in headers
        assert "Accept" in headers

    def test_get_headers_specific_ip(self):
        strategy = CDNBypassStrategy(
            vendor=CDNVendor.GENERIC,
            techniques=[BypassTechnique.HEADER_XFF],
            vendor_headers={},
        )
        headers = strategy.get_headers("192.168.1.50")
        assert headers["X-Forwarded-For"] == "192.168.1.50"

    def test_get_headers_forwarded(self):
        strategy = CDNBypassStrategy(
            vendor=CDNVendor.GENERIC,
            techniques=[BypassTechnique.HEADER_FORWARDED],
            vendor_headers={},
        )
        headers = strategy.get_headers("10.0.0.5")
        assert headers["Forwarded"] == "for=10.0.0.5"

    def test_to_dict(self):
        strategy = CDNBypassStrategy(
            vendor=CDNVendor.AKAMAI,
            techniques=[BypassTechnique.HEADER_TRUE_CLIENT_IP],
            vendor_headers={"True-Client-IP": "10.0.0.1"},
            success_rate=0.35,
        )
        d = strategy.to_dict()
        assert d["vendor"] == "akamai"
        assert d["techniques"] == ["true_client_ip"]
        assert d["success_rate"] == 0.35

    def test_cloudflare_strategy(self):
        s = get_cdn_strategy(CDNVendor.CLOUDFLARE)
        assert s.vendor == CDNVendor.CLOUDFLARE
        assert BypassTechnique.HEADER_CF_CONNECTING_IP in s.techniques
        assert BypassTechnique.DNS_HISTORY in s.techniques

    def test_akamai_strategy(self):
        s = get_cdn_strategy(CDNVendor.AKAMAI)
        assert s.vendor == CDNVendor.AKAMAI
        assert BypassTechnique.HEADER_TRUE_CLIENT_IP in s.techniques

    def test_cloudfront_strategy(self):
        s = get_cdn_strategy("aws_cloudfront")
        assert s.vendor == CDNVendor.AWS_CLOUDFRONT
        assert BypassTechnique.HEADER_XFF in s.techniques

    def test_fastly_strategy(self):
        s = get_cdn_strategy("fastly")
        assert s.vendor == CDNVendor.FASTLY
        assert "Fastly-Debug" in s.vendor_headers

    def test_imperva_strategy(self):
        s = get_cdn_strategy(CDNVendor.IMPERVA)
        assert BypassTechnique.MAIL_HEADER_LEAK in s.techniques

    def test_sucuri_strategy(self):
        s = get_cdn_strategy("sucuri")
        assert "X-Sucuri-ClientIP" in s.vendor_headers

    def test_azure_strategy(self):
        s = get_cdn_strategy(CDNVendor.AZURE_CDN)
        assert BypassTechnique.CERT_TRANSPARENCY in s.techniques

    def test_gcp_strategy(self):
        s = get_cdn_strategy(CDNVendor.GCP_CLOUD_ARMOR)
        assert "X-Cloud-Trace-Context" in s.vendor_headers

    def test_generic_fallback(self):
        s = get_cdn_strategy(CDNVendor.GENERIC)
        assert s.vendor == CDNVendor.GENERIC
        assert BypassTechnique.HEADER_XFF in s.techniques

    def test_unknown_vendor_gets_generic(self):
        s = get_cdn_strategy("totally_unknown_vendor")
        assert s.vendor == CDNVendor.GENERIC

    def test_get_all_strategies(self):
        strategies = get_all_strategies()
        assert len(strategies) >= 9
        assert "cloudflare" in strategies
        assert "akamai" in strategies
        assert "generic" in strategies


# ============================================================================
# OriginDiscovery Tests
# ============================================================================


class TestOriginHint:
    """Tests for OriginHint dataclass."""

    def test_creation(self):
        h = OriginHint(
            technique=BypassTechnique.DNS_HISTORY,
            value="203.0.113.45",
            confidence=0.75,
        )
        assert h.confidence == 0.75
        assert not h.verified

    def test_to_dict(self):
        h = OriginHint(
            technique=BypassTechnique.CERT_TRANSPARENCY,
            value="example.com",
            confidence=0.555,
            source="crt.sh",
            verified=True,
        )
        d = h.to_dict()
        assert d["technique"] == "cert_transparency"
        assert d["confidence"] == 0.555
        assert d["verified"] is True


class TestOriginDiscovery:
    """Tests for OriginDiscovery hints and registration."""

    def test_hints_cloudflare(self):
        od = OriginDiscovery()
        hints = od.get_hints("example.com", CDNVendor.CLOUDFLARE)
        techniques = [h.technique for h in hints]
        assert BypassTechnique.DNS_HISTORY in techniques
        assert BypassTechnique.SUBDOMAIN_ENUM in techniques
        assert BypassTechnique.CERT_TRANSPARENCY in techniques

    def test_hints_imperva(self):
        od = OriginDiscovery()
        hints = od.get_hints("example.com", CDNVendor.IMPERVA)
        techniques = [h.technique for h in hints]
        assert BypassTechnique.MAIL_HEADER_LEAK in techniques
        assert BypassTechnique.DNS_HISTORY in techniques

    def test_hints_subdomain_includes_common_subs(self):
        od = OriginDiscovery()
        hints = od.get_hints("example.com", CDNVendor.CLOUDFLARE)
        sub_hints = [h for h in hints if h.technique == BypassTechnique.SUBDOMAIN_ENUM]
        values = [h.value for h in sub_hints]
        assert "direct.example.com" in values
        assert "origin.example.com" in values
        assert "mail.example.com" in values

    def test_hints_generic_has_dns_history(self):
        od = OriginDiscovery()
        hints = od.get_hints("test.org", CDNVendor.GENERIC)
        techniques = [h.technique for h in hints]
        assert BypassTechnique.DNS_HISTORY in techniques

    def test_register_and_get_origins(self):
        od = OriginDiscovery()
        hint = OriginHint(
            technique=BypassTechnique.DNS_HISTORY,
            value="1.2.3.4",
            confidence=0.9,
            verified=True,
        )
        od.register_origin("example.com", hint)
        origins = od.get_known_origins("example.com")
        assert len(origins) == 1
        assert origins[0].value == "1.2.3.4"

    def test_get_best_origin_prefers_verified(self):
        od = OriginDiscovery()
        od.register_origin("example.com", OriginHint(
            technique=BypassTechnique.DNS_HISTORY,
            value="1.1.1.1",
            confidence=0.9,
            verified=False,
        ))
        od.register_origin("example.com", OriginHint(
            technique=BypassTechnique.CERT_TRANSPARENCY,
            value="2.2.2.2",
            confidence=0.5,
            verified=True,
        ))
        best = od.get_best_origin("example.com")
        assert best is not None
        assert best.value == "2.2.2.2"  # verified wins over confidence

    def test_get_best_origin_none_when_empty(self):
        od = OriginDiscovery()
        assert od.get_best_origin("nonexistent.com") is None

    def test_clear_specific_target(self):
        od = OriginDiscovery()
        od.register_origin("a.com", OriginHint(
            technique=BypassTechnique.DNS_HISTORY, value="1.1.1.1",
        ))
        od.register_origin("b.com", OriginHint(
            technique=BypassTechnique.DNS_HISTORY, value="2.2.2.2",
        ))
        od.clear("a.com")
        assert len(od.get_known_origins("a.com")) == 0
        assert len(od.get_known_origins("b.com")) == 1

    def test_clear_all(self):
        od = OriginDiscovery()
        od.register_origin("a.com", OriginHint(
            technique=BypassTechnique.DNS_HISTORY, value="1.1.1.1",
        ))
        od.register_origin("b.com", OriginHint(
            technique=BypassTechnique.DNS_HISTORY, value="2.2.2.2",
        ))
        od.clear()
        assert len(od.get_known_origins("a.com")) == 0
        assert len(od.get_known_origins("b.com")) == 0


# ============================================================================
# CacheAnalyzer Tests
# ============================================================================


class TestCacheAnalysis:
    """Tests for CacheAnalysis dataclass."""

    def test_creation(self):
        ca = CacheAnalysis(url="https://example.com/test")
        assert not ca.is_cached
        assert ca.cache_status == ""
        assert ca.cache_ttl == 0

    def test_to_dict(self):
        ca = CacheAnalysis(
            url="https://example.com/style.css",
            is_cached=True,
            cache_status="HIT",
            cache_ttl=3600,
            varies_on=["Accept-Encoding"],
            cdn_vendor="cloudflare",
        )
        d = ca.to_dict()
        assert d["is_cached"] is True
        assert d["cache_ttl"] == 3600
        assert "Accept-Encoding" in d["varies_on"]


class TestCacheAnalyzer:
    """Tests for CacheAnalyzer header inspection."""

    def setup_method(self):
        self.analyzer = CacheAnalyzer()

    def test_cloudflare_hit(self):
        result = self.analyzer.analyze(
            "https://example.com/style.css",
            {"CF-Cache-Status": "HIT", "CF-Ray": "abc123"},
        )
        assert result.is_cached is True
        assert result.cdn_vendor == "cloudflare"

    def test_cloudflare_miss(self):
        result = self.analyzer.analyze(
            "https://example.com/api/data",
            {"CF-Cache-Status": "MISS", "CF-Ray": "abc123"},
        )
        assert result.is_cached is False
        assert result.cdn_vendor == "cloudflare"

    def test_cloudfront_detection(self):
        result = self.analyzer.analyze(
            "https://example.com/img.png",
            {"X-Amz-Cf-Id": "abc123", "X-Cache": "Hit from cloudfront"},
        )
        assert result.cdn_vendor == "cloudfront"
        assert result.is_cached is True

    def test_fastly_detection(self):
        result = self.analyzer.analyze(
            "https://example.com/page",
            {"X-Fastly-Request-ID": "abc123", "X-Cache": "MISS"},
        )
        assert result.cdn_vendor == "fastly"
        assert result.is_cached is False

    def test_akamai_detection(self):
        result = self.analyzer.analyze(
            "https://example.com/",
            {"X-Akamai-Transformed": "9/2 orig"},
        )
        assert result.cdn_vendor == "akamai"

    def test_varnish_detection(self):
        result = self.analyzer.analyze(
            "https://example.com/",
            {"X-Varnish": "12345 67890"},
        )
        assert result.cdn_vendor == "varnish"

    def test_age_header_indicates_cache(self):
        result = self.analyzer.analyze(
            "https://example.com/page",
            {"Age": "300"},
        )
        assert result.is_cached is True
        assert result.cache_ttl == 300

    def test_cache_control_no_store(self):
        result = self.analyzer.analyze(
            "https://example.com/private",
            {"Cache-Control": "no-store, private"},
        )
        assert result.is_dynamic is True

    def test_cache_control_max_age(self):
        result = self.analyzer.analyze(
            "https://example.com/image.png",
            {"Cache-Control": "max-age=86400, public"},
        )
        assert result.cache_ttl == 86400

    def test_vary_header(self):
        result = self.analyzer.analyze(
            "https://example.com/page",
            {"Vary": "Accept-Encoding, User-Agent"},
        )
        assert "Accept-Encoding" in result.varies_on
        assert "User-Agent" in result.varies_on

    def test_cacheable_path_css(self):
        result = self.analyzer.analyze(
            "https://example.com/assets/style.css",
            {},
        )
        assert result.cacheable_path is True

    def test_cacheable_path_js(self):
        result = self.analyzer.analyze(
            "https://example.com/bundle.js",
            {},
        )
        assert result.cacheable_path is True

    def test_non_cacheable_path_api(self):
        result = self.analyzer.analyze(
            "https://example.com/api/users",
            {},
        )
        assert result.cacheable_path is False

    def test_redirect_is_dynamic(self):
        result = self.analyzer.analyze(
            "https://example.com/old-page",
            {"Location": "https://example.com/new-page"},
            status_code=301,
        )
        assert result.is_dynamic is True

    def test_set_cookie_is_dynamic(self):
        result = self.analyzer.analyze(
            "https://example.com/login",
            {"Set-Cookie": "session=abc123; Path=/"},
        )
        assert result.is_dynamic is True
        assert any("Set-Cookie" in n for n in result.notes)

    def test_error_status_note(self):
        result = self.analyzer.analyze(
            "https://example.com/missing",
            {},
            status_code=404,
        )
        assert any("404" in n for n in result.notes)

    def test_server_header_cloudflare(self):
        result = self.analyzer.analyze(
            "https://example.com/",
            {"Server": "cloudflare"},
        )
        assert result.cdn_vendor == "cloudflare"

    def test_server_header_akamai(self):
        result = self.analyzer.analyze(
            "https://example.com/",
            {"Server": "AkamaiGHost"},
        )
        assert result.cdn_vendor == "akamai"

    def test_stale_is_cached(self):
        result = self.analyzer.analyze(
            "https://example.com/old.css",
            {"X-Cache": "STALE"},
        )
        assert result.is_cached is True


# ============================================================================
# PathMutator Tests
# ============================================================================


class TestPathMutation:
    """Tests for PathMutation dataclass."""

    def test_creation(self):
        pm = PathMutation(
            original="/admin",
            mutated="/Admin",
            technique="case_variation",
        )
        assert pm.original == "/admin"
        assert pm.risk_level == "low"

    def test_to_dict(self):
        pm = PathMutation(
            original="/test",
            mutated="/test%00",
            technique="null_byte",
            risk_level="high",
        )
        d = pm.to_dict()
        assert d["risk_level"] == "high"
        assert d["technique"] == "null_byte"


class TestPathMutator:
    """Tests for PathMutator URL mutations."""

    def setup_method(self):
        self.mutator = PathMutator()

    def test_mutate_returns_mutations(self):
        mutations = self.mutator.mutate("/admin/login")
        assert len(mutations) >= 5

    def test_double_encode(self):
        mutations = self.mutator.mutate("/admin/login")
        double_encoded = [m for m in mutations if m.technique == "double_url_encode"]
        assert len(double_encoded) == 1
        assert "%252F" in double_encoded[0].mutated

    def test_dot_prefix(self):
        mutations = self.mutator.mutate("/admin")
        dot = [m for m in mutations if m.technique == "dot_prefix"]
        assert len(dot) == 1
        assert dot[0].mutated == "/./admin"

    def test_trailing_slash(self):
        mutations = self.mutator.mutate("/api")
        trailing = [m for m in mutations if m.technique == "trailing_slash"]
        assert len(trailing) == 1
        assert trailing[0].mutated == "/api/"

    def test_trailing_dot_slash(self):
        mutations = self.mutator.mutate("/api")
        trailing = [m for m in mutations if m.technique == "trailing_dot_slash"]
        assert len(trailing) == 1
        assert trailing[0].mutated == "/api/."

    def test_null_byte_high_risk(self):
        mutations = self.mutator.mutate("/admin")
        null_byte = [m for m in mutations if m.technique == "null_byte"]
        assert len(null_byte) == 1
        assert null_byte[0].risk_level == "high"
        assert null_byte[0].mutated == "/admin%00"

    def test_semicolon_parameter(self):
        mutations = self.mutator.mutate("/admin/login")
        semi = [m for m in mutations if m.technique == "semicolon_parameter"]
        assert len(semi) == 1
        assert ";bypass=1/" in semi[0].mutated

    def test_fragment_injection(self):
        mutations = self.mutator.mutate("/page")
        frag = [m for m in mutations if m.technique == "fragment_injection"]
        assert len(frag) == 1
        assert frag[0].mutated == "/page#"

    def test_all_originals_match_input(self):
        mutations = self.mutator.mutate("/test/path")
        for m in mutations:
            assert m.original == "/test/path"


# ============================================================================
# MethodOverride Tests
# ============================================================================


class TestMethodOverride:
    """Tests for MethodOverride dataclass."""

    def test_creation(self):
        mo = MethodOverride(
            original_method="POST",
            override_method="GET",
            headers={"X-HTTP-Method-Override": "GET"},
        )
        assert mo.original_method == "POST"
        assert mo.override_method == "GET"

    def test_to_dict(self):
        mo = MethodOverride(
            original_method="POST",
            override_method="DELETE",
            headers={"X-HTTP-Method": "DELETE"},
            description="Test",
        )
        d = mo.to_dict()
        assert d["override_method"] == "DELETE"


class TestGenerateMethodOverrides:
    """Tests for generate_method_overrides()."""

    def test_default_get(self):
        overrides = generate_method_overrides()
        assert len(overrides) == 4
        for o in overrides:
            assert o.override_method == "GET"
            assert o.original_method == "POST"

    def test_custom_method(self):
        overrides = generate_method_overrides("DELETE")
        for o in overrides:
            assert o.override_method == "DELETE"

    def test_includes_http_method_override(self):
        overrides = generate_method_overrides("PUT")
        headers_all = {}
        for o in overrides:
            headers_all.update(o.headers)
        assert "X-HTTP-Method-Override" in headers_all
        assert "X-Method-Override" in headers_all
        assert "X-HTTP-Method" in headers_all

    def test_all_have_descriptions(self):
        overrides = generate_method_overrides("PATCH")
        for o in overrides:
            assert o.description


# ============================================================================
# WAFBypassEngine — Full Façade Tests
# ============================================================================


class TestWAFBypassEngine:
    """Tests for the WAFBypassEngine façade."""

    def setup_method(self):
        self.engine = WAFBypassEngine()

    # ── Header Operations ────────────────────────

    def test_get_bypass_headers_cloudflare(self):
        headers = self.engine.get_bypass_headers(CDNVendor.CLOUDFLARE)
        assert "CF-Connecting-IP" in headers

    def test_get_bypass_headers_generic(self):
        headers = self.engine.get_bypass_headers()
        assert "X-Forwarded-For" in headers

    def test_get_bypass_headers_with_ip(self):
        headers = self.engine.get_bypass_headers(CDNVendor.GENERIC, "10.0.0.99")
        assert headers["X-Forwarded-For"] == "10.0.0.99"

    def test_get_all_spoof_headers(self):
        headers = self.engine.get_all_spoof_headers("1.2.3.4")
        assert len(headers) == 12
        assert all(isinstance(h, SpoofHeader) for h in headers)

    def test_get_spoof_profile(self):
        p = self.engine.get_spoof_profile("google_crawler")
        assert p is not None
        assert p.client_type == ClientType.SEARCH_CRAWLER

    def test_get_all_profiles(self):
        profiles = self.engine.get_all_profiles()
        assert len(profiles) >= 8

    def test_get_profiles_by_type(self):
        crawlers = self.engine.get_profiles_by_type(ClientType.SEARCH_CRAWLER)
        assert len(crawlers) >= 2

    # ── CDN Strategy ─────────────────────────────

    def test_get_cdn_strategy(self):
        s = self.engine.get_cdn_strategy(CDNVendor.AKAMAI)
        assert s.vendor == CDNVendor.AKAMAI

    def test_get_all_strategies(self):
        strategies = self.engine.get_all_strategies()
        assert len(strategies) >= 9

    # ── Origin Discovery ──────────────────────────

    def test_get_origin_hints(self):
        hints = self.engine.get_origin_hints("test.com", CDNVendor.CLOUDFLARE)
        assert len(hints) > 0

    def test_register_and_retrieve_origin(self):
        hint = OriginHint(
            technique=BypassTechnique.DNS_HISTORY,
            value="5.5.5.5",
            confidence=0.8,
            verified=True,
        )
        self.engine.register_origin("test.com", hint)
        origins = self.engine.get_known_origins("test.com")
        assert len(origins) == 1
        assert origins[0].value == "5.5.5.5"

    def test_get_best_origin(self):
        self.engine.register_origin("test.com", OriginHint(
            technique=BypassTechnique.DNS_HISTORY,
            value="1.1.1.1",
            confidence=0.5,
        ))
        self.engine.register_origin("test.com", OriginHint(
            technique=BypassTechnique.CERT_TRANSPARENCY,
            value="2.2.2.2",
            confidence=0.9,
        ))
        best = self.engine.get_best_origin("test.com")
        assert best is not None
        assert best.value == "2.2.2.2"

    # ── Cache Analysis ────────────────────────────

    def test_analyze_cache(self):
        result = self.engine.analyze_cache(
            "https://example.com/style.css",
            {"CF-Cache-Status": "HIT", "CF-Ray": "abc"},
        )
        assert result.is_cached is True
        assert result.cdn_vendor == "cloudflare"

    # ── Path Mutation ─────────────────────────────

    def test_mutate_path(self):
        mutations = self.engine.mutate_path("/admin")
        assert len(mutations) >= 5
        assert all(isinstance(m, PathMutation) for m in mutations)

    # ── Method Override ───────────────────────────

    def test_get_method_overrides(self):
        overrides = self.engine.get_method_overrides("DELETE")
        assert len(overrides) == 4

    # ── Statistics ────────────────────────────────

    def test_record_and_get_stats(self):
        self.engine.record_bypass_attempt("cloudflare", "xff", True)
        self.engine.record_bypass_attempt("cloudflare", "xff", False)
        self.engine.record_bypass_attempt("cloudflare", "xff", True)

        stats = self.engine.get_bypass_stats()
        assert "cloudflare:xff" in stats
        assert stats["cloudflare:xff"]["attempts"] == 3
        assert stats["cloudflare:xff"]["successes"] == 2
        assert abs(stats["cloudflare:xff"]["success_rate"] - 2 / 3) < 0.01

    def test_vendor_success_rates(self):
        self.engine.record_bypass_attempt("akamai", "tcp", True)
        self.engine.record_bypass_attempt("akamai", "tcp", True)
        self.engine.record_bypass_attempt("akamai", "xff", False)

        rates = self.engine.get_vendor_success_rates()
        assert "akamai" in rates
        assert abs(rates["akamai"] - 2 / 3) < 0.01

    def test_reset_stats(self):
        self.engine.record_bypass_attempt("test", "tech", True)
        self.engine.reset_stats()
        assert len(self.engine.get_bypass_stats()) == 0

    def test_empty_stats(self):
        engine = WAFBypassEngine()
        stats = engine.get_bypass_stats()
        assert stats == {}

    def test_vendor_success_rates_empty(self):
        engine = WAFBypassEngine()
        rates = engine.get_vendor_success_rates()
        assert rates == {}

    # ── Dashboard ─────────────────────────────────

    def test_get_dashboard_data(self):
        d = self.engine.get_dashboard_data()
        assert d["strategies_count"] >= 9
        assert d["profiles_count"] >= 8
        assert d["techniques_count"] == 22
        assert isinstance(d["available_strategies"], list)
        assert isinstance(d["available_profiles"], list)

    def test_dashboard_with_stats(self):
        self.engine.record_bypass_attempt("cf", "xff", True)
        d = self.engine.get_dashboard_data()
        assert "cf:xff" in d["bypass_stats"]


# ============================================================================
# Edge Cases & Integration Tests
# ============================================================================


class TestEdgeCases:
    """Edge case and integration tests."""

    def test_cdn_strategy_with_string_vendor(self):
        s = get_cdn_strategy("cloudflare")
        assert s.vendor == CDNVendor.CLOUDFLARE

    def test_cdn_strategy_with_enum_vendor(self):
        s = get_cdn_strategy(CDNVendor.FASTLY)
        assert s.vendor == CDNVendor.FASTLY

    def test_spoof_headers_with_ipv6(self):
        headers = generate_spoof_headers("::1")
        xff = [h for h in headers if h.name == "X-Forwarded-For"]
        assert len(xff) == 1
        assert xff[0].value == "::1"

    def test_cache_analysis_empty_headers(self):
        analyzer = CacheAnalyzer()
        result = analyzer.analyze("https://example.com/", {})
        assert result.cdn_vendor == ""
        assert not result.is_cached
        assert result.cache_ttl == 0

    def test_path_mutator_root_path(self):
        mutator = PathMutator()
        mutations = mutator.mutate("/")
        assert len(mutations) >= 3

    def test_path_mutator_empty_path(self):
        mutator = PathMutator()
        mutations = mutator.mutate("")
        assert len(mutations) >= 3

    def test_origin_hints_unknown_vendor(self):
        od = OriginDiscovery()
        hints = od.get_hints("example.com", CDNVendor.UNKNOWN)
        # Unknown vendor falls back to generic strategy
        assert isinstance(hints, list)

    def test_multiple_engines_independent(self):
        e1 = WAFBypassEngine()
        e2 = WAFBypassEngine()
        e1.record_bypass_attempt("v1", "t1", True)
        assert len(e1.get_bypass_stats()) == 1
        assert len(e2.get_bypass_stats()) == 0

    def test_cache_analysis_cacheable_extensions(self):
        analyzer = CacheAnalyzer()
        for ext in [".js", ".css", ".png", ".woff2", ".webp"]:
            result = analyzer.analyze(f"https://example.com/file{ext}", {})
            assert result.cacheable_path is True, f"Expected cacheable for {ext}"

    def test_cache_analysis_non_cacheable_paths(self):
        analyzer = CacheAnalyzer()
        for path in ["/api/endpoint", "/login", "/dashboard", "/admin"]:
            result = analyzer.analyze(f"https://example.com{path}", {})
            assert result.cacheable_path is False, f"Expected non-cacheable for {path}"

    def test_method_override_post_original(self):
        """All overrides use POST as the original method."""
        overrides = generate_method_overrides("GET")
        for o in overrides:
            assert o.original_method == "POST"

    def test_strategy_headers_include_vendor_specific(self):
        """Verify vendor-specific headers are included."""
        cf = get_cdn_strategy(CDNVendor.CLOUDFLARE)
        headers = cf.get_headers("10.0.0.1")
        assert "CF-Connecting-IP" in headers
        assert headers["CF-Connecting-IP"] == "10.0.0.1"

    def test_origin_discovery_multiple_registrations(self):
        od = OriginDiscovery()
        for i in range(5):
            od.register_origin("site.com", OriginHint(
                technique=BypassTechnique.DNS_HISTORY,
                value=f"1.1.1.{i}",
                confidence=i * 0.1,
            ))
        assert len(od.get_known_origins("site.com")) == 5
        best = od.get_best_origin("site.com")
        assert best is not None
        assert best.value == "1.1.1.4"  # highest confidence
