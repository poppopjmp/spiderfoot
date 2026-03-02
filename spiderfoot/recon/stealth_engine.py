# -------------------------------------------------------------------------------
# Name:         stealth_engine
# Purpose:      SOTA Stealth & Evasion Engine for SpiderFoot
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-27
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Stealth & Evasion Engine — SOTA Reconnaissance Phase I (Cycles 1–200).

This module provides a comprehensive stealth layer that sits between
SpiderFoot's scan engine and the network, ensuring every outbound
request is fingerprint-diverse, timing-randomized, and optionally
routed through rotating proxies or Tor circuits.

Components
----------
- :class:`UserAgentRotator` — Weighted UA rotation with OS/browser diversity
- :class:`HeaderRandomizer` — Realistic header set generation per request
- :class:`TLSFingerprintDiversifier` — JA3/JA4 fingerprint variation
- :class:`ProxyRotator` — Multi-proxy rotation with health checking
- :class:`TorCircuitManager` — Tor circuit renewal and identity isolation
- :class:`RequestJitter` — Timing randomization with multiple distributions
- :class:`StealthProfile` — Unified configuration for all stealth parameters
- :class:`StealthEngine` — Façade combining all components into a usable API
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import ssl
import struct
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.recon.stealth_engine")


# ============================================================================
# User-Agent Rotation (Cycles 1–3)
# ============================================================================

@dataclass
class UserAgentEntry:
    """A user-agent string with metadata and selection weight."""
    ua_string: str
    browser: str  # chrome, firefox, safari, edge
    os: str  # windows, macos, linux, ios, android
    version: str  # browser version
    weight: float = 1.0  # selection probability weight


# Realistic UA strings covering major browsers and platforms.
# Updated to 2025–2026 era fingerprints.
_DEFAULT_USER_AGENTS: list[UserAgentEntry] = [
    # Chrome on Windows
    UserAgentEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "chrome", "windows", "131", weight=3.0,
    ),
    UserAgentEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "chrome", "windows", "130", weight=2.5,
    ),
    UserAgentEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "chrome", "windows", "128", weight=1.5,
    ),
    # Chrome on macOS
    UserAgentEntry(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "chrome", "macos", "131", weight=2.5,
    ),
    UserAgentEntry(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "chrome", "macos", "129", weight=1.5,
    ),
    # Chrome on Linux
    UserAgentEntry(
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "chrome", "linux", "131", weight=1.0,
    ),
    # Firefox on Windows
    UserAgentEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
        "Gecko/20100101 Firefox/133.0",
        "firefox", "windows", "133", weight=2.0,
    ),
    UserAgentEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
        "Gecko/20100101 Firefox/131.0",
        "firefox", "windows", "131", weight=1.5,
    ),
    # Firefox on macOS
    UserAgentEntry(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) "
        "Gecko/20100101 Firefox/133.0",
        "firefox", "macos", "133", weight=1.5,
    ),
    # Firefox on Linux
    UserAgentEntry(
        "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) "
        "Gecko/20100101 Firefox/133.0",
        "firefox", "linux", "133", weight=1.0,
    ),
    # Safari on macOS
    UserAgentEntry(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.2 Safari/605.1.15",
        "safari", "macos", "18.2", weight=2.0,
    ),
    UserAgentEntry(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.6 Safari/605.1.15",
        "safari", "macos", "17.6", weight=1.0,
    ),
    # Edge on Windows
    UserAgentEntry(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "edge", "windows", "131", weight=1.5,
    ),
    # Mobile — Chrome on Android
    UserAgentEntry(
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "chrome", "android", "131", weight=0.5,
    ),
    # Mobile — Safari on iOS
    UserAgentEntry(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 "
        "Mobile/15E148 Safari/604.1",
        "safari", "ios", "18.2", weight=0.5,
    ),
]


