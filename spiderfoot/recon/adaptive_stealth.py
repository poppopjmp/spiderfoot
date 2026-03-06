# -------------------------------------------------------------------------------
# Name:         adaptive_stealth
# Purpose:      Per-target adaptive stealth + WAF detection triggers
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Adaptive Stealth — SOTA S-005 (Cycles 81–100).

Per-target adaptive stealth that learns from target responses and
automatically adjusts stealth parameters. Complements S-001/S-002
(static stealth) and S-003/S-004 (fingerprint + timing) with
real-time feedback-driven adaptation.

- :class:`TargetProfile` — Learned profile of a target's defenses,
  including WAF vendor, rate-limit thresholds, detection patterns,
  and optimal stealth settings.
- :class:`WAFDetector` — Real-time WAF/CDN detection from response
  headers, bodies, and behavior patterns (Cloudflare, Akamai,
  AWS WAF, Imperva, F5, Sucuri, Barracuda, ModSecurity).
- :class:`DetectionEvent` — Record of a detection or block event
  with classification and response analysis.
- :class:`AdaptiveController` — Feedback controller that adjusts
  stealth parameters based on detection events (delay multiplier,
  profile rotation speed, proxy switching urgency).
- :class:`TargetStealthManager` — Per-target stealth state manager
  that maintains learned profiles and applies adaptive settings.

Usage::

    from spiderfoot.recon.adaptive_stealth import (
        TargetStealthManager,
        WAFDetector,
    )

    mgr = TargetStealthManager()

    # Analyze a response for WAF/detection
    mgr.analyze_response(
        target="example.com",
        status_code=403,
        headers={"server": "cloudflare"},
        body="<html>Attention Required</html>",
    )

    # Get adaptive delay for next request
    delay_mult = mgr.get_delay_multiplier("example.com")

    # Get target's learned profile
    profile = mgr.get_target_profile("example.com")
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.recon.adaptive_stealth")


# ============================================================================
# WAF/CDN Detection (Cycles 81–85)
# ============================================================================


class WAFVendor(Enum):
    """Known WAF/CDN vendors."""
    UNKNOWN = "unknown"
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    AWS_WAF = "aws_waf"
    AWS_CLOUDFRONT = "aws_cloudfront"
    IMPERVA = "imperva"
    F5_BIG_IP = "f5_big_ip"
    SUCURI = "sucuri"
    BARRACUDA = "barracuda"
    MODSECURITY = "modsecurity"
    FASTLY = "fastly"
    STACKPATH = "stackpath"
    DDOS_GUARD = "ddos_guard"
    WORDFENCE = "wordfence"


class DetectionType(Enum):
    """Type of detection event."""
    RATE_LIMIT = "rate_limit"        # 429 Too Many Requests
    WAF_BLOCK = "waf_block"          # WAF blocked the request
    CAPTCHA = "captcha"              # CAPTCHA challenge
    BOT_DETECTION = "bot_detection"  # Bot detection challenge
    IP_BLOCK = "ip_block"            # IP-based block
    GEO_BLOCK = "geo_block"          # Geographic restriction
    AUTH_CHALLENGE = "auth_challenge"  # Authentication challenge
    FINGERPRINT = "fingerprint"       # TLS/HTTP fingerprint rejection
    BEHAVIOR = "behavior"            # Behavioral detection
    NONE = "none"                    # No detection


@dataclass
class WAFSignature:
    """Signature pattern for WAF detection."""
    vendor: WAFVendor
    header_patterns: dict[str, list[str]] = field(default_factory=dict)
    body_patterns: list[str] = field(default_factory=list)
    cookie_patterns: list[str] = field(default_factory=list)
    status_codes: list[int] = field(default_factory=list)


