# -------------------------------------------------------------------------------
# Name:         stealth_scan_engine
# Purpose:      S-006 — Integration with scan_engine + module-level stealth awareness
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Stealth Scan Engine — SOTA S-006 (Cycles 101–120).

Bridges stealth subsystems (S-001 through S-005) into the scan engine
pipeline. Provides module-level stealth awareness so each module
automatically inherits and respects adaptive stealth settings.

Key components:

- :class:`StealthLevel` — Predefined stealth levels mapping to
  concrete configurations (NONE/LOW/MEDIUM/HIGH/MAXIMUM).
- :class:`StealthConfig` — Complete stealth configuration snapshot
  combining TLS fingerprint, request orchestration, adaptive
  feedback, and WAF-aware settings.
- :class:`ModuleStealthProfile` — Per-module stealth metadata
  (risk level, request intensity, typical targets, recommended limits).
- :class:`ModuleStealthRegistry` — Registry of module stealth profiles
  with categorisation and query support.
- :class:`StealthScanBridge` — Main bridge that injects stealth
  settings into ``ScanEngine`` configurations, producing
  stealth-aware scan configs automatically.
- :class:`StealthDashboardData` — Real-time dashboard-ready data
  aggregator for UI/CLI consumption.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.recon.stealth_scan_engine")


# ============================================================================
# Stealth Levels (Cycles 101–104)
# ============================================================================


class StealthLevel(Enum):
    """Predefined stealth levels."""
    NONE = "none"         # No stealth — maximum speed
    LOW = "low"           # Basic UA rotation + jitter
    MEDIUM = "medium"     # TLS rotation + timing profiles + domain throttle
    HIGH = "high"         # Full fingerprint evasion + session simulation
    MAXIMUM = "maximum"   # All stealth + proxy rotation + adaptive feedback


# Default configuration values for each stealth level
_STEALTH_LEVEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "none": {
        "ua_rotation": False,
        "header_randomization": False,
        "tls_fingerprint_rotation": False,
        "request_jitter": False,
        "timing_profile": "fast",
        "session_simulation": False,
        "proxy_rotation": False,
        "adaptive_feedback": False,
        "waf_detection": False,
        "domain_throttle": False,
        "fingerprint_grease": False,
        "max_requests_per_second": 0,
        "request_delay_ms": 0,
        "profile_rotation_interval": 0,
    },
    "low": {
        "ua_rotation": True,
        "header_randomization": True,
        "tls_fingerprint_rotation": False,
        "request_jitter": True,
        "timing_profile": "browsing",
        "session_simulation": False,
        "proxy_rotation": False,
        "adaptive_feedback": False,
        "waf_detection": False,
        "domain_throttle": True,
        "fingerprint_grease": False,
        "max_requests_per_second": 10,
        "request_delay_ms": 200,
        "profile_rotation_interval": 50,
    },
    "medium": {
        "ua_rotation": True,
        "header_randomization": True,
        "tls_fingerprint_rotation": True,
        "request_jitter": True,
        "timing_profile": "research",
        "session_simulation": False,
        "proxy_rotation": False,
        "adaptive_feedback": True,
        "waf_detection": True,
        "domain_throttle": True,
        "fingerprint_grease": True,
        "max_requests_per_second": 5,
        "request_delay_ms": 500,
        "profile_rotation_interval": 20,
    },
    "high": {
        "ua_rotation": True,
        "header_randomization": True,
        "tls_fingerprint_rotation": True,
        "request_jitter": True,
        "timing_profile": "cautious",
        "session_simulation": True,
        "proxy_rotation": True,
        "adaptive_feedback": True,
        "waf_detection": True,
        "domain_throttle": True,
        "fingerprint_grease": True,
        "max_requests_per_second": 2,
        "request_delay_ms": 2000,
        "profile_rotation_interval": 5,
    },
    "maximum": {
        "ua_rotation": True,
        "header_randomization": True,
        "tls_fingerprint_rotation": True,
        "request_jitter": True,
        "timing_profile": "paranoid",
        "session_simulation": True,
        "proxy_rotation": True,
        "adaptive_feedback": True,
        "waf_detection": True,
        "domain_throttle": True,
        "fingerprint_grease": True,
        "max_requests_per_second": 0.5,
        "request_delay_ms": 5000,
        "profile_rotation_interval": 1,
    },
}


