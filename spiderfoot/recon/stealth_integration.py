# -------------------------------------------------------------------------------
# Name:         stealth_integration
# Purpose:      Wire StealthEngine into SpiderFoot's HTTP fetch layer
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-27
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Stealth Integration Layer — SOTA S-002 (Cycles 21–40).

Bridges the :class:`StealthEngine` with SpiderFoot's network-level
``fetchUrl`` and ``async_fetch_url`` functions, providing:

- :class:`ProxyChain` / :class:`ProxyChainManager` — multi-hop proxy chaining
  with health monitoring and automatic failover.
- :class:`DomainThrottler` — per-domain adaptive rate limiting to avoid
  triggering WAF/IDS/IPS or getting banned.
- :class:`StealthMetricsCollector` — real-time effectiveness metrics
  (detection rate, block rate, fingerprint diversity).
- :class:`ScanStealthConfig` — scan-level stealth configuration that maps
  to SpiderFoot's options system.
- :class:`StealthScanContext` — per-scan stealth state container that holds
  engine instance, throttler, metrics, and domain blacklist.
- :class:`StealthFetchMiddleware` — transparent middleware wrapping every
  outbound HTTP request with stealth measures.
- :func:`stealthy_fetch` — drop-in replacement for ``network.fetchUrl``.
- :func:`create_stealth_context` — factory for per-scan stealth contexts.

Usage::

    from spiderfoot.recon.stealth_integration import (
        create_stealth_context,
        stealthy_fetch,
        ScanStealthConfig,
    )

    # Create a scan context with high stealth
    config = ScanStealthConfig(stealth_level="high", tor_enabled=True)
    ctx = create_stealth_context(config)

    # Fetch a URL with full stealth
    result = stealthy_fetch("https://target.com/page", context=ctx)

    # Or use the middleware directly in a scan engine
    middleware = StealthFetchMiddleware(ctx)
    result = middleware.fetch("https://target.com/page")

    # Get stealth stats
    stats = ctx.get_stats()
"""

from __future__ import annotations

import copy
import hashlib
import logging
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .stealth_engine import (
    ProxyEntry,
    ProxyProtocol,
    ProxyRotator,
    ProxySelectionStrategy,
    RequestJitter,
    JitterConfig,
    JitterDistribution,
    StealthEngine,
    StealthLevel,
    StealthProfileConfig,
    TorCircuitManager,
)

log = logging.getLogger("spiderfoot.recon.stealth_integration")


# ============================================================================
# Proxy Chain Support (Cycles 21–24)
# ============================================================================


class ProxyChainStrategy(Enum):
    """Strategy for selecting proxy chains."""
    STATIC = "static"           # Use the same chain for all requests
    ROTATING = "rotating"       # Rotate through available chains
    PER_DOMAIN = "per_domain"   # Pin a chain per target domain
    RANDOM = "random"           # Random chain selection each request


@dataclass
class ProxyHop:
    """A single hop in a proxy chain.

    Represents one proxy server through which traffic is routed.
    The chain is traversed in order: hop1 → hop2 → ... → target.
    """
    url: str
    protocol: ProxyProtocol = ProxyProtocol.SOCKS5
    username: str | None = None
    password: str | None = None
    region: str | None = None
    label: str = ""

    # Health tracking
    consecutive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    last_used: float = 0.0
    last_failure: float = 0.0

    @property
    def is_healthy(self) -> bool:
        """Hop considered healthy if < 3 consecutive failures."""
        return self.consecutive_failures < 3

    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_failures / self.total_requests

    def record_success(self, latency_ms: float = 0.0) -> None:
        self.consecutive_failures = 0
        self.total_requests += 1
        self.last_used = time.time()
        if latency_ms > 0:
            # Exponential moving average
            alpha = 0.3
            self.avg_latency_ms = alpha * latency_ms + (1 - alpha) * self.avg_latency_ms

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.total_requests += 1
        self.total_failures += 1
        self.last_failure = time.time()

    def to_proxy_url(self) -> str:
        """Build the full proxy URL with auth if present."""
        proto = self.protocol.value
        if self.username and self.password:
            return f"{proto}://{self.username}:{self.password}@{self.url}"
        return f"{proto}://{self.url}"


@dataclass
class ProxyChain:
    """An ordered sequence of proxy hops forming a chain.

    Multi-hop proxy chains route traffic through multiple proxy servers
    before reaching the target, making traffic analysis and attribution
    significantly harder.

    For ``requests`` library, only the **first hop** is set as the proxy,
    as ``requests`` doesn't natively support SOCKS chain tunneling.
    For true multi-hop, the remaining hops are assumed to be pre-configured
    (e.g., via SSH tunnels, proxychains-ng, or VPN layers).
    """
    hops: list[ProxyHop] = field(default_factory=list)
    chain_id: str = ""
    label: str = ""
    _total_requests: int = 0
    _total_failures: int = 0

    def __post_init__(self) -> None:
        if not self.chain_id:
            self.chain_id = hashlib.md5(
                "|".join(h.url for h in self.hops).encode()
            ).hexdigest()[:12]

    @property
    def is_healthy(self) -> bool:
        """Chain is healthy if all hops are healthy."""
        return all(h.is_healthy for h in self.hops)

    @property
    def hop_count(self) -> int:
        return len(self.hops)

    @property
    def total_latency_ms(self) -> float:
        """Sum of average latencies across all hops."""
        return sum(h.avg_latency_ms for h in self.hops)

    @property
    def entry_proxy(self) -> ProxyHop | None:
        """The first hop (entry point) of the chain."""
        return self.hops[0] if self.hops else None

    @property
    def exit_proxy(self) -> ProxyHop | None:
        """The last hop (exit point) of the chain."""
        return self.hops[-1] if self.hops else None

    def to_requests_proxies(self) -> dict[str, str] | None:
        """Return proxy dict for ``requests`` library.

        Only the entry proxy is returned since multi-hop is handled
        at the network layer (proxychains-ng, SSH tunnels, etc.).
        """
        if not self.hops:
            return None
        entry = self.hops[0]
        proxy_url = entry.to_proxy_url()
        return {"http": proxy_url, "https": proxy_url}

    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record successful chain traversal."""
        self._total_requests += 1
        per_hop = latency_ms / max(len(self.hops), 1)
        for hop in self.hops:
            hop.record_success(per_hop)

    def record_failure(self, failed_hop_index: int = -1) -> None:
        """Record chain failure, optionally specifying which hop failed."""
        self._total_requests += 1
        self._total_failures += 1
        if 0 <= failed_hop_index < len(self.hops):
            self.hops[failed_hop_index].record_failure()
        elif self.hops:
            # Assume last hop (exit) failed
            self.hops[-1].record_failure()

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "label": self.label,
            "hop_count": self.hop_count,
            "healthy": self.is_healthy,
            "total_latency_ms": round(self.total_latency_ms, 1),
            "total_requests": self._total_requests,
            "total_failures": self._total_failures,
            "hops": [
                {
                    "url": h.url,
                    "protocol": h.protocol.value,
                    "region": h.region,
                    "healthy": h.is_healthy,
                    "avg_latency_ms": round(h.avg_latency_ms, 1),
                }
                for h in self.hops
            ],
        }