# Pre-built WAF signatures
_WAF_SIGNATURES: list[WAFSignature] = [
    WAFSignature(
        vendor=WAFVendor.CLOUDFLARE,
        header_patterns={
            "server": ["cloudflare"],
            "cf-ray": [".*"],
            "cf-cache-status": [".*"],
        },
        body_patterns=[
            r"Attention Required.*Cloudflare",
            r"cf-browser-verification",
            r"__cf_chl_managed_tk__",
            r"challenges\.cloudflare\.com",
        ],
        cookie_patterns=["__cfduid", "cf_clearance", "__cf_bm"],
    ),
    WAFSignature(
        vendor=WAFVendor.AKAMAI,
        header_patterns={
            "server": ["AkamaiGHost", "AkamaiNetStorage"],
            "x-akamai-transformed": [".*"],
        },
        body_patterns=[
            r"Access Denied.*akamai",
            r"Reference\s*#\d+\.\w+\.\d+",
        ],
        cookie_patterns=["ak_bmsc", "bm_sz", "akamai_generated"],
    ),
    WAFSignature(
        vendor=WAFVendor.AWS_WAF,
        header_patterns={
            "x-amzn-requestid": [".*"],
            "x-amz-cf-id": [".*"],
        },
        body_patterns=[
            r"<html>.*Request blocked",
            r"aws-waf-token",
        ],
        status_codes=[403],
    ),
    WAFSignature(
        vendor=WAFVendor.AWS_CLOUDFRONT,
        header_patterns={
            "server": ["CloudFront"],
            "x-amz-cf-pop": [".*"],
            "via": [".*cloudfront.*"],
        },
    ),
    WAFSignature(
        vendor=WAFVendor.IMPERVA,
        header_patterns={
            "x-iinfo": [".*"],
        },
        body_patterns=[
            r"Incapsula incident ID",
            r"_Incapsula_Resource",
            r"imperva\.com",
        ],
        cookie_patterns=["visid_incap", "incap_ses", "nlbi_"],
    ),
    WAFSignature(
        vendor=WAFVendor.F5_BIG_IP,
        header_patterns={
            "server": ["BigIP", "BIG-IP"],
            "x-cnection": [".*"],
        },
        cookie_patterns=["BigIPServer", "BIGipServer"],
    ),
    WAFSignature(
        vendor=WAFVendor.SUCURI,
        header_patterns={
            "server": ["Sucuri"],
            "x-sucuri-id": [".*"],
            "x-sucuri-cache": [".*"],
        },
        body_patterns=[
            r"sucuri\.net",
            r"Sucuri WebSite Firewall",
            r"cloudproxy@sucuri\.net",
        ],
    ),
    WAFSignature(
        vendor=WAFVendor.BARRACUDA,
        header_patterns={
            "server": ["BarracudaWAF"],
        },
        body_patterns=[
            r"Barracuda.*blocked",
        ],
        cookie_patterns=["barra_counter_session"],
    ),
    WAFSignature(
        vendor=WAFVendor.MODSECURITY,
        header_patterns={
            "server": [".*mod_security.*", ".*NOYB.*"],
        },
        body_patterns=[
            r"Mod_Security",
            r"NOYB",
            r"This error was generated by Mod_Security",
        ],
    ),
    WAFSignature(
        vendor=WAFVendor.FASTLY,
        header_patterns={
            "via": [".*varnish.*"],
            "x-served-by": ["cache-.*"],
            "x-fastly-request-id": [".*"],
        },
    ),
    WAFSignature(
        vendor=WAFVendor.DDOS_GUARD,
        header_patterns={
            "server": ["ddos-guard"],
        },
        cookie_patterns=["__ddg1", "__ddg2"],
    ),
    WAFSignature(
        vendor=WAFVendor.WORDFENCE,
        body_patterns=[
            r"Generated by Wordfence",
            r"wordfence.*block",
            r"wfPage",
        ],
    ),
]


@dataclass
class WAFDetectionResult:
    """Result of WAF/CDN detection analysis."""
    detected: bool
    vendor: WAFVendor
    confidence: float  # 0.0 – 1.0
    signals: list[str]  # What triggered detection
    detection_type: DetectionType

    def __str__(self) -> str:
        if not self.detected:
            return "No WAF detected"
        return f"{self.vendor.value} (confidence={self.confidence:.0%})"


