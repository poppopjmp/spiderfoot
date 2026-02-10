"""Scan Policy Engine for SpiderFoot.

Configurable policies that govern scan behavior including scope limits,
timeouts, rate limits, target exclusions, and module restrictions.
Policies are composable and can be loaded from dictionaries.
"""

import ipaddress
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger("spiderfoot.scan_policy")


class PolicyAction(Enum):
    """Action when a policy violation occurs."""
    BLOCK = "block"       # Block the operation
    WARN = "warn"         # Log warning but allow
    SKIP = "skip"         # Silently skip


class ViolationSeverity(Enum):
    """Severity of a policy violation."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class PolicyViolation:
    """Records a policy violation."""
    policy_name: str
    message: str
    severity: ViolationSeverity = ViolationSeverity.WARNING
    action: PolicyAction = PolicyAction.BLOCK
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class PolicyCheckResult:
    """Result of checking an operation against all policies."""
    allowed: bool
    violations: list[PolicyViolation] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def blocked(self) -> bool:
        return any(v.action == PolicyAction.BLOCK for v in self.violations)


class ScanPolicy:
    """Configurable scan policy with scope, rate, and module restrictions.

    Usage:
        policy = ScanPolicy(name="strict")
        policy.set_max_events(10000)
        policy.set_max_depth(3)
        policy.exclude_targets(["*.gov", "10.0.0.0/8"])
        policy.restrict_modules(allowed={"sfp_dns", "sfp_ssl"})

        result = policy.check_target("example.gov")
        if not result.allowed:
            print(result.violations)
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._enabled = True

        # Scope limits
        self._max_events: Optional[int] = None
        self._max_depth: Optional[int] = None
        self._max_duration_seconds: Optional[float] = None
        self._max_targets: Optional[int] = None

        # Target exclusions
        self._excluded_patterns: list[re.Pattern] = []
        self._excluded_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        self._allowed_targets: Optional[set[str]] = None

        # Module restrictions
        self._allowed_modules: Optional[set[str]] = None
        self._denied_modules: set[str] = set()

        # Event type restrictions
        self._denied_event_types: set[str] = set()
        self._max_events_per_type: dict[str, int] = {}

        # Rate limits
        self._rate_limit_per_module: dict[str, float] = {}  # module -> max requests/sec
        self._global_rate_limit: Optional[float] = None

        # Tracking
        self._violations: list[PolicyViolation] = []

    def set_max_events(self, n: int) -> "ScanPolicy":
        self._max_events = n
        return self

    def set_max_depth(self, n: int) -> "ScanPolicy":
        self._max_depth = n
        return self

    def set_max_duration(self, seconds: float) -> "ScanPolicy":
        self._max_duration_seconds = seconds
        return self

    def set_max_targets(self, n: int) -> "ScanPolicy":
        self._max_targets = n
        return self

    def exclude_targets(self, patterns: list[str]) -> "ScanPolicy":
        """Exclude targets matching glob patterns or CIDR networks."""
        for p in patterns:
            try:
                net = ipaddress.ip_network(p, strict=False)
                self._excluded_networks.append(net)
            except ValueError:
                regex = p.replace(".", r"\.").replace("*", ".*")
                self._excluded_patterns.append(re.compile(f"^{regex}$", re.IGNORECASE))
        return self

    def allow_targets(self, targets: set[str]) -> "ScanPolicy":
        self._allowed_targets = targets
        return self

    def restrict_modules(
        self,
        allowed: Optional[set[str]] = None,
        denied: Optional[set[str]] = None,
    ) -> "ScanPolicy":
        if allowed is not None:
            self._allowed_modules = allowed
        if denied is not None:
            self._denied_modules = denied
        return self

    def deny_event_types(self, types: set[str]) -> "ScanPolicy":
        self._denied_event_types = types
        return self

    def set_max_events_per_type(self, limits: dict[str, int]) -> "ScanPolicy":
        self._max_events_per_type = limits
        return self

    def set_rate_limit(self, module: str, max_per_second: float) -> "ScanPolicy":
        self._rate_limit_per_module[module] = max_per_second
        return self

    def set_global_rate_limit(self, max_per_second: float) -> "ScanPolicy":
        self._global_rate_limit = max_per_second
        return self

    def check_target(self, target: str) -> PolicyCheckResult:
        """Check if a target is allowed by this policy."""
        violations = []

        if not self._enabled:
            return PolicyCheckResult(allowed=True)

        # Check exclusion patterns
        for pat in self._excluded_patterns:
            if pat.match(target):
                violations.append(PolicyViolation(
                    policy_name=self.name,
                    message=f"Target '{target}' matches exclusion pattern",
                    severity=ViolationSeverity.ERROR,
                    action=PolicyAction.BLOCK,
                    context={"target": target, "pattern": pat.pattern},
                ))

        # Check excluded networks (only for IP-like targets)
        try:
            addr = ipaddress.ip_address(target)
            for net in self._excluded_networks:
                if addr in net:
                    violations.append(PolicyViolation(
                        policy_name=self.name,
                        message=f"Target '{target}' is in excluded network {net}",
                        severity=ViolationSeverity.ERROR,
                        action=PolicyAction.BLOCK,
                        context={"target": target, "network": str(net)},
                    ))
        except ValueError:
            pass  # Not an IP address

        # Check allowed targets
        if self._allowed_targets is not None and target not in self._allowed_targets:
            violations.append(PolicyViolation(
                policy_name=self.name,
                message=f"Target '{target}' is not in the allowed list",
                severity=ViolationSeverity.WARNING,
                action=PolicyAction.BLOCK,
                context={"target": target},
            ))

        self._violations.extend(violations)
        blocked = any(v.action == PolicyAction.BLOCK for v in violations)
        return PolicyCheckResult(allowed=not blocked, violations=violations)

    def check_module(self, module_name: str) -> PolicyCheckResult:
        """Check if a module is allowed by this policy."""
        violations = []

        if not self._enabled:
            return PolicyCheckResult(allowed=True)

        if module_name in self._denied_modules:
            violations.append(PolicyViolation(
                policy_name=self.name,
                message=f"Module '{module_name}' is denied",
                severity=ViolationSeverity.ERROR,
                action=PolicyAction.BLOCK,
                context={"module": module_name},
            ))

        if self._allowed_modules is not None and module_name not in self._allowed_modules:
            violations.append(PolicyViolation(
                policy_name=self.name,
                message=f"Module '{module_name}' is not in allowed list",
                severity=ViolationSeverity.WARNING,
                action=PolicyAction.BLOCK,
                context={"module": module_name},
            ))

        self._violations.extend(violations)
        blocked = any(v.action == PolicyAction.BLOCK for v in violations)
        return PolicyCheckResult(allowed=not blocked, violations=violations)

    def check_event_type(self, event_type: str, current_count: int = 0) -> PolicyCheckResult:
        """Check if an event type is allowed."""
        violations = []

        if not self._enabled:
            return PolicyCheckResult(allowed=True)

        if event_type in self._denied_event_types:
            violations.append(PolicyViolation(
                policy_name=self.name,
                message=f"Event type '{event_type}' is denied",
                severity=ViolationSeverity.ERROR,
                action=PolicyAction.BLOCK,
                context={"event_type": event_type},
            ))

        if event_type in self._max_events_per_type:
            limit = self._max_events_per_type[event_type]
            if current_count >= limit:
                violations.append(PolicyViolation(
                    policy_name=self.name,
                    message=f"Event type '{event_type}' exceeded limit of {limit}",
                    severity=ViolationSeverity.WARNING,
                    action=PolicyAction.BLOCK,
                    context={"event_type": event_type, "limit": limit, "count": current_count},
                ))

        self._violations.extend(violations)
        blocked = any(v.action == PolicyAction.BLOCK for v in violations)
        return PolicyCheckResult(allowed=not blocked, violations=violations)

    def check_depth(self, depth: int) -> PolicyCheckResult:
        """Check if the scan depth is within limits."""
        if not self._enabled or self._max_depth is None:
            return PolicyCheckResult(allowed=True)

        if depth > self._max_depth:
            v = PolicyViolation(
                policy_name=self.name,
                message=f"Scan depth {depth} exceeds limit {self._max_depth}",
                severity=ViolationSeverity.WARNING,
                action=PolicyAction.BLOCK,
                context={"depth": depth, "limit": self._max_depth},
            )
            self._violations.append(v)
            return PolicyCheckResult(allowed=False, violations=[v])

        return PolicyCheckResult(allowed=True)

    def check_event_count(self, count: int) -> PolicyCheckResult:
        """Check if total event count is within limits."""
        if not self._enabled or self._max_events is None:
            return PolicyCheckResult(allowed=True)

        if count >= self._max_events:
            v = PolicyViolation(
                policy_name=self.name,
                message=f"Total events {count} exceeds limit {self._max_events}",
                severity=ViolationSeverity.WARNING,
                action=PolicyAction.BLOCK,
                context={"count": count, "limit": self._max_events},
            )
            self._violations.append(v)
            return PolicyCheckResult(allowed=False, violations=[v])

        return PolicyCheckResult(allowed=True)

    def check_duration(self, elapsed_seconds: float) -> PolicyCheckResult:
        """Check if scan duration is within limits."""
        if not self._enabled or self._max_duration_seconds is None:
            return PolicyCheckResult(allowed=True)

        if elapsed_seconds > self._max_duration_seconds:
            v = PolicyViolation(
                policy_name=self.name,
                message=f"Scan duration {elapsed_seconds:.0f}s exceeds limit {self._max_duration_seconds:.0f}s",
                severity=ViolationSeverity.ERROR,
                action=PolicyAction.BLOCK,
                context={"elapsed": elapsed_seconds, "limit": self._max_duration_seconds},
            )
            self._violations.append(v)
            return PolicyCheckResult(allowed=False, violations=[v])

        return PolicyCheckResult(allowed=True)

    @property
    def violations(self) -> list[PolicyViolation]:
        return list(self._violations)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    def clear_violations(self) -> None:
        self._violations.clear()

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enabled": self._enabled,
            "max_events": self._max_events,
            "max_depth": self._max_depth,
            "max_duration_seconds": self._max_duration_seconds,
            "max_targets": self._max_targets,
            "denied_modules": sorted(self._denied_modules),
            "allowed_modules": sorted(self._allowed_modules) if self._allowed_modules else None,
            "denied_event_types": sorted(self._denied_event_types),
            "max_events_per_type": self._max_events_per_type,
            "violation_count": len(self._violations),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScanPolicy":
        """Create a policy from a dictionary."""
        policy = cls(name=d.get("name", "default"))

        if "max_events" in d and d["max_events"] is not None:
            policy.set_max_events(d["max_events"])
        if "max_depth" in d and d["max_depth"] is not None:
            policy.set_max_depth(d["max_depth"])
        if "max_duration_seconds" in d and d["max_duration_seconds"] is not None:
            policy.set_max_duration(d["max_duration_seconds"])
        if "max_targets" in d and d["max_targets"] is not None:
            policy.set_max_targets(d["max_targets"])
        if "denied_modules" in d:
            policy.restrict_modules(denied=set(d["denied_modules"]))
        if "allowed_modules" in d and d["allowed_modules"] is not None:
            policy.restrict_modules(allowed=set(d["allowed_modules"]))
        if "denied_event_types" in d:
            policy.deny_event_types(set(d["denied_event_types"]))
        if "exclude_targets" in d:
            policy.exclude_targets(d["exclude_targets"])
        if "max_events_per_type" in d:
            policy.set_max_events_per_type(d["max_events_per_type"])

        return policy