class UserAgentRotator:
    """Weighted rotation of realistic User-Agent strings.

    Supports filtering by browser/OS family, weighted random selection
    mirroring real-world browser market share, and per-session pinning
    to avoid UA changes within a single target interaction.

    Args:
        user_agents: Custom UA list. Defaults to built-in realistic set.
        pin_per_session: If True, returns the same UA for the same session key.
    """

    def __init__(
        self,
        user_agents: list[UserAgentEntry] | None = None,
        pin_per_session: bool = False,
    ) -> None:
        if user_agents is not None:
            self._entries = list(user_agents)
        else:
            self._entries = list(_DEFAULT_USER_AGENTS)
        if not self._entries:
            raise ValueError("At least one UserAgentEntry is required")
        self._pin_per_session = pin_per_session
        self._session_pins: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        """Number of available UA entries."""
        return len(self._entries)

    def get(
        self,
        *,
        browser: str | None = None,
        os_family: str | None = None,
        session_key: str | None = None,
    ) -> str:
        """Return a weighted-random User-Agent string.

        Args:
            browser: Filter to specific browser (chrome/firefox/safari/edge).
            os_family: Filter to specific OS (windows/macos/linux/ios/android).
            session_key: If pin_per_session is enabled, pin the UA for this key.
        """
        if self._pin_per_session and session_key:
            with self._lock:
                if session_key in self._session_pins:
                    return self._session_pins[session_key]

        candidates = self._entries
        if browser:
            candidates = [e for e in candidates if e.browser == browser.lower()]
        if os_family:
            candidates = [e for e in candidates if e.os == os_family.lower()]

        if not candidates:
            candidates = self._entries  # fallback to full list

        weights = [e.weight for e in candidates]
        chosen = random.choices(candidates, weights=weights, k=1)[0]

        if self._pin_per_session and session_key:
            with self._lock:
                self._session_pins[session_key] = chosen.ua_string

        return chosen.ua_string

    def get_consistent_headers(self, ua_string: str) -> dict[str, str]:
        """Generate browser-consistent headers for a given UA string.

        Returns Accept, Accept-Language, Accept-Encoding headers that
        match the browser identified in the UA string.
        """
        entry = None
        for e in self._entries:
            if e.ua_string == ua_string:
                entry = e
                break

        if entry is None:
            # Parse browser from UA string
            browser = "chrome"
            if "Firefox" in ua_string:
                browser = "firefox"
            elif "Safari" in ua_string and "Chrome" not in ua_string:
                browser = "safari"
            elif "Edg/" in ua_string:
                browser = "edge"
        else:
            browser = entry.browser

        return _BROWSER_HEADERS.get(browser, _BROWSER_HEADERS["chrome"]).copy()

    def clear_sessions(self) -> None:
        """Clear all pinned session UAs."""
        with self._lock:
            self._session_pins.clear()


# Browser-realistic Accept/Accept-Language/Accept-Encoding headers
_BROWSER_HEADERS: dict[str, dict[str, str]] = {
    "chrome": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
    "firefox": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
    "safari": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    },
    "edge": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-Ch-Ua": '"Microsoft Edge";v="131", "Chromium";v="131"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    },
}


# ============================================================================
# Header Randomizer (Cycles 4–6)
# ============================================================================


class HeaderRandomizer:
    """Generate realistic, fingerprint-diverse HTTP header sets.

    Randomizes header ordering, optional header inclusion, and values
    to avoid creating a static fingerprint across requests.
    """

    # Headers that can be optionally included/excluded per request
    _OPTIONAL_HEADERS = [
        ("DNT", ["1", "0"]),
        ("Cache-Control", ["max-age=0", "no-cache"]),
        ("Pragma", ["no-cache"]),
        ("Connection", ["keep-alive"]),
    ]

    # Referrer strategies
    _REFERRER_STRATEGIES = [
        "none",       # No Referer header
        "self",       # Same-origin referer
        "google",     # Google search referrer
        "direct",     # No Referer (direct navigation)
    ]

    def __init__(
        self,
        ua_rotator: UserAgentRotator | None = None,
        include_rate: float = 0.5,
    ) -> None:
        self._ua_rotator = ua_rotator or UserAgentRotator()
        self._include_rate = max(0.0, min(1.0, include_rate))

    def generate(
        self,
        *,
        target_url: str = "",
        session_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
        referrer_strategy: str | None = None,
    ) -> dict[str, str]:
        """Generate a complete, realistic header set for a request.

        Args:
            target_url: The URL being requested (used for Referer generation).
            session_key: Optional session key for UA pinning.
            extra_headers: Additional headers to merge (override generated ones).
            referrer_strategy: Force a specific referrer strategy.

        Returns:
            Header dict with randomized ordering via insertion order.
        """
        # Get a user-agent and its consistent browser headers
        ua = self._ua_rotator.get(session_key=session_key)
        browser_headers = self._ua_rotator.get_consistent_headers(ua)

        headers: dict[str, str] = {}
        headers["User-Agent"] = ua

        # Add browser-consistent headers
        for key, val in browser_headers.items():
            headers[key] = val

        # Optionally include additional headers
        for header_name, possible_values in self._OPTIONAL_HEADERS:
            if random.random() < self._include_rate:
                headers[header_name] = random.choice(possible_values)

        # Referrer
        strategy = referrer_strategy or random.choice(self._REFERRER_STRATEGIES)
        referer = self._generate_referer(target_url, strategy)
        if referer:
            headers["Referer"] = referer

        # Merge extra headers (user overrides take precedence)
        if extra_headers:
            headers.update(extra_headers)

        # Randomize header ordering to diversify HTTP/2 fingerprint
        items = list(headers.items())
        # Keep Host and User-Agent near the top (realistic)
        prioritized = []
        rest = []
        for k, v in items:
            if k.lower() in ("host", "user-agent"):
                prioritized.append((k, v))
            else:
                rest.append((k, v))
        random.shuffle(rest)
        return dict(prioritized + rest)

    @staticmethod
    def _generate_referer(target_url: str, strategy: str) -> str | None:
        """Generate a realistic Referer header value."""
        if strategy == "none" or strategy == "direct":
            return None
        if strategy == "self" and target_url:
            # Use the origin of the target URL as referer
            try:
                from urllib.parse import urlparse
                parsed = urlparse(target_url)
                return f"{parsed.scheme}://{parsed.netloc}/"
            except Exception:
                return None
        if strategy == "google":
            domains = [
                "https://www.google.com/",
                "https://www.google.co.uk/",
                "https://www.google.ca/",
                "https://www.google.com.au/",
            ]
            return random.choice(domains)
        return None