class WAFDetector:
    """Detect WAF/CDN vendors from HTTP responses.

    Analyzes response headers, body content, cookies, and status
    codes to identify the WAF/CDN protecting a target.
    """

    def __init__(self) -> None:
        self._signatures = list(_WAF_SIGNATURES)
        self._detection_cache: dict[str, WAFDetectionResult] = {}
        self._lock = threading.Lock()

    def detect(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        body: str = "",
        cookies: dict[str, str] | None = None,
        target: str = "",
    ) -> WAFDetectionResult:
        """Detect WAF/CDN from response data.

        Args:
            status_code: HTTP status code.
            headers: Response headers (case-insensitive matching).
            body: Response body text.
            cookies: Response cookies.
            target: Target hostname (for caching).

        Returns:
            WAFDetectionResult with vendor and confidence.
        """
        headers = headers or {}
        cookies = cookies or {}
        headers_lower = {k.lower(): v.lower() for k, v in headers.items()}
        body_lower = body.lower() if body else ""

        best_match: WAFDetectionResult | None = None
        best_score = 0.0

        for sig in self._signatures:
            score, signals = self._match_signature(
                sig, status_code, headers_lower, body_lower, cookies
            )
            if score > best_score:
                best_score = score
                detection_type = self._classify_detection(status_code, body_lower)
                best_match = WAFDetectionResult(
                    detected=True,
                    vendor=sig.vendor,
                    confidence=min(score, 1.0),
                    signals=signals,
                    detection_type=detection_type,
                )

        if best_match is None or best_score < 0.2:
            detection_type = self._classify_detection(status_code, body_lower)
            result = WAFDetectionResult(
                detected=False,
                vendor=WAFVendor.UNKNOWN,
                confidence=0.0,
                signals=[],
                detection_type=detection_type,
            )
        else:
            result = best_match

        # Cache per-target
        if target:
            with self._lock:
                self._detection_cache[target] = result

        return result

    def get_cached(self, target: str) -> WAFDetectionResult | None:
        """Get cached WAF detection for a target."""
        with self._lock:
            return self._detection_cache.get(target)

    def _match_signature(
        self,
        sig: WAFSignature,
        status_code: int,
        headers: dict[str, str],
        body: str,
        cookies: dict[str, str],
    ) -> tuple[float, list[str]]:
        """Match a WAF signature against response data.

        Returns:
            Tuple of (match score 0-1, list of matching signals).
        """
        signals: list[str] = []
        total_checks = 0
        matches = 0

        # Header matching
        for header_name, patterns in sig.header_patterns.items():
            total_checks += 1
            header_value = headers.get(header_name, "")
            if header_value:
                for pattern in patterns:
                    if re.search(pattern, header_value, re.IGNORECASE):
                        matches += 1
                        signals.append(f"header:{header_name}={header_value[:50]}")
                        break

        # Body pattern matching
        for pattern in sig.body_patterns:
            total_checks += 1
            if re.search(pattern, body, re.IGNORECASE):
                matches += 1
                signals.append(f"body:/{pattern[:40]}/")

        # Cookie matching
        cookie_names_lower = {k.lower(): v for k, v in cookies.items()}
        for cookie_pattern in sig.cookie_patterns:
            total_checks += 1
            for cookie_name in cookie_names_lower:
                if re.search(cookie_pattern, cookie_name, re.IGNORECASE):
                    matches += 1
                    signals.append(f"cookie:{cookie_name}")
                    break

        # Status code matching
        if sig.status_codes:
            total_checks += 1
            if status_code in sig.status_codes:
                matches += 1
                signals.append(f"status:{status_code}")

        if total_checks == 0 or matches == 0:
            return 0.0, []

        # Each positive match contributes significant confidence;
        # use the higher of ratio-based or per-match scoring so
        # that even 1 header hit on a 10-pattern signature is meaningful.
        ratio_score = matches / total_checks
        per_match_score = min(1.0, matches * 0.25)
        return max(ratio_score, per_match_score), signals

    def _classify_detection(self, status_code: int, body: str) -> DetectionType:
        """Classify the type of detection from status code and body."""
        if status_code == 429:
            return DetectionType.RATE_LIMIT
        if status_code == 403:
            if "captcha" in body or "challenge" in body:
                return DetectionType.CAPTCHA
            if "bot" in body or "automated" in body:
                return DetectionType.BOT_DETECTION
            return DetectionType.WAF_BLOCK
        if status_code == 503:
            if "captcha" in body:
                return DetectionType.CAPTCHA
            return DetectionType.WAF_BLOCK
        if status_code in (401, 407):
            return DetectionType.AUTH_CHALLENGE
        return DetectionType.NONE

    @property
    def signature_count(self) -> int:
        return len(self._signatures)

    @property
    def cached_targets(self) -> int:
        with self._lock:
            return len(self._detection_cache)


# ============================================================================
# Detection Events (Cycles 86–88)
# ============================================================================


