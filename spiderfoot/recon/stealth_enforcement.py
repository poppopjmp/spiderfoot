# -------------------------------------------------------------------------------
# Name:         stealth_enforcement
# Purpose:      S-009 — Full stealth profile enforcement across all modules
#
# Author:       Agostino Panico @poppopjmp
#
# Created:      2026-02-28
# Copyright:    (c) Agostino Panico 2026
# Licence:      MIT
# -------------------------------------------------------------------------------
"""Stealth Profile Enforcement Engine — SOTA S-009 (Cycles 161–180).

Ensures every module in the SpiderFoot ecosystem adheres to the
configured stealth profile before, during, and after execution.
Provides enforcement policies, violation tracking, remediation
actions, and audit logging.

Components
----------
- :class:`EnforcementMode` — Enum for enforcement strictness.
- :class:`ViolationType` — Enum for types of stealth violations.
- :class:`StealthViolation` — A recorded violation event.
- :class:`EnforcementPolicy` — Per-module or global policy.
- :class:`ModuleEnforcementState` — Runtime enforcement state per module.
- :class:`RemediationAction` — Actions to take on violations.
- :class:`StealthAuditor` — Audits module behaviour against policies.
- :class:`StealthEnforcementEngine` — Façade for the enforcement system.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.recon.stealth_enforcement")


# ============================================================================
# Enums (Cycles 161–163)
# ============================================================================


class EnforcementMode(Enum):
    """How strictly stealth profiles are enforced."""
    DISABLED = "disabled"     # No enforcement
    ADVISORY = "advisory"     # Log violations but allow execution
    MODERATE = "moderate"     # Block high-risk violations, warn others
    STRICT = "strict"         # Block all violations
    PARANOID = "paranoid"     # Block + quarantine violating modules


class ViolationType(Enum):
    """Categories of stealth violations."""
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    USER_AGENT_LEAKED = "user_agent_leaked"
    TLS_FINGERPRINT_STATIC = "tls_fingerprint_static"
    DNS_PLAINTEXT = "dns_plaintext"
    NO_PROXY_ROTATION = "no_proxy_rotation"
    HEADER_MISMATCH = "header_mismatch"
    REQUEST_PATTERN_DETECTED = "request_pattern_detected"
    TIMING_TOO_REGULAR = "timing_too_regular"
    SESSION_REUSE = "session_reuse"
    GEOLOCATION_MISMATCH = "geolocation_mismatch"
    CERTIFICATE_LEAK = "certificate_leak"
    DIRECT_IP_EXPOSURE = "direct_ip_exposure"
    MISSING_JITTER = "missing_jitter"
    SEQUENTIAL_SCAN = "sequential_scan"
    WAF_DETECTION_IGNORED = "waf_detection_ignored"


class Severity(Enum):
    """Severity of a stealth violation."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class RemediationActionType(Enum):
    """Types of remediation actions."""
    LOG_ONLY = "log_only"
    WARN_USER = "warn_user"
    THROTTLE = "throttle"
    RETRY_WITH_STEALTH = "retry_with_stealth"
    BLOCK_REQUEST = "block_request"
    ROTATE_IDENTITY = "rotate_identity"
    QUARANTINE_MODULE = "quarantine_module"
    PAUSE_SCAN = "pause_scan"


# ============================================================================
# Violation severity mapping
# ============================================================================