def get_stealth_defaults(level: StealthLevel | str) -> dict[str, Any]:
    """Get default configuration for a stealth level.

    Args:
        level: StealthLevel enum or string name.

    Returns:
        Dict of configuration values.
    """
    if isinstance(level, StealthLevel):
        key = level.value
    else:
        key = str(level).lower()
    return dict(_STEALTH_LEVEL_DEFAULTS.get(key, _STEALTH_LEVEL_DEFAULTS["none"]))


# ============================================================================
# Stealth Configuration (Cycles 105–108)
# ============================================================================


@dataclass
class StealthConfig:
    """Complete stealth configuration for a scan.

    Combines settings from all stealth subsystems (S-001 to S-005)
    into a single snapshot that can be applied to a scan engine.
    """
    level: StealthLevel = StealthLevel.NONE

    # S-001: Basic stealth
    ua_rotation: bool = False
    header_randomization: bool = False
    request_jitter: bool = False

    # S-003: TLS fingerprint
    tls_fingerprint_rotation: bool = False
    fingerprint_grease: bool = False
    profile_rotation_interval: int = 0

    # S-004: Request orchestration
    timing_profile: str = "fast"
    session_simulation: bool = False
    max_requests_per_second: float = 0
    request_delay_ms: int = 0

    # S-005: Adaptive stealth
    adaptive_feedback: bool = False
    waf_detection: bool = False

    # Network stealth
    proxy_rotation: bool = False
    domain_throttle: bool = False

    @classmethod
    def from_level(cls, level: StealthLevel | str) -> StealthConfig:
        """Create a StealthConfig from a predefined level.

        Args:
            level: StealthLevel enum or string name.
        """
        if isinstance(level, str):
            level = StealthLevel(level.lower())
        defaults = get_stealth_defaults(level)
        return cls(level=level, **defaults)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StealthConfig:
        """Create from a dict (e.g. from API request or YAML)."""
        level_str = data.get("level", "none")
        try:
            level = StealthLevel(level_str.lower())
        except ValueError:
            level = StealthLevel.NONE

        return cls(
            level=level,
            ua_rotation=data.get("ua_rotation", False),
            header_randomization=data.get("header_randomization", False),
            request_jitter=data.get("request_jitter", False),
            tls_fingerprint_rotation=data.get("tls_fingerprint_rotation", False),
            fingerprint_grease=data.get("fingerprint_grease", False),
            profile_rotation_interval=data.get("profile_rotation_interval", 0),
            timing_profile=data.get("timing_profile", "fast"),
            session_simulation=data.get("session_simulation", False),
            max_requests_per_second=data.get("max_requests_per_second", 0),
            request_delay_ms=data.get("request_delay_ms", 0),
            adaptive_feedback=data.get("adaptive_feedback", False),
            waf_detection=data.get("waf_detection", False),
            proxy_rotation=data.get("proxy_rotation", False),
            domain_throttle=data.get("domain_throttle", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "level": self.level.value,
            "ua_rotation": self.ua_rotation,
            "header_randomization": self.header_randomization,
            "request_jitter": self.request_jitter,
            "tls_fingerprint_rotation": self.tls_fingerprint_rotation,
            "fingerprint_grease": self.fingerprint_grease,
            "profile_rotation_interval": self.profile_rotation_interval,
            "timing_profile": self.timing_profile,
            "session_simulation": self.session_simulation,
            "max_requests_per_second": self.max_requests_per_second,
            "request_delay_ms": self.request_delay_ms,
            "adaptive_feedback": self.adaptive_feedback,
            "waf_detection": self.waf_detection,
            "proxy_rotation": self.proxy_rotation,
            "domain_throttle": self.domain_throttle,
        }

    def is_active(self) -> bool:
        """Check if any stealth feature is active."""
        return self.level != StealthLevel.NONE


# ============================================================================
# Module Stealth Profiles (Cycles 109–112)
# ============================================================================


class ModuleRiskLevel(Enum):
    """How likely a module is to trigger detection."""
    PASSIVE = "passive"     # Pure OSINT, no direct target contact
    LOW = "low"             # DNS/WHOIS — unlikely to trigger
    MEDIUM = "medium"       # HTTP requests — may trigger rate limits
    HIGH = "high"           # Active scanning — likely to trigger
    AGGRESSIVE = "aggressive"  # Brute-force/fuzzing — will trigger


@dataclass
class ModuleStealthProfile:
    """Stealth metadata for a single module.

    Defines how a module interacts with targets and what
    stealth constraints should be applied.
    """
    module_name: str
    risk_level: ModuleRiskLevel = ModuleRiskLevel.MEDIUM

    # Request characteristics
    typical_requests_per_target: int = 10
    makes_http_requests: bool = True
    makes_dns_requests: bool = False
    uses_third_party_apis: bool = False

    # Stealth recommendations
    min_stealth_level: StealthLevel = StealthLevel.NONE
    recommended_delay_ms: int = 0
    max_concurrent_requests: int = 5
    supports_proxy: bool = True

    # Categorisation
    category: str = "general"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "module_name": self.module_name,
            "risk_level": self.risk_level.value,
            "typical_requests_per_target": self.typical_requests_per_target,
            "makes_http_requests": self.makes_http_requests,
            "makes_dns_requests": self.makes_dns_requests,
            "uses_third_party_apis": self.uses_third_party_apis,
            "min_stealth_level": self.min_stealth_level.value,
            "recommended_delay_ms": self.recommended_delay_ms,
            "max_concurrent_requests": self.max_concurrent_requests,
            "supports_proxy": self.supports_proxy,
            "category": self.category,
            "tags": self.tags,
        }


