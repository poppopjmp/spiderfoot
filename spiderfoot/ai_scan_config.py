"""
AI Scan Configuration — intelligent scan parameter recommendation.

Analyses a target (domain, IP, netblock, etc.) and recommends optimal
scan modules, depth, timing, and resource settings based on:
  - Target type and scope estimation
  - Scan objective (recon, vulnerability, full-audit, bug-bounty, osint)
  - Infrastructure constraints (rate limits, stealth, concurrency)
  - Historical scan performance data

v5.6.3
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

_log = logging.getLogger("spiderfoot.ai_scan_config")


# ── Enumerations ──────────────────────────────────────────────────────

class ScanObjective(str, Enum):
    RECON = "recon"
    VULNERABILITY = "vulnerability"
    FULL_AUDIT = "full_audit"
    BUG_BOUNTY = "bug_bounty"
    OSINT = "osint"
    QUICK_LOOK = "quick_look"
    SUBDOMAIN_ENUM = "subdomain_enum"
    DARK_WEB = "dark_web"


class TargetType(str, Enum):
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"
    NETBLOCK = "netblock"
    EMAIL = "email"
    USERNAME = "username"
    PHONE = "phone"
    BITCOIN_ADDRESS = "bitcoin_address"
    URL = "url"


class StealthLevel(str, Enum):
    NONE = "none"          # No stealth — maximum speed
    LOW = "low"            # Basic rate limiting
    MEDIUM = "medium"      # Spread requests, randomize timing
    HIGH = "high"          # Passive-only modules, minimal footprint
    PARANOID = "paranoid"  # Tor-routed, maximum delays


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class ModuleRecommendation:
    """A recommended module with confidence and reason."""
    module: str
    enabled: bool = True
    priority: int = 50  # 1-100, higher = more important
    reason: str = ""
    category: str = "general"


@dataclass
class TimingConfig:
    """Timing and rate-limit settings."""
    max_threads: int = 10
    delay_between_requests: float = 0.5
    max_requests_per_second: int = 20
    timeout_per_module: int = 300
    global_timeout: int = 3600
    retry_count: int = 2
    backoff_factor: float = 1.5


@dataclass
class ScanRecommendation:
    """Complete scan configuration recommendation."""
    recommendation_id: str = ""
    target: str = ""
    target_type: str = ""
    objective: str = ""
    stealth_level: str = "low"
    confidence: float = 0.0  # 0-1 overall confidence

    # Module recommendations
    modules: list[dict] = field(default_factory=list)
    module_count: int = 0

    # Timing
    timing: dict = field(default_factory=dict)

    # Scope
    max_depth: int = 3
    follow_redirects: bool = True
    include_subdomains: bool = True
    include_affiliates: bool = False

    # Estimated resources
    estimated_duration_minutes: int = 30
    estimated_events: int = 500
    estimated_api_calls: int = 100

    # Warnings and notes
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # Metadata
    created_at: float = 0.0
    engine_version: str = "1.0.0"


# ── Module knowledge base ────────────────────────────────────────────

# Categories of modules and their properties
MODULE_CATALOG = {
    # Core passive modules (safe, no direct target interaction)
    "sfp_dnsresolve": {"category": "dns", "passive": True, "targets": ["domain"], "speed": "fast",
                       "value_recon": 90, "value_vuln": 40, "value_osint": 60},
    "sfp_dnsbrute": {"category": "dns", "passive": False, "targets": ["domain"], "speed": "medium",
                     "value_recon": 85, "value_vuln": 30, "value_osint": 40},
    "sfp_dnszonexfer": {"category": "dns", "passive": False, "targets": ["domain"], "speed": "fast",
                        "value_recon": 70, "value_vuln": 60, "value_osint": 30},
    "sfp_whois": {"category": "whois", "passive": True, "targets": ["domain", "ip_address"], "speed": "fast",
                  "value_recon": 80, "value_vuln": 20, "value_osint": 85},
    "sfp_reversewhois": {"category": "whois", "passive": True, "targets": ["domain"], "speed": "medium",
                         "value_recon": 70, "value_vuln": 10, "value_osint": 75},
    "sfp_shodan": {"category": "search_engine", "passive": True, "targets": ["domain", "ip_address", "netblock"],
                   "speed": "fast", "value_recon": 90, "value_vuln": 85, "value_osint": 60, "api_key": True},
    "sfp_censys": {"category": "search_engine", "passive": True, "targets": ["domain", "ip_address"],
                   "speed": "fast", "value_recon": 85, "value_vuln": 80, "value_osint": 55, "api_key": True},
    "sfp_binaryedge": {"category": "search_engine", "passive": True, "targets": ["domain", "ip_address"],
                       "speed": "fast", "value_recon": 80, "value_vuln": 75, "value_osint": 50, "api_key": True},
    "sfp_virustotal": {"category": "threat_intel", "passive": True, "targets": ["domain", "ip_address"],
                       "speed": "fast", "value_recon": 75, "value_vuln": 70, "value_osint": 65, "api_key": True},
    "sfp_alienvaultoTX": {"category": "threat_intel", "passive": True, "targets": ["domain", "ip_address"],
                          "speed": "fast", "value_recon": 60, "value_vuln": 65, "value_osint": 55},
    "sfp_hunter": {"category": "email", "passive": True, "targets": ["domain"], "speed": "fast",
                   "value_recon": 70, "value_vuln": 10, "value_osint": 85, "api_key": True},
    "sfp_emailformat": {"category": "email", "passive": True, "targets": ["domain"], "speed": "fast",
                        "value_recon": 60, "value_vuln": 5, "value_osint": 75},
    "sfp_haveibeenpwned": {"category": "breach", "passive": True, "targets": ["email"], "speed": "fast",
                           "value_recon": 40, "value_vuln": 60, "value_osint": 80, "api_key": True},
    "sfp_leakix": {"category": "breach", "passive": True, "targets": ["domain", "ip_address"], "speed": "fast",
                   "value_recon": 55, "value_vuln": 75, "value_osint": 50, "api_key": True},
    "sfp_crt": {"category": "certificate", "passive": True, "targets": ["domain"], "speed": "fast",
                "value_recon": 85, "value_vuln": 30, "value_osint": 40},
    "sfp_sslcert": {"category": "certificate", "passive": False, "targets": ["domain", "ip_address"],
                    "speed": "fast", "value_recon": 70, "value_vuln": 50, "value_osint": 30},
    "sfp_spider": {"category": "web", "passive": False, "targets": ["domain", "url"], "speed": "slow",
                   "value_recon": 80, "value_vuln": 50, "value_osint": 40},
    "sfp_httpheaders": {"category": "web", "passive": False, "targets": ["domain", "url"], "speed": "fast",
                        "value_recon": 65, "value_vuln": 60, "value_osint": 20},
    "sfp_socialprofiles": {"category": "social", "passive": True, "targets": ["username", "email"],
                           "speed": "medium", "value_recon": 50, "value_vuln": 5, "value_osint": 90},
    "sfp_blockchain": {"category": "crypto", "passive": True, "targets": ["bitcoin_address"],
                       "speed": "fast", "value_recon": 30, "value_vuln": 10, "value_osint": 70},
    "sfp_github": {"category": "code", "passive": True, "targets": ["domain", "username"],
                   "speed": "medium", "value_recon": 65, "value_vuln": 55, "value_osint": 70, "api_key": True},
    "sfp_grep_app": {"category": "code", "passive": True, "targets": ["domain"], "speed": "medium",
                     "value_recon": 50, "value_vuln": 45, "value_osint": 35},
    "sfp_darkweb": {"category": "dark_web", "passive": True, "targets": ["domain", "email"],
                    "speed": "slow", "value_recon": 40, "value_vuln": 50, "value_osint": 70},
    "sfp_subdomain_takeover": {"category": "web", "passive": False, "targets": ["domain"],
                               "speed": "medium", "value_recon": 60, "value_vuln": 90, "value_osint": 10},
    "sfp_nuclei": {"category": "vuln_scanner", "passive": False, "targets": ["domain", "ip_address", "url"],
                   "speed": "slow", "value_recon": 30, "value_vuln": 95, "value_osint": 5},
    "sfp_nmap": {"category": "port_scanner", "passive": False, "targets": ["domain", "ip_address", "netblock"],
                 "speed": "slow", "value_recon": 85, "value_vuln": 70, "value_osint": 20},
    "sfp_httpx": {"category": "web", "passive": False, "targets": ["domain", "ip_address"],
                  "speed": "medium", "value_recon": 75, "value_vuln": 40, "value_osint": 15},
    "sfp_subfinder": {"category": "dns", "passive": True, "targets": ["domain"],
                      "speed": "fast", "value_recon": 90, "value_vuln": 20, "value_osint": 30},
    "sfp_bugbounty": {"category": "bounty", "passive": True, "targets": ["domain"],
                      "speed": "fast", "value_recon": 40, "value_vuln": 30, "value_osint": 20},
    "sfp_portscan_tcp": {"category": "port_scanner", "passive": False, "targets": ["domain", "ip_address"],
                         "speed": "slow", "value_recon": 75, "value_vuln": 60, "value_osint": 15},
    "sfp_tlsscan": {"category": "certificate", "passive": False, "targets": ["domain", "ip_address"],
                    "speed": "fast", "value_recon": 50, "value_vuln": 65, "value_osint": 10},
    "sfp_accounts": {"category": "social", "passive": True, "targets": ["username"],
                     "speed": "slow", "value_recon": 45, "value_vuln": 5, "value_osint": 85},
    "sfp_googlesearch": {"category": "search_engine", "passive": True, "targets": ["domain", "email", "username"],
                         "speed": "medium", "value_recon": 60, "value_vuln": 20, "value_osint": 55},
}

# Objective-to-module-value mapping key
OBJECTIVE_VALUE_KEY = {
    ScanObjective.RECON: "value_recon",
    ScanObjective.VULNERABILITY: "value_vuln",
    ScanObjective.FULL_AUDIT: None,  # average of all
    ScanObjective.BUG_BOUNTY: "value_vuln",
    ScanObjective.OSINT: "value_osint",
    ScanObjective.QUICK_LOOK: "value_recon",
    ScanObjective.SUBDOMAIN_ENUM: "value_recon",
    ScanObjective.DARK_WEB: "value_osint",
}

# Stealth profiles
STEALTH_PROFILES: dict[str, TimingConfig] = {
    StealthLevel.NONE: TimingConfig(
        max_threads=25, delay_between_requests=0.1,
        max_requests_per_second=50, timeout_per_module=600,
        global_timeout=7200, retry_count=3, backoff_factor=1.0,
    ),
    StealthLevel.LOW: TimingConfig(
        max_threads=10, delay_between_requests=0.5,
        max_requests_per_second=20, timeout_per_module=300,
        global_timeout=3600, retry_count=2, backoff_factor=1.5,
    ),
    StealthLevel.MEDIUM: TimingConfig(
        max_threads=5, delay_between_requests=1.5,
        max_requests_per_second=8, timeout_per_module=300,
        global_timeout=5400, retry_count=1, backoff_factor=2.0,
    ),
    StealthLevel.HIGH: TimingConfig(
        max_threads=2, delay_between_requests=3.0,
        max_requests_per_second=3, timeout_per_module=600,
        global_timeout=10800, retry_count=1, backoff_factor=3.0,
    ),
    StealthLevel.PARANOID: TimingConfig(
        max_threads=1, delay_between_requests=10.0,
        max_requests_per_second=1, timeout_per_module=900,
        global_timeout=21600, retry_count=0, backoff_factor=5.0,
    ),
}


class AIScanConfigurator:
    """Intelligent scan configuration recommender.

    Analyses a target and scan objective, then produces a complete
    scan configuration recommendation with module selections,
    timing, scope, and resource estimates.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._feedback_key = "sf:ai_config:feedback"

    # ── Public API ────────────────────────────────────────────────────

    def recommend(
        self,
        target: str,
        target_type: str | TargetType,
        objective: str | ScanObjective = ScanObjective.RECON,
        stealth: str | StealthLevel = StealthLevel.LOW,
        *,
        include_api_key_modules: bool = True,
        max_modules: int | None = None,
        exclude_modules: list[str] | None = None,
        prefer_modules: list[str] | None = None,
        scope_limit: str | None = None,
    ) -> ScanRecommendation:
        """Generate a scan configuration recommendation.

        Args:
            target: The scan target (domain, IP, etc.)
            target_type: Type of the target
            objective: Scan objective/goal
            stealth: Desired stealth level
            include_api_key_modules: Include modules requiring API keys
            max_modules: Maximum number of modules to enable
            exclude_modules: Modules to exclude from recommendation
            prefer_modules: Modules to prioritize (always include)
            scope_limit: Optional scope constraint (e.g. "target_only")

        Returns:
            ScanRecommendation with complete configuration
        """
        if isinstance(target_type, str):
            target_type = TargetType(target_type)
        if isinstance(objective, str):
            objective = ScanObjective(objective)
        if isinstance(stealth, str):
            stealth = StealthLevel(stealth)

        exclude = set(exclude_modules or [])
        prefer = set(prefer_modules or [])

        # Generate recommendation ID
        rec_id = hashlib.sha256(
            f"{target}:{target_type}:{objective}:{stealth}:{time.time()}".encode()
        ).hexdigest()[:16]

        # Select modules
        modules = self._select_modules(
            target_type, objective, stealth,
            include_api_key_modules, exclude, prefer,
        )

        # Apply max_modules cap
        if max_modules and len(modules) > max_modules:
            modules.sort(key=lambda m: m.priority, reverse=True)
            modules = modules[:max_modules]

        # Get timing config
        timing = STEALTH_PROFILES.get(stealth, STEALTH_PROFILES[StealthLevel.LOW])

        # Determine scope
        scope = self._determine_scope(target_type, objective, scope_limit)

        # Estimate resources
        estimates = self._estimate_resources(modules, timing, target_type)

        # Generate warnings
        warnings = self._generate_warnings(
            target, target_type, objective, stealth, modules
        )

        # Build notes
        notes = self._generate_notes(objective, stealth, modules)

        rec = ScanRecommendation(
            recommendation_id=rec_id,
            target=target,
            target_type=target_type.value,
            objective=objective.value,
            stealth_level=stealth.value,
            confidence=self._calculate_confidence(modules, objective),
            modules=[asdict(m) for m in modules],
            module_count=len(modules),
            timing=asdict(timing),
            max_depth=scope["max_depth"],
            follow_redirects=scope["follow_redirects"],
            include_subdomains=scope["include_subdomains"],
            include_affiliates=scope["include_affiliates"],
            estimated_duration_minutes=estimates["duration_minutes"],
            estimated_events=estimates["events"],
            estimated_api_calls=estimates["api_calls"],
            warnings=warnings,
            notes=notes,
            created_at=time.time(),
            engine_version="1.0.0",
        )

        # Cache recommendation
        self._cache_recommendation(rec)

        return rec

    def get_recommendation(self, rec_id: str) -> ScanRecommendation | None:
        """Retrieve a cached recommendation by ID."""
        if not self._redis:
            return None
        try:
            data = self._redis.get(f"sf:ai_config:rec:{rec_id}")
            if data:
                d = json.loads(data)
                return ScanRecommendation(**d)
        except Exception as e:
            _log.warning("Failed to retrieve recommendation %s: %s", rec_id, e)
        return None

    def submit_feedback(
        self,
        recommendation_id: str,
        rating: int,
        actual_duration_minutes: int | None = None,
        actual_events: int | None = None,
        notes: str = "",
    ) -> dict:
        """Submit feedback on a recommendation to improve future suggestions.

        Args:
            recommendation_id: The recommendation ID
            rating: 1-5 star rating
            actual_duration_minutes: How long the scan actually took
            actual_events: How many events were produced
            notes: Free-form feedback text

        Returns:
            Confirmation dict
        """
        rating = max(1, min(5, rating))
        feedback = {
            "recommendation_id": recommendation_id,
            "rating": rating,
            "actual_duration_minutes": actual_duration_minutes,
            "actual_events": actual_events,
            "notes": notes,
            "submitted_at": time.time(),
        }

        if self._redis:
            try:
                self._redis.lpush(self._feedback_key, json.dumps(feedback))
                self._redis.ltrim(self._feedback_key, 0, 999)  # Keep last 1000
            except Exception as e:
                _log.warning("Failed to store feedback: %s", e)

        _log.info("Feedback submitted for recommendation %s: rating=%d",
                  recommendation_id, rating)
        return {"status": "accepted", "recommendation_id": recommendation_id}

    def get_presets(self) -> list[dict]:
        """Return available scan objective presets with descriptions."""
        return [
            {
                "id": ScanObjective.QUICK_LOOK.value,
                "name": "Quick Look",
                "description": "Fast surface-level scan — DNS, WHOIS, certificate transparency. "
                               "Completes in minutes with minimal footprint.",
                "estimated_time": "5-10 minutes",
                "module_count": "8-12",
                "stealth": "low",
            },
            {
                "id": ScanObjective.RECON.value,
                "name": "Reconnaissance",
                "description": "Comprehensive passive and light-active reconnaissance. "
                               "Subdomain enumeration, WHOIS, DNS, certificates, search engines.",
                "estimated_time": "15-30 minutes",
                "module_count": "15-25",
                "stealth": "low",
            },
            {
                "id": ScanObjective.VULNERABILITY.value,
                "name": "Vulnerability Assessment",
                "description": "Active vulnerability scanning with Nuclei, Nmap, port scanning, "
                               "and technology fingerprinting.",
                "estimated_time": "30-60 minutes",
                "module_count": "20-30",
                "stealth": "none",
            },
            {
                "id": ScanObjective.FULL_AUDIT.value,
                "name": "Full Security Audit",
                "description": "Complete audit: recon + vuln assessment + OSINT + threat intel. "
                               "Maximum coverage with all available modules.",
                "estimated_time": "60-120 minutes",
                "module_count": "30+",
                "stealth": "none",
            },
            {
                "id": ScanObjective.BUG_BOUNTY.value,
                "name": "Bug Bounty",
                "description": "Optimized for bug bounty hunting — subdomain enum, takeover checks, "
                               "vulnerability scanning, and scope-aware filtering.",
                "estimated_time": "30-60 minutes",
                "module_count": "20-28",
                "stealth": "low",
            },
            {
                "id": ScanObjective.OSINT.value,
                "name": "OSINT Investigation",
                "description": "People and entity investigation — social profiles, breach data, "
                               "email intelligence, dark web mentions.",
                "estimated_time": "15-30 minutes",
                "module_count": "15-20",
                "stealth": "medium",
            },
            {
                "id": ScanObjective.SUBDOMAIN_ENUM.value,
                "name": "Subdomain Enumeration",
                "description": "Focused subdomain discovery using all available techniques — "
                               "CT logs, DNS brute, subfinder, search engines.",
                "estimated_time": "10-20 minutes",
                "module_count": "10-15",
                "stealth": "low",
            },
            {
                "id": ScanObjective.DARK_WEB.value,
                "name": "Dark Web Intel",
                "description": "Dark web and breach monitoring — paste sites, leak databases, "
                               "Tor hidden services, credential exposures.",
                "estimated_time": "15-30 minutes",
                "module_count": "10-15",
                "stealth": "high",
            },
        ]

    def get_target_types(self) -> list[dict]:
        """Return supported target types with descriptions."""
        return [
            {"id": t.value, "name": t.value.replace("_", " ").title(),
             "description": f"Scan target of type: {t.value}"}
            for t in TargetType
        ]

    def get_stealth_levels(self) -> list[dict]:
        """Return stealth levels with timing details."""
        result = []
        for level in StealthLevel:
            tc = STEALTH_PROFILES[level]
            result.append({
                "id": level.value,
                "name": level.value.title(),
                "description": self._stealth_description(level),
                "timing": asdict(tc),
            })
        return result

    def get_module_catalog(self) -> list[dict]:
        """Return the full module catalog with metadata."""
        result = []
        for name, meta in MODULE_CATALOG.items():
            result.append({
                "module": name,
                "category": meta["category"],
                "passive": meta["passive"],
                "targets": meta["targets"],
                "speed": meta["speed"],
                "requires_api_key": meta.get("api_key", False),
                "value_recon": meta.get("value_recon", 0),
                "value_vuln": meta.get("value_vuln", 0),
                "value_osint": meta.get("value_osint", 0),
            })
        return result

    # ── Private helpers ───────────────────────────────────────────────

    def _select_modules(
        self,
        target_type: TargetType,
        objective: ScanObjective,
        stealth: StealthLevel,
        include_api_key: bool,
        exclude: set[str],
        prefer: set[str],
    ) -> list[ModuleRecommendation]:
        """Select and score modules based on target, objective, and stealth."""
        value_key = OBJECTIVE_VALUE_KEY.get(objective)
        recommendations = []

        for name, meta in MODULE_CATALOG.items():
            if name in exclude:
                continue
            if not include_api_key and meta.get("api_key"):
                continue
            if target_type.value not in meta["targets"]:
                continue

            # Skip active modules in high/paranoid stealth
            if stealth in (StealthLevel.HIGH, StealthLevel.PARANOID) and not meta["passive"]:
                continue

            # Calculate priority score
            if value_key:
                priority = meta.get(value_key, 50)
            else:
                # Full audit: average of all values
                priority = (
                    meta.get("value_recon", 0) +
                    meta.get("value_vuln", 0) +
                    meta.get("value_osint", 0)
                ) // 3

            # Boost preferred modules
            if name in prefer:
                priority = min(100, priority + 20)

            # Objective-specific adjustments
            priority = self._adjust_for_objective(name, meta, objective, priority)

            # Build reason
            reason = self._build_reason(name, meta, objective, target_type, priority)

            # Minimum threshold
            if priority < 20 and name not in prefer:
                continue

            recommendations.append(ModuleRecommendation(
                module=name,
                enabled=True,
                priority=priority,
                reason=reason,
                category=meta["category"],
            ))

        recommendations.sort(key=lambda r: r.priority, reverse=True)
        return recommendations

    def _adjust_for_objective(
        self, name: str, meta: dict,
        objective: ScanObjective, base_priority: int,
    ) -> int:
        """Apply objective-specific priority adjustments."""
        p = base_priority

        if objective == ScanObjective.SUBDOMAIN_ENUM:
            if meta["category"] in ("dns", "certificate"):
                p = min(100, p + 15)
            elif meta["category"] not in ("search_engine",):
                p = max(10, p - 20)

        elif objective == ScanObjective.BUG_BOUNTY:
            if name in ("sfp_subdomain_takeover", "sfp_nuclei", "sfp_httpx"):
                p = min(100, p + 15)
            if name == "sfp_bugbounty":
                p = 95  # Always high for bug bounty

        elif objective == ScanObjective.DARK_WEB:
            if meta["category"] in ("dark_web", "breach"):
                p = min(100, p + 20)
            elif meta["category"] in ("port_scanner", "vuln_scanner"):
                p = max(5, p - 30)

        elif objective == ScanObjective.QUICK_LOOK:
            if meta["speed"] == "slow":
                p = max(10, p - 30)
            if meta["speed"] == "fast":
                p = min(100, p + 10)

        return p

    def _build_reason(
        self, name: str, meta: dict,
        objective: ScanObjective, target_type: TargetType,
        priority: int,
    ) -> str:
        """Build a human-readable reason for a module recommendation."""
        parts = []
        if priority >= 80:
            parts.append("Highly recommended")
        elif priority >= 60:
            parts.append("Recommended")
        else:
            parts.append("Optional")

        parts.append(f"for {objective.value} scans")

        if meta["passive"]:
            parts.append("(passive, no direct target interaction)")
        else:
            parts.append("(active, interacts with target)")

        if meta.get("api_key"):
            parts.append("— requires API key")

        return " ".join(parts)

    def _determine_scope(
        self, target_type: TargetType,
        objective: ScanObjective,
        scope_limit: str | None,
    ) -> dict:
        """Determine scan scope parameters."""
        scope = {
            "max_depth": 3,
            "follow_redirects": True,
            "include_subdomains": target_type == TargetType.DOMAIN,
            "include_affiliates": False,
        }

        if objective == ScanObjective.QUICK_LOOK:
            scope["max_depth"] = 1
            scope["include_subdomains"] = False
        elif objective == ScanObjective.FULL_AUDIT:
            scope["max_depth"] = 5
            scope["include_affiliates"] = True
        elif objective == ScanObjective.SUBDOMAIN_ENUM:
            scope["max_depth"] = 2
            scope["include_subdomains"] = True
        elif objective == ScanObjective.BUG_BOUNTY:
            scope["max_depth"] = 4
            scope["include_subdomains"] = True

        if scope_limit == "target_only":
            scope["max_depth"] = 1
            scope["include_subdomains"] = False
            scope["include_affiliates"] = False

        return scope

    def _estimate_resources(
        self, modules: list[ModuleRecommendation],
        timing: TimingConfig, target_type: TargetType,
    ) -> dict:
        """Estimate scan duration, events, and API calls."""
        speed_minutes = {"fast": 2, "medium": 8, "slow": 20}
        total_minutes = 0
        total_api_calls = 0
        total_events = 0

        for mod in modules:
            meta = MODULE_CATALOG.get(mod.module, {})
            speed = meta.get("speed", "medium")
            total_minutes += speed_minutes.get(speed, 8)
            if meta.get("api_key"):
                total_api_calls += 10
            total_events += 15 + (mod.priority // 5)

        # Adjust for parallelism
        parallelism = max(1, timing.max_threads // 2)
        effective_minutes = max(5, total_minutes // parallelism)

        # Adjust for delay overhead
        delay_overhead = timing.delay_between_requests * len(modules)
        effective_minutes += int(delay_overhead / 60)

        # Netblocks take longer
        if target_type == TargetType.NETBLOCK:
            effective_minutes *= 3
            total_events *= 5

        return {
            "duration_minutes": effective_minutes,
            "events": total_events,
            "api_calls": total_api_calls,
        }

    def _generate_warnings(
        self, target: str, target_type: TargetType,
        objective: ScanObjective, stealth: StealthLevel,
        modules: list[ModuleRecommendation],
    ) -> list[str]:
        """Generate warnings for the scan configuration."""
        warnings = []

        # Active scanning warnings
        active_mods = [m for m in modules if not MODULE_CATALOG.get(m.module, {}).get("passive", True)]
        if active_mods and stealth == StealthLevel.NONE:
            warnings.append(
                f"{len(active_mods)} active module(s) will directly interact with the target. "
                "Ensure you have authorization to scan."
            )

        # Netblock warning
        if target_type == TargetType.NETBLOCK:
            warnings.append(
                "Scanning a netblock can affect many hosts. Ensure the entire "
                "range is within scope and consider rate limiting."
            )

        # Vuln scanner warning
        vuln_mods = [m for m in modules if MODULE_CATALOG.get(m.module, {}).get("category") == "vuln_scanner"]
        if vuln_mods:
            warnings.append(
                "Vulnerability scanning modules (Nuclei) are enabled. These send "
                "exploit-like payloads — only use with explicit authorization."
            )

        # API key modules without keys
        api_mods = [m for m in modules if MODULE_CATALOG.get(m.module, {}).get("api_key")]
        if api_mods:
            warnings.append(
                f"{len(api_mods)} module(s) require API keys. Configure them in "
                "Settings → Module Configuration for best results."
            )

        # Low stealth with many modules
        if stealth == StealthLevel.NONE and len(modules) > 20:
            warnings.append(
                "Running 20+ modules with no stealth may trigger rate limiting "
                "or blocking by the target. Consider increasing stealth level."
            )

        return warnings

    def _generate_notes(
        self, objective: ScanObjective, stealth: StealthLevel,
        modules: list[ModuleRecommendation],
    ) -> list[str]:
        """Generate helpful notes for the recommendation."""
        notes = []

        passive_count = sum(1 for m in modules if MODULE_CATALOG.get(m.module, {}).get("passive", True))
        active_count = len(modules) - passive_count

        notes.append(f"{len(modules)} modules selected: {passive_count} passive, {active_count} active")

        if objective == ScanObjective.BUG_BOUNTY:
            notes.append(
                "Bug bounty mode: results will be optimized for actionable findings. "
                "Check bug bounty program scope before scanning."
            )

        if stealth in (StealthLevel.HIGH, StealthLevel.PARANOID):
            notes.append(
                "High stealth mode: only passive modules are enabled. "
                "Results will be limited to publicly available information."
            )

        if objective == ScanObjective.FULL_AUDIT:
            notes.append(
                "Full audit mode: maximum module coverage enabled. "
                "This may take significantly longer but provides comprehensive results."
            )

        return notes

    def _calculate_confidence(
        self, modules: list[ModuleRecommendation],
        objective: ScanObjective,
    ) -> float:
        """Calculate overall confidence score (0-1) for the recommendation."""
        if not modules:
            return 0.0

        avg_priority = sum(m.priority for m in modules) / len(modules)
        module_count_factor = min(1.0, len(modules) / 15)  # diminishing returns
        diversity = len(set(m.category for m in modules)) / 10  # category coverage

        confidence = (avg_priority / 100 * 0.4) + (module_count_factor * 0.3) + (min(1.0, diversity) * 0.3)
        return round(min(1.0, confidence), 3)

    def _cache_recommendation(self, rec: ScanRecommendation) -> None:
        """Cache a recommendation in Redis (TTL 1 hour)."""
        if not self._redis:
            return
        try:
            self._redis.setex(
                f"sf:ai_config:rec:{rec.recommendation_id}",
                3600,
                json.dumps(asdict(rec)),
            )
        except Exception as e:
            _log.warning("Failed to cache recommendation: %s", e)

    @staticmethod
    def _stealth_description(level: StealthLevel) -> str:
        """Human-readable stealth level description."""
        return {
            StealthLevel.NONE: "No stealth — maximum speed, all modules enabled",
            StealthLevel.LOW: "Basic rate limiting — minor delays between requests",
            StealthLevel.MEDIUM: "Moderate stealth — spread requests, reduced concurrency",
            StealthLevel.HIGH: "High stealth — passive-only modules, minimal footprint",
            StealthLevel.PARANOID: "Maximum stealth — single thread, large delays, passive only",
        }[level]
