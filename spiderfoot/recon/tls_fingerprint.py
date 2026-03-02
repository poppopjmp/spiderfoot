# -------------------------------------------------------------------------------
# Name:         tls_fingerprint
# Purpose:      Advanced JA3/JA4+ fingerprint evasion & TLS extension control
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Advanced TLS Fingerprint Evasion — SOTA S-003 (Cycles 41–60).

Goes beyond basic cipher-suite rotation to provide comprehensive
TLS fingerprint evasion covering:

- :class:`JA3Calculator` — Compute JA3/JA3S fingerprint hashes from
  TLS handshake parameters for verification and diversity auditing.
- :class:`JA4Calculator` — Compute JA4+ fingerprint strings (protocol +
  cipher count + extension count + ALPN + cipher hash + extension hash).
- :class:`TLSExtensionProfile` — Full TLS extension set (SNI, ALPN,
  supported versions, key share, signature algorithms) mimicking real
  browser stacks.
- :class:`HTTP2FingerprintProfile` — HTTP/2 SETTINGS frame parameters,
  window sizes, and priority ordering matching real browsers.
- :class:`BrowserFingerprintProfile` — Composite profile combining TLS
  extensions, HTTP/2 settings, and header ordering to fully replicate
  a browser's network fingerprint.
- :class:`FingerprintEvasionEngine` — Unified engine that selects,
  rotates, and applies browser fingerprint profiles per-request or
  per-target with diversity monitoring.

Usage::

    from spiderfoot.recon.tls_fingerprint import (
        FingerprintEvasionEngine,
        JA3Calculator,
        JA4Calculator,
    )

    engine = FingerprintEvasionEngine()

    # Get a complete fingerprint profile for a target
    profile = engine.get_profile(target_host="example.com")

    # Apply to SSL context
    ssl_ctx = engine.apply_to_ssl_context(target_host="example.com")

    # Get HTTP/2 settings for the active profile
    h2_settings = profile.http2.to_settings_dict()

    # Calculate JA3 hash for verification
    ja3 = JA3Calculator.compute(
        tls_version=0x0303,
        ciphers=[0x1301, 0x1302],
        extensions=[0, 10, 11, 13, 43, 51],
        elliptic_curves=[29, 23, 24],
        ec_point_formats=[0],
    )