@dataclass
class DetectionEvent:
    """Record of a detection or block event.

    Captures all relevant context for analysis and adaptation.
    """
    timestamp: float = field(default_factory=time.time)
    target: str = ""
    detection_type: DetectionType = DetectionType.NONE
    waf_vendor: WAFVendor = WAFVendor.UNKNOWN
    status_code: int = 0
    severity: float = 0.0  # 0.0 (info) to 1.0 (critical)
    description: str = ""
    response_time_ms: float = 0.0
    request_count_at_event: int = 0

    def __post_init__(self) -> None:
        if self.severity == 0.0 and self.detection_type != DetectionType.NONE:
            self.severity = _SEVERITY_MAP.get(self.detection_type, 0.5)


# Severity mapping for detection types
_SEVERITY_MAP: dict[DetectionType, float] = {
    DetectionType.RATE_LIMIT: 0.4,
    DetectionType.WAF_BLOCK: 0.7,
    DetectionType.CAPTCHA: 0.6,
    DetectionType.BOT_DETECTION: 0.8,
    DetectionType.IP_BLOCK: 0.9,
    DetectionType.GEO_BLOCK: 0.5,
    DetectionType.AUTH_CHALLENGE: 0.3,
    DetectionType.FINGERPRINT: 0.7,
    DetectionType.BEHAVIOR: 0.8,
    DetectionType.NONE: 0.0,
}


# ============================================================================
# Target Profile (Cycles 89–92)
# ============================================================================


class ThreatLevel(Enum):
    """Assessed threat level of a target's defenses."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TargetProfile:
    """Learned profile of a target's defenses.

    Built up incrementally from response analysis. Used to
    adapt stealth parameters for optimal evasion.
    """
    domain: str
    waf_vendor: WAFVendor = WAFVendor.UNKNOWN
    waf_confidence: float = 0.0
    threat_level: ThreatLevel = ThreatLevel.NONE

    # Learned thresholds
    estimated_rate_limit_rpm: float = 0.0  # Estimated requests/minute limit
    estimated_block_threshold: int = 0  # Requests before block

    # Detection history
    total_requests: int = 0
    total_detections: int = 0
    detection_rate: float = 0.0
    consecutive_successes: int = 0
    consecutive_failures: int = 0

    # Response timing
    avg_response_time_ms: float = 0.0
    _response_times: list[float] = field(default_factory=list)

    # Stealth parameters (adapted)
    delay_multiplier: float = 1.0
    profile_rotation_interval: int = 10  # Rotate every N requests
    proxy_switch_urgency: float = 0.0  # 0=none, 1=immediate

    # History
    events: list[DetectionEvent] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def detection_rate_pct(self) -> float:
        """Detection rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.total_detections / self.total_requests) * 100

    def update_response_time(self, time_ms: float) -> None:
        """Update response time tracking."""
        self._response_times.append(time_ms)
        if len(self._response_times) > 100:
            self._response_times = self._response_times[-100:]
        self.avg_response_time_ms = sum(self._response_times) / len(self._response_times)

    def to_dict(self) -> dict[str, Any]:
        """Serialize profile to dict."""
        return {
            "domain": self.domain,
            "waf_vendor": self.waf_vendor.value,
            "waf_confidence": self.waf_confidence,
            "threat_level": self.threat_level.value,
            "total_requests": self.total_requests,
            "total_detections": self.total_detections,
            "detection_rate": round(self.detection_rate, 4),
            "delay_multiplier": round(self.delay_multiplier, 2),
            "profile_rotation_interval": self.profile_rotation_interval,
            "proxy_switch_urgency": round(self.proxy_switch_urgency, 2),
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
            "event_count": len(self.events),
        }


# ============================================================================
# Adaptive Controller (Cycles 93–96)
# ============================================================================