# ============================================================================
# TLS Fingerprint Diversifier (Cycles 7–10)
# ============================================================================


class TLSCipherProfile:
    """Represents a TLS cipher suite configuration mimicking a real browser."""

    # Pre-built cipher profiles matching real browser JA3 fingerprints
    PROFILES: dict[str, dict[str, Any]] = {
        "chrome_131": {
            "ciphers": (
                "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:"
                "TLS_CHACHA20_POLY1305_SHA256:"
                "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
                "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
                "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
            ),
            "min_version": ssl.TLSVersion.TLSv1_2,
            "max_version": ssl.TLSVersion.TLSv1_3,
            "curves": ["X25519", "prime256v1", "secp384r1"],
        },
        "firefox_133": {
            "ciphers": (
                "TLS_AES_128_GCM_SHA256:TLS_CHACHA20_POLY1305_SHA256:"
                "TLS_AES_256_GCM_SHA384:"
                "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
                "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:"
                "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384"
            ),
            "min_version": ssl.TLSVersion.TLSv1_2,
            "max_version": ssl.TLSVersion.TLSv1_3,
            "curves": ["X25519", "prime256v1", "secp384r1", "secp521r1"],
        },
        "safari_18": {
            "ciphers": (
                "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:"
                "TLS_CHACHA20_POLY1305_SHA256:"
                "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:"
                "ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:"
                "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
            ),
            "min_version": ssl.TLSVersion.TLSv1_2,
            "max_version": ssl.TLSVersion.TLSv1_3,
            "curves": ["X25519", "prime256v1", "secp384r1"],
        },
        "edge_131": {
            "ciphers": (
                "TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:"
                "TLS_CHACHA20_POLY1305_SHA256:"
                "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
                "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
                "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
            ),
            "min_version": ssl.TLSVersion.TLSv1_2,
            "max_version": ssl.TLSVersion.TLSv1_3,
            "curves": ["X25519", "prime256v1", "secp384r1"],
        },
    }

    @classmethod
    def profile_names(cls) -> list[str]:
        """Return available profile names."""
        return list(cls.PROFILES.keys())

    @classmethod
    def get_profile(cls, name: str) -> dict[str, Any]:
        """Get a specific cipher profile by name."""
        if name not in cls.PROFILES:
            raise ValueError(f"Unknown TLS profile: {name}")
        return cls.PROFILES[name].copy()


class TLSFingerprintDiversifier:
    """Diversify TLS fingerprints to evade JA3/JA4-based detection.

    Creates SSL contexts with cipher suites, TLS versions, and curve
    preferences matching real browsers, rotating per-request or
    per-session to avoid fingerprint consistency.

    Args:
        profiles: List of profile names to rotate through.
                  Defaults to all available profiles.
        pin_per_target: If True, use the same profile for the same target host.
    """

    def __init__(
        self,
        profiles: list[str] | None = None,
        pin_per_target: bool = True,
    ) -> None:
        available = TLSCipherProfile.profile_names()
        if profiles:
            self._profiles = [p for p in profiles if p in available]
        else:
            self._profiles = available

        if not self._profiles:
            raise ValueError("No valid TLS profiles specified")

        self._pin_per_target = pin_per_target
        self._target_pins: dict[str, str] = {}
        self._lock = threading.Lock()

    def create_ssl_context(
        self,
        *,
        target_host: str | None = None,
        verify: bool = False,
    ) -> ssl.SSLContext:
        """Create an SSL context with a browser-mimicking TLS fingerprint.

        Args:
            target_host: Target hostname (for per-target pinning).
            verify: Whether to verify server certificates.
        """
        profile_name = self._select_profile(target_host)
        profile = TLSCipherProfile.get_profile(profile_name)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        # Set cipher suites
        try:
            ctx.set_ciphers(profile["ciphers"])
        except ssl.SSLError:
            log.debug("Some ciphers not available, using defaults")

        # TLS version range
        ctx.minimum_version = profile["min_version"]
        ctx.maximum_version = profile["max_version"]

        # Certificate verification
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        else:
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED

        # Elliptic curve preferences (where supported)
        curves = profile.get("curves", [])
        if curves:
            try:
                ctx.set_ecdh_curve(curves[0])
            except (ssl.SSLError, ValueError):
                pass  # Not all curves available on all platforms

        return ctx

    def get_current_profile(self, target_host: str | None = None) -> str:
        """Return the profile name being used for a target."""
        return self._select_profile(target_host)

    def _select_profile(self, target_host: str | None) -> str:
        """Select a TLS profile, optionally pinned to a target."""
        if self._pin_per_target and target_host:
            with self._lock:
                if target_host in self._target_pins:
                    return self._target_pins[target_host]
                profile = random.choice(self._profiles)
                self._target_pins[target_host] = profile
                return profile
        return random.choice(self._profiles)

    def clear_pins(self) -> None:
        """Clear all target-pinned profiles."""
        with self._lock:
            self._target_pins.clear()