"""

from __future__ import annotations

import hashlib
import logging
import random
import ssl
import struct
import threading
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any

log = logging.getLogger("spiderfoot.recon.tls_fingerprint")


# ============================================================================
# TLS Constants & Extensions (Cycle 41)
# ============================================================================


class TLSVersion(IntEnum):
    """TLS version identifiers used in JA3 computation."""
    TLS_1_0 = 0x0301
    TLS_1_1 = 0x0302
    TLS_1_2 = 0x0303
    TLS_1_3 = 0x0304


class TLSExtensionType(IntEnum):
    """Common TLS extension type identifiers."""
    SERVER_NAME = 0               # SNI
    STATUS_REQUEST = 5            # OCSP stapling
    SUPPORTED_GROUPS = 10         # Elliptic curves
    EC_POINT_FORMATS = 11
    SIGNATURE_ALGORITHMS = 13
    APPLICATION_LAYER_PROTOCOL = 16  # ALPN
    SIGNED_CERTIFICATE_TIMESTAMP = 18
    EXTENDED_MASTER_SECRET = 23
    COMPRESS_CERTIFICATE = 27
    SESSION_TICKET = 35
    SUPPORTED_VERSIONS = 43
    PSK_KEY_EXCHANGE_MODES = 45
    KEY_SHARE = 51
    RENEGOTIATION_INFO = 65281


class EllipticCurve(IntEnum):
    """Named elliptic curves / groups."""
    SECP256R1 = 23    # prime256v1 / P-256
    SECP384R1 = 24    # P-384
    SECP521R1 = 25    # P-521
    X25519 = 29
    X448 = 30
    FFDHE2048 = 256
    FFDHE3072 = 257


class SignatureScheme(IntEnum):
    """TLS 1.3 signature schemes."""
    ECDSA_SECP256R1_SHA256 = 0x0403
    ECDSA_SECP384R1_SHA384 = 0x0503
    ECDSA_SECP521R1_SHA512 = 0x0603
    RSA_PSS_RSAE_SHA256 = 0x0804
    RSA_PSS_RSAE_SHA384 = 0x0805
    RSA_PSS_RSAE_SHA512 = 0x0806
    RSA_PKCS1_SHA256 = 0x0401
    RSA_PKCS1_SHA384 = 0x0501
    RSA_PKCS1_SHA512 = 0x0601


class CipherSuite(IntEnum):
    """Common TLS cipher suite identifiers."""
    # TLS 1.3
    TLS_AES_128_GCM_SHA256 = 0x1301
    TLS_AES_256_GCM_SHA384 = 0x1302
    TLS_CHACHA20_POLY1305_SHA256 = 0x1303
    # TLS 1.2
    TLS_ECDHE_ECDSA_AES128_GCM_SHA256 = 0xC02B
    TLS_ECDHE_RSA_AES128_GCM_SHA256 = 0xC02F
    TLS_ECDHE_ECDSA_AES256_GCM_SHA384 = 0xC02C
    TLS_ECDHE_RSA_AES256_GCM_SHA384 = 0xC030
    TLS_ECDHE_ECDSA_CHACHA20_POLY1305 = 0xCCA9
    TLS_ECDHE_RSA_CHACHA20_POLY1305 = 0xCCA8
    # Legacy
    TLS_RSA_AES128_GCM_SHA256 = 0x009C
    TLS_RSA_AES256_GCM_SHA384 = 0x009D


# ============================================================================
# JA3 Calculator (Cycles 42–43)
# ============================================================================


@dataclass
class JA3Fingerprint:
    """A computed JA3 fingerprint."""
    raw_string: str
    hash: str
    tls_version: int
    cipher_count: int
    extension_count: int
    curve_count: int

    def __str__(self) -> str:
        return self.hash

    def __eq__(self, other: object) -> bool:
        if isinstance(other, JA3Fingerprint):
            return self.hash == other.hash
        if isinstance(other, str):
            return self.hash == other
        return NotImplemented


class JA3Calculator:
    """Compute JA3 fingerprint hashes from TLS ClientHello parameters.

    JA3 is a method for creating SSL/TLS client fingerprints using
    five fields from the ClientHello: TLS version, cipher suites,
    extensions, elliptic curves, and EC point formats.

    The fields are concatenated with commas, and the result is MD5-hashed.
    """

    @staticmethod
    def compute(
        *,
        tls_version: int,
        ciphers: list[int],
        extensions: list[int],
        elliptic_curves: list[int],
        ec_point_formats: list[int],
    ) -> JA3Fingerprint:
        """Compute a JA3 fingerprint from ClientHello parameters.

        Args:
            tls_version: TLS version (e.g., 0x0303 for TLS 1.2).
            ciphers: List of cipher suite identifiers.
            extensions: List of extension type identifiers.
            elliptic_curves: List of supported group/curve identifiers.
            ec_point_formats: List of EC point format identifiers.

        Returns:
            JA3Fingerprint with raw string and MD5 hash.
        """
        # Filter GREASE values (0x?a?a pattern)
        ciphers_clean = [c for c in ciphers if not JA3Calculator._is_grease(c)]
        extensions_clean = [e for e in extensions if not JA3Calculator._is_grease(e)]
        curves_clean = [c for c in elliptic_curves if not JA3Calculator._is_grease(c)]
        formats_clean = [f for f in ec_point_formats if not JA3Calculator._is_grease(f)]

        parts = [
            str(tls_version),
            "-".join(str(c) for c in ciphers_clean),
            "-".join(str(e) for e in extensions_clean),
            "-".join(str(c) for c in curves_clean),
            "-".join(str(f) for f in formats_clean),
        ]

        raw_string = ",".join(parts)
        ja3_hash = hashlib.md5(raw_string.encode()).hexdigest()

        return JA3Fingerprint(
            raw_string=raw_string,
            hash=ja3_hash,
            tls_version=tls_version,
            cipher_count=len(ciphers_clean),
            extension_count=len(extensions_clean),
            curve_count=len(curves_clean),
        )

    @staticmethod
    def _is_grease(value: int) -> bool:
        """Check if a value is a GREASE (Generate Random Extensions And
        Sustain Extensibility) value. GREASE values follow 0x?a?a pattern."""
        if value < 0x0A0A:
            return False
        return (value & 0x0F0F) == 0x0A0A and ((value >> 8) & 0x0F) == 0x0A


# ============================================================================
# JA4 Calculator (Cycles 44–45)
# ============================================================================


@dataclass
class JA4Fingerprint:
    """A computed JA4+ fingerprint."""
    full_string: str
    protocol: str    # "t" for TCP, "q" for QUIC
    version: str     # e.g., "13" for TLS 1.3
    sni: str         # "d" for domain SNI, "i" for IP
    cipher_count: str
    extension_count: str
    alpn_first: str  # First ALPN value
    cipher_hash: str  # Truncated SHA-256 of sorted ciphers
    extension_hash: str  # Truncated SHA-256 of sorted extensions

    def __str__(self) -> str:
        return self.full_string


class JA4Calculator:
    """Compute JA4+ fingerprint strings.

    JA4 is the successor to JA3 with better granularity and resistance
    to randomization. It has three sections:
    - JA4_a: protocol + version + SNI + cipher_count + ext_count + ALPN
    - JA4_b: SHA-256 of sorted cipher suites (first 12 hex chars)
    - JA4_c: SHA-256 of sorted extensions (first 12 hex chars)
    """

    @staticmethod
    def compute(
        *,
        tls_version: int,
        ciphers: list[int],
        extensions: list[int],
        alpn_protocols: list[str] | None = None,
        sni_type: str = "domain",  # "domain" or "ip"
        transport: str = "tcp",    # "tcp" or "quic"
    ) -> JA4Fingerprint:
        """Compute a JA4 fingerprint.

        Args:
            tls_version: TLS version identifier.
            ciphers: List of cipher suite identifiers.
            extensions: List of extension type identifiers.
            alpn_protocols: ALPN protocol strings (e.g., ["h2", "http/1.1"]).
            sni_type: "domain" or "ip".
            transport: "tcp" or "quic".

        Returns:
            JA4Fingerprint instance.
        """
        # Filter GREASE
        ciphers_clean = sorted(
            c for c in ciphers if not JA3Calculator._is_grease(c)
        )
        extensions_clean = sorted(
            e for e in extensions
            if not JA3Calculator._is_grease(e)
            and e != TLSExtensionType.SERVER_NAME  # SNI excluded from JA4
            and e != TLSExtensionType.APPLICATION_LAYER_PROTOCOL  # ALPN excluded
        )

        # Protocol indicator
        proto = "t" if transport == "tcp" else "q"

        # TLS version
        version_map = {
            TLSVersion.TLS_1_0: "10",
            TLSVersion.TLS_1_1: "11",
            TLSVersion.TLS_1_2: "12",
            TLSVersion.TLS_1_3: "13",
        }
        ver = version_map.get(tls_version, "00")

        # SNI type
        sni = "d" if sni_type == "domain" else "i"

        # Counts (2-digit, zero-padded)
        cc = f"{min(len(ciphers_clean), 99):02d}"
        ec = f"{min(len(extensions_clean), 99):02d}"

        # First ALPN
        alpn_first = "00"
        if alpn_protocols:
            first = alpn_protocols[0]
            if first == "h2":
                alpn_first = "h2"
            elif first == "http/1.1":
                alpn_first = "h1"
            else:
                alpn_first = first[:2]

        # JA4_a
        ja4_a = f"{proto}{ver}{sni}{cc}{ec}{alpn_first}"

        # JA4_b: SHA-256 of comma-joined sorted ciphers
        cipher_str = ",".join(str(c) for c in ciphers_clean)
        cipher_hash = hashlib.sha256(cipher_str.encode()).hexdigest()[:12]

        # JA4_c: SHA-256 of comma-joined sorted extensions
        ext_str = ",".join(str(e) for e in extensions_clean)
        ext_hash = hashlib.sha256(ext_str.encode()).hexdigest()[:12]

        full = f"{ja4_a}_{cipher_hash}_{ext_hash}"

        return JA4Fingerprint(
            full_string=full,
            protocol=proto,
            version=ver,
            sni=sni,
            cipher_count=cc,
            extension_count=ec,
            alpn_first=alpn_first,
            cipher_hash=cipher_hash,
            extension_hash=ext_hash,
        )


# ============================================================================
# TLS Extension Profile (Cycles 46–48)
# ============================================================================


@dataclass
class TLSExtensionProfile:
    """Full TLS extension set mimicking a specific browser.

    Controls the exact set of TLS extensions, their ordering, and
    parameter values in the ClientHello to match a target browser's
    fingerprint as closely as possible.
    """
    name: str
    browser: str
    browser_version: str
    os: str

    # Extension ordering (list of TLSExtensionType values)
    extension_order: list[int] = field(default_factory=list)

    # Cipher suite order
    cipher_suites: list[int] = field(default_factory=list)

    # Supported groups (elliptic curves)
    supported_groups: list[int] = field(default_factory=list)

    # EC point formats
    ec_point_formats: list[int] = field(default_factory=lambda: [0])

    # Signature algorithms
    signature_algorithms: list[int] = field(default_factory=list)

    # ALPN protocols
    alpn_protocols: list[str] = field(default_factory=lambda: ["h2", "http/1.1"])

    # Supported TLS versions (for supported_versions extension)
    supported_versions: list[int] = field(
        default_factory=lambda: [TLSVersion.TLS_1_3, TLSVersion.TLS_1_2]
    )

    # PSK key exchange modes
    psk_modes: list[int] = field(default_factory=lambda: [1])  # psk_dhe_ke

    # Compress certificate algorithms (e.g., brotli=2, zlib=1)
    compress_cert_algos: list[int] = field(default_factory=lambda: [2])

    # Session ticket support
    session_ticket: bool = True

    # OCSP stapling
    ocsp_stapling: bool = True

    # Extended master secret
    extended_master_secret: bool = True

    # Enable GREASE values (randomized)
    grease_enabled: bool = True

    def compute_ja3(self) -> JA3Fingerprint:
        """Compute the JA3 fingerprint for this profile."""
        return JA3Calculator.compute(
            tls_version=max(self.supported_versions) if self.supported_versions else TLSVersion.TLS_1_2,
            ciphers=self.cipher_suites,
            extensions=self.extension_order,
            elliptic_curves=self.supported_groups,
            ec_point_formats=self.ec_point_formats,
        )

    def compute_ja4(self) -> JA4Fingerprint:
        """Compute the JA4 fingerprint for this profile."""
        return JA4Calculator.compute(
            tls_version=max(self.supported_versions) if self.supported_versions else TLSVersion.TLS_1_2,
            ciphers=self.cipher_suites,
            extensions=self.extension_order,
            alpn_protocols=self.alpn_protocols,
        )

    def to_openssl_ciphers(self) -> str:
        """Convert cipher suites to OpenSSL cipher string."""
        # Map cipher suite IDs to OpenSSL names
        cipher_map = {
            CipherSuite.TLS_AES_128_GCM_SHA256: "TLS_AES_128_GCM_SHA256",
            CipherSuite.TLS_AES_256_GCM_SHA384: "TLS_AES_256_GCM_SHA384",
            CipherSuite.TLS_CHACHA20_POLY1305_SHA256: "TLS_CHACHA20_POLY1305_SHA256",
            CipherSuite.TLS_ECDHE_ECDSA_AES128_GCM_SHA256: "ECDHE-ECDSA-AES128-GCM-SHA256",
            CipherSuite.TLS_ECDHE_RSA_AES128_GCM_SHA256: "ECDHE-RSA-AES128-GCM-SHA256",
            CipherSuite.TLS_ECDHE_ECDSA_AES256_GCM_SHA384: "ECDHE-ECDSA-AES256-GCM-SHA384",
            CipherSuite.TLS_ECDHE_RSA_AES256_GCM_SHA384: "ECDHE-RSA-AES256-GCM-SHA384",
            CipherSuite.TLS_ECDHE_ECDSA_CHACHA20_POLY1305: "ECDHE-ECDSA-CHACHA20-POLY1305",
            CipherSuite.TLS_ECDHE_RSA_CHACHA20_POLY1305: "ECDHE-RSA-CHACHA20-POLY1305",
            CipherSuite.TLS_RSA_AES128_GCM_SHA256: "AES128-GCM-SHA256",
            CipherSuite.TLS_RSA_AES256_GCM_SHA384: "AES256-GCM-SHA384",
        }
        names = []
        for cs in self.cipher_suites:
            name = cipher_map.get(cs)
            if name:
                names.append(name)
        return ":".join(names) if names else "DEFAULT"

    def with_grease(self) -> "TLSExtensionProfile":
        """Return a copy of this profile with GREASE values injected.

        GREASE values are random 0x?a?a patterns inserted into cipher
        suites, extensions, and supported groups to mimic real browser
        behavior and evade static fingerprint matching.
        """
        if not self.grease_enabled:
            return self

        grease_values = [
            0x0A0A, 0x1A1A, 0x2A2A, 0x3A3A, 0x4A4A,
            0x5A5A, 0x6A6A, 0x7A7A, 0x8A8A, 0x9A9A,
            0xAAAA, 0xBABA, 0xCACA, 0xDADA, 0xEAEA, 0xFAFA,
        ]

        import copy
        profile = copy.deepcopy(self)

        # Insert GREASE into ciphers (at position 0)
        grease_cipher = random.choice(grease_values)
        profile.cipher_suites = [grease_cipher] + profile.cipher_suites

        # Insert GREASE into extensions (at positions 0 and ~middle)
        grease_ext1 = random.choice(grease_values)
        grease_ext2 = random.choice(grease_values)
        profile.extension_order = [grease_ext1] + profile.extension_order
        mid = len(profile.extension_order) // 2
        profile.extension_order.insert(mid, grease_ext2)

        # Insert GREASE into supported groups
        grease_group = random.choice(grease_values)
        profile.supported_groups = [grease_group] + profile.supported_groups

        return profile


# ============================================================================
# Browser Fingerprint Profiles (Cycles 48–50)
# ============================================================================


@dataclass
class HTTP2FingerprintProfile:
    """HTTP/2 SETTINGS frame and behavior fingerprint.

    Different browsers send different HTTP/2 SETTINGS values and
    use different priority/dependency patterns. Matching these
    prevents HTTP/2 fingerprinting detection.
    """
    # SETTINGS frame parameters
    header_table_size: int = 65536
    enable_push: bool = False
    max_concurrent_streams: int = 100
    initial_window_size: int = 6291456
    max_frame_size: int = 16384
    max_header_list_size: int = 262144

    # Window update (connection-level)
    connection_window_size: int = 15663105

    # Priority / dependency (H2 PRIORITY frames)
    # Chrome uses a flat priority tree, Firefox uses a more complex tree
    priority_scheme: str = "chrome"  # "chrome", "firefox", "safari"

    # Header ordering (pseudo-headers come first in H2)
    pseudo_header_order: list[str] = field(
        default_factory=lambda: [":method", ":authority", ":scheme", ":path"]
    )

    def to_settings_dict(self) -> dict[str, int]:
        """Return HTTP/2 SETTINGS as a dict for h2 library."""
        settings = {
            "HEADER_TABLE_SIZE": self.header_table_size,
            "MAX_CONCURRENT_STREAMS": self.max_concurrent_streams,
            "INITIAL_WINDOW_SIZE": self.initial_window_size,
            "MAX_FRAME_SIZE": self.max_frame_size,
            "MAX_HEADER_LIST_SIZE": self.max_header_list_size,
        }
        if not self.enable_push:
            settings["ENABLE_PUSH"] = 0
        return settings

    def to_settings_bytes(self) -> bytes:
        """Serialize SETTINGS frame parameters as bytes.

        Each setting is a 16-bit ID + 32-bit value (6 bytes per setting).
        """
        # SETTINGS IDs per RFC 7540
        setting_ids = {
            "HEADER_TABLE_SIZE": 0x1,
            "ENABLE_PUSH": 0x2,
            "MAX_CONCURRENT_STREAMS": 0x3,
            "INITIAL_WINDOW_SIZE": 0x4,
            "MAX_FRAME_SIZE": 0x5,
            "MAX_HEADER_LIST_SIZE": 0x6,
        }
        result = b""
        for name, sid in setting_ids.items():
            if name == "ENABLE_PUSH":
                value = 0 if not self.enable_push else 1
            elif name == "HEADER_TABLE_SIZE":
                value = self.header_table_size
            elif name == "MAX_CONCURRENT_STREAMS":
                value = self.max_concurrent_streams
            elif name == "INITIAL_WINDOW_SIZE":
                value = self.initial_window_size
            elif name == "MAX_FRAME_SIZE":
                value = self.max_frame_size
            elif name == "MAX_HEADER_LIST_SIZE":
                value = self.max_header_list_size
            else:
                continue
            result += struct.pack("!HI", sid, value)
        return result


@dataclass
class BrowserFingerprintProfile:
    """Composite browser fingerprint combining TLS + HTTP/2 settings.

    Represents the complete network fingerprint of a specific browser,
    allowing us to fully replicate its behavior and evade fingerprint-
    based detection systems.
    """
    name: str
    tls: TLSExtensionProfile
    http2: HTTP2FingerprintProfile

    def compute_ja3(self) -> JA3Fingerprint:
        return self.tls.compute_ja3()

    def compute_ja4(self) -> JA4Fingerprint:
        return self.tls.compute_ja4()

    def to_openssl_ciphers(self) -> str:
        return self.tls.to_openssl_ciphers()


# Pre-built browser fingerprint profiles
_BROWSER_PROFILES: dict[str, BrowserFingerprintProfile] = {}


def _init_browser_profiles() -> None:
    """Initialize pre-built browser fingerprint profiles."""
    global _BROWSER_PROFILES

    # Chrome 131 (Windows 10)
    chrome_131_tls = TLSExtensionProfile(
        name="chrome_131_win10",
        browser="chrome",
        browser_version="131",
        os="windows",
        extension_order=[
            TLSExtensionType.SERVER_NAME,
            TLSExtensionType.EXTENDED_MASTER_SECRET,
            TLSExtensionType.RENEGOTIATION_INFO,
            TLSExtensionType.SUPPORTED_GROUPS,
            TLSExtensionType.EC_POINT_FORMATS,
            TLSExtensionType.SESSION_TICKET,
            TLSExtensionType.APPLICATION_LAYER_PROTOCOL,
            TLSExtensionType.STATUS_REQUEST,
            TLSExtensionType.SIGNATURE_ALGORITHMS,
            TLSExtensionType.SIGNED_CERTIFICATE_TIMESTAMP,
            TLSExtensionType.KEY_SHARE,
            TLSExtensionType.PSK_KEY_EXCHANGE_MODES,
            TLSExtensionType.SUPPORTED_VERSIONS,
            TLSExtensionType.COMPRESS_CERTIFICATE,
        ],
        cipher_suites=[
            CipherSuite.TLS_AES_128_GCM_SHA256,
            CipherSuite.TLS_AES_256_GCM_SHA384,
            CipherSuite.TLS_CHACHA20_POLY1305_SHA256,
            CipherSuite.TLS_ECDHE_ECDSA_AES128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_RSA_AES128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_ECDSA_AES256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_RSA_AES256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_ECDSA_CHACHA20_POLY1305,
            CipherSuite.TLS_ECDHE_RSA_CHACHA20_POLY1305,
        ],
        supported_groups=[
            EllipticCurve.X25519,
            EllipticCurve.SECP256R1,
            EllipticCurve.SECP384R1,
        ],
        signature_algorithms=[
            SignatureScheme.ECDSA_SECP256R1_SHA256,
            SignatureScheme.RSA_PSS_RSAE_SHA256,
            SignatureScheme.RSA_PKCS1_SHA256,
            SignatureScheme.ECDSA_SECP384R1_SHA384,
            SignatureScheme.RSA_PSS_RSAE_SHA384,
            SignatureScheme.RSA_PKCS1_SHA384,
            SignatureScheme.RSA_PSS_RSAE_SHA512,
            SignatureScheme.RSA_PKCS1_SHA512,
        ],
        alpn_protocols=["h2", "http/1.1"],
    )
    chrome_131_h2 = HTTP2FingerprintProfile(
        header_table_size=65536,
        enable_push=False,
        max_concurrent_streams=1000,
        initial_window_size=6291456,
        max_frame_size=16384,
        max_header_list_size=262144,
        connection_window_size=15663105,
        priority_scheme="chrome",
        pseudo_header_order=[":method", ":authority", ":scheme", ":path"],
    )

    # Firefox 133 (Windows 10)
    firefox_133_tls = TLSExtensionProfile(
        name="firefox_133_win10",
        browser="firefox",
        browser_version="133",
        os="windows",
        extension_order=[
            TLSExtensionType.SERVER_NAME,
            TLSExtensionType.EXTENDED_MASTER_SECRET,
            TLSExtensionType.RENEGOTIATION_INFO,
            TLSExtensionType.SUPPORTED_GROUPS,
            TLSExtensionType.EC_POINT_FORMATS,
            TLSExtensionType.SESSION_TICKET,
            TLSExtensionType.APPLICATION_LAYER_PROTOCOL,
            TLSExtensionType.STATUS_REQUEST,
            TLSExtensionType.KEY_SHARE,
            TLSExtensionType.SUPPORTED_VERSIONS,
            TLSExtensionType.SIGNATURE_ALGORITHMS,
            TLSExtensionType.PSK_KEY_EXCHANGE_MODES,
            TLSExtensionType.COMPRESS_CERTIFICATE,
        ],
        cipher_suites=[
            CipherSuite.TLS_AES_128_GCM_SHA256,
            CipherSuite.TLS_CHACHA20_POLY1305_SHA256,
            CipherSuite.TLS_AES_256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_ECDSA_AES128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_RSA_AES128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_ECDSA_CHACHA20_POLY1305,
            CipherSuite.TLS_ECDHE_RSA_CHACHA20_POLY1305,
            CipherSuite.TLS_ECDHE_ECDSA_AES256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_RSA_AES256_GCM_SHA384,
        ],
        supported_groups=[
            EllipticCurve.X25519,
            EllipticCurve.SECP256R1,
            EllipticCurve.SECP384R1,
            EllipticCurve.SECP521R1,
        ],
        signature_algorithms=[
            SignatureScheme.ECDSA_SECP256R1_SHA256,
            SignatureScheme.ECDSA_SECP384R1_SHA384,
            SignatureScheme.ECDSA_SECP521R1_SHA512,
            SignatureScheme.RSA_PSS_RSAE_SHA256,
            SignatureScheme.RSA_PSS_RSAE_SHA384,
            SignatureScheme.RSA_PSS_RSAE_SHA512,
            SignatureScheme.RSA_PKCS1_SHA256,
            SignatureScheme.RSA_PKCS1_SHA384,
            SignatureScheme.RSA_PKCS1_SHA512,
        ],
        alpn_protocols=["h2", "http/1.1"],
    )
    firefox_133_h2 = HTTP2FingerprintProfile(
        header_table_size=65536,
        enable_push=False,
        max_concurrent_streams=100,
        initial_window_size=131072,
        max_frame_size=16384,
        max_header_list_size=65536,
        connection_window_size=12517377,
        priority_scheme="firefox",
        pseudo_header_order=[":method", ":path", ":authority", ":scheme"],
    )

    # Safari 18 (macOS)
    safari_18_tls = TLSExtensionProfile(
        name="safari_18_macos",
        browser="safari",
        browser_version="18",
        os="macos",
        extension_order=[
            TLSExtensionType.SERVER_NAME,
            TLSExtensionType.EXTENDED_MASTER_SECRET,
            TLSExtensionType.RENEGOTIATION_INFO,
            TLSExtensionType.SUPPORTED_GROUPS,
            TLSExtensionType.EC_POINT_FORMATS,
            TLSExtensionType.APPLICATION_LAYER_PROTOCOL,
            TLSExtensionType.STATUS_REQUEST,
            TLSExtensionType.SIGNATURE_ALGORITHMS,
            TLSExtensionType.SIGNED_CERTIFICATE_TIMESTAMP,
            TLSExtensionType.KEY_SHARE,
            TLSExtensionType.SUPPORTED_VERSIONS,
            TLSExtensionType.PSK_KEY_EXCHANGE_MODES,
            TLSExtensionType.COMPRESS_CERTIFICATE,
        ],
        cipher_suites=[
            CipherSuite.TLS_AES_128_GCM_SHA256,
            CipherSuite.TLS_AES_256_GCM_SHA384,
            CipherSuite.TLS_CHACHA20_POLY1305_SHA256,
            CipherSuite.TLS_ECDHE_ECDSA_AES256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_ECDSA_AES128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_RSA_AES256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_RSA_AES128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_ECDSA_CHACHA20_POLY1305,
            CipherSuite.TLS_ECDHE_RSA_CHACHA20_POLY1305,
        ],
        supported_groups=[
            EllipticCurve.X25519,
            EllipticCurve.SECP256R1,
            EllipticCurve.SECP384R1,
        ],
        signature_algorithms=[
            SignatureScheme.ECDSA_SECP256R1_SHA256,
            SignatureScheme.RSA_PSS_RSAE_SHA256,
            SignatureScheme.RSA_PKCS1_SHA256,
            SignatureScheme.ECDSA_SECP384R1_SHA384,
            SignatureScheme.RSA_PSS_RSAE_SHA384,
            SignatureScheme.RSA_PKCS1_SHA384,
            SignatureScheme.RSA_PSS_RSAE_SHA512,
            SignatureScheme.RSA_PKCS1_SHA512,
        ],
        alpn_protocols=["h2", "http/1.1"],
    )
    safari_18_h2 = HTTP2FingerprintProfile(
        header_table_size=4096,
        enable_push=False,
        max_concurrent_streams=100,
        initial_window_size=2097152,
        max_frame_size=16384,
        max_header_list_size=0,  # Safari doesn't send this
        connection_window_size=10485760,
        priority_scheme="safari",
        pseudo_header_order=[":method", ":scheme", ":path", ":authority"],
    )

    # Edge 131 (Windows 10) — same engine as Chrome but different UA
    edge_131_tls = TLSExtensionProfile(
        name="edge_131_win10",
        browser="edge",
        browser_version="131",
        os="windows",
        extension_order=chrome_131_tls.extension_order.copy(),
        cipher_suites=chrome_131_tls.cipher_suites.copy(),
        supported_groups=chrome_131_tls.supported_groups.copy(),
        signature_algorithms=chrome_131_tls.signature_algorithms.copy(),
        alpn_protocols=["h2", "http/1.1"],
    )
    edge_131_h2 = HTTP2FingerprintProfile(
        header_table_size=65536,
        enable_push=False,
        max_concurrent_streams=1000,
        initial_window_size=6291456,
        max_frame_size=16384,
        max_header_list_size=262144,
        connection_window_size=15663105,
        priority_scheme="chrome",
        pseudo_header_order=[":method", ":authority", ":scheme", ":path"],
    )

    # Chrome 131 (macOS)
    chrome_131_mac_tls = TLSExtensionProfile(
        name="chrome_131_macos",
        browser="chrome",
        browser_version="131",
        os="macos",
        extension_order=chrome_131_tls.extension_order.copy(),
        cipher_suites=chrome_131_tls.cipher_suites.copy(),
        supported_groups=chrome_131_tls.supported_groups.copy(),
        signature_algorithms=chrome_131_tls.signature_algorithms.copy(),
        alpn_protocols=["h2", "http/1.1"],
    )
    chrome_131_mac_h2 = HTTP2FingerprintProfile(
        header_table_size=65536,
        enable_push=False,
        max_concurrent_streams=1000,
        initial_window_size=6291456,
        max_frame_size=16384,
        max_header_list_size=262144,
        connection_window_size=15663105,
        priority_scheme="chrome",
        pseudo_header_order=[":method", ":authority", ":scheme", ":path"],
    )

    # Firefox 133 (Linux)
    firefox_133_linux_tls = TLSExtensionProfile(
        name="firefox_133_linux",
        browser="firefox",
        browser_version="133",
        os="linux",
        extension_order=firefox_133_tls.extension_order.copy(),
        cipher_suites=firefox_133_tls.cipher_suites.copy(),
        supported_groups=firefox_133_tls.supported_groups.copy(),
        signature_algorithms=firefox_133_tls.signature_algorithms.copy(),
        alpn_protocols=["h2", "http/1.1"],
    )
    firefox_133_linux_h2 = HTTP2FingerprintProfile(
        header_table_size=65536,
        enable_push=False,
        max_concurrent_streams=100,
        initial_window_size=131072,
        max_frame_size=16384,
        max_header_list_size=65536,
        connection_window_size=12517377,
        priority_scheme="firefox",
        pseudo_header_order=[":method", ":path", ":authority", ":scheme"],
    )

    _BROWSER_PROFILES.update({
        "chrome_131_win10": BrowserFingerprintProfile(
            name="chrome_131_win10",
            tls=chrome_131_tls,
            http2=chrome_131_h2,
        ),
        "firefox_133_win10": BrowserFingerprintProfile(
            name="firefox_133_win10",
            tls=firefox_133_tls,
            http2=firefox_133_h2,
        ),
        "safari_18_macos": BrowserFingerprintProfile(
            name="safari_18_macos",
            tls=safari_18_tls,
            http2=safari_18_h2,
        ),
        "edge_131_win10": BrowserFingerprintProfile(
            name="edge_131_win10",
            tls=edge_131_tls,
            http2=edge_131_h2,
        ),
        "chrome_131_macos": BrowserFingerprintProfile(
            name="chrome_131_macos",
            tls=chrome_131_mac_tls,
            http2=chrome_131_mac_h2,
        ),
        "firefox_133_linux": BrowserFingerprintProfile(
            name="firefox_133_linux",
            tls=firefox_133_linux_tls,
            http2=firefox_133_linux_h2,
        ),
    })


# Initialize profiles on module load
_init_browser_profiles()


def get_browser_profiles() -> dict[str, BrowserFingerprintProfile]:
    """Return all available browser fingerprint profiles."""
    return dict(_BROWSER_PROFILES)


def get_browser_profile(name: str) -> BrowserFingerprintProfile | None:
    """Get a specific browser fingerprint profile by name."""
    return _BROWSER_PROFILES.get(name)


def list_profile_names() -> list[str]:
    """List all available profile names."""
    return list(_BROWSER_PROFILES.keys())


# ============================================================================
# Fingerprint Diversity Monitor (Cycles 51–53)
# ============================================================================


class FingerprintDiversityMonitor:
    """Monitor and analyze fingerprint diversity during a scan.

    Tracks which JA3/JA4 fingerprints are being used, how evenly
    they are distributed, and whether any particular fingerprint
    is being overused (which could trigger detection).
    """

    def __init__(self) -> None:
        self._ja3_usage: dict[str, int] = {}
        self._ja4_usage: dict[str, int] = {}
        self._profile_usage: dict[str, int] = {}
        self._target_profiles: dict[str, str] = {}  # target -> profile
        self._total_requests = 0
        self._lock = threading.Lock()

    def record_usage(
        self,
        profile_name: str,
        ja3_hash: str,
        ja4_string: str,
        target_host: str = "",
    ) -> None:
        """Record that a fingerprint was used for a request."""
        with self._lock:
            self._total_requests += 1
            self._ja3_usage[ja3_hash] = self._ja3_usage.get(ja3_hash, 0) + 1
            self._ja4_usage[ja4_string] = self._ja4_usage.get(ja4_string, 0) + 1
            self._profile_usage[profile_name] = (
                self._profile_usage.get(profile_name, 0) + 1
            )
            if target_host:
                self._target_profiles[target_host] = profile_name

    @property
    def unique_ja3_count(self) -> int:
        return len(self._ja3_usage)

    @property
    def unique_ja4_count(self) -> int:
        return len(self._ja4_usage)

    @property
    def unique_profile_count(self) -> int:
        return len(self._profile_usage)

    @property
    def diversity_score(self) -> float:
        """Score from 0–1 indicating JA3 fingerprint diversity.

        Uses Shannon entropy normalized to the number of profiles.
        Higher score = more evenly distributed = harder to fingerprint.
        """
        if self._total_requests == 0 or not self._ja3_usage:
            return 0.0

        import math
        total = sum(self._ja3_usage.values())
        entropy = 0.0
        for count in self._ja3_usage.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

        max_entropy = math.log2(max(len(self._ja3_usage), 1))
        if max_entropy == 0:
            return 0.0
        return min(entropy / max_entropy, 1.0)

    def get_overused_fingerprints(self, threshold: float = 0.5) -> list[str]:
        """Return JA3 hashes that account for more than ``threshold``
        fraction of all requests."""
        if self._total_requests == 0:
            return []
        return [
            ja3 for ja3, count in self._ja3_usage.items()
            if count / self._total_requests > threshold
        ]

    def get_report(self) -> dict[str, Any]:
        """Generate a diversity report."""
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "unique_ja3_hashes": self.unique_ja3_count,
                "unique_ja4_strings": self.unique_ja4_count,
                "unique_profiles": self.unique_profile_count,
                "diversity_score": round(self.diversity_score, 3),
                "ja3_distribution": dict(self._ja3_usage),
                "profile_distribution": dict(self._profile_usage),
                "overused_fingerprints": self.get_overused_fingerprints(),
                "targets_pinned": len(self._target_profiles),
            }

    def reset(self) -> None:
        with self._lock:
            self._ja3_usage.clear()
            self._ja4_usage.clear()
            self._profile_usage.clear()
            self._target_profiles.clear()
            self._total_requests = 0


# ============================================================================
# Fingerprint Evasion Engine (Cycles 54–60)
# ============================================================================


class FingerprintRotationStrategy(Enum):
    """How to select fingerprint profiles for each request."""
    RANDOM = "random"              # Random profile per request
    ROUND_ROBIN = "round_robin"    # Sequential rotation
    PIN_PER_TARGET = "pin_per_target"  # Same profile per target host
    WEIGHTED = "weighted"          # Weighted by browser market share


# Approximate browser market share weights (2025 Q4)
_BROWSER_WEIGHTS: dict[str, float] = {
    "chrome_131_win10": 0.35,
    "chrome_131_macos": 0.15,
    "firefox_133_win10": 0.10,
    "firefox_133_linux": 0.05,
    "safari_18_macos": 0.20,
    "edge_131_win10": 0.15,
}


class FingerprintEvasionEngine:
    """Unified engine for TLS fingerprint evasion.

    Selects, rotates, and applies browser fingerprint profiles
    per-request or per-target, with GREASE injection, diversity
    monitoring, and SSL context configuration.

    Args:
        strategy: How to select profiles for each request.
        profiles: List of profile names to use (None = all available).
        pin_per_target: If True, use consistent profile per target host.
        enable_grease: If True, inject GREASE values into TLS extensions.
        monitor_diversity: If True, track fingerprint diversity metrics.
    """

    def __init__(
        self,
        strategy: FingerprintRotationStrategy = FingerprintRotationStrategy.PIN_PER_TARGET,
        profiles: list[str] | None = None,
        enable_grease: bool = True,
        monitor_diversity: bool = True,
    ) -> None:
        available = list_profile_names()
        if profiles:
            self._profile_names = [p for p in profiles if p in available]
        else:
            self._profile_names = available

        if not self._profile_names:
            raise ValueError("No valid browser fingerprint profiles specified")

        self._strategy = strategy
        self._enable_grease = enable_grease
        self._rr_index = 0
        self._target_pins: dict[str, str] = {}
        self._lock = threading.Lock()

        self._monitor: FingerprintDiversityMonitor | None = None
        if monitor_diversity:
            self._monitor = FingerprintDiversityMonitor()

    @property
    def profile_count(self) -> int:
        return len(self._profile_names)

    @property
    def monitor(self) -> FingerprintDiversityMonitor | None:
        return self._monitor

    def get_profile(
        self,
        *,
        target_host: str | None = None,
    ) -> BrowserFingerprintProfile:
        """Get a browser fingerprint profile for a request.

        Args:
            target_host: Target hostname (for per-target pinning).

        Returns:
            BrowserFingerprintProfile with optional GREASE injection.
        """
        profile_name = self._select_profile(target_host)
        profile = _BROWSER_PROFILES[profile_name]

        # Apply GREASE if enabled
        if self._enable_grease:
            profile = BrowserFingerprintProfile(
                name=profile.name,
                tls=profile.tls.with_grease(),
                http2=profile.http2,
            )

        # Record diversity metrics
        if self._monitor:
            ja3 = profile.compute_ja3()
            ja4 = profile.compute_ja4()
            self._monitor.record_usage(
                profile_name=profile_name,
                ja3_hash=ja3.hash,
                ja4_string=str(ja4),
                target_host=target_host or "",
            )

        return profile

    def apply_to_ssl_context(
        self,
        *,
        target_host: str | None = None,
        verify: bool = False,
    ) -> ssl.SSLContext:
        """Create an SSL context configured to match a browser's TLS fingerprint.

        Args:
            target_host: Target hostname (for per-target pinning + SNI).
            verify: Whether to verify server certificates.
        """
        profile = self.get_profile(target_host=target_host)
        tls = profile.tls

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        # Set cipher suites using OpenSSL names
        cipher_string = tls.to_openssl_ciphers()
        try:
            ctx.set_ciphers(cipher_string)
        except ssl.SSLError:
            log.debug("Some ciphers unavailable, using defaults")

        # TLS version range
        if tls.supported_versions:
            max_ver = max(tls.supported_versions)
            min_ver = min(tls.supported_versions)
            if max_ver >= TLSVersion.TLS_1_3:
                ctx.maximum_version = ssl.TLSVersion.TLSv1_3
            else:
                ctx.maximum_version = ssl.TLSVersion.TLSv1_2
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        # Certificate verification
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        else:
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED

        # Elliptic curve preferences
        if tls.supported_groups:
            curve_map = {
                EllipticCurve.X25519: "X25519",
                EllipticCurve.SECP256R1: "prime256v1",
                EllipticCurve.SECP384R1: "secp384r1",
                EllipticCurve.SECP521R1: "secp521r1",
            }
            for curve_id in tls.supported_groups:
                curve_name = curve_map.get(curve_id)
                if curve_name:
                    try:
                        ctx.set_ecdh_curve(curve_name)
                        break  # Only first curve is settable via Python API
                    except (ssl.SSLError, ValueError):
                        continue

        # ALPN protocols
        if tls.alpn_protocols:
            try:
                ctx.set_alpn_protocols(tls.alpn_protocols)
            except (ssl.SSLError, NotImplementedError):
                pass

        return ctx

    def get_http2_settings(
        self,
        *,
        target_host: str | None = None,
    ) -> dict[str, int]:
        """Get HTTP/2 SETTINGS matching the selected browser profile."""
        profile = self.get_profile(target_host=target_host)
        return profile.http2.to_settings_dict()

    def get_diversity_report(self) -> dict[str, Any]:
        """Get fingerprint diversity report."""
        if self._monitor:
            return self._monitor.get_report()
        return {}

    def clear_pins(self) -> None:
        """Clear all per-target profile pins."""
        with self._lock:
            self._target_pins.clear()

    def reset(self) -> None:
        """Reset all state."""
        self.clear_pins()
        if self._monitor:
            self._monitor.reset()
        self._rr_index = 0

    def _select_profile(self, target_host: str | None) -> str:
        """Select a profile based on the configured strategy."""
        with self._lock:
            if self._strategy == FingerprintRotationStrategy.PIN_PER_TARGET:
                if target_host and target_host in self._target_pins:
                    return self._target_pins[target_host]
                name = self._weighted_select()
                if target_host:
                    self._target_pins[target_host] = name
                return name

            if self._strategy == FingerprintRotationStrategy.ROUND_ROBIN:
                name = self._profile_names[self._rr_index % len(self._profile_names)]
                self._rr_index += 1
                return name

            if self._strategy == FingerprintRotationStrategy.WEIGHTED:
                return self._weighted_select()

            # RANDOM
            return random.choice(self._profile_names)

    def _weighted_select(self) -> str:
        """Select a profile weighted by browser market share."""
        weights = [
            _BROWSER_WEIGHTS.get(name, 0.1)
            for name in self._profile_names
        ]
        total = sum(weights)
        if total == 0:
            return random.choice(self._profile_names)
        # Normalize and select
        r = random.random() * total
        cumulative = 0.0
        for name, weight in zip(self._profile_names, weights):
            cumulative += weight
            if r <= cumulative:
                return name
        return self._profile_names[-1]