# Pre-built module profiles for common SpiderFoot modules
_DEFAULT_MODULE_PROFILES: list[ModuleStealthProfile] = [
    # Passive / OSINT
    ModuleStealthProfile("sfp_dnsresolve", ModuleRiskLevel.LOW, 5, False, True, False, StealthLevel.NONE, 0, 10, True, "dns", ["passive", "dns"]),
    ModuleStealthProfile("sfp_whois", ModuleRiskLevel.LOW, 2, True, False, True, StealthLevel.NONE, 100, 3, True, "osint", ["passive", "whois"]),
    ModuleStealthProfile("sfp_sslcert", ModuleRiskLevel.LOW, 3, True, False, False, StealthLevel.NONE, 0, 5, True, "crypto", ["passive", "ssl"]),

    # Low risk
    ModuleStealthProfile("sfp_hackertarget", ModuleRiskLevel.LOW, 5, True, False, True, StealthLevel.LOW, 500, 3, True, "osint", ["api", "passive"]),
    ModuleStealthProfile("sfp_ipinfo", ModuleRiskLevel.LOW, 2, True, False, True, StealthLevel.NONE, 200, 3, True, "osint", ["api", "passive"]),
    ModuleStealthProfile("sfp_dnsbrute", ModuleRiskLevel.MEDIUM, 100, False, True, False, StealthLevel.LOW, 50, 10, True, "dns", ["active", "brute"]),

    # Medium risk
    ModuleStealthProfile("sfp_spider", ModuleRiskLevel.MEDIUM, 50, True, False, False, StealthLevel.MEDIUM, 500, 5, True, "web", ["active", "crawl"]),
    ModuleStealthProfile("sfp_httpheaders", ModuleRiskLevel.MEDIUM, 10, True, False, False, StealthLevel.LOW, 200, 5, True, "web", ["active", "http"]),
    ModuleStealthProfile("sfp_webframework", ModuleRiskLevel.MEDIUM, 5, True, False, False, StealthLevel.LOW, 200, 5, True, "web", ["active", "fingerprint"]),
    ModuleStealthProfile("sfp_pageinfo", ModuleRiskLevel.MEDIUM, 20, True, False, False, StealthLevel.MEDIUM, 300, 5, True, "web", ["active", "content"]),

    # High risk
    ModuleStealthProfile("sfp_portscan_tcp", ModuleRiskLevel.HIGH, 1000, False, False, False, StealthLevel.HIGH, 100, 2, True, "network", ["active", "scan"]),
    ModuleStealthProfile("sfp_socialprofiles", ModuleRiskLevel.MEDIUM, 20, True, False, True, StealthLevel.MEDIUM, 1000, 3, True, "social", ["active", "osint"]),
]