_VIOLATION_SEVERITY: dict[ViolationType, Severity] = {
    ViolationType.RATE_LIMIT_EXCEEDED: Severity.HIGH,
    ViolationType.USER_AGENT_LEAKED: Severity.WARNING,
    ViolationType.TLS_FINGERPRINT_STATIC: Severity.WARNING,
    ViolationType.DNS_PLAINTEXT: Severity.HIGH,
    ViolationType.NO_PROXY_ROTATION: Severity.WARNING,
    ViolationType.HEADER_MISMATCH: Severity.INFO,
    ViolationType.REQUEST_PATTERN_DETECTED: Severity.HIGH,
    ViolationType.TIMING_TOO_REGULAR: Severity.WARNING,
    ViolationType.SESSION_REUSE: Severity.INFO,
    ViolationType.GEOLOCATION_MISMATCH: Severity.WARNING,
    ViolationType.CERTIFICATE_LEAK: Severity.CRITICAL,
    ViolationType.DIRECT_IP_EXPOSURE: Severity.CRITICAL,
    ViolationType.MISSING_JITTER: Severity.INFO,
    ViolationType.SEQUENTIAL_SCAN: Severity.WARNING,
    ViolationType.WAF_DETECTION_IGNORED: Severity.HIGH,
}


def get_violation_severity(vtype: ViolationType) -> Severity:
    """Get default severity for a violation type."""
    return _VIOLATION_SEVERITY.get(vtype, Severity.WARNING)


# ============================================================================
# Data classes (Cycles 163–166)
# ============================================================================