class AdaptiveController:
    """Feedback controller that adjusts stealth parameters.

    Uses detection events to adapt delay multiplier, profile
    rotation speed, and proxy switching urgency in real-time.

    The controller implements a proportional-integral (PI) control
    loop with exponential decay for recovery:

    - On detection: increase delay multiplier by severity * gain
    - On success: decay multiplier toward 1.0
    - Track moving average of detection rate for trend analysis
    """

    def __init__(
        self,
        *,
        detection_gain: float = 1.5,
        recovery_rate: float = 0.95,
        max_delay_multiplier: float = 10.0,
        min_delay_multiplier: float = 0.5,
        escalation_threshold: int = 3,  # Consecutive detections to escalate
    ) -> None:
        self._detection_gain = detection_gain
        self._recovery_rate = recovery_rate
        self._max_mult = max_delay_multiplier
        self._min_mult = min_delay_multiplier
        self._escalation_threshold = escalation_threshold

    def update_on_detection(
        self, profile: TargetProfile, event: DetectionEvent
    ) -> None:
        """Update profile parameters after a detection event.

        Args:
            profile: Target's learned profile.
            event: The detection event.
        """
        profile.total_detections += 1
        profile.consecutive_failures += 1
        profile.consecutive_successes = 0
        profile.events.append(event)
        profile.last_seen = time.time()

        # Update detection rate (EMA with alpha=0.1)
        alpha = 0.1
        profile.detection_rate = (
            alpha * 1.0 + (1 - alpha) * profile.detection_rate
        )

        # Increase delay multiplier proportional to severity
        increase = event.severity * self._detection_gain
        profile.delay_multiplier = min(
            profile.delay_multiplier + increase,
            self._max_mult,
        )

        # Adjust profile rotation (more frequent under detection)
        if profile.consecutive_failures >= self._escalation_threshold:
            profile.profile_rotation_interval = max(
                1, profile.profile_rotation_interval // 2
            )

        # Adjust proxy switch urgency
        if event.detection_type == DetectionType.IP_BLOCK:
            profile.proxy_switch_urgency = 1.0
        elif event.detection_type in (
            DetectionType.WAF_BLOCK,
            DetectionType.BOT_DETECTION,
        ):
            profile.proxy_switch_urgency = min(
                profile.proxy_switch_urgency + 0.3, 1.0
            )
        elif event.detection_type == DetectionType.RATE_LIMIT:
            profile.proxy_switch_urgency = min(
                profile.proxy_switch_urgency + 0.1, 1.0
            )

        # Update threat level
        self._update_threat_level(profile)

        # Update WAF info
        if event.waf_vendor != WAFVendor.UNKNOWN:
            profile.waf_vendor = event.waf_vendor

    def update_on_success(self, profile: TargetProfile) -> None:
        """Update profile parameters after a successful request.

        Gradually decays security parameters toward baseline.
        """
        profile.total_requests += 1
        profile.consecutive_successes += 1
        profile.consecutive_failures = 0
        profile.last_seen = time.time()

        # Update detection rate EMA (0 for success)
        alpha = 0.1
        profile.detection_rate = (1 - alpha) * profile.detection_rate

        # Decay delay multiplier toward 1.0
        if profile.delay_multiplier > 1.0:
            profile.delay_multiplier = max(
                1.0,
                profile.delay_multiplier * self._recovery_rate,
            )

        # Recover profile rotation interval
        if profile.consecutive_successes >= self._escalation_threshold * 2:
            profile.profile_rotation_interval = min(
                profile.profile_rotation_interval + 1, 10
            )

        # Decay proxy switch urgency
        profile.proxy_switch_urgency = max(
            0.0,
            profile.proxy_switch_urgency * self._recovery_rate,
        )

        # Update threat level
        self._update_threat_level(profile)

    def _update_threat_level(self, profile: TargetProfile) -> None:
        """Update the target's assessed threat level."""
        rate = profile.detection_rate
        if rate >= 0.5:
            profile.threat_level = ThreatLevel.CRITICAL
        elif rate >= 0.3:
            profile.threat_level = ThreatLevel.HIGH
        elif rate >= 0.1:
            profile.threat_level = ThreatLevel.MEDIUM
        elif rate > 0.01:
            profile.threat_level = ThreatLevel.LOW
        else:
            profile.threat_level = ThreatLevel.NONE


# ============================================================================
# Target Stealth Manager (Cycles 97–100)
# ============================================================================