class ModuleStealthRegistry:
    """Registry of module stealth profiles.

    Maps module names to their stealth metadata and provides
    query methods for batch stealth configuration.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ModuleStealthProfile] = {}
        self._lock = threading.Lock()
        # Load defaults
        for p in _DEFAULT_MODULE_PROFILES:
            self._profiles[p.module_name] = p

    def register(self, profile: ModuleStealthProfile) -> None:
        """Register a module stealth profile."""
        with self._lock:
            self._profiles[profile.module_name] = profile

    def get(self, module_name: str) -> ModuleStealthProfile | None:
        """Get stealth profile for a module."""
        return self._profiles.get(module_name)

    def get_or_default(self, module_name: str) -> ModuleStealthProfile:
        """Get stealth profile, creating a default if not registered."""
        p = self._profiles.get(module_name)
        if p is not None:
            return p
        return ModuleStealthProfile(module_name=module_name)

    def get_by_risk_level(self, risk_level: ModuleRiskLevel) -> list[ModuleStealthProfile]:
        """Get all modules with a specific risk level."""
        return [p for p in self._profiles.values() if p.risk_level == risk_level]

    def get_by_category(self, category: str) -> list[ModuleStealthProfile]:
        """Get all modules in a category."""
        return [p for p in self._profiles.values() if p.category == category]

    def get_high_risk_modules(self) -> list[str]:
        """Get module names that are HIGH or AGGRESSIVE risk."""
        return [
            p.module_name for p in self._profiles.values()
            if p.risk_level in (ModuleRiskLevel.HIGH, ModuleRiskLevel.AGGRESSIVE)
        ]

    def get_stealth_compatible(self, level: StealthLevel) -> list[str]:
        """Get modules compatible with a stealth level.

        Returns modules whose min_stealth_level is at or below
        the given level.
        """
        level_order = {
            StealthLevel.NONE: 0,
            StealthLevel.LOW: 1,
            StealthLevel.MEDIUM: 2,
            StealthLevel.HIGH: 3,
            StealthLevel.MAXIMUM: 4,
        }
        threshold = level_order.get(level, 0)
        return [
            p.module_name for p in self._profiles.values()
            if level_order.get(p.min_stealth_level, 0) <= threshold
        ]

    @property
    def module_count(self) -> int:
        return len(self._profiles)

    def all_profiles(self) -> list[ModuleStealthProfile]:
        """Return all registered profiles."""
        return list(self._profiles.values())

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Serialize all profiles."""
        return {name: p.to_dict() for name, p in self._profiles.items()}


# ============================================================================
# Stealth Scan Bridge (Cycles 113–116)
# ============================================================================