@dataclass
class StealthViolation:
    """A recorded stealth policy violation."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    violation_type: ViolationType = ViolationType.HEADER_MISMATCH
    severity: Severity = Severity.INFO
    module_name: str = ""
    scan_id: str = ""
    target: str = ""
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    remediation_applied: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "module_name": self.module_name,
            "scan_id": self.scan_id,
            "target": self.target,
            "description": self.description,
            "details": self.details,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "remediation_applied": self.remediation_applied,
        }


@dataclass
class RemediationAction:
    """An action to take when a violation is detected."""
    action_type: RemediationActionType
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "description": self.description,
            "parameters": self.parameters,
        }


# ============================================================================
# Enforcement Policy (Cycles 166–169)
# ============================================================================


@dataclass
class EnforcementPolicy:
    """Stealth enforcement policy for a module or globally.

    Defines which violations to check, severity thresholds,
    and remediation actions.
    """
    name: str = "default"
    mode: EnforcementMode = EnforcementMode.MODERATE
    check_rate_limits: bool = True
    check_user_agent: bool = True
    check_tls_fingerprint: bool = True
    check_dns_encryption: bool = True
    check_proxy_rotation: bool = True
    check_request_patterns: bool = True
    check_timing_regularity: bool = True
    check_session_reuse: bool = True
    check_geolocation: bool = False
    check_waf_compliance: bool = True
    max_violations_before_block: int = 5
    violation_window_seconds: float = 300.0  # 5 minutes
    auto_remediate: bool = True
    quarantine_on_critical: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mode": self.mode.value,
            "check_rate_limits": self.check_rate_limits,
            "check_user_agent": self.check_user_agent,
            "check_tls_fingerprint": self.check_tls_fingerprint,
            "check_dns_encryption": self.check_dns_encryption,
            "check_proxy_rotation": self.check_proxy_rotation,
            "check_request_patterns": self.check_request_patterns,
            "check_timing_regularity": self.check_timing_regularity,
            "check_session_reuse": self.check_session_reuse,
            "check_geolocation": self.check_geolocation,
            "check_waf_compliance": self.check_waf_compliance,
            "max_violations_before_block": self.max_violations_before_block,
            "violation_window_seconds": self.violation_window_seconds,
            "auto_remediate": self.auto_remediate,
            "quarantine_on_critical": self.quarantine_on_critical,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnforcementPolicy:
        mode = data.get("mode", "moderate")
        return cls(
            name=data.get("name", "default"),
            mode=EnforcementMode(mode) if isinstance(mode, str) else mode,
            check_rate_limits=data.get("check_rate_limits", True),
            check_user_agent=data.get("check_user_agent", True),
            check_tls_fingerprint=data.get("check_tls_fingerprint", True),
            check_dns_encryption=data.get("check_dns_encryption", True),
            check_proxy_rotation=data.get("check_proxy_rotation", True),
            check_request_patterns=data.get("check_request_patterns", True),
            check_timing_regularity=data.get("check_timing_regularity", True),
            check_session_reuse=data.get("check_session_reuse", True),
            check_geolocation=data.get("check_geolocation", False),
            check_waf_compliance=data.get("check_waf_compliance", True),
            max_violations_before_block=data.get("max_violations_before_block", 5),
            violation_window_seconds=data.get("violation_window_seconds", 300.0),
            auto_remediate=data.get("auto_remediate", True),
            quarantine_on_critical=data.get("quarantine_on_critical", True),
        )

    @classmethod
    def for_mode(cls, mode: EnforcementMode) -> EnforcementPolicy:
        """Create a policy pre-tuned for a given mode."""
        base = cls(name=mode.value, mode=mode)
        if mode == EnforcementMode.DISABLED:
            for attr in dir(base):
                if attr.startswith("check_"):
                    setattr(base, attr, False)
            base.auto_remediate = False
        elif mode == EnforcementMode.ADVISORY:
            base.max_violations_before_block = 999
            base.quarantine_on_critical = False
        elif mode == EnforcementMode.STRICT:
            base.max_violations_before_block = 2
            base.check_geolocation = True
        elif mode == EnforcementMode.PARANOID:
            base.max_violations_before_block = 1
            base.check_geolocation = True
            base.quarantine_on_critical = True
        return base


# ============================================================================
# Pre-built enforcement policies by stealth level
# ============================================================================

_DEFAULT_POLICIES: dict[str, EnforcementPolicy] = {
    "none": EnforcementPolicy.for_mode(EnforcementMode.DISABLED),
    "low": EnforcementPolicy.for_mode(EnforcementMode.ADVISORY),
    "medium": EnforcementPolicy.for_mode(EnforcementMode.MODERATE),
    "high": EnforcementPolicy.for_mode(EnforcementMode.STRICT),
    "maximum": EnforcementPolicy.for_mode(EnforcementMode.PARANOID),
}


def get_policy_for_level(level: str) -> EnforcementPolicy:
    """Get the default enforcement policy for a stealth level."""
    return _DEFAULT_POLICIES.get(
        level.lower(),
        _DEFAULT_POLICIES["medium"],
    )


# ============================================================================
# Module Enforcement State (Cycles 169–172)
# ============================================================================


@dataclass
class ModuleEnforcementState:
    """Runtime enforcement state for a single module."""
    module_name: str
    policy: EnforcementPolicy = field(default_factory=EnforcementPolicy)
    violations: list[StealthViolation] = field(default_factory=list)
    is_quarantined: bool = False
    is_paused: bool = False
    total_requests: int = 0
    blocked_requests: int = 0
    last_check_time: float = field(default_factory=time.time)

    @property
    def recent_violations(self) -> list[StealthViolation]:
        """Violations within the current window."""
        cutoff = time.time() - self.policy.violation_window_seconds
        return [v for v in self.violations if v.timestamp >= cutoff]

    @property
    def should_block(self) -> bool:
        """Whether the module should be blocked based on violations."""
        if self.policy.mode == EnforcementMode.DISABLED:
            return False
        if self.is_quarantined:
            return True
        if self.policy.mode in (EnforcementMode.STRICT, EnforcementMode.PARANOID):
            recent = self.recent_violations
            if len(recent) >= self.policy.max_violations_before_block:
                return True
            # Critical violations in paranoid mode → immediate block
            if self.policy.mode == EnforcementMode.PARANOID:
                if any(v.severity == Severity.CRITICAL for v in recent):
                    return True
        return False

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def compliance_rate(self) -> float:
        """Percentage of requests that passed without violation."""
        if self.total_requests == 0:
            return 1.0
        return 1.0 - (self.blocked_requests / self.total_requests)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_name": self.module_name,
            "policy": self.policy.name,
            "mode": self.policy.mode.value,
            "is_quarantined": self.is_quarantined,
            "is_paused": self.is_paused,
            "total_requests": self.total_requests,
            "blocked_requests": self.blocked_requests,
            "violation_count": self.violation_count,
            "recent_violation_count": len(self.recent_violations),
            "compliance_rate": round(self.compliance_rate, 4),
            "should_block": self.should_block,
        }


# ============================================================================
# Stealth Auditor (Cycles 172–176)
# ============================================================================


class StealthAuditor:
    """Audits module behaviour against stealth policies.

    Performs rule-based checks on module actions and produces
    violation records.
    """

    def __init__(self) -> None:
        self._rules: list[dict[str, Any]] = self._build_default_rules()

    def _build_default_rules(self) -> list[dict[str, Any]]:
        """Build the default audit rules."""
        return [
            {
                "id": "rate_limit",
                "check": "check_rate_limits",
                "violation_type": ViolationType.RATE_LIMIT_EXCEEDED,
                "description": "Module exceeds configured request rate limit",
            },
            {
                "id": "user_agent",
                "check": "check_user_agent",
                "violation_type": ViolationType.USER_AGENT_LEAKED,
                "description": "Module uses default or identifiable user agent",
            },
            {
                "id": "tls_fp",
                "check": "check_tls_fingerprint",
                "violation_type": ViolationType.TLS_FINGERPRINT_STATIC,
                "description": "Module uses static TLS fingerprint",
            },
            {
                "id": "dns_enc",
                "check": "check_dns_encryption",
                "violation_type": ViolationType.DNS_PLAINTEXT,
                "description": "Module makes plaintext DNS queries",
            },
            {
                "id": "proxy_rot",
                "check": "check_proxy_rotation",
                "violation_type": ViolationType.NO_PROXY_ROTATION,
                "description": "Module does not rotate proxies",
            },
            {
                "id": "req_pattern",
                "check": "check_request_patterns",
                "violation_type": ViolationType.REQUEST_PATTERN_DETECTED,
                "description": "Detectable request pattern identified",
            },
            {
                "id": "timing",
                "check": "check_timing_regularity",
                "violation_type": ViolationType.TIMING_TOO_REGULAR,
                "description": "Request timing is too regular (no jitter)",
            },
            {
                "id": "session",
                "check": "check_session_reuse",
                "violation_type": ViolationType.SESSION_REUSE,
                "description": "Session or connection is reused excessively",
            },
            {
                "id": "geo",
                "check": "check_geolocation",
                "violation_type": ViolationType.GEOLOCATION_MISMATCH,
                "description": "Request geolocation doesn't match proxy location",
            },
            {
                "id": "waf",
                "check": "check_waf_compliance",
                "violation_type": ViolationType.WAF_DETECTION_IGNORED,
                "description": "Module ignores WAF detection signals",
            },
        ]

    @property
    def rules(self) -> list[dict[str, Any]]:
        return list(self._rules)

    def audit_module(
        self,
        module_name: str,
        policy: EnforcementPolicy,
        context: dict[str, Any] | None = None,
    ) -> list[StealthViolation]:
        """Run all applicable audit rules against a module.

        Args:
            module_name: Name of the module being audited.
            policy: Enforcement policy to check against.
            context: Optional context data about the module's behaviour.
                Keys may include:
                - requests_per_second: float
                - user_agent: str
                - tls_fingerprint_rotated: bool
                - dns_encrypted: bool
                - proxy_rotated: bool
                - request_interval_variance: float
                - session_age_seconds: float
                - waf_detected: bool

        Returns:
            List of violations found.
        """
        ctx = context or {}
        violations: list[StealthViolation] = []

        for rule in self._rules:
            check_flag = rule["check"]
            if not getattr(policy, check_flag, False):
                continue

            vtype: ViolationType = rule["violation_type"]
            violation = self._evaluate_rule(rule, module_name, ctx)
            if violation:
                violation.severity = get_violation_severity(vtype)
                violations.append(violation)

        return violations

    def _evaluate_rule(
        self,
        rule: dict[str, Any],
        module_name: str,
        ctx: dict[str, Any],
    ) -> StealthViolation | None:
        """Evaluate a single rule against the context."""
        vtype: ViolationType = rule["violation_type"]
        rid = rule["id"]

        if rid == "rate_limit":
            rps = ctx.get("requests_per_second", 0)
            if rps > 10:  # Threshold
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description=f"Rate {rps:.1f} req/s exceeds limit (10 req/s)",
                    details={"requests_per_second": rps},
                )

        elif rid == "user_agent":
            ua = ctx.get("user_agent", "")
            bad_uas = ["python-requests", "urllib", "spiderfoot", "scrapy", "httpx"]
            if any(bad in ua.lower() for bad in bad_uas):
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description=f"Identifiable user agent detected: {ua[:50]}",
                    details={"user_agent": ua},
                )

        elif rid == "tls_fp":
            if ctx.get("tls_fingerprint_rotated") is False:
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description="TLS fingerprint not being rotated",
                )

        elif rid == "dns_enc":
            if ctx.get("dns_encrypted") is False:
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description="Plaintext DNS queries detected (use DoH/DoT)",
                )

        elif rid == "proxy_rot":
            if ctx.get("proxy_rotated") is False:
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description="Proxy rotation not enabled",
                )

        elif rid == "req_pattern":
            variance = ctx.get("request_interval_variance", 1.0)
            if variance < 0.05:  # Too uniform
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description=f"Request pattern too uniform (variance={variance:.3f})",
                    details={"variance": variance},
                )

        elif rid == "timing":
            variance = ctx.get("request_interval_variance", 1.0)
            if 0.05 <= variance < 0.15:
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description=f"Request timing regularity suspicious (variance={variance:.3f})",
                    details={"variance": variance},
                )

        elif rid == "session":
            age = ctx.get("session_age_seconds", 0)
            if age > 300:  # 5 minutes without rotation
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description=f"Session reused for {age:.0f}s without rotation",
                    details={"session_age_seconds": age},
                )

        elif rid == "geo":
            if ctx.get("geolocation_mismatch") is True:
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description="Geolocation mismatch between request origin and proxy",
                )

        elif rid == "waf":
            if ctx.get("waf_detected") is True and ctx.get("waf_action_taken") is not True:
                return StealthViolation(
                    violation_type=vtype,
                    module_name=module_name,
                    description="WAF detected but no evasion action was taken",
                )

        return None

    def get_recommended_remediation(
        self,
        violation: StealthViolation,
    ) -> RemediationAction:
        """Get the recommended remediation for a violation."""
        severity = violation.severity
        vtype = violation.violation_type

        if severity == Severity.CRITICAL:
            return RemediationAction(
                action_type=RemediationActionType.QUARANTINE_MODULE,
                description=f"Quarantine module due to critical violation: {vtype.value}",
            )
        elif severity == Severity.HIGH:
            if vtype == ViolationType.RATE_LIMIT_EXCEEDED:
                return RemediationAction(
                    action_type=RemediationActionType.THROTTLE,
                    description="Reduce request rate to safe levels",
                    parameters={"target_rps": 2.0},
                )
            elif vtype == ViolationType.DNS_PLAINTEXT:
                return RemediationAction(
                    action_type=RemediationActionType.RETRY_WITH_STEALTH,
                    description="Switch to DoH/DoT for DNS resolution",
                    parameters={"dns_protocol": "doh"},
                )
            return RemediationAction(
                action_type=RemediationActionType.BLOCK_REQUEST,
                description=f"Block requests until {vtype.value} is resolved",
            )
        elif severity == Severity.WARNING:
            return RemediationAction(
                action_type=RemediationActionType.ROTATE_IDENTITY,
                description="Rotate identity (user agent, TLS fingerprint, etc.)",
            )
        else:
            return RemediationAction(
                action_type=RemediationActionType.LOG_ONLY,
                description="Log for audit trail",
            )


# ============================================================================
# Stealth Enforcement Engine — Façade (Cycles 176–180)
# ============================================================================


class StealthEnforcementEngine:
    """Unified stealth enforcement engine.

    Manages enforcement policies, tracks module states, records
    violations, and applies remediations.

    Usage::

        engine = StealthEnforcementEngine()
        engine.set_global_policy("high")

        # Check a module
        result = engine.check_module("sfp_dns", {
            "requests_per_second": 15.0,
            "dns_encrypted": False,
        })

        # Get violations
        violations = engine.get_violations()

        # Dashboard
        dashboard = engine.get_dashboard_data()
    """

    def __init__(self, stealth_level: str = "medium") -> None:
        self._global_policy = get_policy_for_level(stealth_level)
        self._module_states: dict[str, ModuleEnforcementState] = {}
        self._auditor = StealthAuditor()
        self._violations: list[StealthViolation] = []
        self._lock = threading.Lock()
        self._total_checks = 0
        self._total_blocks = 0

    @property
    def global_policy(self) -> EnforcementPolicy:
        return self._global_policy

    @property
    def auditor(self) -> StealthAuditor:
        return self._auditor

    # ── Policy Management ─────────────────────────────────────

    def set_global_policy(self, level: str) -> EnforcementPolicy:
        """Set the global enforcement policy by stealth level."""
        self._global_policy = get_policy_for_level(level)
        return self._global_policy

    def set_module_policy(
        self,
        module_name: str,
        policy: EnforcementPolicy,
    ) -> None:
        """Set a custom policy for a specific module."""
        state = self._get_or_create_state(module_name)
        state.policy = policy

    # ── Module Checking ───────────────────────────────────────

    def check_module(
        self,
        module_name: str,
        context: dict[str, Any] | None = None,
        scan_id: str = "",
    ) -> dict[str, Any]:
        """Check a module for stealth violations.

        Args:
            module_name: Module to check.
            context: Current module behaviour context.
            scan_id: Optional scan ID for tracking.

        Returns:
            Dict with: allowed (bool), violations (list),
            remediations (list), module_state (dict).
        """
        state = self._get_or_create_state(module_name)
        state.total_requests += 1

        with self._lock:
            self._total_checks += 1

        # Run audit
        new_violations = self._auditor.audit_module(
            module_name, state.policy, context,
        )

        # Tag violations
        for v in new_violations:
            v.scan_id = scan_id
            v.target = (context or {}).get("target", "")

        # Record violations
        state.violations.extend(new_violations)
        with self._lock:
            self._violations.extend(new_violations)

        # Determine remediations
        remediations: list[RemediationAction] = []
        if state.policy.auto_remediate:
            for v in new_violations:
                rem = self._auditor.get_recommended_remediation(v)
                remediations.append(rem)
                v.remediation_applied = rem.action_type.value

        # Check if module should be blocked
        allowed = True
        if state.should_block:
            allowed = False
            state.blocked_requests += 1
            with self._lock:
                self._total_blocks += 1

        # Quarantine on critical violations in appropriate modes
        if state.policy.quarantine_on_critical:
            if any(v.severity == Severity.CRITICAL for v in new_violations):
                state.is_quarantined = True
                allowed = False

        return {
            "allowed": allowed,
            "violations": [v.to_dict() for v in new_violations],
            "remediations": [r.to_dict() for r in remediations],
            "module_state": state.to_dict(),
        }

    # ── State Access ──────────────────────────────────────────

    def get_module_state(self, module_name: str) -> ModuleEnforcementState:
        """Get enforcement state for a module."""
        return self._get_or_create_state(module_name)

    def get_all_module_states(self) -> dict[str, dict[str, Any]]:
        """Get all module enforcement states."""
        with self._lock:
            return {
                name: state.to_dict()
                for name, state in self._module_states.items()
            }

    def get_violations(
        self,
        module_name: str | None = None,
        severity: Severity | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recorded violations with optional filters."""
        with self._lock:
            violations = list(self._violations)

        if module_name:
            violations = [v for v in violations if v.module_name == module_name]
        if severity:
            violations = [v for v in violations if v.severity == severity]

        # Sort by timestamp desc
        violations.sort(key=lambda v: v.timestamp, reverse=True)
        return [v.to_dict() for v in violations[:limit]]

    def get_quarantined_modules(self) -> list[str]:
        """Get list of quarantined module names."""
        with self._lock:
            return [
                name for name, state in self._module_states.items()
                if state.is_quarantined
            ]

    def unquarantine_module(self, module_name: str) -> bool:
        """Remove a module from quarantine."""
        if module_name in self._module_states:
            self._module_states[module_name].is_quarantined = False
            return True
        return False

    def clear_violations(self, module_name: str | None = None) -> int:
        """Clear recorded violations."""
        with self._lock:
            if module_name:
                before = len(self._violations)
                self._violations = [
                    v for v in self._violations
                    if v.module_name != module_name
                ]
                if module_name in self._module_states:
                    self._module_states[module_name].violations.clear()
                return before - len(self._violations)
            else:
                count = len(self._violations)
                self._violations.clear()
                for state in self._module_states.values():
                    state.violations.clear()
                return count

    # ── Statistics & Dashboard ────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get enforcement statistics."""
        with self._lock:
            total_violations = len(self._violations)
            severity_counts: dict[str, int] = {}
            type_counts: dict[str, int] = {}
            for v in self._violations:
                sev = v.severity.value
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
                vt = v.violation_type.value
                type_counts[vt] = type_counts.get(vt, 0) + 1

        return {
            "total_checks": self._total_checks,
            "total_violations": total_violations,
            "total_blocks": self._total_blocks,
            "quarantined_modules": len(self.get_quarantined_modules()),
            "monitored_modules": len(self._module_states),
            "block_rate": self._total_blocks / self._total_checks if self._total_checks > 0 else 0.0,
            "severity_breakdown": severity_counts,
            "violation_type_breakdown": type_counts,
        }

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get dashboard-ready enforcement data."""
        return {
            "global_policy": self._global_policy.to_dict(),
            "enforcement_mode": self._global_policy.mode.value,
            "stats": self.get_stats(),
            "modules": self.get_all_module_states(),
            "quarantined": self.get_quarantined_modules(),
            "recent_violations": self.get_violations(limit=20),
            "enforcement_modes": [m.value for m in EnforcementMode],
            "violation_types": [v.value for v in ViolationType],
            "severity_levels": [s.value for s in Severity],
        }

    # ── Internal ──────────────────────────────────────────────

    def _get_or_create_state(
        self,
        module_name: str,
    ) -> ModuleEnforcementState:
        """Get or create enforcement state for a module."""
        with self._lock:
            if module_name not in self._module_states:
                self._module_states[module_name] = ModuleEnforcementState(
                    module_name=module_name,
                    policy=self._global_policy,
                )
            return self._module_states[module_name]


# ============================================================================
# Module-level convenience functions
# ============================================================================


def get_enforcement_modes() -> list[str]:
    """Get all enforcement mode names."""
    return [m.value for m in EnforcementMode]


def get_violation_types() -> list[str]:
    """Get all violation type names."""
    return [v.value for v in ViolationType]


def get_severity_levels() -> list[str]:
    """Get all severity level names."""
    return [s.value for s in Severity]


def get_remediation_types() -> list[str]:
    """Get all remediation action type names."""
    return [r.value for r in RemediationActionType]