# ============================================================================
# Proxy Rotator (Cycles 11–14)
# ============================================================================


class ProxyProtocol(Enum):
    """Supported proxy protocols."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"
    SOCKS5H = "socks5h"  # DNS through proxy


@dataclass
class ProxyEntry:
    """A proxy endpoint with health tracking."""
    url: str
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    username: str | None = None
    password: str | None = None
    region: str | None = None
    # Health tracking
    consecutive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0
    last_used: float = 0.0
    last_failure: float = 0.0
    avg_latency_ms: float = 0.0
    _latency_samples: list[float] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        """Proxy considered healthy if < 5 consecutive failures."""
        return self.consecutive_failures < 5

    @property
    def failure_rate(self) -> float:
        """Fraction of requests that failed."""
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests

    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record a successful request through this proxy."""
        self.consecutive_failures = 0
        self.total_requests += 1
        self.last_used = time.time()
        if latency_ms > 0:
            self._latency_samples.append(latency_ms)
            # Keep last 50 samples
            if len(self._latency_samples) > 50:
                self._latency_samples = self._latency_samples[-50:]
            self.avg_latency_ms = sum(self._latency_samples) / len(self._latency_samples)

    def record_failure(self) -> None:
        """Record a failed request through this proxy."""
        self.consecutive_failures += 1
        self.total_requests += 1
        self.total_failures += 1
        self.last_failure = time.time()

    def to_requests_dict(self) -> dict[str, str]:
        """Return a proxy dict suitable for requests library."""
        if self.username and self.password:
            proto = self.protocol.value
            proxy_url = f"{proto}://{self.username}:{self.password}@{self.url}"
        else:
            proto = self.protocol.value
            proxy_url = f"{proto}://{self.url}"
        return {
            "http": proxy_url,
            "https": proxy_url,
        }


class ProxySelectionStrategy(Enum):
    """How to select the next proxy."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_USED = "least_used"
    LOWEST_LATENCY = "lowest_latency"
    REGION_AFFINITY = "region_affinity"


class ProxyRotator:
    """Multi-proxy rotation with health checking and selection strategies.

    Manages a pool of proxy endpoints, rotating between them per-request
    with automatic failover when proxies become unhealthy.

    Args:
        proxies: List of proxy entries. Can be empty for no-proxy mode.
        strategy: Selection strategy for choosing the next proxy.
        max_consecutive_failures: Failures before marking proxy unhealthy.
        cooldown_seconds: Seconds before retrying an unhealthy proxy.
    """

    def __init__(
        self,
        proxies: list[ProxyEntry] | None = None,
        strategy: ProxySelectionStrategy = ProxySelectionStrategy.ROUND_ROBIN,
        max_consecutive_failures: int = 5,
        cooldown_seconds: float = 300.0,
    ) -> None:
        self._proxies = list(proxies or [])
        self._strategy = strategy
        self._max_failures = max_consecutive_failures
        self._cooldown = cooldown_seconds
        self._rr_index = 0
        self._lock = threading.Lock()

    @property
    def count(self) -> int:
        """Number of configured proxies."""
        return len(self._proxies)

    @property
    def healthy_count(self) -> int:
        """Number of healthy proxies."""
        return sum(1 for p in self._proxies if p.is_healthy)

    def add_proxy(self, proxy: ProxyEntry) -> None:
        """Add a proxy to the rotation pool."""
        with self._lock:
            self._proxies.append(proxy)

    def remove_proxy(self, url: str) -> bool:
        """Remove a proxy by URL."""
        with self._lock:
            before = len(self._proxies)
            self._proxies = [p for p in self._proxies if p.url != url]
            return len(self._proxies) < before

    def get_next(self, *, region: str | None = None) -> ProxyEntry | None:
        """Get the next proxy according to the selection strategy.

        Args:
            region: Preferred region for REGION_AFFINITY strategy.

        Returns:
            ProxyEntry or None if no healthy proxies available.
        """
        with self._lock:
            healthy = self._get_healthy_proxies()
            if not healthy:
                # Try to recover cooled-down proxies
                healthy = self._get_cooled_proxies()
            if not healthy:
                return None

            if self._strategy == ProxySelectionStrategy.ROUND_ROBIN:
                proxy = healthy[self._rr_index % len(healthy)]
                self._rr_index += 1
                return proxy

            if self._strategy == ProxySelectionStrategy.RANDOM:
                return random.choice(healthy)

            if self._strategy == ProxySelectionStrategy.LEAST_USED:
                return min(healthy, key=lambda p: p.total_requests)

            if self._strategy == ProxySelectionStrategy.LOWEST_LATENCY:
                proxies_with_data = [p for p in healthy if p.avg_latency_ms > 0]
                if proxies_with_data:
                    return min(proxies_with_data, key=lambda p: p.avg_latency_ms)
                return random.choice(healthy)

            if self._strategy == ProxySelectionStrategy.REGION_AFFINITY:
                if region:
                    regional = [p for p in healthy if p.region == region]
                    if regional:
                        return random.choice(regional)
                return random.choice(healthy)

            return random.choice(healthy)

    def record_result(self, proxy_url: str, success: bool, latency_ms: float = 0.0) -> None:
        """Record the result of a request through a proxy."""
        with self._lock:
            for p in self._proxies:
                if p.url == proxy_url:
                    if success:
                        p.record_success(latency_ms)
                    else:
                        p.record_failure()
                    break

    def get_stats(self) -> list[dict[str, Any]]:
        """Return statistics for all proxies."""
        return [
            {
                "url": p.url,
                "protocol": p.protocol.value,
                "region": p.region,
                "healthy": p.is_healthy,
                "total_requests": p.total_requests,
                "failure_rate": round(p.failure_rate, 3),
                "avg_latency_ms": round(p.avg_latency_ms, 1),
                "consecutive_failures": p.consecutive_failures,
            }
            for p in self._proxies
        ]

    def _get_healthy_proxies(self) -> list[ProxyEntry]:
        """Return proxies that haven't exceeded failure threshold."""
        return [p for p in self._proxies if p.consecutive_failures < self._max_failures]

    def _get_cooled_proxies(self) -> list[ProxyEntry]:
        """Return unhealthy proxies whose cooldown has expired."""
        now = time.time()
        return [
            p for p in self._proxies
            if p.consecutive_failures >= self._max_failures
            and (now - p.last_failure) > self._cooldown
        ]


