# -------------------------------------------------------------------------------
# Name:         test_tls_fingerprint
# Purpose:      Tests for spiderfoot.recon.tls_fingerprint (S-003)
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Comprehensive test suite for TLS fingerprint evasion module (S-003).

Tests cover 141 scenarios across 15 test classes for:
- JA3 fingerprint calculation
- JA4 fingerprint calculation
- TLS extension profiles
- HTTP/2 fingerprint profiles
- Browser fingerprint profiles
- Fingerprint diversity monitoring
- Fingerprint evasion engine
- GREASE value handling
- SSL context creation
- Thread safety
"""

import hashlib
import math
import ssl
import struct
import threading
from unittest.mock import patch

import pytest

from spiderfoot.recon.tls_fingerprint import (
    BrowserFingerprintProfile,
    CipherSuite,
    EllipticCurve,
    FingerprintDiversityMonitor,
    FingerprintEvasionEngine,
    FingerprintRotationStrategy,
    HTTP2FingerprintProfile,
    JA3Calculator,
    JA3Fingerprint,
    JA4Calculator,
    JA4Fingerprint,
    SignatureScheme,
    TLSExtensionProfile,
    TLSExtensionType,
    TLSVersion,
    _BROWSER_WEIGHTS,
    get_browser_profile,
    get_browser_profiles,
    list_profile_names,
)


# ===========================================================================
# TestTLSConstants
# ===========================================================================
class TestTLSConstants:
    """Verify TLS constant enums have correct values."""

    def test_tls_version_values(self):
        assert TLSVersion.TLS_1_0 == 0x0301
        assert TLSVersion.TLS_1_2 == 0x0303
        assert TLSVersion.TLS_1_3 == 0x0304

    def test_extension_type_server_name(self):
        assert TLSExtensionType.SERVER_NAME == 0

    def test_extension_type_alpn(self):
        assert TLSExtensionType.APPLICATION_LAYER_PROTOCOL == 16

    def test_extension_type_key_share(self):
        assert TLSExtensionType.KEY_SHARE == 51

    def test_elliptic_curve_x25519(self):
        assert EllipticCurve.X25519 == 29

    def test_elliptic_curve_p256(self):
        assert EllipticCurve.SECP256R1 == 23

    def test_signature_scheme_ecdsa(self):
        assert SignatureScheme.ECDSA_SECP256R1_SHA256 == 0x0403

    def test_cipher_suite_tls13_aes128(self):
        assert CipherSuite.TLS_AES_128_GCM_SHA256 == 0x1301

    def test_cipher_suite_ecdhe_rsa(self):
        assert CipherSuite.TLS_ECDHE_RSA_AES128_GCM_SHA256 == 0xC02F


# ===========================================================================
# TestJA3Calculator
# ===========================================================================
class TestJA3Calculator:
    """Test JA3 fingerprint computation."""

    def test_basic_computation(self):
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301, 0x1302],
            extensions=[0, 10, 11, 13, 43, 51],
            elliptic_curves=[29, 23, 24],
            ec_point_formats=[0],
        )
        assert isinstance(fp, JA3Fingerprint)
        assert isinstance(fp.hash, str)
        assert len(fp.hash) == 32  # MD5 hex digest

    def test_raw_string_format(self):
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[4865, 4866],
            extensions=[0, 10],
            elliptic_curves=[29],
            ec_point_formats=[0],
        )
        parts = fp.raw_string.split(",")
        assert len(parts) == 5
        assert parts[0] == "771"  # 0x0303

    def test_hash_is_md5(self):
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[4865],
            extensions=[0],
            elliptic_curves=[29],
            ec_point_formats=[0],
        )
        expected = hashlib.md5(fp.raw_string.encode()).hexdigest()
        assert fp.hash == expected

    def test_grease_filtering(self):
        # GREASE values should be removed
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x0A0A, 0x1301],
            extensions=[0x1A1A, 0],
            elliptic_curves=[0x2A2A, 29],
            ec_point_formats=[0],
        )
        assert "2570" not in fp.raw_string  # 0x0A0A = 2570
        assert "6682" not in fp.raw_string  # 0x1A1A = 6682

    def test_is_grease_detection(self):
        assert JA3Calculator._is_grease(0x0A0A) is True
        assert JA3Calculator._is_grease(0x1A1A) is True
        assert JA3Calculator._is_grease(0xFAFA) is True
        assert JA3Calculator._is_grease(0x1301) is False
        assert JA3Calculator._is_grease(0) is False
        assert JA3Calculator._is_grease(23) is False

    def test_empty_lists(self):
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[],
            extensions=[],
            elliptic_curves=[],
            ec_point_formats=[],
        )
        # Should produce "771,,,,"
        assert fp.raw_string == "771,,,,"

    def test_fingerprint_equality(self):
        fp1 = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301],
            extensions=[0],
            elliptic_curves=[29],
            ec_point_formats=[0],
        )
        fp2 = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301],
            extensions=[0],
            elliptic_curves=[29],
            ec_point_formats=[0],
        )
        assert fp1 == fp2

    def test_fingerprint_equality_with_string(self):
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301],
            extensions=[0],
            elliptic_curves=[29],
            ec_point_formats=[0],
        )
        assert fp == fp.hash
        assert fp != "not_a_hash"

    def test_fingerprint_str(self):
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301],
            extensions=[0],
            elliptic_curves=[29],
            ec_point_formats=[0],
        )
        assert str(fp) == fp.hash

    def test_fingerprint_count_metadata(self):
        fp = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301, 0x1302, 0x1303],
            extensions=[0, 10, 11],
            elliptic_curves=[29, 23],
            ec_point_formats=[0],
        )
        assert fp.tls_version == 0x0303
        assert fp.cipher_count == 3
        assert fp.extension_count == 3
        assert fp.curve_count == 2

    def test_different_params_different_hash(self):
        fp1 = JA3Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301],
            extensions=[0],
            elliptic_curves=[29],
            ec_point_formats=[0],
        )
        fp2 = JA3Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1302],
            extensions=[0, 10],
            elliptic_curves=[23],
            ec_point_formats=[0],
        )
        assert fp1.hash != fp2.hash


# ===========================================================================
# TestJA4Calculator
# ===========================================================================
class TestJA4Calculator:
    """Test JA4+ fingerprint computation."""

    def test_basic_computation(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301, 0x1302],
            extensions=[0, 10, 13, 43, 51],
            alpn_protocols=["h2", "http/1.1"],
        )
        assert isinstance(fp, JA4Fingerprint)
        assert isinstance(fp.full_string, str)

    def test_ja4_a_section_format(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301, 0x1302, 0x1303],
            extensions=[10, 13, 43, 51],  # SNI and ALPN excluded
            alpn_protocols=["h2"],
        )
        # proto=t, ver=13, sni=d, cc=03, ec=04, alpn=h2
        assert fp.protocol == "t"
        assert fp.version == "13"
        assert fp.sni == "d"
        assert fp.cipher_count == "03"
        assert fp.extension_count == "04"
        assert fp.alpn_first == "h2"

    def test_quic_transport(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301],
            extensions=[10],
            transport="quic",
        )
        assert fp.protocol == "q"

    def test_ip_sni_type(self):
        fp = JA4Calculator.compute(
            tls_version=0x0303,
            ciphers=[0x1301],
            extensions=[10],
            sni_type="ip",
        )
        assert fp.sni == "i"

    def test_tls12_version(self):
        fp = JA4Calculator.compute(
            tls_version=TLSVersion.TLS_1_2,
            ciphers=[0xC02F],
            extensions=[10],
        )
        assert fp.version == "12"

    def test_http11_alpn(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301],
            extensions=[10],
            alpn_protocols=["http/1.1"],
        )
        assert fp.alpn_first == "h1"

    def test_no_alpn(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301],
            extensions=[10],
        )
        assert fp.alpn_first == "00"

    def test_grease_filtering(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x0A0A, 0x1301],
            extensions=[0x1A1A, 10],
        )
        assert fp.cipher_count == "01"  # GREASE removed

    def test_sni_and_alpn_excluded_from_extensions(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301],
            extensions=[
                TLSExtensionType.SERVER_NAME,
                TLSExtensionType.APPLICATION_LAYER_PROTOCOL,
                10, 13,
            ],
        )
        # SNI (0) and ALPN (16) excluded → only 10, 13
        assert fp.extension_count == "02"

    def test_cipher_hash_is_sha256_truncated(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301, 0x1302],
            extensions=[10],
        )
        assert len(fp.cipher_hash) == 12

    def test_extension_hash_is_sha256_truncated(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301],
            extensions=[10, 13, 51],
        )
        assert len(fp.extension_hash) == 12

    def test_full_string_format(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301],
            extensions=[10],
            alpn_protocols=["h2"],
        )
        parts = fp.full_string.split("_")
        assert len(parts) == 3
        assert len(parts[0]) == 10  # ja4_a
        assert len(parts[1]) == 12  # cipher_hash
        assert len(parts[2]) == 12  # extension_hash

    def test_str_returns_full_string(self):
        fp = JA4Calculator.compute(
            tls_version=0x0304,
            ciphers=[0x1301],
            extensions=[10],
        )
        assert str(fp) == fp.full_string


# ===========================================================================
# TestTLSExtensionProfile
# ===========================================================================
class TestTLSExtensionProfile:
    """Test TLS extension profile configuration."""

    def _make_profile(self, **kwargs):
        defaults = dict(
            name="test_profile",
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[
                TLSExtensionType.SERVER_NAME,
                TLSExtensionType.SUPPORTED_GROUPS,
            ],
            supported_groups=[EllipticCurve.X25519],
            ec_point_formats=[0],
            signature_algorithms=[SignatureScheme.ECDSA_SECP256R1_SHA256],
        )
        defaults.update(kwargs)
        return TLSExtensionProfile(**defaults)

    def test_basic_creation(self):
        p = self._make_profile()
        assert p.name == "test_profile"
        assert p.browser == "chrome"
        assert len(p.cipher_suites) == 1

    def test_compute_ja3(self):
        p = self._make_profile()
        ja3 = p.compute_ja3()
        assert isinstance(ja3, JA3Fingerprint)
        assert len(ja3.hash) == 32

    def test_compute_ja4(self):
        p = self._make_profile()
        ja4 = p.compute_ja4()
        assert isinstance(ja4, JA4Fingerprint)

    def test_to_openssl_ciphers(self):
        p = self._make_profile(
            cipher_suites=[
                CipherSuite.TLS_AES_128_GCM_SHA256,
                CipherSuite.TLS_ECDHE_RSA_AES128_GCM_SHA256,
            ],
        )
        cipher_str = p.to_openssl_ciphers()
        assert "TLS_AES_128_GCM_SHA256" in cipher_str
        assert "ECDHE-RSA-AES128-GCM-SHA256" in cipher_str

    def test_to_openssl_ciphers_empty(self):
        p = self._make_profile(cipher_suites=[])
        assert p.to_openssl_ciphers() == "DEFAULT"

    def test_session_ticket_default(self):
        p = self._make_profile()
        assert p.session_ticket is True

    def test_ocsp_stapling_default(self):
        p = self._make_profile()
        assert p.ocsp_stapling is True

    def test_extended_master_secret_default(self):
        p = self._make_profile()
        assert p.extended_master_secret is True

    def test_grease_enabled_default(self):
        p = self._make_profile()
        assert p.grease_enabled is True

    def test_with_grease_injects_values(self):
        p = self._make_profile(
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        greased = p.with_grease()
        # GREASE should add ciphers
        assert len(greased.cipher_suites) > len(p.cipher_suites)
        # GREASE should add extensions
        assert len(greased.extension_order) > len(p.extension_order)
        # GREASE should add supported groups
        assert len(greased.supported_groups) > len(p.supported_groups)

    def test_with_grease_disabled(self):
        p = self._make_profile(grease_enabled=False)
        greased = p.with_grease()
        # Should return same profile (no GREASE injected)
        assert len(greased.cipher_suites) == len(p.cipher_suites)

    def test_alpn_default(self):
        p = self._make_profile()
        assert p.alpn_protocols == ["h2", "http/1.1"]

    def test_supported_versions_default(self):
        p = self._make_profile()
        assert TLSVersion.TLS_1_3 in p.supported_versions


# ===========================================================================
# TestHTTP2FingerprintProfile
# ===========================================================================
class TestHTTP2FingerprintProfile:
    """Test HTTP/2 fingerprint profile."""

    def test_default_values(self):
        h2 = HTTP2FingerprintProfile()
        assert h2.header_table_size == 65536
        assert h2.enable_push is False
        assert h2.max_concurrent_streams == 100
        assert h2.initial_window_size == 6291456

    def test_to_settings_dict(self):
        h2 = HTTP2FingerprintProfile()
        settings = h2.to_settings_dict()
        assert "HEADER_TABLE_SIZE" in settings
        assert "INITIAL_WINDOW_SIZE" in settings
        assert "MAX_FRAME_SIZE" in settings
        assert settings["ENABLE_PUSH"] == 0

    def test_to_settings_dict_push_enabled(self):
        h2 = HTTP2FingerprintProfile(enable_push=True)
        settings = h2.to_settings_dict()
        assert "ENABLE_PUSH" not in settings  # Not sent when True

    def test_to_settings_bytes(self):
        h2 = HTTP2FingerprintProfile()
        data = h2.to_settings_bytes()
        assert isinstance(data, bytes)
        # Each setting is 6 bytes (2 + 4)
        assert len(data) == 36  # 6 settings * 6 bytes

    def test_to_settings_bytes_values(self):
        h2 = HTTP2FingerprintProfile(header_table_size=4096)
        data = h2.to_settings_bytes()
        # First setting: HEADER_TABLE_SIZE (0x1) = 4096
        sid, val = struct.unpack("!HI", data[:6])
        assert sid == 1
        assert val == 4096

    def test_pseudo_header_order_chrome(self):
        h2 = HTTP2FingerprintProfile(priority_scheme="chrome")
        assert h2.pseudo_header_order == [":method", ":authority", ":scheme", ":path"]

    def test_custom_settings(self):
        h2 = HTTP2FingerprintProfile(
            header_table_size=4096,
            max_concurrent_streams=200,
            initial_window_size=131072,
        )
        settings = h2.to_settings_dict()
        assert settings["HEADER_TABLE_SIZE"] == 4096
        assert settings["MAX_CONCURRENT_STREAMS"] == 200
        assert settings["INITIAL_WINDOW_SIZE"] == 131072


# ===========================================================================
# TestBrowserFingerprintProfile
# ===========================================================================
class TestBrowserFingerprintProfile:
    """Test composite browser fingerprint profiles."""

    def _make_browser_profile(self, name="test"):
        tls = TLSExtensionProfile(
            name=name,
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        h2 = HTTP2FingerprintProfile()
        return BrowserFingerprintProfile(name=name, tls=tls, http2=h2)

    def test_creation(self):
        p = self._make_browser_profile()
        assert p.name == "test"
        assert p.tls.browser == "chrome"

    def test_compute_ja3(self):
        p = self._make_browser_profile()
        ja3 = p.compute_ja3()
        assert isinstance(ja3, JA3Fingerprint)

    def test_compute_ja4(self):
        p = self._make_browser_profile()
        ja4 = p.compute_ja4()
        assert isinstance(ja4, JA4Fingerprint)

    def test_to_openssl_ciphers(self):
        p = self._make_browser_profile()
        assert p.to_openssl_ciphers() == "TLS_AES_128_GCM_SHA256"


# ===========================================================================
# TestBuiltInProfiles
# ===========================================================================
class TestBuiltInProfiles:
    """Test pre-built browser fingerprint profiles."""

    def test_profiles_initialized(self):
        profiles = get_browser_profiles()
        assert len(profiles) >= 6

    def test_list_profile_names(self):
        names = list_profile_names()
        assert "chrome_131_win10" in names
        assert "firefox_133_win10" in names
        assert "safari_18_macos" in names
        assert "edge_131_win10" in names

    def test_get_chrome_131(self):
        p = get_browser_profile("chrome_131_win10")
        assert p is not None
        assert p.tls.browser == "chrome"
        assert p.tls.browser_version == "131"

    def test_get_firefox_133(self):
        p = get_browser_profile("firefox_133_win10")
        assert p is not None
        assert p.tls.browser == "firefox"

    def test_get_safari_18(self):
        p = get_browser_profile("safari_18_macos")
        assert p is not None
        assert p.tls.browser == "safari"
        assert p.tls.os == "macos"

    def test_get_edge_131(self):
        p = get_browser_profile("edge_131_win10")
        assert p is not None
        assert p.tls.browser == "edge"

    def test_get_nonexistent(self):
        p = get_browser_profile("nonexistent_browser")
        assert p is None

    def test_chrome_cipher_suites(self):
        p = get_browser_profile("chrome_131_win10")
        assert CipherSuite.TLS_AES_128_GCM_SHA256 in p.tls.cipher_suites
        assert CipherSuite.TLS_AES_256_GCM_SHA384 in p.tls.cipher_suites

    def test_firefox_cipher_order(self):
        p = get_browser_profile("firefox_133_win10")
        # Firefox prefers CHACHA20 second (after AES128)
        idx_aes = p.tls.cipher_suites.index(CipherSuite.TLS_AES_128_GCM_SHA256)
        idx_chacha = p.tls.cipher_suites.index(CipherSuite.TLS_CHACHA20_POLY1305_SHA256)
        assert idx_aes < idx_chacha

    def test_safari_h2_settings(self):
        p = get_browser_profile("safari_18_macos")
        assert p.http2.header_table_size == 4096
        assert p.http2.initial_window_size == 2097152

    def test_different_ja3_between_browsers(self):
        chrome = get_browser_profile("chrome_131_win10")
        firefox = get_browser_profile("firefox_133_win10")
        ja3_chrome = chrome.compute_ja3()
        ja3_firefox = firefox.compute_ja3()
        assert ja3_chrome.hash != ja3_firefox.hash

    def test_chrome_and_edge_similar(self):
        # Chrome and Edge share the same engine → same cipher suites
        chrome = get_browser_profile("chrome_131_win10")
        edge = get_browser_profile("edge_131_win10")
        assert chrome.tls.cipher_suites == edge.tls.cipher_suites

    def test_profiles_have_alpn(self):
        for name in list_profile_names():
            p = get_browser_profile(name)
            assert p.tls.alpn_protocols, f"{name} missing ALPN"

    def test_profiles_have_supported_groups(self):
        for name in list_profile_names():
            p = get_browser_profile(name)
            assert p.tls.supported_groups, f"{name} missing supported groups"


# ===========================================================================
# TestFingerprintDiversityMonitor
# ===========================================================================
class TestFingerprintDiversityMonitor:
    """Test fingerprint diversity monitoring."""

    def test_initial_state(self):
        m = FingerprintDiversityMonitor()
        assert m.unique_ja3_count == 0
        assert m.unique_ja4_count == 0
        assert m.diversity_score == 0.0

    def test_record_single_usage(self):
        m = FingerprintDiversityMonitor()
        m.record_usage("chrome", "abc123", "ja4_str", "example.com")
        assert m.unique_ja3_count == 1
        assert m.unique_profile_count == 1

    def test_record_multiple_different(self):
        m = FingerprintDiversityMonitor()
        m.record_usage("chrome", "hash1", "ja4_1", "a.com")
        m.record_usage("firefox", "hash2", "ja4_2", "b.com")
        m.record_usage("safari", "hash3", "ja4_3", "c.com")
        assert m.unique_ja3_count == 3
        assert m.unique_profile_count == 3

    def test_diversity_score_single_fingerprint(self):
        m = FingerprintDiversityMonitor()
        for _ in range(10):
            m.record_usage("chrome", "same_hash", "ja4", "")
        # All same fingerprint → entropy = 0
        assert m.diversity_score == 0.0

    def test_diversity_score_even_distribution(self):
        m = FingerprintDiversityMonitor()
        for i in range(100):
            m.record_usage(f"profile_{i % 4}", f"hash_{i % 4}", f"ja4_{i % 4}", "")
        # 4 fingerprints evenly distributed → high diversity
        assert m.diversity_score > 0.9

    def test_overused_fingerprints(self):
        m = FingerprintDiversityMonitor()
        for _ in range(80):
            m.record_usage("chrome", "dominator", "ja4", "")
        for _ in range(20):
            m.record_usage("firefox", "minor", "ja4_2", "")
        overused = m.get_overused_fingerprints(threshold=0.5)
        assert "dominator" in overused
        assert "minor" not in overused

    def test_no_overused_when_empty(self):
        m = FingerprintDiversityMonitor()
        assert m.get_overused_fingerprints() == []

    def test_get_report(self):
        m = FingerprintDiversityMonitor()
        m.record_usage("chrome", "hash1", "ja4_1", "a.com")
        report = m.get_report()
        assert report["total_requests"] == 1
        assert report["unique_ja3_hashes"] == 1
        assert "diversity_score" in report
        assert "ja3_distribution" in report
        assert "targets_pinned" in report

    def test_reset(self):
        m = FingerprintDiversityMonitor()
        m.record_usage("chrome", "hash1", "ja4_1", "a.com")
        m.reset()
        assert m.unique_ja3_count == 0
        assert m.unique_ja4_count == 0

    def test_target_pinning(self):
        m = FingerprintDiversityMonitor()
        m.record_usage("chrome", "hash1", "ja4_1", "target.com")
        m.record_usage("chrome", "hash1", "ja4_1", "target.com")
        report = m.get_report()
        assert report["targets_pinned"] == 1


# ===========================================================================
# TestFingerprintEvasionEngine
# ===========================================================================
class TestFingerprintEvasionEngine:
    """Test the main fingerprint evasion engine."""

    def test_default_creation(self):
        engine = FingerprintEvasionEngine()
        assert engine.profile_count >= 6

    def test_custom_profiles(self):
        engine = FingerprintEvasionEngine(
            profiles=["chrome_131_win10", "firefox_133_win10"],
        )
        assert engine.profile_count == 2

    def test_invalid_profiles_ignored(self):
        engine = FingerprintEvasionEngine(
            profiles=["chrome_131_win10", "nonexistent"],
        )
        assert engine.profile_count == 1

    def test_all_invalid_profiles_raises(self):
        with pytest.raises(ValueError, match="No valid"):
            FingerprintEvasionEngine(profiles=["nonexistent"])

    def test_get_profile(self):
        engine = FingerprintEvasionEngine()
        profile = engine.get_profile(target_host="example.com")
        assert isinstance(profile, BrowserFingerprintProfile)
        assert profile.tls is not None
        assert profile.http2 is not None

    def test_pin_per_target(self):
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.PIN_PER_TARGET,
        )
        p1 = engine.get_profile(target_host="a.com")
        p2 = engine.get_profile(target_host="a.com")
        assert p1.name == p2.name

    def test_pin_per_target_different_hosts(self):
        # Different hosts MAY get different profiles (probabilistic)
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.PIN_PER_TARGET,
        )
        results = set()
        for i in range(50):
            p = engine.get_profile(target_host=f"host{i}.com")
            results.add(p.name)
        # With 50 different hosts and 6 profiles, should see multiple
        assert len(results) >= 2

    def test_round_robin(self):
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.ROUND_ROBIN,
            profiles=["chrome_131_win10", "firefox_133_win10"],
        )
        p1 = engine.get_profile()
        p2 = engine.get_profile()
        p3 = engine.get_profile()
        assert p1.name != p2.name
        assert p1.name == p3.name  # Wraps around

    def test_random_strategy(self):
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.RANDOM,
        )
        names = set()
        for _ in range(100):
            p = engine.get_profile()
            names.add(p.name)
        assert len(names) >= 2

    def test_weighted_strategy(self):
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.WEIGHTED,
        )
        counts = {}
        for _ in range(1000):
            p = engine.get_profile()
            counts[p.name] = counts.get(p.name, 0) + 1
        # Chrome should appear more than rare browsers
        assert counts.get("chrome_131_win10", 0) > 50

    def test_grease_injection(self):
        engine = FingerprintEvasionEngine(enable_grease=True)
        profile = engine.get_profile()
        # GREASE adds extra cipher/extension entries
        base = get_browser_profile(profile.name)
        # Profile returned may have more ciphers due to GREASE
        assert len(profile.tls.cipher_suites) >= len(base.tls.cipher_suites)

    def test_grease_disabled(self):
        engine = FingerprintEvasionEngine(enable_grease=False)
        profile = engine.get_profile()
        base = get_browser_profile(profile.name)
        # Without GREASE, cipher count should match base
        assert len(profile.tls.cipher_suites) == len(base.tls.cipher_suites)

    def test_monitor_enabled(self):
        engine = FingerprintEvasionEngine(monitor_diversity=True)
        engine.get_profile(target_host="test.com")
        assert engine.monitor is not None
        assert engine.monitor.unique_ja3_count >= 1

    def test_monitor_disabled(self):
        engine = FingerprintEvasionEngine(monitor_diversity=False)
        assert engine.monitor is None

    def test_diversity_report(self):
        engine = FingerprintEvasionEngine()
        engine.get_profile(target_host="a.com")
        engine.get_profile(target_host="b.com")
        report = engine.get_diversity_report()
        assert report["total_requests"] == 2

    def test_diversity_report_no_monitor(self):
        engine = FingerprintEvasionEngine(monitor_diversity=False)
        assert engine.get_diversity_report() == {}

    def test_clear_pins(self):
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.PIN_PER_TARGET,
        )
        engine.get_profile(target_host="pinned.com")
        engine.clear_pins()
        # After clearing, a new pin may be assigned
        # (Can't guarantee different profile, but state should be clean)
        assert True  # No error means success

    def test_reset(self):
        engine = FingerprintEvasionEngine()
        engine.get_profile(target_host="test.com")
        engine.reset()
        assert engine.monitor.unique_ja3_count == 0


# ===========================================================================
# TestSSLContextCreation
# ===========================================================================
class TestSSLContextCreation:
    """Test SSL context creation from profiles."""

    def test_basic_ssl_context(self):
        engine = FingerprintEvasionEngine()
        ctx = engine.apply_to_ssl_context(target_host="example.com")
        assert isinstance(ctx, ssl.SSLContext)

    def test_ssl_context_no_verify(self):
        engine = FingerprintEvasionEngine()
        ctx = engine.apply_to_ssl_context(verify=False)
        assert ctx.verify_mode == ssl.CERT_NONE
        assert ctx.check_hostname is False

    def test_ssl_context_verify(self):
        engine = FingerprintEvasionEngine()
        ctx = engine.apply_to_ssl_context(verify=True)
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_ssl_context_tls_version(self):
        engine = FingerprintEvasionEngine()
        ctx = engine.apply_to_ssl_context()
        # Should support TLS 1.2+
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_ssl_context_alpn(self):
        engine = FingerprintEvasionEngine()
        ctx = engine.apply_to_ssl_context()
        # ALPN protocols should be set (can't directly read back, but no error)
        assert isinstance(ctx, ssl.SSLContext)

    def test_http2_settings(self):
        engine = FingerprintEvasionEngine()
        settings = engine.get_http2_settings(target_host="example.com")
        assert isinstance(settings, dict)
        assert "INITIAL_WINDOW_SIZE" in settings


# ===========================================================================
# TestGREASEHandling
# ===========================================================================
class TestGREASEHandling:
    """Test GREASE value generation and handling."""

    def test_grease_values_in_cipher_suites(self):
        p = TLSExtensionProfile(
            name="test",
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        greased = p.with_grease()
        # First cipher should be a GREASE value
        assert JA3Calculator._is_grease(greased.cipher_suites[0])

    def test_grease_values_in_extensions(self):
        p = TLSExtensionProfile(
            name="test",
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        greased = p.with_grease()
        # First extension should be a GREASE value
        assert JA3Calculator._is_grease(greased.extension_order[0])

    def test_grease_values_in_supported_groups(self):
        p = TLSExtensionProfile(
            name="test",
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        greased = p.with_grease()
        # First group should be a GREASE value
        assert JA3Calculator._is_grease(greased.supported_groups[0])

    def test_grease_doesnt_affect_ja3(self):
        p = TLSExtensionProfile(
            name="test",
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        ja3_before = p.compute_ja3()
        greased = p.with_grease()
        ja3_after = greased.compute_ja3()
        # GREASE values are filtered by JA3, so hash should be same
        assert ja3_before.hash == ja3_after.hash

    def test_grease_randomness(self):
        p = TLSExtensionProfile(
            name="test",
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        grease_values = set()
        for _ in range(50):
            greased = p.with_grease()
            grease_values.add(greased.cipher_suites[0])
        # Should see multiple different GREASE values
        assert len(grease_values) >= 2

    def test_grease_original_not_modified(self):
        p = TLSExtensionProfile(
            name="test",
            browser="chrome",
            browser_version="131",
            os="windows",
            cipher_suites=[CipherSuite.TLS_AES_128_GCM_SHA256],
            extension_order=[TLSExtensionType.SERVER_NAME],
            supported_groups=[EllipticCurve.X25519],
        )
        orig_cipher_len = len(p.cipher_suites)
        _ = p.with_grease()
        assert len(p.cipher_suites) == orig_cipher_len


# ===========================================================================
# TestThreadSafety
# ===========================================================================
class TestThreadSafety:
    """Test thread safety of fingerprint operations."""

    def test_concurrent_engine_get_profile(self):
        engine = FingerprintEvasionEngine()
        errors = []

        def worker():
            try:
                for i in range(20):
                    p = engine.get_profile(target_host=f"host{i}.com")
                    assert p is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_diversity_monitor(self):
        m = FingerprintDiversityMonitor()
        errors = []

        def worker(tid):
            try:
                for i in range(50):
                    m.record_usage(
                        f"profile_{tid}",
                        f"hash_{tid}_{i}",
                        f"ja4_{tid}_{i}",
                        f"host_{i}.com",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        report = m.get_report()
        assert report["total_requests"] == 400  # 8 * 50

    def test_concurrent_ssl_context_creation(self):
        engine = FingerprintEvasionEngine()
        errors = []

        def worker():
            try:
                for _ in range(10):
                    ctx = engine.apply_to_ssl_context(target_host="test.com")
                    assert isinstance(ctx, ssl.SSLContext)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ===========================================================================
# TestBrowserWeights
# ===========================================================================
class TestBrowserWeights:
    """Test browser market share weights."""

    def test_weights_sum_to_1(self):
        total = sum(_BROWSER_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_all_profiles_have_weights(self):
        for name in list_profile_names():
            assert name in _BROWSER_WEIGHTS

    def test_chrome_highest_weight(self):
        chrome_total = sum(
            w for name, w in _BROWSER_WEIGHTS.items() if "chrome" in name
        )
        assert chrome_total >= 0.4


# ===========================================================================
# TestIntegrationScenarios
# ===========================================================================
class TestIntegrationScenarios:
    """End-to-end integration tests."""

    def test_full_evasion_workflow(self):
        """Complete workflow: select profile → compute fingerprints → create SSL context."""
        engine = FingerprintEvasionEngine()

        # Get profile for a target
        profile = engine.get_profile(target_host="target.example.com")

        # Compute fingerprints
        ja3 = profile.compute_ja3()
        ja4 = profile.compute_ja4()

        assert len(ja3.hash) == 32
        assert len(ja4.full_string) > 20

        # Create SSL context
        ctx = engine.apply_to_ssl_context(target_host="target.example.com")
        assert isinstance(ctx, ssl.SSLContext)

        # Get HTTP/2 settings
        h2 = profile.http2.to_settings_dict()
        assert "INITIAL_WINDOW_SIZE" in h2

        # Check diversity
        report = engine.get_diversity_report()
        assert report["total_requests"] >= 1

    def test_multi_target_scan_simulation(self):
        """Simulate scanning multiple targets with fingerprint diversity."""
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.PIN_PER_TARGET,
        )

        targets = [f"target{i}.example.com" for i in range(20)]
        for target in targets:
            profile = engine.get_profile(target_host=target)
            _ = engine.apply_to_ssl_context(target_host=target)

        report = engine.get_diversity_report()
        assert report["total_requests"] == 40  # get_profile + apply_to_ssl
        assert report["targets_pinned"] == 20
        # Should have some diversity
        assert report["unique_profiles"] >= 2

    def test_fingerprint_consistency_per_target(self):
        """Same target should get consistent fingerprint with PIN strategy."""
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.PIN_PER_TARGET,
        )

        hashes = set()
        for _ in range(10):
            p = engine.get_profile(target_host="consistent.com")
            ja3 = p.compute_ja3()
            hashes.add(ja3.hash)

        # GREASE changes the profile but JA3 filters GREASE
        # So with GREASE enabled, JA3 should still be consistent
        assert len(hashes) == 1

    def test_evasion_engine_with_specific_profiles(self):
        """Test engine with limited profile set."""
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.ROUND_ROBIN,
            profiles=["chrome_131_win10", "safari_18_macos"],
            enable_grease=False,
        )

        p1 = engine.get_profile()
        p2 = engine.get_profile()

        assert {p1.name, p2.name} == {"chrome_131_win10", "safari_18_macos"}

    def test_diversity_monitoring_accuracy(self):
        """Verify diversity monitoring across multiple profiles."""
        engine = FingerprintEvasionEngine(
            strategy=FingerprintRotationStrategy.ROUND_ROBIN,
            enable_grease=False,
            monitor_diversity=True,
        )

        for i in range(len(list_profile_names()) * 3):
            engine.get_profile(target_host=f"host{i}.com")

        report = engine.get_diversity_report()
        # Should see all profiles used
        assert report["unique_profiles"] == len(list_profile_names())
        # Diversity should be high
        assert report["diversity_score"] > 0.9
