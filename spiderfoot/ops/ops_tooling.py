"""Operations and Scale Tooling (Phase 6, Cycles 451-550).

Provides production-readiness tools for SpiderFoot v6 — health checks,
circuit breakers, dead letter queues, data retention, multi-tenancy
validation, load testing, and monitoring/alerting configuration.

All implementations are self-contained (no external service connections)
for testing and development.

Covers:
  - Cycle 451: Health check endpoints
  - Cycle 452: Circuit breakers for external APIs
  - Cycle 453: Dead letter queue for Celery tasks
  - Cycle 454: Scan state recovery
  - Cycle 455: Data retention policy
  - Cycles 456-480: Multi-tenancy isolation validation
  - Cycles 481-500: K8s resource configuration
  - Cycles 501-530: Load testing framework
  - Cycles 531-550: Monitoring, alerting, SLO definitions
"""

from __future__ import annotations

import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.ops")


# ── Health Checks (Cycle 451) ─────────────────────────────────────────


class HealthStatus(str, Enum):
    """Health check status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    metadata: dict = field(default_factory=dict)


class HealthChecker:
    """Aggregates health checks for all system components.

    Verifies actual connectivity (not just process liveness).
    Components register check functions; the checker invokes all
    and aggregates into an overall status.

    Usage::

        checker = HealthChecker()
        checker.register("database", lambda: ComponentHealth("database", HealthStatus.HEALTHY))
        checker.register("redis", lambda: ComponentHealth("redis", HealthStatus.HEALTHY))
        report = checker.check_all()
    """

    def __init__(self) -> None:
        self._checks: dict[str, Any] = {}

    def register(self, name: str, check_fn: Any) -> None:
        """Register a health check function.

        Args:
            name: Component name.
            check_fn: Callable that returns ComponentHealth.
        """
        self._checks[name] = check_fn

    def check(self, name: str) -> ComponentHealth:
        """Run a single health check."""
        if name not in self._checks:
            return ComponentHealth(name, HealthStatus.UNHEALTHY,
                                  message="Unknown component")
        try:
            return self._checks[name]()
        except Exception as e:
            return ComponentHealth(name, HealthStatus.UNHEALTHY,
                                  message=str(e))

    def check_all(self) -> dict:
        """Run all registered health checks.

        Returns a dict with overall status and per-component results.
        """
        results = {}
        for name in self._checks:
            results[name] = self.check(name)

        statuses = [r.status for r in results.values()]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.DEGRADED

        return {
            "status": overall.value,
            "components": {
                name: {
                    "status": r.status.value,
                    "latency_ms": round(r.latency_ms, 2),
                    "message": r.message,
                }
                for name, r in results.items()
            },
            "timestamp": time.time(),
        }

    @property
    def component_count(self) -> int:
        return len(self._checks)


# ── Circuit Breaker (Cycle 452) ───────────────────────────────────────


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, rejecting calls
    HALF_OPEN = "half_open" # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for external API calls.

    Trips after `failure_threshold` consecutive failures, waits
    `recovery_timeout` seconds before allowing a test call.

    Usage::

        cb = CircuitBreaker("external-api", failure_threshold=5)
        if cb.allow_request():
            try:
                result = call_api()
                cb.record_success()
            except Exception:
                cb.record_failure()
    """

    def __init__(self, name: str, *,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 30.0) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._total_calls = 0
        self._total_failures = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def allow_request(self) -> bool:
        """Check if a request is allowed."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True  # Allow one test request
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        self._total_calls += 1
        self._success_count += 1
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        self._total_calls += 1
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "error_rate": round(
                self._total_failures / max(1, self._total_calls) * 100, 2
            ),
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(self, name: str, **kwargs) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, **kwargs)
        return self._breakers[name]

    def get_all_stats(self) -> dict:
        """Get stats for all circuit breakers."""
        return {name: cb.get_stats()
                for name, cb in self._breakers.items()}

    @property
    def count(self) -> int:
        return len(self._breakers)


# ── Dead Letter Queue (Cycle 453) ─────────────────────────────────────


@dataclass
class DeadLetter:
    """A failed task that has been sent to the dead letter queue."""
    task_id: str
    task_name: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    exception: str = ""
    traceback: str = ""
    retry_count: int = 0
    max_retries: int = 3
    timestamp: float = field(default_factory=time.time)


class DeadLetterQueue:
    """In-memory dead letter queue for failed Celery tasks.

    Failed tasks are stored and can be retried, inspected, or purged.
    """

    def __init__(self, max_size: int = 10000) -> None:
        self._queue: list[DeadLetter] = []
        self._max_size = max_size
        self._total_received = 0
        self._total_retried = 0
        self._total_purged = 0

    def enqueue(self, letter: DeadLetter) -> None:
        """Add a failed task to the DLQ."""
        if len(self._queue) >= self._max_size:
            self._queue.pop(0)  # Drop oldest
            self._total_purged += 1
        self._queue.append(letter)
        self._total_received += 1

    def peek(self, limit: int = 10) -> list[DeadLetter]:
        """View items without removing them."""
        return self._queue[:limit]

    def dequeue(self) -> DeadLetter | None:
        """Remove and return the oldest item."""
        if self._queue:
            return self._queue.pop(0)
        return None

    def retry_eligible(self) -> list[DeadLetter]:
        """Get items that can be retried."""
        return [dl for dl in self._queue
                if dl.retry_count < dl.max_retries]

    def mark_retried(self, task_id: str) -> bool:
        """Mark a task as retried (increment retry count)."""
        for dl in self._queue:
            if dl.task_id == task_id:
                dl.retry_count += 1
                self._total_retried += 1
                return True
        return False

    def purge(self, *, older_than: float | None = None) -> int:
        """Purge items from the DLQ.

        Args:
            older_than: Remove items older than this timestamp.

        Returns:
            Number of items purged.
        """
        if older_than is None:
            count = len(self._queue)
            self._queue.clear()
            self._total_purged += count
            return count

        before = len(self._queue)
        self._queue = [dl for dl in self._queue
                       if dl.timestamp >= older_than]
        purged = before - len(self._queue)
        self._total_purged += purged
        return purged

    @property
    def size(self) -> int:
        return len(self._queue)

    def get_stats(self) -> dict:
        task_counts = Counter(dl.task_name for dl in self._queue)
        return {
            "size": self.size,
            "total_received": self._total_received,
            "total_retried": self._total_retried,
            "total_purged": self._total_purged,
            "retry_eligible": len(self.retry_eligible()),
            "by_task": dict(task_counts),
        }


# ── Scan State Recovery (Cycle 454) ──────────────────────────────────


class ScanPhase(str, Enum):
    """Scan lifecycle phases for recovery."""
    INITIALIZING = "initializing"
    MODULES_LOADING = "modules_loading"
    SCANNING = "scanning"
    CORRELATING = "correlating"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScanCheckpoint:
    """A checkpoint for scan state recovery."""
    scan_id: str
    phase: ScanPhase
    completed_modules: list[str] = field(default_factory=list)
    pending_modules: list[str] = field(default_factory=list)
    events_processed: int = 0
    last_event_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class ScanRecoveryManager:
    """Manages scan checkpoints for crash recovery.

    When a worker dies mid-scan, another worker picks up the scan
    from the last committed checkpoint.
    """

    def __init__(self) -> None:
        self._checkpoints: dict[str, ScanCheckpoint] = {}

    def save_checkpoint(self, checkpoint: ScanCheckpoint) -> None:
        """Save or update a scan checkpoint."""
        self._checkpoints[checkpoint.scan_id] = checkpoint

    def get_checkpoint(self, scan_id: str) -> ScanCheckpoint | None:
        """Get the last checkpoint for a scan."""
        return self._checkpoints.get(scan_id)

    def get_recoverable_scans(self) -> list[ScanCheckpoint]:
        """Find scans that can be resumed.

        Returns scans that are not completed or failed.
        """
        terminal_phases = {ScanPhase.COMPLETED, ScanPhase.FAILED}
        return [cp for cp in self._checkpoints.values()
                if cp.phase not in terminal_phases]

    def resume_scan(self, scan_id: str) -> dict | None:
        """Generate a resume plan for a scan.

        Returns:
            Dict with resume instructions or None if not recoverable.
        """
        cp = self.get_checkpoint(scan_id)
        if cp is None:
            return None
        if cp.phase in (ScanPhase.COMPLETED, ScanPhase.FAILED):
            return None

        return {
            "scan_id": scan_id,
            "phase": cp.phase.value,
            "completed_modules": cp.completed_modules,
            "modules_to_run": cp.pending_modules,
            "resume_from_event": cp.last_event_id,
            "events_already_processed": cp.events_processed,
        }

    def mark_completed(self, scan_id: str) -> None:
        """Mark a scan as completed."""
        if scan_id in self._checkpoints:
            cp = self._checkpoints[scan_id]
            cp.phase = ScanPhase.COMPLETED

    def delete_checkpoint(self, scan_id: str) -> bool:
        """Delete a checkpoint."""
        if scan_id in self._checkpoints:
            del self._checkpoints[scan_id]
            return True
        return False

    @property
    def checkpoint_count(self) -> int:
        return len(self._checkpoints)


# ── Data Retention (Cycle 455) ────────────────────────────────────────


@dataclass
class RetentionPolicy:
    """Data retention policy definition."""
    name: str
    max_age_days: int
    applies_to: str  # "scan_results", "events", "logs", etc.
    enabled: bool = True
    dry_run: bool = False


class DataRetentionManager:
    """Enforces data retention policies.

    Tracks what should be pruned and produces audit logs.
    """

    def __init__(self) -> None:
        self._policies: list[RetentionPolicy] = []
        self._audit_log: list[dict] = []

    def add_policy(self, policy: RetentionPolicy) -> None:
        """Add a retention policy."""
        self._policies.append(policy)

    def get_policies(self) -> list[RetentionPolicy]:
        """Get all policies."""
        return list(self._policies)

    def evaluate(self, records: list[dict],
                 timestamp_field: str = "created_at"
                 ) -> dict:
        """Evaluate records against retention policies.

        Args:
            records: List of records with timestamp fields.
            timestamp_field: Name of the timestamp field.

        Returns:
            Dict with "keep" and "prune" lists.
        """
        now = time.time()
        keep = []
        prune = []

        for record in records:
            ts = record.get(timestamp_field, now)
            age_days = (now - ts) / 86400
            should_prune = False

            for policy in self._policies:
                if not policy.enabled:
                    continue
                record_type = record.get("type", "")
                if policy.applies_to != "*" and record_type != policy.applies_to:
                    continue
                if age_days > policy.max_age_days:
                    should_prune = True
                    self._audit_log.append({
                        "action": "prune" if not policy.dry_run else "dry_run_prune",
                        "record": record,
                        "policy": policy.name,
                        "age_days": round(age_days, 1),
                        "timestamp": now,
                    })
                    break

            if should_prune:
                prune.append(record)
            else:
                keep.append(record)

        return {"keep": keep, "prune": prune}

    @property
    def audit_log(self) -> list[dict]:
        return list(self._audit_log)

    @property
    def policy_count(self) -> int:
        return len(self._policies)


# ── Multi-Tenancy Validation (Cycles 456-480) ────────────────────────


@dataclass
class TenantContext:
    """Tenant isolation context."""
    tenant_id: str
    name: str
    scans: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)


class TenantIsolationValidator:
    """Validates cross-tenant data isolation.

    Tests that queries for one tenant never return data
    belonging to another tenant.
    """

    def __init__(self) -> None:
        self._tenants: dict[str, TenantContext] = {}

    def add_tenant(self, tenant: TenantContext) -> None:
        """Register a tenant."""
        self._tenants[tenant.tenant_id] = tenant

    def add_scan(self, tenant_id: str, scan_id: str) -> None:
        """Associate a scan with a tenant."""
        if tenant_id in self._tenants:
            self._tenants[tenant_id].scans.append(scan_id)

    def validate_isolation(self, query_tenant_id: str,
                           results: list[dict],
                           tenant_field: str = "tenant_id"
                           ) -> dict:
        """Validate that results belong to the querying tenant.

        Returns:
            Dict with "valid", "total", "violations" counts.
        """
        violations = []
        for record in results:
            record_tenant = record.get(tenant_field, "")
            if record_tenant and record_tenant != query_tenant_id:
                violations.append({
                    "record": record,
                    "expected_tenant": query_tenant_id,
                    "actual_tenant": record_tenant,
                })

        return {
            "valid": len(violations) == 0,
            "total": len(results),
            "violations": len(violations),
            "details": violations,
        }

    def get_scan_owner(self, scan_id: str) -> str | None:
        """Find which tenant owns a scan."""
        for tenant in self._tenants.values():
            if scan_id in tenant.scans:
                return tenant.tenant_id
        return None

    @property
    def tenant_count(self) -> int:
        return len(self._tenants)


# ── K8s Resource Configuration (Cycles 481-500) ──────────────────────


@dataclass
class K8sResource:
    """Kubernetes resource specification."""
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"


@dataclass
class K8sServiceConfig:
    """Kubernetes service deployment configuration."""
    name: str
    replicas: int = 1
    resources: K8sResource = field(default_factory=K8sResource)
    pdb_min_available: int = 1
    hpa_min_replicas: int = 1
    hpa_max_replicas: int = 10
    hpa_target_cpu: int = 70
    readiness_path: str = "/healthz"
    liveness_path: str = "/healthz"


class K8sConfigGenerator:
    """Generates Kubernetes resource configurations.

    Produces PodDisruptionBudget, HPA, and resource limit YAML.
    """

    DEFAULT_SERVICES = {
        "api": K8sServiceConfig(
            "api", replicas=2,
            resources=K8sResource("250m", "1000m", "256Mi", "1Gi"),
            pdb_min_available=1, hpa_max_replicas=8,
        ),
        "worker": K8sServiceConfig(
            "worker", replicas=3,
            resources=K8sResource("500m", "2000m", "512Mi", "2Gi"),
            pdb_min_available=2, hpa_max_replicas=20,
        ),
        "scheduler": K8sServiceConfig(
            "scheduler", replicas=1,
            resources=K8sResource("100m", "500m", "128Mi", "512Mi"),
            pdb_min_available=1, hpa_max_replicas=1,
        ),
    }

    def __init__(self) -> None:
        self._services: dict[str, K8sServiceConfig] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for name, svc in self.DEFAULT_SERVICES.items():
            self._services[name] = svc

    def add_service(self, config: K8sServiceConfig) -> None:
        """Add or update a service configuration."""
        self._services[config.name] = config

    def generate_pdb(self, name: str) -> dict:
        """Generate PodDisruptionBudget spec."""
        svc = self._services.get(name)
        if svc is None:
            return {}

        return {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {"name": f"{name}-pdb"},
            "spec": {
                "minAvailable": svc.pdb_min_available,
                "selector": {"matchLabels": {"app": name}},
            },
        }

    def generate_hpa(self, name: str) -> dict:
        """Generate HorizontalPodAutoscaler spec."""
        svc = self._services.get(name)
        if svc is None:
            return {}

        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": f"{name}-hpa"},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": name,
                },
                "minReplicas": svc.hpa_min_replicas,
                "maxReplicas": svc.hpa_max_replicas,
                "metrics": [{
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": svc.hpa_target_cpu,
                        },
                    },
                }],
            },
        }

    def generate_resources(self, name: str) -> dict:
        """Generate resource limits/requests spec."""
        svc = self._services.get(name)
        if svc is None:
            return {}

        return {
            "resources": {
                "requests": {
                    "cpu": svc.resources.cpu_request,
                    "memory": svc.resources.memory_request,
                },
                "limits": {
                    "cpu": svc.resources.cpu_limit,
                    "memory": svc.resources.memory_limit,
                },
            },
        }

    @property
    def service_count(self) -> int:
        return len(self._services)


# ── Load Testing (Cycles 501-530) ─────────────────────────────────────


@dataclass
class LoadTestResult:
    """Result of a load test run."""
    name: str
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    events_per_second: float = 0.0
    duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.successful / self.total_requests * 100, 2)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "events_per_second": round(self.events_per_second, 2),
            "duration_seconds": round(self.duration_seconds, 2),
        }


class LoadTestScenario:
    """Defines and runs simulated load test scenarios.

    Tracks latencies from individual operations and computes
    aggregate metrics.
    """

    def __init__(self, name: str, concurrency: int = 10) -> None:
        self.name = name
        self.concurrency = concurrency
        self._latencies: list[float] = []
        self._successes = 0
        self._failures = 0
        self._start_time = 0.0
        self._end_time = 0.0
        self._events_count = 0

    def start(self) -> None:
        """Mark the start of a load test."""
        self._start_time = time.time()

    def record_operation(self, latency_ms: float, success: bool = True,
                         events: int = 0) -> None:
        """Record a single operation result."""
        self._latencies.append(latency_ms)
        if success:
            self._successes += 1
        else:
            self._failures += 1
        self._events_count += events

    def finish(self) -> LoadTestResult:
        """Finish the load test and compute results."""
        self._end_time = time.time()
        duration = max(0.001, self._end_time - self._start_time)

        sorted_latencies = sorted(self._latencies) if self._latencies else [0]
        p99_idx = int(len(sorted_latencies) * 0.99)

        return LoadTestResult(
            name=self.name,
            total_requests=len(self._latencies),
            successful=self._successes,
            failed=self._failures,
            avg_latency_ms=(sum(self._latencies) / len(self._latencies)
                            if self._latencies else 0.0),
            p99_latency_ms=sorted_latencies[min(p99_idx,
                                                 len(sorted_latencies) - 1)],
            max_latency_ms=max(sorted_latencies),
            events_per_second=self._events_count / duration,
            duration_seconds=duration,
        )


# ── SLO Definitions (Cycles 531-550) ─────────────────────────────────


class SLOStatus(str, Enum):
    """SLO compliance status."""
    MEETING = "meeting"
    AT_RISK = "at_risk"
    BREACHED = "breached"


@dataclass
class SLODefinition:
    """Service Level Objective definition."""
    name: str
    target: float
    metric: str  # "latency_ms", "error_rate", "throughput"
    comparison: str = "lte"  # "lte", "gte"
    description: str = ""


class SLOTracker:
    """Tracks SLO compliance.

    Default SLOs:
      - Scan start latency < 2s
      - Events/second > 100
      - API p99 latency < 500ms
      - Error rate < 5%
    """

    DEFAULT_SLOS = [
        SLODefinition("scan_start_latency", 2000.0, "latency_ms",
                       "lte", "Scan start latency < 2s"),
        SLODefinition("events_throughput", 100.0, "throughput",
                       "gte", "Events/second > 100"),
        SLODefinition("api_p99_latency", 500.0, "latency_ms",
                       "lte", "API p99 latency < 500ms"),
        SLODefinition("error_rate", 5.0, "error_rate",
                       "lte", "Error rate < 5%"),
    ]

    def __init__(self) -> None:
        self._slos: list[SLODefinition] = list(self.DEFAULT_SLOS)
        self._measurements: dict[str, list[float]] = defaultdict(list)

    def add_slo(self, slo: SLODefinition) -> None:
        """Add a custom SLO."""
        self._slos.append(slo)

    def record_measurement(self, slo_name: str, value: float) -> None:
        """Record a measurement for an SLO."""
        self._measurements[slo_name].append(value)

    def evaluate(self, slo_name: str) -> SLOStatus:
        """Evaluate current SLO status."""
        slo = None
        for s in self._slos:
            if s.name == slo_name:
                slo = s
                break
        if slo is None:
            return SLOStatus.BREACHED

        values = self._measurements.get(slo_name, [])
        if not values:
            return SLOStatus.MEETING  # No data yet

        avg = sum(values) / len(values)

        if slo.comparison == "lte":
            if avg <= slo.target:
                return SLOStatus.MEETING
            elif avg <= slo.target * 1.1:
                return SLOStatus.AT_RISK
            else:
                return SLOStatus.BREACHED
        else:  # gte
            if avg >= slo.target:
                return SLOStatus.MEETING
            elif avg >= slo.target * 0.9:
                return SLOStatus.AT_RISK
            else:
                return SLOStatus.BREACHED

    def evaluate_all(self) -> dict:
        """Evaluate all SLOs."""
        results = {}
        for slo in self._slos:
            results[slo.name] = {
                "status": self.evaluate(slo.name).value,
                "target": slo.target,
                "description": slo.description,
                "measurements": len(self._measurements.get(slo.name, [])),
            }
        return results

    @property
    def slo_count(self) -> int:
        return len(self._slos)


# ── Alerting Rules (Cycles 531-550) ───────────────────────────────────


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """An alerting rule definition."""
    name: str
    metric: str
    condition: str  # "gt", "lt", "gte", "lte"
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    description: str = ""


@dataclass
class Alert:
    """A triggered alert instance."""
    rule_name: str
    severity: AlertSeverity
    value: float
    threshold: float
    message: str
    timestamp: float = field(default_factory=time.time)


class AlertManager:
    """Manages alerting rules and evaluates metrics against them.

    Default rules:
      - Scan stuck > 30 minutes → CRITICAL
      - Error rate > 5% → WARNING
      - Queue depth > 10000 → CRITICAL
      - DB pool exhausted (free connections = 0) → CRITICAL
    """

    DEFAULT_RULES = [
        AlertRule("scan_stuck", "scan_duration_min", "gt", 30.0,
                  AlertSeverity.CRITICAL,
                  "Scan stuck for > 30 minutes"),
        AlertRule("error_rate_high", "error_rate_pct", "gt", 5.0,
                  AlertSeverity.WARNING,
                  "Error rate > 5%"),
        AlertRule("queue_depth_critical", "queue_depth", "gt", 10000.0,
                  AlertSeverity.CRITICAL,
                  "Queue depth > 10,000"),
        AlertRule("db_pool_exhausted", "db_free_connections", "lte", 0.0,
                  AlertSeverity.CRITICAL,
                  "DB connection pool exhausted"),
    ]

    def __init__(self) -> None:
        self._rules: list[AlertRule] = list(self.DEFAULT_RULES)
        self._alerts: list[Alert] = []

    def add_rule(self, rule: AlertRule) -> None:
        """Add a custom alerting rule."""
        self._rules.append(rule)

    def evaluate(self, metrics: dict[str, float]) -> list[Alert]:
        """Evaluate metrics against all rules.

        Args:
            metrics: Dict of metric_name -> value.

        Returns:
            List of triggered alerts.
        """
        triggered = []
        for rule in self._rules:
            value = metrics.get(rule.metric)
            if value is None:
                continue

            fired = False
            if rule.condition == "gt" and value > rule.threshold:
                fired = True
            elif rule.condition == "lt" and value < rule.threshold:
                fired = True
            elif rule.condition == "gte" and value >= rule.threshold:
                fired = True
            elif rule.condition == "lte" and value <= rule.threshold:
                fired = True

            if fired:
                alert = Alert(
                    rule_name=rule.name,
                    severity=rule.severity,
                    value=value,
                    threshold=rule.threshold,
                    message=rule.description,
                )
                triggered.append(alert)
                self._alerts.append(alert)

        return triggered

    def get_history(self, severity: AlertSeverity | None = None
                    ) -> list[Alert]:
        """Get alert history, optionally filtered by severity."""
        if severity is None:
            return list(self._alerts)
        return [a for a in self._alerts if a.severity == severity]

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def alert_count(self) -> int:
        return len(self._alerts)