# ============================================================================
# Tor Circuit Manager (Cycles 15–16)
# ============================================================================


class TorCircuitManager:
    """Manage Tor circuit renewal for identity isolation.

    Controls Tor SOCKS proxy connections and circuit renewal via
    Tor's control port. Each circuit renewal gives a new exit IP.

    Args:
        socks_host: Tor SOCKS proxy host (default: 127.0.0.1).
        socks_port: Tor SOCKS proxy port (default: 9050).
        control_port: Tor control port (default: 9051).
        control_password: Password for Tor control port authentication.
        min_circuit_age: Minimum seconds before allowing circuit renewal.
    """

    def __init__(
        self,
        socks_host: str = "127.0.0.1",
        socks_port: int = 9050,
        control_port: int = 9051,
        control_password: str = "",
        min_circuit_age: float = 10.0,
    ) -> None:
        self._socks_host = socks_host
        self._socks_port = socks_port
        self._control_port = control_port
        self._control_password = control_password
        self._min_circuit_age = min_circuit_age
        self._last_renewal = 0.0
        self._circuit_count = 0
        self._lock = threading.Lock()

    @property
    def proxy_url(self) -> str:
        """Return the Tor SOCKS5 proxy URL."""
        return f"socks5h://{self._socks_host}:{self._socks_port}"

    @property
    def proxy_dict(self) -> dict[str, str]:
        """Return proxy dict for requests library."""
        url = self.proxy_url
        return {"http": url, "https": url}

    @property
    def circuit_count(self) -> int:
        """Number of circuit renewals performed."""
        return self._circuit_count

    def renew_circuit(self) -> bool:
        """Request a new Tor circuit via the control port.

        Returns True if the circuit was renewed, False if the minimum
        age hasn't elapsed or renewal failed.
        """
        with self._lock:
            now = time.time()
            if (now - self._last_renewal) < self._min_circuit_age:
                return False

            try:
                import socket
                ctrl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                ctrl.settimeout(10)
                ctrl.connect((self._socks_host, self._control_port))

                # Authenticate
                if self._control_password:
                    ctrl.send(
                        f'AUTHENTICATE "{self._control_password}"\r\n'.encode()
                    )
                else:
                    ctrl.send(b'AUTHENTICATE\r\n')

                auth_resp = ctrl.recv(256).decode()
                if "250" not in auth_resp:
                    log.warning("Tor auth failed: %s", auth_resp.strip())
                    ctrl.close()
                    return False

                # Send NEWNYM signal for new circuit
                ctrl.send(b'SIGNAL NEWNYM\r\n')
                nym_resp = ctrl.recv(256).decode()
                ctrl.close()

                if "250" in nym_resp:
                    self._last_renewal = now
                    self._circuit_count += 1
                    log.info("Tor circuit renewed (#%d)", self._circuit_count)
                    return True

                log.warning("Tor NEWNYM failed: %s", nym_resp.strip())
                return False

            except Exception as e:
                log.debug("Tor circuit renewal failed: %s", e)
                return False

    def should_renew(self, requests_since_last: int = 0, threshold: int = 10) -> bool:
        """Determine if circuit should be renewed based on usage."""
        if requests_since_last >= threshold:
            return True
        # Only check elapsed time if we've renewed at least once
        if self._last_renewal > 0:
            elapsed = time.time() - self._last_renewal
            # Renew every 10 minutes minimum
            if elapsed > 600:
                return True
        return False