class PolicyEngine:
    """Manages multiple scan policies and evaluates operations against all.

    Usage:
        engine = PolicyEngine()
        engine.add_policy(ScanPolicy("strict").set_max_depth(3))
        engine.add_policy(ScanPolicy("scope").exclude_targets(["*.gov"]))

        result = engine.evaluate_target("example.gov")
        if not result.allowed:
            for v in result.violations:
                print(v.message)
    """

    def __init__(self):
        self._policies: dict[str, ScanPolicy] = {}

    def add_policy(self, policy: ScanPolicy) -> "PolicyEngine":
        self._policies[policy.name] = policy
        return self

    def remove_policy(self, name: str) -> bool:
        return self._policies.pop(name, None) is not None

    def get_policy(self, name: str) -> Optional[ScanPolicy]:
        return self._policies.get(name)

    def evaluate_target(self, target: str) -> PolicyCheckResult:
        all_violations = []
        for policy in self._policies.values():
            result = policy.check_target(target)
            all_violations.extend(result.violations)
        blocked = any(v.action == PolicyAction.BLOCK for v in all_violations)
        return PolicyCheckResult(allowed=not blocked, violations=all_violations)

    def evaluate_module(self, module_name: str) -> PolicyCheckResult:
        all_violations = []
        for policy in self._policies.values():
            result = policy.check_module(module_name)
            all_violations.extend(result.violations)
        blocked = any(v.action == PolicyAction.BLOCK for v in all_violations)
        return PolicyCheckResult(allowed=not blocked, violations=all_violations)

    def evaluate_event_type(self, event_type: str, count: int = 0) -> PolicyCheckResult:
        all_violations = []
        for policy in self._policies.values():
            result = policy.check_event_type(event_type, count)
            all_violations.extend(result.violations)
        blocked = any(v.action == PolicyAction.BLOCK for v in all_violations)
        return PolicyCheckResult(allowed=not blocked, violations=all_violations)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def policy_names(self) -> list[str]:
        return sorted(self._policies.keys())

    def get_all_violations(self) -> list[PolicyViolation]:
        violations = []
        for policy in self._policies.values():
            violations.extend(policy.violations)
        return violations

    def clear_all_violations(self) -> None:
        for policy in self._policies.values():
            policy.clear_violations()

    def to_dict(self) -> dict:
        return {
            "policies": {name: p.to_dict() for name, p in self._policies.items()},
            "total_violations": sum(p.violation_count for p in self._policies.values()),
        }