class ProxyChainManager:
    """Manages a pool of proxy chains with rotation and health monitoring.

    Provides chain selection based on configurable strategies, automatic
    failover when chains become unhealthy, and per-domain chain pinning
    for session consistency.

    Args:
        chains: Initial list of proxy chains.
        strategy: Chain selection strategy.
        cooldown_seconds: Seconds before retrying an unhealthy chain.
    """

    def __init__(
        self,
        chains: list[ProxyChain] | None = None,
        strategy: ProxyChainStrategy = ProxyChainStrategy.ROTATING,
        cooldown_seconds: float = 300.0,
    ) -> None:
        self._chains: list[ProxyChain] = list(chains or [])
        self._strategy = strategy
        self._cooldown = cooldown_seconds
        self._rr_index = 0
        self._domain_pins: dict[str, str] = {}  # domain -> chain_id
        self._lock = threading.Lock()

    @property
    def chain_count(self) -> int:
        return len(self._chains)

    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self._chains if c.is_healthy)

    def add_chain(self, chain: ProxyChain) -> None:
        """Add a proxy chain to the pool."""
        with self._lock:
            self._chains.append(chain)

    def remove_chain(self, chain_id: str) -> bool:
        """Remove a chain by ID."""
        with self._lock:
            before = len(self._chains)
            self._chains = [c for c in self._chains if c.chain_id != chain_id]
            # Clean up any domain pins
            self._domain_pins = {
                d: cid for d, cid in self._domain_pins.items()
                if cid != chain_id
            }
            return len(self._chains) < before

    def get_chain(
        self,
        *,
        domain: str | None = None,
        region: str | None = None,
    ) -> ProxyChain | None:
        """Get the next proxy chain based on the selection strategy.

        Args:
            domain: Target domain for per-domain pinning.
            region: Preferred region for region-affinity selection.

        Returns:
            ProxyChain or None if no healthy chains available.
        """
        with self._lock:
            healthy = [c for c in self._chains if c.is_healthy]
            if not healthy:
                # Try cooled-down chains
                now = time.time()
                healthy = [
                    c for c in self._chains
                    if not c.is_healthy
                    and c.hops
                    and all(
                        (now - h.last_failure) > self._cooldown
                        for h in c.hops
                        if not h.is_healthy
                    )
                ]
            if not healthy:
                return None

            # PER_DOMAIN: pin a chain to a specific domain
            if self._strategy == ProxyChainStrategy.PER_DOMAIN and domain:
                if domain in self._domain_pins:
                    pinned_id = self._domain_pins[domain]
                    pinned = [c for c in healthy if c.chain_id == pinned_id]
                    if pinned:
                        return pinned[0]
                # Assign a new chain to this domain
                chain = random.choice(healthy)
                self._domain_pins[domain] = chain.chain_id
                return chain

            # STATIC: always use the first chain
            if self._strategy == ProxyChainStrategy.STATIC:
                return healthy[0]

            # ROTATING: round-robin through chains
            if self._strategy == ProxyChainStrategy.ROTATING:
                chain = healthy[self._rr_index % len(healthy)]
                self._rr_index += 1
                return chain

            # RANDOM: random selection
            return random.choice(healthy)

    def record_result(
        self,
        chain_id: str,
        success: bool,
        latency_ms: float = 0.0,
        failed_hop_index: int = -1,
    ) -> None:
        """Record the result of a request through a chain."""
        with self._lock:
            for chain in self._chains:
                if chain.chain_id == chain_id:
                    if success:
                        chain.record_success(latency_ms)
                    else:
                        chain.record_failure(failed_hop_index)
                    break

    def get_stats(self) -> list[dict[str, Any]]:
        """Return statistics for all chains."""
        return [c.to_dict() for c in self._chains]

    def clear_domain_pins(self) -> None:
        """Clear all domain-to-chain pinning."""
        with self._lock:
            self._domain_pins.clear()


# ============================================================================
# Domain Throttler (Cycles 25–27)
# ============================================================================


class ThrottleAction(Enum):
    """Action determined by the throttler."""
    PROCEED = "proceed"       # OK to send request
    DELAY = "delay"           # Wait before sending
    BACKOFF = "backoff"       # Exponential backoff recommended
    BLOCK = "block"           # Too many errors, stop requests


@dataclass
class DomainBucket:
    """Rate-limiting state for a single domain."""
    domain: str
    requests_total: int = 0
    requests_in_window: int = 0
    errors_in_window: int = 0
    window_start: float = 0.0
    window_seconds: float = 60.0
    last_request: float = 0.0
    last_error: float = 0.0
    backoff_until: float = 0.0
    backoff_count: int = 0
    # Adaptive limits
    max_requests_per_window: int = 30
    min_interval_seconds: float = 1.0
    # HTTP response tracking
    last_status_codes: list[int] = field(default_factory=list)

    def _reset_window_if_needed(self) -> None:
        """Reset the sliding window if it has expired."""
        now = time.time()
        if (now - self.window_start) > self.window_seconds:
            self.requests_in_window = 0
            self.errors_in_window = 0
            self.window_start = now

    def record_request(self) -> None:
        self._reset_window_if_needed()
        self.requests_total += 1
        self.requests_in_window += 1
        self.last_request = time.time()

    def record_response(self, status_code: int) -> None:
        """Record an HTTP response, tracking errors for adaptive throttling."""
        self.last_status_codes.append(status_code)
        if len(self.last_status_codes) > 20:
            self.last_status_codes = self.last_status_codes[-20:]

        if status_code in (429, 503, 403):
            self._reset_window_if_needed()
            self.errors_in_window += 1
            self.last_error = time.time()

            # Exponential backoff: 2^n seconds, capped at 300s
            self.backoff_count += 1
            backoff_duration = min(2 ** self.backoff_count, 300)
            self.backoff_until = time.time() + backoff_duration

            # Reduce max requests per window adaptively
            if self.max_requests_per_window > 5:
                self.max_requests_per_window = max(
                    5, int(self.max_requests_per_window * 0.7)
                )
            # Increase minimum interval
            self.min_interval_seconds = min(
                self.min_interval_seconds * 1.5, 30.0
            )
        elif 200 <= status_code < 400:
            # Successful response — slowly recover throttle limits
            if self.backoff_count > 0:
                self.backoff_count = max(0, self.backoff_count - 1)
            if self.max_requests_per_window < 30:
                self.max_requests_per_window = min(
                    30, self.max_requests_per_window + 1
                )
            if self.min_interval_seconds > 1.0:
                self.min_interval_seconds = max(
                    1.0, self.min_interval_seconds * 0.95
                )

    @property
    def error_rate(self) -> float:
        if self.requests_in_window == 0:
            return 0.0
        return self.errors_in_window / self.requests_in_window

    @property
    def recent_block_rate(self) -> float:
        """Fraction of recent responses that were blocks (429/403/503)."""
        if not self.last_status_codes:
            return 0.0
        blocks = sum(
            1 for s in self.last_status_codes if s in (429, 503, 403)
        )
        return blocks / len(self.last_status_codes)