# ============================================================================
# Request Jitter Engine (Cycles 17–18)
# ============================================================================


class JitterDistribution(Enum):
    """Distribution types for request timing jitter."""
    UNIFORM = "uniform"         # flat random between min/max
    GAUSSIAN = "gaussian"       # normal distribution around mean
    EXPONENTIAL = "exponential" # exponential decay (bursty)
    POISSON = "poisson"         # poisson-like inter-arrival times
    HUMAN = "human"             # mimics human browsing patterns


@dataclass
class JitterConfig:
    """Configuration for request timing jitter."""
    distribution: JitterDistribution = JitterDistribution.HUMAN
    min_delay: float = 0.1      # minimum delay in seconds
    max_delay: float = 5.0      # maximum delay in seconds
    mean_delay: float = 1.5     # mean delay for gaussian/poisson
    stddev: float = 0.8         # standard deviation for gaussian
    burst_probability: float = 0.15  # probability of burst (short delay)
    burst_delay: float = 0.05   # delay during burst periods


class RequestJitter:
    """Generate realistic request timing to avoid detection.

    Uses configurable probability distributions to add human-like
    delays between requests. The HUMAN distribution combines burst
    behavior with reading pauses to mimic real browsing.

    Args:
        config: Jitter configuration. Defaults to HUMAN distribution.
    """

    def __init__(self, config: JitterConfig | None = None) -> None:
        self._config = config or JitterConfig()
        self._request_count = 0
        self._total_jitter = 0.0

    @property
    def avg_jitter(self) -> float:
        """Average jitter delay applied so far."""
        if self._request_count == 0:
            return 0.0
        return self._total_jitter / self._request_count

    @property
    def request_count(self) -> int:
        """Number of jitter delays generated."""
        return self._request_count

    def get_delay(self) -> float:
        """Generate a delay value using the configured distribution.

        Returns:
            Delay in seconds, clamped to [min_delay, max_delay].
        """
        c = self._config
        delay: float

        if c.distribution == JitterDistribution.UNIFORM:
            delay = random.uniform(c.min_delay, c.max_delay)

        elif c.distribution == JitterDistribution.GAUSSIAN:
            delay = random.gauss(c.mean_delay, c.stddev)

        elif c.distribution == JitterDistribution.EXPONENTIAL:
            # Mean = 1/lambda, so lambda = 1/mean_delay
            delay = random.expovariate(1.0 / c.mean_delay) if c.mean_delay > 0 else c.min_delay

        elif c.distribution == JitterDistribution.POISSON:
            # Approximate Poisson inter-arrival via exponential
            delay = random.expovariate(1.0 / c.mean_delay) if c.mean_delay > 0 else c.min_delay

        elif c.distribution == JitterDistribution.HUMAN:
            delay = self._human_delay()

        else:
            delay = c.mean_delay

        # Clamp to bounds
        delay = max(c.min_delay, min(c.max_delay, delay))
        self._request_count += 1
        self._total_jitter += delay
        return delay

    def apply_delay(self) -> float:
        """Generate and apply a delay via time.sleep().

        Returns:
            The delay that was applied in seconds.
        """
        delay = self.get_delay()
        if delay > 0:
            time.sleep(delay)
        return delay

    def _human_delay(self) -> float:
        """Generate a human-like browsing delay.

        Models real user behavior:
        - 15% chance of rapid-fire clicks (burst)
        - 25% chance of prolonged reading (3-8 seconds)
        - 60% normal navigation (0.5-3 seconds)
        """
        c = self._config
        roll = random.random()

        if roll < c.burst_probability:
            # Burst: rapid clicking
            return random.uniform(c.burst_delay, c.burst_delay * 3)

        if roll < (c.burst_probability + 0.25):
            # Reading: longer pause
            return random.uniform(3.0, min(8.0, c.max_delay))

        # Normal navigation
        return random.gauss(c.mean_delay, c.stddev * 0.5)


# ============================================================================
# Stealth Profile (Cycles 19–20)
# ============================================================================


class StealthLevel(Enum):
    """Stealth intensity levels."""
    NONE = "none"           # No stealth measures
    LOW = "low"             # Basic UA rotation + some jitter
    MEDIUM = "medium"       # Full header randomization + proxy + moderate jitter
    HIGH = "high"           # All measures + TLS diversification + slow timing
    PARANOID = "paranoid"   # Maximum stealth: Tor + heavy jitter + all evasion