class StealthScanBridge:
    """Bridge between stealth subsystem and scan engine.

    Takes a ScanEngine config dict and injects stealth settings,
    producing a stealth-aware scan configuration.
    """

    def __init__(self, registry: ModuleStealthRegistry | None = None) -> None:
        self._registry = registry or ModuleStealthRegistry()

    def apply_stealth(
        self,
        scan_config: dict[str, Any],
        stealth: StealthConfig,
    ) -> dict[str, Any]:
        """Apply stealth configuration to a scan config.

        Merges stealth settings into the scan config dict,
        adjusting rate limits, module options, and threading.

        Args:
            scan_config: Base scan engine config (from ScanEngine.to_sf_config).
            stealth: Stealth configuration to apply.

        Returns:
            Modified scan config dict with stealth settings injected.
        """
        config = dict(scan_config)  # shallow copy

        if not stealth.is_active():
            config["_stealth"] = stealth.to_dict()
            return config

        # Rate limiting adjustments
        if stealth.max_requests_per_second > 0:
            config["_max_requests_per_second"] = stealth.max_requests_per_second

        if stealth.request_delay_ms > 0:
            config["_delay"] = max(
                config.get("_delay", 0),
                stealth.request_delay_ms,
            )

        # Thread reduction for higher stealth levels
        if stealth.level in (StealthLevel.HIGH, StealthLevel.MAXIMUM):
            current = config.get("_maxthreads", 10)
            config["_maxthreads"] = max(1, current // 2)

        # Feature flags
        config["_stealth_ua_rotation"] = stealth.ua_rotation
        config["_stealth_header_randomization"] = stealth.header_randomization
        config["_stealth_request_jitter"] = stealth.request_jitter
        config["_stealth_tls_rotation"] = stealth.tls_fingerprint_rotation
        config["_stealth_fingerprint_grease"] = stealth.fingerprint_grease
        config["_stealth_session_sim"] = stealth.session_simulation
        config["_stealth_proxy_rotation"] = stealth.proxy_rotation
        config["_stealth_domain_throttle"] = stealth.domain_throttle
        config["_stealth_adaptive"] = stealth.adaptive_feedback
        config["_stealth_waf_detect"] = stealth.waf_detection
        config["_stealth_timing_profile"] = stealth.timing_profile
        config["_stealth_rotation_interval"] = stealth.profile_rotation_interval

        # Full stealth config snapshot
        config["_stealth"] = stealth.to_dict()

        return config

    def apply_module_stealth(
        self,
        scan_config: dict[str, Any],
        modules: list[str],
        stealth: StealthConfig,
    ) -> dict[str, Any]:
        """Apply per-module stealth adjustments.

        For each module in the scan, looks up its stealth profile
        and applies appropriate constraints.

        Args:
            scan_config: Scan config dict.
            modules: List of module names in the scan.
            stealth: Global stealth config.

        Returns:
            Modified scan config with per-module stealth settings.
        """
        config = dict(scan_config)
        module_stealth: dict[str, dict[str, Any]] = {}

        for mod_name in modules:
            profile = self._registry.get_or_default(mod_name)
            mod_config: dict[str, Any] = {
                "risk_level": profile.risk_level.value,
                "max_concurrent": profile.max_concurrent_requests,
            }

            # Apply delay based on risk level and stealth config
            if stealth.is_active():
                base_delay = profile.recommended_delay_ms or stealth.request_delay_ms
                risk_multiplier = {
                    ModuleRiskLevel.PASSIVE: 0.5,
                    ModuleRiskLevel.LOW: 0.8,
                    ModuleRiskLevel.MEDIUM: 1.0,
                    ModuleRiskLevel.HIGH: 2.0,
                    ModuleRiskLevel.AGGRESSIVE: 3.0,
                }.get(profile.risk_level, 1.0)
                mod_config["delay_ms"] = int(base_delay * risk_multiplier)

                # Limit concurrency for high-risk modules
                if profile.risk_level in (ModuleRiskLevel.HIGH, ModuleRiskLevel.AGGRESSIVE):
                    mod_config["max_concurrent"] = min(
                        profile.max_concurrent_requests, 2
                    )

            module_stealth[mod_name] = mod_config

        config["_module_stealth"] = module_stealth
        return config

    def get_module_warnings(
        self,
        modules: list[str],
        stealth: StealthConfig,
    ) -> list[dict[str, str]]:
        """Get warnings about module/stealth incompatibilities.

        Args:
            modules: List of module names.
            stealth: Current stealth config.

        Returns:
            List of warning dicts with 'module', 'level', and 'message'.
        """
        warnings: list[dict[str, str]] = []
        level_order = {
            StealthLevel.NONE: 0,
            StealthLevel.LOW: 1,
            StealthLevel.MEDIUM: 2,
            StealthLevel.HIGH: 3,
            StealthLevel.MAXIMUM: 4,
        }
        current_level = level_order.get(stealth.level, 0)

        for mod_name in modules:
            profile = self._registry.get(mod_name)
            if profile is None:
                continue

            min_required = level_order.get(profile.min_stealth_level, 0)
            if min_required > current_level:
                warnings.append({
                    "module": mod_name,
                    "level": "warning",
                    "message": (
                        f"Module '{mod_name}' recommends stealth level "
                        f"'{profile.min_stealth_level.value}' but current is "
                        f"'{stealth.level.value}'"
                    ),
                })

            if profile.risk_level in (ModuleRiskLevel.HIGH, ModuleRiskLevel.AGGRESSIVE):
                if stealth.level == StealthLevel.MAXIMUM:
                    warnings.append({
                        "module": mod_name,
                        "level": "info",
                        "message": (
                            f"Module '{mod_name}' ({profile.risk_level.value} risk) "
                            f"may be slow under MAXIMUM stealth"
                        ),
                    })

        return warnings

    @property
    def registry(self) -> ModuleStealthRegistry:
        return self._registry


# ============================================================================
# Stealth Dashboard Data (Cycles 117–120)
# ============================================================================


@dataclass
class StealthDashboardData:
    """Real-time stealth dashboard data aggregator.

    Collects and formats stealth metrics for UI and CLI consumption.
    Thread-safe for concurrent access from scan workers.
    """
    # Global metrics
    active_stealth_level: str = "none"
    total_requests: int = 0
    total_detections: int = 0
    detection_rate: float = 0.0

    # Per-target stats
    targets: dict[str, dict[str, Any]] = field(default_factory=dict)

    # WAF distribution
    waf_distribution: dict[str, int] = field(default_factory=dict)

    # Timing
    avg_delay_ms: float = 0.0
    avg_response_time_ms: float = 0.0

    # Module risk distribution
    module_risk_distribution: dict[str, int] = field(default_factory=dict)

    # Active features
    active_features: list[str] = field(default_factory=list)

    # Timestamp
    collected_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/CLI output."""
        return {
            "active_stealth_level": self.active_stealth_level,
            "total_requests": self.total_requests,
            "total_detections": self.total_detections,
            "detection_rate": round(self.detection_rate, 4),
            "target_count": len(self.targets),
            "targets": self.targets,
            "waf_distribution": self.waf_distribution,
            "avg_delay_ms": round(self.avg_delay_ms, 1),
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "module_risk_distribution": self.module_risk_distribution,
            "active_features": self.active_features,
            "collected_at": self.collected_at,
        }


class StealthDashboardCollector:
    """Collects stealth metrics into dashboard-ready format.

    Pulls data from the stealth subsystems and the module
    registry to produce a unified StealthDashboardData snapshot.
    """

    def __init__(
        self,
        stealth_config: StealthConfig | None = None,
        registry: ModuleStealthRegistry | None = None,
    ) -> None:
        self._config = stealth_config or StealthConfig()
        self._registry = registry or ModuleStealthRegistry()
        self._lock = threading.Lock()
        self._request_count = 0
        self._detection_count = 0
        self._response_times: list[float] = []
        self._target_stats: dict[str, dict[str, Any]] = {}

    def record_request(
        self,
        target: str,
        response_time_ms: float = 0.0,
        detected: bool = False,
        waf_vendor: str = "",
    ) -> None:
        """Record a request for metrics."""
        with self._lock:
            self._request_count += 1
            if detected:
                self._detection_count += 1
            if response_time_ms > 0:
                self._response_times.append(response_time_ms)
                if len(self._response_times) > 1000:
                    self._response_times = self._response_times[-1000:]

            if target not in self._target_stats:
                self._target_stats[target] = {
                    "requests": 0,
                    "detections": 0,
                    "waf": "",
                }
            self._target_stats[target]["requests"] += 1
            if detected:
                self._target_stats[target]["detections"] += 1
            if waf_vendor:
                self._target_stats[target]["waf"] = waf_vendor

    def collect(self) -> StealthDashboardData:
        """Collect current dashboard data snapshot."""
        with self._lock:
            total_req = self._request_count
            total_det = self._detection_count
            resp_times = list(self._response_times)
            targets = dict(self._target_stats)

        # Active features
        features: list[str] = []
        cfg = self._config
        if cfg.ua_rotation:
            features.append("UA Rotation")
        if cfg.header_randomization:
            features.append("Header Randomization")
        if cfg.tls_fingerprint_rotation:
            features.append("TLS Fingerprint Rotation")
        if cfg.request_jitter:
            features.append("Request Jitter")
        if cfg.session_simulation:
            features.append("Session Simulation")
        if cfg.proxy_rotation:
            features.append("Proxy Rotation")
        if cfg.adaptive_feedback:
            features.append("Adaptive Feedback")
        if cfg.waf_detection:
            features.append("WAF Detection")
        if cfg.domain_throttle:
            features.append("Domain Throttle")

        # WAF distribution
        waf_dist: dict[str, int] = {}
        for tgt in targets.values():
            waf = tgt.get("waf", "")
            if waf:
                waf_dist[waf] = waf_dist.get(waf, 0) + 1

        # Module risk distribution
        risk_dist: dict[str, int] = {}
        for p in self._registry.all_profiles():
            rl = p.risk_level.value
            risk_dist[rl] = risk_dist.get(rl, 0) + 1

        return StealthDashboardData(
            active_stealth_level=cfg.level.value,
            total_requests=total_req,
            total_detections=total_det,
            detection_rate=total_det / total_req if total_req > 0 else 0.0,
            targets=targets,
            waf_distribution=waf_dist,
            avg_delay_ms=float(cfg.request_delay_ms),
            avg_response_time_ms=(
                sum(resp_times) / len(resp_times)
                if resp_times else 0.0
            ),
            module_risk_distribution=risk_dist,
            active_features=features,
        )

    def update_config(self, config: StealthConfig) -> None:
        """Update the stealth config used for dashboard data."""
        self._config = config

    def reset(self) -> None:
        """Reset all collected metrics."""
        with self._lock:
            self._request_count = 0
            self._detection_count = 0
            self._response_times.clear()
            self._target_stats.clear()