class DomainThrottler:
    """Per-domain adaptive rate limiting.

    Tracks request rates and HTTP responses per-domain, automatically
    adjusting throttle parameters when WAF/IDS responses (429, 403, 503)
    are detected. Uses exponential backoff to avoid trigger-happy
    defenses.

    Args:
        default_max_rpm: Default maximum requests per minute per domain.
        default_min_interval: Minimum seconds between requests to same domain.
        window_seconds: Sliding window duration for rate tracking.
    """

    def __init__(
        self,
        default_max_rpm: int = 30,
        default_min_interval: float = 1.0,
        window_seconds: float = 60.0,
    ) -> None:
        self._default_max_rpm = default_max_rpm
        self._default_min_interval = default_min_interval
        self._window_seconds = window_seconds
        self._buckets: dict[str, DomainBucket] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, domain: str) -> DomainBucket:
        """Get or create a rate-limiting bucket for a domain."""
        if domain not in self._buckets:
            self._buckets[domain] = DomainBucket(
                domain=domain,
                window_seconds=self._window_seconds,
                max_requests_per_window=self._default_max_rpm,
                min_interval_seconds=self._default_min_interval,
                window_start=time.time(),
            )
        return self._buckets[domain]

    def check_throttle(self, domain: str) -> tuple[ThrottleAction, float]:
        """Check if a request to ``domain`` should proceed.

        Returns:
            Tuple of (action, delay_seconds). If action is PROCEED,
            delay is 0. If DELAY, delay is the recommended wait.
            If BACKOFF, delay is the backoff duration remaining.
            If BLOCK, delay is time until backoff expires.
        """
        with self._lock:
            bucket = self._get_bucket(domain)
            bucket._reset_window_if_needed()
            now = time.time()

            # Check backoff
            if now < bucket.backoff_until:
                remaining = bucket.backoff_until - now
                if bucket.backoff_count >= 5:
                    return ThrottleAction.BLOCK, remaining
                return ThrottleAction.BACKOFF, remaining

            # Check rate limit
            if bucket.requests_in_window >= bucket.max_requests_per_window:
                wait = bucket.window_seconds - (now - bucket.window_start)
                return ThrottleAction.DELAY, max(0.0, wait)

            # Check minimum interval
            elapsed = now - bucket.last_request
            if elapsed < bucket.min_interval_seconds:
                wait = bucket.min_interval_seconds - elapsed
                return ThrottleAction.DELAY, wait

            return ThrottleAction.PROCEED, 0.0

    def record_request(self, domain: str) -> None:
        """Record that a request was sent to ``domain``."""
        with self._lock:
            self._get_bucket(domain).record_request()

    def record_response(self, domain: str, status_code: int) -> None:
        """Record the response status code for adaptive throttling."""
        with self._lock:
            self._get_bucket(domain).record_response(status_code)

    def get_domain_stats(self, domain: str) -> dict[str, Any]:
        """Get throttling statistics for a specific domain."""
        with self._lock:
            bucket = self._get_bucket(domain)
            return {
                "domain": domain,
                "requests_total": bucket.requests_total,
                "requests_in_window": bucket.requests_in_window,
                "errors_in_window": bucket.errors_in_window,
                "error_rate": round(bucket.error_rate, 3),
                "recent_block_rate": round(bucket.recent_block_rate, 3),
                "max_rpm": bucket.max_requests_per_window,
                "min_interval": round(bucket.min_interval_seconds, 2),
                "backoff_count": bucket.backoff_count,
                "is_backed_off": time.time() < bucket.backoff_until,
            }

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get throttling statistics for all tracked domains."""
        with self._lock:
            return {
                domain: {
                    "requests_total": b.requests_total,
                    "error_rate": round(b.error_rate, 3),
                    "recent_block_rate": round(b.recent_block_rate, 3),
                    "max_rpm": b.max_requests_per_window,
                    "backoff_count": b.backoff_count,
                }
                for domain, b in self._buckets.items()
            }

    def reset_domain(self, domain: str) -> None:
        """Reset throttling state for a domain."""
        with self._lock:
            self._buckets.pop(domain, None)

    def reset_all(self) -> None:
        """Reset all throttling state."""
        with self._lock:
            self._buckets.clear()


# ============================================================================
# Stealth Metrics Collector (Cycles 28–30)
# ============================================================================


@dataclass
class StealthEventRecord:
    """A single stealth-related event for metrics tracking."""
    timestamp: float
    event_type: str  # "request", "block", "detection", "circuit_renewal"
    domain: str = ""
    proxy_chain_id: str = ""
    status_code: int = 0
    latency_ms: float = 0.0
    user_agent: str = ""
    tls_profile: str = ""
    was_detected: bool = False
    detection_type: str = ""  # "captcha", "block", "rate_limit", "fingerprint"


class StealthMetricsCollector:
    """Collect and analyze stealth effectiveness metrics.

    Tracks detection rates, block rates, fingerprint diversity,
    proxy health, and timing patterns across a scan to provide
    real-time stealth effectiveness analysis.
    """

    def __init__(self, max_events: int = 10000) -> None:
        self._events: list[StealthEventRecord] = []
        self._max_events = max_events
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Counters for fast access
        self._total_requests = 0
        self._total_blocks = 0
        self._total_detections = 0
        self._total_successes = 0
        self._unique_user_agents: set[str] = set()
        self._unique_tls_profiles: set[str] = set()
        self._unique_proxies: set[str] = set()
        self._domain_blocks: dict[str, int] = defaultdict(int)

    def record_event(self, event: StealthEventRecord) -> None:
        """Record a stealth event."""
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

            if event.event_type == "request":
                self._total_requests += 1
                if event.user_agent:
                    self._unique_user_agents.add(event.user_agent)
                if event.tls_profile:
                    self._unique_tls_profiles.add(event.tls_profile)
                if event.proxy_chain_id:
                    self._unique_proxies.add(event.proxy_chain_id)

                if event.was_detected:
                    self._total_detections += 1
                    self._domain_blocks[event.domain] = (
                        self._domain_blocks.get(event.domain, 0) + 1
                    )

                if event.status_code in (429, 403, 503):
                    self._total_blocks += 1
                    self._domain_blocks[event.domain] = (
                        self._domain_blocks.get(event.domain, 0) + 1
                    )
                elif 200 <= event.status_code < 400:
                    self._total_successes += 1

    def record_request(
        self,
        domain: str = "",
        status_code: int = 0,
        latency_ms: float = 0.0,
        user_agent: str = "",
        tls_profile: str = "",
        proxy_chain_id: str = "",
        was_detected: bool = False,
        detection_type: str = "",
    ) -> None:
        """Convenience method to record a request event."""
        self.record_event(StealthEventRecord(
            timestamp=time.time(),
            event_type="request",
            domain=domain,
            proxy_chain_id=proxy_chain_id,
            status_code=status_code,
            latency_ms=latency_ms,
            user_agent=user_agent,
            tls_profile=tls_profile,
            was_detected=was_detected,
            detection_type=detection_type,
        ))

    @property
    def detection_rate(self) -> float:
        """Fraction of requests that were detected as automated."""
        if self._total_requests == 0:
            return 0.0
        return self._total_detections / self._total_requests

    @property
    def block_rate(self) -> float:
        """Fraction of requests that were blocked (429/403/503)."""
        if self._total_requests == 0:
            return 0.0
        return self._total_blocks / self._total_requests

    @property
    def success_rate(self) -> float:
        """Fraction of requests that succeeded (2xx/3xx)."""
        if self._total_requests == 0:
            return 0.0
        return self._total_successes / self._total_requests

    @property
    def fingerprint_diversity_score(self) -> float:
        """Score from 0–1 indicating how diverse request fingerprints are.

        Higher is better. Considers UA diversity, TLS profile diversity,
        and proxy diversity.
        """
        scores = []

        # UA diversity: ratio of unique UAs to expected (10+)
        ua_count = len(self._unique_user_agents)
        scores.append(min(ua_count / 10, 1.0))

        # TLS diversity: ratio of profiles used to available (4)
        tls_count = len(self._unique_tls_profiles)
        scores.append(min(tls_count / 4, 1.0))

        # Proxy diversity: ratio of proxies used to expected (3+)
        proxy_count = len(self._unique_proxies)
        if proxy_count > 0:
            scores.append(min(proxy_count / 3, 1.0))

        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def get_report(self) -> dict[str, Any]:
        """Generate a comprehensive stealth effectiveness report."""
        with self._lock:
            elapsed = time.time() - self._start_time
            return {
                "elapsed_seconds": round(elapsed, 1),
                "total_requests": self._total_requests,
                "total_successes": self._total_successes,
                "total_blocks": self._total_blocks,
                "total_detections": self._total_detections,
                "success_rate": round(self.success_rate, 4),
                "block_rate": round(self.block_rate, 4),
                "detection_rate": round(self.detection_rate, 4),
                "fingerprint_diversity": round(
                    self.fingerprint_diversity_score, 3
                ),
                "unique_user_agents": len(self._unique_user_agents),
                "unique_tls_profiles": len(self._unique_tls_profiles),
                "unique_proxies": len(self._unique_proxies),
                "requests_per_minute": round(
                    self._total_requests / max(elapsed / 60, 0.01), 1
                ),
                "most_blocked_domains": dict(
                    sorted(
                        self._domain_blocks.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]
                ),
            }

    def get_domain_risk(self, domain: str) -> str:
        """Assess detection risk level for a domain.

        Returns: "low", "medium", "high", or "critical".
        """
        blocks = self._domain_blocks.get(domain, 0)
        if blocks == 0:
            return "low"
        if blocks <= 2:
            return "medium"
        if blocks <= 5:
            return "high"
        return "critical"

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._events.clear()
            self._total_requests = 0
            self._total_blocks = 0
            self._total_detections = 0
            self._total_successes = 0
            self._unique_user_agents.clear()
            self._unique_tls_profiles.clear()
            self._unique_proxies.clear()
            self._domain_blocks.clear()
            self._start_time = time.time()


# ============================================================================
# Scan-Level Stealth Configuration (Cycles 31–33)
# ============================================================================


@dataclass
class ScanStealthConfig:
    """Scan-level stealth configuration.

    Maps to SpiderFoot's options system and controls all stealth
    behavior for a scan. Can be serialized/deserialized for persistence.

    This is the user-facing configuration; it gets translated into
    the lower-level :class:`StealthProfileConfig` internally.
    """
    # Core stealth level
    stealth_level: str = "medium"  # none, low, medium, high, paranoid

    # Proxy configuration
    proxy_list: list[str] = field(default_factory=list)
    proxy_strategy: str = "round_robin"  # round_robin, random, least_used, etc.

    # Proxy chain configuration
    proxy_chains: list[list[str]] = field(default_factory=list)
    chain_strategy: str = "rotating"  # static, rotating, per_domain, random

    # Tor configuration
    tor_enabled: bool = False
    tor_socks_port: int = 9050
    tor_control_port: int = 9051
    tor_control_password: str = ""
    tor_renew_every_n: int = 10

    # Throttling
    max_requests_per_minute: int = 30
    min_request_interval: float = 1.0
    throttle_on_block: bool = True

    # TLS fingerprinting
    tls_diversify: bool = True
    tls_pin_per_target: bool = True

    # Header randomization
    rotate_user_agents: bool = True
    header_randomization_rate: float = 0.5

    # Jitter
    jitter_min: float = 0.1
    jitter_max: float = 5.0
    jitter_mean: float = 1.5
    jitter_distribution: str = "human"  # uniform, gaussian, human, pareto

    # Domain blacklist (never apply stealth, e.g., internal APIs)
    stealth_bypass_domains: list[str] = field(default_factory=list)

    # Metrics
    collect_metrics: bool = True
    max_metric_events: int = 10000

    def to_stealth_profile(self) -> StealthProfileConfig:
        """Convert to the lower-level StealthProfileConfig."""
        level = StealthLevel(self.stealth_level.lower())

        # Start with level presets
        config = StealthProfileConfig.from_level(level)

        # Override with scan-specific settings
        config.ua_pin_per_session = True
        config.header_optional_rate = self.header_randomization_rate

        if self.tls_diversify:
            config.tls_pin_per_target = self.tls_pin_per_target

        # Proxy entries
        proxy_entries = []
        for proxy_url in self.proxy_list:
            protocol = ProxyProtocol.HTTP
            if "socks5" in proxy_url:
                protocol = ProxyProtocol.SOCKS5
            elif "socks4" in proxy_url:
                protocol = ProxyProtocol.SOCKS4
            elif "https" in proxy_url.split("://")[0]:
                protocol = ProxyProtocol.HTTPS

            # Strip protocol prefix for ProxyEntry URL
            clean_url = proxy_url
            for prefix in ("socks5h://", "socks5://", "socks4://", "https://", "http://"):
                if clean_url.startswith(prefix):
                    clean_url = clean_url[len(prefix):]
                    break

            proxy_entries.append(ProxyEntry(
                url=clean_url,
                protocol=protocol,
            ))

        if proxy_entries:
            config.proxy_entries = proxy_entries
            try:
                config.proxy_strategy = ProxySelectionStrategy(self.proxy_strategy)
            except ValueError:
                config.proxy_strategy = ProxySelectionStrategy.ROUND_ROBIN

        # Tor
        config.use_tor = self.tor_enabled
        config.tor_control_password = self.tor_control_password
        config.tor_renew_every_n = self.tor_renew_every_n

        # Jitter
        try:
            config.jitter_distribution = JitterDistribution(self.jitter_distribution)
        except ValueError:
            config.jitter_distribution = JitterDistribution.HUMAN
        config.jitter_min_delay = self.jitter_min
        config.jitter_max_delay = self.jitter_max
        config.jitter_mean_delay = self.jitter_mean

        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for persistence."""
        return {
            "stealth_level": self.stealth_level,
            "proxy_list": self.proxy_list,
            "proxy_strategy": self.proxy_strategy,
            "proxy_chains": self.proxy_chains,
            "chain_strategy": self.chain_strategy,
            "tor_enabled": self.tor_enabled,
            "tor_socks_port": self.tor_socks_port,
            "tor_control_port": self.tor_control_port,
            "tor_renew_every_n": self.tor_renew_every_n,
            "max_requests_per_minute": self.max_requests_per_minute,
            "min_request_interval": self.min_request_interval,
            "throttle_on_block": self.throttle_on_block,
            "tls_diversify": self.tls_diversify,
            "tls_pin_per_target": self.tls_pin_per_target,
            "rotate_user_agents": self.rotate_user_agents,
            "header_randomization_rate": self.header_randomization_rate,
            "jitter_min": self.jitter_min,
            "jitter_max": self.jitter_max,
            "jitter_mean": self.jitter_mean,
            "jitter_distribution": self.jitter_distribution,
            "stealth_bypass_domains": self.stealth_bypass_domains,
            "collect_metrics": self.collect_metrics,
            "max_metric_events": self.max_metric_events,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScanStealthConfig":
        """Deserialize from dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    @classmethod
    def from_sf_options(cls, opts: dict[str, Any]) -> "ScanStealthConfig":
        """Create from SpiderFoot's options dictionary.

        Maps SpiderFoot option keys (prefixed with ``_stealth_``) to
        scan stealth configuration.
        """
        config = cls()
        prefix = "_stealth_"

        mappings = {
            f"{prefix}level": "stealth_level",
            f"{prefix}proxy_list": "proxy_list",
            f"{prefix}proxy_strategy": "proxy_strategy",
            f"{prefix}proxy_chains": "proxy_chains",
            f"{prefix}chain_strategy": "chain_strategy",
            f"{prefix}tor_enabled": "tor_enabled",
            f"{prefix}tor_socks_port": "tor_socks_port",
            f"{prefix}tor_control_port": "tor_control_port",
            f"{prefix}tor_control_password": "tor_control_password",
            f"{prefix}tor_renew_every_n": "tor_renew_every_n",
            f"{prefix}max_rpm": "max_requests_per_minute",
            f"{prefix}min_interval": "min_request_interval",
            f"{prefix}throttle_on_block": "throttle_on_block",
            f"{prefix}tls_diversify": "tls_diversify",
            f"{prefix}tls_pin_per_target": "tls_pin_per_target",
            f"{prefix}rotate_ua": "rotate_user_agents",
            f"{prefix}header_rate": "header_randomization_rate",
            f"{prefix}jitter_min": "jitter_min",
            f"{prefix}jitter_max": "jitter_max",
            f"{prefix}jitter_mean": "jitter_mean",
            f"{prefix}jitter_dist": "jitter_distribution",
            f"{prefix}bypass_domains": "stealth_bypass_domains",
            f"{prefix}collect_metrics": "collect_metrics",
        }

        for opt_key, attr_name in mappings.items():
            if opt_key in opts:
                setattr(config, attr_name, opts[opt_key])

        # Also check legacy SOCKS options
        if opts.get("_socks1type") and not config.proxy_list:
            socks_type = opts["_socks1type"]
            socks_addr = opts.get("_socks2addr", "")
            socks_port = opts.get("_socks3port", "")
            if socks_addr and socks_port:
                proxy_url = f"{socks_type}://{socks_addr}:{socks_port}"
                config.proxy_list = [proxy_url]

        return config


# ============================================================================
# Stealth Scan Context (Cycles 34–36)
# ============================================================================


class StealthScanContext:
    """Per-scan stealth state container.

    Holds the stealth engine, throttler, metrics collector, and
    domain blacklist for a single scan instance. Thread-safe.

    This is the primary object that gets attached to a scan and
    provides all stealth functionality.
    """

    def __init__(self, config: ScanStealthConfig | None = None) -> None:
        self._config = config or ScanStealthConfig()
        self._engine = StealthEngine(self._config.to_stealth_profile())
        self._throttler = DomainThrottler(
            default_max_rpm=self._config.max_requests_per_minute,
            default_min_interval=self._config.min_request_interval,
        )
        self._metrics = StealthMetricsCollector(
            max_events=self._config.max_metric_events,
        ) if self._config.collect_metrics else None

        # Proxy chain manager
        self._chain_manager: ProxyChainManager | None = None
        if self._config.proxy_chains:
            chains = []
            for chain_urls in self._config.proxy_chains:
                hops = []
                for url in chain_urls:
                    protocol = ProxyProtocol.SOCKS5
                    if url.startswith("http://"):
                        protocol = ProxyProtocol.HTTP
                    elif url.startswith("https://"):
                        protocol = ProxyProtocol.HTTPS
                    clean = url
                    for prefix in ("socks5h://", "socks5://", "socks4://",
                                   "https://", "http://"):
                        if clean.startswith(prefix):
                            clean = clean[len(prefix):]
                            break
                    hops.append(ProxyHop(url=clean, protocol=protocol))
                chains.append(ProxyChain(hops=hops))

            try:
                strategy = ProxyChainStrategy(self._config.chain_strategy)
            except ValueError:
                strategy = ProxyChainStrategy.ROTATING
            self._chain_manager = ProxyChainManager(
                chains=chains, strategy=strategy,
            )

        self._bypass_domains = set(self._config.stealth_bypass_domains)
        self._active = True
        self._lock = threading.Lock()

        # ── Optional advanced stealth components ──────────────────────
        # Wired in as optional enhancers — when available, the
        # StealthFetchMiddleware uses them for adaptive response
        # analysis and scan-level request orchestration.

        self._adaptive_manager: Any | None = None  # TargetStealthManager
        self._orchestrator: Any | None = None       # RequestOrchestrator

        # Auto-create adaptive stealth for medium+ levels
        if self._config.stealth_level in ("medium", "high", "paranoid"):
            try:
                from .adaptive_stealth import TargetStealthManager
                self._adaptive_manager = TargetStealthManager()
            except Exception:
                log.debug("Adaptive stealth not available")

        # Auto-create request orchestrator for high+ levels
        if self._config.stealth_level in ("high", "paranoid"):
            try:
                from .request_orchestration import (
                    RequestOrchestrator,
                    get_timing_profile,
                )
                profile_map = {
                    "high": "cautious",
                    "paranoid": "paranoid",
                }
                profile_name = profile_map.get(
                    self._config.stealth_level, "research"
                )
                timing = get_timing_profile(profile_name)
                self._orchestrator = RequestOrchestrator(timing=timing)
            except Exception:
                log.debug("Request orchestration not available")

    @property
    def engine(self) -> StealthEngine:
        return self._engine

    @property
    def throttler(self) -> DomainThrottler:
        return self._throttler

    @property
    def metrics(self) -> StealthMetricsCollector | None:
        return self._metrics

    @property
    def chain_manager(self) -> ProxyChainManager | None:
        return self._chain_manager

    @property
    def adaptive_manager(self) -> Any | None:
        """Per-target adaptive stealth manager (WAF detection + feedback loop)."""
        return self._adaptive_manager

    @property
    def orchestrator(self) -> Any | None:
        """Scan-level request orchestrator (timing profiles + scheduling)."""
        return self._orchestrator

    @property
    def config(self) -> ScanStealthConfig:
        return self._config

    @property
    def is_active(self) -> bool:
        return self._active

    def is_bypass_domain(self, domain: str) -> bool:
        """Check if a domain should bypass stealth measures."""
        if not domain:
            return False
        return domain in self._bypass_domains or any(
            domain.endswith(f".{d}") for d in self._bypass_domains
        )

    def add_bypass_domain(self, domain: str) -> None:
        """Add a domain to the bypass list."""
        self._bypass_domains.add(domain)

    def deactivate(self) -> None:
        """Deactivate the stealth context (e.g., on scan completion)."""
        self._active = False

    def reactivate(self) -> None:
        self._active = True

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive stealth statistics for this scan."""
        stats: dict[str, Any] = {
            "active": self._active,
            "stealth_level": self._config.stealth_level,
            "engine_stats": self._engine.get_stats(),
            "throttler_stats": self._throttler.get_all_stats(),
        }
        if self._metrics:
            stats["metrics"] = self._metrics.get_report()
        if self._chain_manager:
            stats["proxy_chains"] = self._chain_manager.get_stats()
        if self._adaptive_manager:
            try:
                stats["adaptive_stealth"] = self._adaptive_manager.get_global_stats()
            except Exception:
                pass
        if self._orchestrator:
            try:
                stats["orchestrator"] = self._orchestrator.get_stats()
            except Exception:
                pass
        return stats

    def reset(self) -> None:
        """Reset all stealth state (engine, throttler, metrics)."""
        self._engine.reset()
        self._throttler.reset_all()
        if self._metrics:
            self._metrics.reset()
        if self._chain_manager:
            self._chain_manager.clear_domain_pins()


# ============================================================================
# Stealth Fetch Middleware (Cycles 37–40)
# ============================================================================


def _extract_domain(url: str) -> str:
    """Extract domain from a URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


class StealthFetchMiddleware:
    """Transparent middleware wrapping every outbound HTTP request.

    Intercepts ``fetchUrl`` calls and applies:
    1. Domain throttling (rate limit + adaptive backoff)
    2. Stealth headers (UA rotation, header randomization)
    3. Proxy/chain selection
    4. Request jitter (timing randomization)
    5. Response analysis (detection/block detection)
    6. Metrics collection

    Thread-safe for concurrent scan module execution.

    Args:
        context: The stealth scan context for this scan.
        max_retries: Maximum retries when blocked.
        detection_patterns: List of patterns indicating automated detection.
    """

    # Common detection indicators in response bodies/headers
    DEFAULT_DETECTION_PATTERNS = [
        "captcha",
        "cloudflare",
        "are you a robot",
        "automated access",
        "bot detected",
        "access denied",
        "rate limit exceeded",
        "too many requests",
        "please verify you are human",
        "unusual traffic",
        "security check",
        "ddos protection",
    ]

    def __init__(
        self,
        context: StealthScanContext,
        max_retries: int = 2,
        detection_patterns: list[str] | None = None,
    ) -> None:
        self._ctx = context
        self._max_retries = max_retries
        self._detection_patterns = (
            detection_patterns or self.DEFAULT_DETECTION_PATTERNS
        )
        self._fetch_count = 0
        self._lock = threading.Lock()

    def fetch(
        self,
        url: str,
        *,
        cookies: str | None = None,
        timeout: int = 30,
        useragent: str = "SpiderFoot",
        headers: dict[str, str] | None = None,
        noLog: bool = False,
        postData: str | None = None,
        disableContentEncoding: bool = False,
        sizeLimit: int | None = None,
        headOnly: bool = False,
        verify: bool = True,
        _original_fetch: Callable | None = None,
    ) -> dict | None:
        """Fetch a URL with full stealth measures applied.

        This is intended as a drop-in replacement for ``fetchUrl``.
        The ``_original_fetch`` parameter should be the original
        ``fetchUrl`` function to delegate to after applying stealth.

        Returns:
            Dict matching fetchUrl's return format, or None on total failure.
        """
        if not url:
            return None

        domain = _extract_domain(url)

        # Check bypass
        if not self._ctx.is_active or self._ctx.is_bypass_domain(domain):
            if _original_fetch:
                return _original_fetch(
                    url, cookies=cookies, timeout=timeout,
                    useragent=useragent, headers=headers,
                    noLog=noLog, postData=postData,
                    disableContentEncoding=disableContentEncoding,
                    sizeLimit=sizeLimit, headOnly=headOnly,
                    verify=verify,
                )
            return self._default_result(url)

        # Attempt with retries
        for attempt in range(1 + self._max_retries):
            result = self._do_stealthy_fetch(
                url=url,
                domain=domain,
                cookies=cookies,
                timeout=timeout,
                headers=headers,
                noLog=noLog,
                postData=postData,
                disableContentEncoding=disableContentEncoding,
                sizeLimit=sizeLimit,
                headOnly=headOnly,
                verify=verify,
                _original_fetch=_original_fetch,
                attempt=attempt,
            )

            if result is None:
                continue

            status_code = self._parse_status_code(result)

            # If blocked and we can retry, wait and try again
            if status_code in (429, 503) and attempt < self._max_retries:
                backoff = min(2 ** (attempt + 1), 30)
                log.debug(
                    "Stealth: %d on %s, retrying in %ds (attempt %d/%d)",
                    status_code, domain, backoff, attempt + 1, self._max_retries,
                )
                time.sleep(backoff)
                continue

            return result

        return self._default_result(url)

    def _do_stealthy_fetch(
        self,
        *,
        url: str,
        domain: str,
        cookies: str | None,
        timeout: int,
        headers: dict[str, str] | None,
        noLog: bool,
        postData: str | None,
        disableContentEncoding: bool,
        sizeLimit: int | None,
        headOnly: bool,
        verify: bool,
        _original_fetch: Callable | None,
        attempt: int,
    ) -> dict | None:
        """Execute a single fetch attempt with stealth measures."""
        engine = self._ctx.engine
        throttler = self._ctx.throttler
        metrics = self._ctx.metrics
        chain_mgr = self._ctx.chain_manager

        # 1. Throttle check
        action, delay = throttler.check_throttle(domain)
        if action == ThrottleAction.BLOCK:
            log.warning("Stealth: domain %s is blocked (backoff), skipping", domain)
            return self._default_result(url)
        if action in (ThrottleAction.DELAY, ThrottleAction.BACKOFF):
            if delay > 0:
                time.sleep(min(delay, 30))

        # 2. Apply jitter (amplified by adaptive delay when available)
        jitter_delay = engine.apply_jitter()

        # Apply adaptive delay multiplier from per-target learning
        adaptive_mgr = self._ctx.adaptive_manager
        if adaptive_mgr is not None:
            try:
                multiplier = adaptive_mgr.get_delay_multiplier(domain)
                if multiplier > 1.0 and jitter_delay > 0:
                    extra = jitter_delay * (multiplier - 1.0)
                    time.sleep(extra)
            except Exception:
                pass

        # 3. Prepare stealth headers
        stealth_headers = engine.prepare_headers(
            target_url=url,
            extra_headers=headers,
        )

        # Extract the UA being used for metrics
        ua_used = stealth_headers.get("User-Agent", "SpiderFoot")

        # 4. Get proxy (chain or regular)
        proxies = None
        chain_id = ""
        if chain_mgr and chain_mgr.healthy_count > 0:
            chain = chain_mgr.get_chain(domain=domain)
            if chain:
                proxies = chain.to_requests_proxies()
                chain_id = chain.chain_id
        else:
            proxy_dict = engine.get_proxy()
            if proxy_dict:
                proxies = proxy_dict

        # 5. Record request in throttler
        throttler.record_request(domain)

        # 6. Execute the actual fetch
        t0 = time.monotonic()
        try:
            if _original_fetch:
                result = _original_fetch(
                    url,
                    cookies=cookies,
                    timeout=timeout,
                    useragent=stealth_headers.get("User-Agent", "SpiderFoot"),
                    headers=stealth_headers,
                    noLog=noLog,
                    postData=postData,
                    disableContentEncoding=disableContentEncoding,
                    sizeLimit=sizeLimit,
                    headOnly=headOnly,
                    verify=verify,
                )
            else:
                result = self._default_result(url)
        except Exception as exc:
            log.debug("Stealth fetch error for %s: %s", url, exc)
            result = self._default_result(url)

        latency_ms = (time.monotonic() - t0) * 1000

        # 7. Analyze response
        status_code = self._parse_status_code(result)
        was_detected = self._check_detection(result)
        detection_type = ""
        if was_detected:
            detection_type = self._classify_detection(result)

        # 8. Record response in throttler
        if status_code > 0:
            throttler.record_response(domain, status_code)

        # 9. Record proxy chain result
        if chain_id and chain_mgr:
            chain_mgr.record_result(
                chain_id,
                success=(200 <= status_code < 400),
                latency_ms=latency_ms,
            )
        elif proxies:
            proxy_url = list(proxies.values())[0] if proxies else ""
            engine.record_proxy_result(
                proxy_url, success=(200 <= status_code < 400),
                latency_ms=latency_ms,
            )

        # 10. Record metrics
        if metrics:
            tls_profile = ""
            if hasattr(engine, '_tls_diversifier') and engine._tls_diversifier:
                tls_profile = engine._tls_diversifier.get_current_profile(domain)
            metrics.record_request(
                domain=domain,
                status_code=status_code,
                latency_ms=latency_ms,
                user_agent=ua_used,
                tls_profile=tls_profile,
                proxy_chain_id=chain_id,
                was_detected=was_detected,
                detection_type=detection_type,
            )

        # 11. Adaptive stealth — feed response to per-target learning
        adaptive_mgr = self._ctx.adaptive_manager
        if adaptive_mgr is not None:
            try:
                content = (result.get("content") or "") if result else ""
                resp_headers = (result.get("headers") or {}) if result else {}
                adaptive_mgr.analyze_response(
                    target=domain,
                    status_code=status_code,
                    headers=resp_headers,
                    body=content[:5000],  # limit body analysis
                    response_time_ms=latency_ms,
                )
            except Exception as adp_err:
                log.debug("Adaptive stealth analysis failed for %s: %s",
                          domain, adp_err)

        # 12. Increment request counter
        with self._lock:
            self._fetch_count += 1

        return result

    def _check_detection(self, result: dict | None) -> bool:
        """Check if the response indicates automated access detection."""
        if not result:
            return False

        status_code = self._parse_status_code(result)
        if status_code in (403, 429, 503):
            # Could be detection, check content
            content = (result.get("content") or "").lower()
            for pattern in self._detection_patterns:
                if pattern in content:
                    return True

        # Check for captcha indicators in headers
        resp_headers = result.get("headers") or {}
        for key, value in resp_headers.items():
            key_lower = key.lower()
            if "captcha" in key_lower or "challenge" in key_lower:
                return True
            if key_lower == "server" and "cloudflare" in str(value).lower():
                content = (result.get("content") or "").lower()
                if "challenge" in content or "ray id" in content:
                    return True

        return False

    def _classify_detection(self, result: dict | None) -> str:
        """Classify the type of detection encountered."""
        if not result:
            return "unknown"

        status_code = self._parse_status_code(result)
        content = (result.get("content") or "").lower()

        if status_code == 429:
            return "rate_limit"
        if "captcha" in content or "recaptcha" in content:
            return "captcha"
        if "cloudflare" in content:
            return "waf_cloudflare"
        if "akamai" in content:
            return "waf_akamai"
        if status_code == 403:
            if any(p in content for p in ("bot", "automated", "robot")):
                return "bot_detection"
            return "block"
        if status_code == 503:
            return "service_protection"

        return "unknown"

    @staticmethod
    def _parse_status_code(result: dict | None) -> int:
        """Parse status code from fetchUrl result."""
        if not result:
            return 0
        code = result.get("code")
        if code is None:
            return 0
        try:
            return int(code)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _default_result(url: str) -> dict:
        """Return an empty result matching fetchUrl's format."""
        return {
            "code": None,
            "status": None,
            "content": None,
            "headers": None,
            "realurl": url,
        }

    @property
    def fetch_count(self) -> int:
        return self._fetch_count


# ============================================================================
# Public API — Factory + Convenience Functions (Cycles 39–40)
# ============================================================================


def create_stealth_context(
    config: ScanStealthConfig | None = None,
    *,
    stealth_level: str | None = None,
    sf_options: dict[str, Any] | None = None,
) -> StealthScanContext:
    """Factory function to create a per-scan stealth context.

    Args:
        config: Explicit stealth configuration.
        stealth_level: Quick shortcut — creates a config from level name.
        sf_options: SpiderFoot options dict — extracts ``_stealth_*`` keys.

    Priority: config > sf_options > stealth_level > defaults.
    """
    if config:
        return StealthScanContext(config)
    if sf_options:
        config = ScanStealthConfig.from_sf_options(sf_options)
        return StealthScanContext(config)
    if stealth_level:
        config = ScanStealthConfig(stealth_level=stealth_level)
        return StealthScanContext(config)
    return StealthScanContext()


# Module-level stealth context registry (scan_id -> context)
_scan_contexts: dict[str, StealthScanContext] = {}
_registry_lock = threading.Lock()


def register_scan_context(scan_id: str, context: StealthScanContext) -> None:
    """Register a stealth context for a scan."""
    with _registry_lock:
        _scan_contexts[scan_id] = context


def get_scan_context(scan_id: str) -> StealthScanContext | None:
    """Retrieve the stealth context for a scan."""
    with _registry_lock:
        return _scan_contexts.get(scan_id)


def unregister_scan_context(scan_id: str) -> None:
    """Remove a stealth context when a scan is complete."""
    with _registry_lock:
        ctx = _scan_contexts.pop(scan_id, None)
        if ctx:
            ctx.deactivate()


def stealthy_fetch(
    url: str,
    *,
    context: StealthScanContext | None = None,
    scan_id: str | None = None,
    cookies: str | None = None,
    timeout: int = 30,
    useragent: str = "SpiderFoot",
    headers: dict[str, str] | None = None,
    noLog: bool = False,
    postData: str | None = None,
    disableContentEncoding: bool = False,
    sizeLimit: int | None = None,
    headOnly: bool = False,
    verify: bool = True,
    _original_fetch: Callable | None = None,
) -> dict | None:
    """Drop-in replacement for ``fetchUrl`` with stealth measures.

    Can be used in two ways:

    1. Pass a ``context`` directly::

        result = stealthy_fetch("https://target.com", context=ctx)

    2. Pass a ``scan_id`` to look up the registered context::

        result = stealthy_fetch("https://target.com", scan_id="scan-123")

    If no context is found, falls back to plain fetchUrl behavior.
    """
    # Resolve context
    if context is None and scan_id:
        context = get_scan_context(scan_id)

    if context is None:
        # No stealth — direct fetch
        if _original_fetch:
            return _original_fetch(
                url, cookies=cookies, timeout=timeout,
                useragent=useragent, headers=headers,
                noLog=noLog, postData=postData,
                disableContentEncoding=disableContentEncoding,
                sizeLimit=sizeLimit, headOnly=headOnly,
                verify=verify,
            )
        # Import and use network.fetchUrl
        from ..sflib.network import fetchUrl as raw_fetch
        return raw_fetch(
            url, cookies=cookies, timeout=timeout,
            useragent=useragent, headers=headers,
            noLog=noLog, postData=postData,
            disableContentEncoding=disableContentEncoding,
            sizeLimit=sizeLimit, headOnly=headOnly,
            verify=verify,
        )

    # Apply stealth middleware
    middleware = StealthFetchMiddleware(context)
    return middleware.fetch(
        url,
        cookies=cookies,
        timeout=timeout,
        useragent=useragent,
        headers=headers,
        noLog=noLog,
        postData=postData,
        disableContentEncoding=disableContentEncoding,
        sizeLimit=sizeLimit,
        headOnly=headOnly,
        verify=verify,
        _original_fetch=_original_fetch,
    )


def get_all_scan_stats() -> dict[str, dict[str, Any]]:
    """Get stealth statistics for all active scans."""
    with _registry_lock:
        return {
            scan_id: ctx.get_stats()
            for scan_id, ctx in _scan_contexts.items()
            if ctx.is_active
        }