@dataclass
class StealthProfileConfig:
    """Complete stealth configuration for a scan."""
    level: StealthLevel = StealthLevel.MEDIUM

    # UA rotation
    ua_pin_per_session: bool = True
    ua_browser_filter: str | None = None

    # Header randomization
    header_optional_rate: float = 0.5

    # TLS diversification
    tls_profiles: list[str] | None = None
    tls_pin_per_target: bool = True

    # Proxy
    proxy_strategy: ProxySelectionStrategy = ProxySelectionStrategy.ROUND_ROBIN
    proxy_entries: list[ProxyEntry] = field(default_factory=list)

    # Tor
    use_tor: bool = False
    tor_renew_every_n: int = 10
    tor_control_password: str = ""

    # Jitter
    jitter_distribution: JitterDistribution = JitterDistribution.HUMAN
    jitter_min_delay: float = 0.1
    jitter_max_delay: float = 5.0
    jitter_mean_delay: float = 1.5

    @classmethod
    def from_level(cls, level: StealthLevel | str) -> "StealthProfileConfig":
        """Create a profile config from a stealth level preset."""
        if isinstance(level, str):
            level = StealthLevel(level.lower())

        presets: dict[StealthLevel, dict[str, Any]] = {
            StealthLevel.NONE: {
                "level": StealthLevel.NONE,
                "ua_pin_per_session": False,
                "header_optional_rate": 0.0,
                "jitter_distribution": JitterDistribution.UNIFORM,
                "jitter_min_delay": 0.0,
                "jitter_max_delay": 0.1,
                "jitter_mean_delay": 0.05,
            },
            StealthLevel.LOW: {
                "level": StealthLevel.LOW,
                "ua_pin_per_session": True,
                "header_optional_rate": 0.3,
                "jitter_distribution": JitterDistribution.UNIFORM,
                "jitter_min_delay": 0.1,
                "jitter_max_delay": 1.0,
                "jitter_mean_delay": 0.5,
            },
            StealthLevel.MEDIUM: {
                "level": StealthLevel.MEDIUM,
                "ua_pin_per_session": True,
                "header_optional_rate": 0.5,
                "jitter_distribution": JitterDistribution.HUMAN,
                "jitter_min_delay": 0.3,
                "jitter_max_delay": 3.0,
                "jitter_mean_delay": 1.0,
            },
            StealthLevel.HIGH: {
                "level": StealthLevel.HIGH,
                "ua_pin_per_session": True,
                "header_optional_rate": 0.7,
                "tls_pin_per_target": True,
                "jitter_distribution": JitterDistribution.HUMAN,
                "jitter_min_delay": 1.0,
                "jitter_max_delay": 8.0,
                "jitter_mean_delay": 3.0,
            },
            StealthLevel.PARANOID: {
                "level": StealthLevel.PARANOID,
                "ua_pin_per_session": True,
                "header_optional_rate": 0.8,
                "tls_pin_per_target": True,
                "use_tor": True,
                "tor_renew_every_n": 5,
                "jitter_distribution": JitterDistribution.HUMAN,
                "jitter_min_delay": 3.0,
                "jitter_max_delay": 15.0,
                "jitter_mean_delay": 7.0,
            },
        }

        preset = presets.get(level, presets[StealthLevel.MEDIUM])
        return cls(**preset)


# ============================================================================
# Stealth Engine — Unified Façade (Cycle 20)
# ============================================================================