class TargetStealthManager:
    """Per-target stealth state manager.

    Maintains learned profiles for each target and provides
    adaptive stealth recommendations based on real-time feedback.

    Thread-safe for use across concurrent scan workers.
    """

    def __init__(
        self,
        *,
        detection_gain: float = 1.5,
        recovery_rate: float = 0.95,
        max_delay_multiplier: float = 10.0,
    ) -> None:
        self._profiles: dict[str, TargetProfile] = {}
        self._waf_detector = WAFDetector()
        self._controller = AdaptiveController(
            detection_gain=detection_gain,
            recovery_rate=recovery_rate,
            max_delay_multiplier=max_delay_multiplier,
        )
        self._lock = threading.Lock()
        self._total_detections = 0
        self._total_requests = 0

    def analyze_response(
        self,
        *,
        target: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        body: str = "",
        cookies: dict[str, str] | None = None,
        response_time_ms: float = 0.0,
    ) -> DetectionEvent | None:
        """Analyze an HTTP response for WAF/detection signals.

        Updates the target's learned profile and returns a
        DetectionEvent if detection was found.

        Args:
            target: Target domain.
            status_code: HTTP status code.
            headers: Response headers.
            body: Response body.
            cookies: Response cookies.
            response_time_ms: Response time in milliseconds.

        Returns:
            DetectionEvent if detection found, None otherwise.
        """
        profile = self._get_or_create_profile(target)

        # Run WAF detection
        waf_result = self._waf_detector.detect(
            status_code=status_code,
            headers=headers,
            body=body,
            cookies=cookies,
            target=target,
        )

        # Update response time
        if response_time_ms > 0:
            profile.update_response_time(response_time_ms)

        # Update WAF info if detected
        if waf_result.detected and waf_result.confidence > profile.waf_confidence:
            profile.waf_vendor = waf_result.vendor
            profile.waf_confidence = waf_result.confidence

        with self._lock:
            self._total_requests += 1

        # Create detection event if applicable
        if waf_result.detection_type != DetectionType.NONE:
            event = DetectionEvent(
                target=target,
                detection_type=waf_result.detection_type,
                waf_vendor=waf_result.vendor,
                status_code=status_code,
                response_time_ms=response_time_ms,
                request_count_at_event=profile.total_requests,
                description=str(waf_result),
            )
            self._controller.update_on_detection(profile, event)
            with self._lock:
                self._total_detections += 1
            return event

        # Successful response
        self._controller.update_on_success(profile)
        return None

    def get_delay_multiplier(self, target: str) -> float:
        """Get the current delay multiplier for a target.

        Returns:
            Multiplier (1.0 = normal, >1.0 = slower, <1.0 = faster).
        """
        profile = self._profiles.get(target)
        if profile is None:
            return 1.0
        return profile.delay_multiplier

    def get_target_profile(self, target: str) -> TargetProfile | None:
        """Get the learned profile for a target."""
        return self._profiles.get(target)

    def get_threat_level(self, target: str) -> ThreatLevel:
        """Get the assessed threat level for a target."""
        profile = self._profiles.get(target)
        if profile is None:
            return ThreatLevel.NONE
        return profile.threat_level

    def should_switch_proxy(self, target: str) -> bool:
        """Check if a proxy switch is recommended for this target."""
        profile = self._profiles.get(target)
        if profile is None:
            return False
        return profile.proxy_switch_urgency > 0.5

    def should_rotate_profile(self, target: str) -> bool:
        """Check if a fingerprint profile rotation is recommended."""
        profile = self._profiles.get(target)
        if profile is None:
            return False
        if profile.profile_rotation_interval <= 0:
            return True
        return (
            profile.total_requests % profile.profile_rotation_interval == 0
        )

    def get_all_targets(self) -> list[str]:
        """Return all tracked target domains."""
        return list(self._profiles.keys())

    def get_global_stats(self) -> dict[str, Any]:
        """Get global statistics across all targets."""
        with self._lock:
            profiles = list(self._profiles.values())
            total = self._total_requests
            detections = self._total_detections

        if not profiles:
            return {
                "total_targets": 0,
                "total_requests": total,
                "total_detections": detections,
                "global_detection_rate": 0.0,
            }

        threat_dist: dict[str, int] = {}
        waf_dist: dict[str, int] = {}
        for p in profiles:
            tl = p.threat_level.value
            threat_dist[tl] = threat_dist.get(tl, 0) + 1
            if p.waf_vendor != WAFVendor.UNKNOWN:
                wv = p.waf_vendor.value
                waf_dist[wv] = waf_dist.get(wv, 0) + 1

        return {
            "total_targets": len(profiles),
            "total_requests": total,
            "total_detections": detections,
            "global_detection_rate": (
                round(detections / total, 4) if total > 0 else 0.0
            ),
            "threat_distribution": threat_dist,
            "waf_distribution": waf_dist,
            "avg_delay_multiplier": round(
                sum(p.delay_multiplier for p in profiles) / len(profiles), 2
            ),
        }

    def reset(self) -> None:
        """Reset all state."""
        with self._lock:
            self._profiles.clear()
            self._total_detections = 0
            self._total_requests = 0

    def _get_or_create_profile(self, target: str) -> TargetProfile:
        """Get or create a profile for a target."""
        with self._lock:
            if target not in self._profiles:
                self._profiles[target] = TargetProfile(domain=target)
            return self._profiles[target]