class StealthEngine:
    """Unified stealth & evasion engine for SpiderFoot.

    Combines all stealth components into a single façade that can be
    injected into the scan engine to transparently apply stealth
    measures to every outbound request.

    Usage::

        engine = StealthEngine(StealthProfileConfig.from_level("high"))

        # Get stealthy headers for a request
        headers = engine.prepare_headers(target_url="https://example.com")

        # Get SSL context with diversified fingerprint
        ssl_ctx = engine.get_ssl_context(target_host="example.com")

        # Get proxy for the next request
        proxy = engine.get_proxy()

        # Apply timing jitter before a request
        engine.apply_jitter()
    """

    def __init__(self, config: StealthProfileConfig | None = None) -> None:
        self._config = config or StealthProfileConfig.from_level(StealthLevel.MEDIUM)
        self._request_counter = 0
        self._lock = threading.Lock()

        # Initialize components based on stealth level
        self._ua_rotator = UserAgentRotator(
            pin_per_session=self._config.ua_pin_per_session,
        )

        self._header_randomizer = HeaderRandomizer(
            ua_rotator=self._ua_rotator,
            include_rate=self._config.header_optional_rate,
        )

        self._tls_diversifier: TLSFingerprintDiversifier | None = None
        if self._config.level in (StealthLevel.HIGH, StealthLevel.PARANOID):
            self._tls_diversifier = TLSFingerprintDiversifier(
                profiles=self._config.tls_profiles,
                pin_per_target=self._config.tls_pin_per_target,
            )

        self._proxy_rotator: ProxyRotator | None = None
        if self._config.proxy_entries:
            self._proxy_rotator = ProxyRotator(
                proxies=self._config.proxy_entries,
                strategy=self._config.proxy_strategy,
            )

        self._tor_manager: TorCircuitManager | None = None
        if self._config.use_tor:
            self._tor_manager = TorCircuitManager(
                control_password=self._config.tor_control_password,
            )

        self._jitter = RequestJitter(
            config=JitterConfig(
                distribution=self._config.jitter_distribution,
                min_delay=self._config.jitter_min_delay,
                max_delay=self._config.jitter_max_delay,
                mean_delay=self._config.jitter_mean_delay,
            )
        )

    @property
    def stealth_level(self) -> StealthLevel:
        """Return the active stealth level."""
        return self._config.level

    @property
    def request_count(self) -> int:
        """Total requests processed by this engine."""
        return self._request_counter

    def prepare_headers(
        self,
        *,
        target_url: str = "",
        session_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Generate stealth-enhanced HTTP headers for a request.

        If stealth level is NONE, returns only extra_headers with
        a default User-Agent.
        """
        if self._config.level == StealthLevel.NONE:
            headers = {"User-Agent": "SpiderFoot"}
            if extra_headers:
                headers.update(extra_headers)
            return headers

        return self._header_randomizer.generate(
            target_url=target_url,
            session_key=session_key,
            extra_headers=extra_headers,
        )

    def get_ssl_context(
        self,
        *,
        target_host: str | None = None,
        verify: bool = False,
    ) -> ssl.SSLContext:
        """Get an SSL context with diversified TLS fingerprint.

        Falls back to a basic SSL context if TLS diversification
        is not enabled at the current stealth level.
        """
        if self._tls_diversifier:
            return self._tls_diversifier.create_ssl_context(
                target_host=target_host,
                verify=verify,
            )

        # Default: basic context
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def get_proxy(self, *, region: str | None = None) -> dict[str, str] | None:
        """Get the next proxy dict for requests library.

        Returns None if no proxies are configured.
        Handles Tor circuit renewal automatically.
        """
        # Tor mode
        if self._tor_manager:
            with self._lock:
                self._request_counter += 1
                if self._tor_manager.should_renew(
                    requests_since_last=self._request_counter % self._config.tor_renew_every_n,
                    threshold=self._config.tor_renew_every_n,
                ):
                    self._tor_manager.renew_circuit()
            return self._tor_manager.proxy_dict

        # Regular proxy rotation
        if self._proxy_rotator:
            proxy = self._proxy_rotator.get_next(region=region)
            if proxy:
                return proxy.to_requests_dict()

        return None

    def apply_jitter(self) -> float:
        """Apply request timing jitter. Returns the delay applied."""
        if self._config.level == StealthLevel.NONE:
            return 0.0
        return self._jitter.apply_delay()

    def get_jitter_delay(self) -> float:
        """Get the next jitter delay without sleeping."""
        if self._config.level == StealthLevel.NONE:
            return 0.0
        return self._jitter.get_delay()

    def record_proxy_result(
        self,
        proxy_url: str,
        success: bool,
        latency_ms: float = 0.0,
    ) -> None:
        """Record the result of a request through a proxy."""
        if self._proxy_rotator:
            self._proxy_rotator.record_result(proxy_url, success, latency_ms)

    def increment_request_counter(self) -> int:
        """Increment and return the request counter."""
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def get_stats(self) -> dict[str, Any]:
        """Return comprehensive stealth engine statistics."""
        stats: dict[str, Any] = {
            "stealth_level": self._config.level.value,
            "total_requests": self._request_counter,
            "avg_jitter_seconds": round(self._jitter.avg_jitter, 3),
            "jitter_distribution": self._config.jitter_distribution.value,
        }

        if self._proxy_rotator:
            stats["proxies"] = self._proxy_rotator.get_stats()
            stats["healthy_proxies"] = self._proxy_rotator.healthy_count

        if self._tor_manager:
            stats["tor_circuits_renewed"] = self._tor_manager.circuit_count

        if self._tls_diversifier:
            stats["tls_profiles"] = TLSCipherProfile.profile_names()

        return stats

    def reset(self) -> None:
        """Reset all state (sessions, pins, counters)."""
        self._request_counter = 0
        self._ua_rotator.clear_sessions()
        if self._tls_diversifier:
            self._tls_diversifier.clear_pins()
        self._jitter = RequestJitter(
            config=JitterConfig(
                distribution=self._config.jitter_distribution,
                min_delay=self._config.jitter_min_delay,
                max_delay=self._config.jitter_max_delay,
                mean_delay=self._config.jitter_mean_delay,
            )
        )
