"""Tests for spiderfoot.ops.ops_tooling (Phase 6, Cycles 451-550)."""

import time
import pytest
from spiderfoot.ops.ops_tooling import (
    HealthStatus,
    ComponentHealth,
    HealthChecker,
    CircuitState,
    CircuitBreaker,
    CircuitBreakerRegistry,
    DeadLetter,
    DeadLetterQueue,
    ScanPhase,
    ScanCheckpoint,
    ScanRecoveryManager,
    RetentionPolicy,
    DataRetentionManager,
    TenantContext,
    TenantIsolationValidator,
    K8sResource,
    K8sServiceConfig,
    K8sConfigGenerator,
    LoadTestResult,
    LoadTestScenario,
    SLOStatus,
    SLODefinition,
    SLOTracker,
    AlertSeverity,
    AlertRule,
    Alert,
    AlertManager,
)


# ── HealthChecker ─────────────────────────────────────────────────────


class TestHealthStatus:
    def test_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"


class TestHealthChecker:
    def test_register(self):
        hc = HealthChecker()
        hc.register("db", lambda: ComponentHealth("db", HealthStatus.HEALTHY))
        assert hc.component_count == 1

    def test_check_healthy(self):
        hc = HealthChecker()
        hc.register("db", lambda: ComponentHealth("db", HealthStatus.HEALTHY, 5.0))
        result = hc.check("db")
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms == 5.0

    def test_check_unknown(self):
        hc = HealthChecker()
        result = hc.check("unknown")
        assert result.status == HealthStatus.UNHEALTHY

    def test_check_exception(self):
        hc = HealthChecker()
        hc.register("bad", lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        result = hc.check("bad")
        assert result.status == HealthStatus.UNHEALTHY

    def test_check_all_healthy(self):
        hc = HealthChecker()
        hc.register("a", lambda: ComponentHealth("a", HealthStatus.HEALTHY))
        hc.register("b", lambda: ComponentHealth("b", HealthStatus.HEALTHY))
        report = hc.check_all()
        assert report["status"] == "healthy"

    def test_check_all_degraded(self):
        hc = HealthChecker()
        hc.register("a", lambda: ComponentHealth("a", HealthStatus.HEALTHY))
        hc.register("b", lambda: ComponentHealth("b", HealthStatus.DEGRADED))
        report = hc.check_all()
        assert report["status"] == "degraded"

    def test_check_all_unhealthy(self):
        hc = HealthChecker()
        hc.register("a", lambda: ComponentHealth("a", HealthStatus.UNHEALTHY))
        report = hc.check_all()
        assert report["status"] == "unhealthy"
        assert "timestamp" in report


# ── CircuitBreaker ────────────────────────────────────────────────────


class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_stays_closed_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_opens_on_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_closes_on_success_after_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_stats(self):
        cb = CircuitBreaker("test")
        cb.record_success()
        cb.record_failure()
        stats = cb.get_stats()
        assert stats["total_calls"] == 2
        assert stats["total_failures"] == 1
        assert stats["error_rate"] == 50.0

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerRegistry:
    def test_get_or_create(self):
        reg = CircuitBreakerRegistry()
        cb1 = reg.get_or_create("api", failure_threshold=5)
        cb2 = reg.get_or_create("api")
        assert cb1 is cb2
        assert reg.count == 1

    def test_get_all_stats(self):
        reg = CircuitBreakerRegistry()
        reg.get_or_create("api-a")
        reg.get_or_create("api-b")
        stats = reg.get_all_stats()
        assert len(stats) == 2


# ── DeadLetterQueue ───────────────────────────────────────────────────


class TestDeadLetterQueue:
    def test_enqueue(self):
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "task.run"))
        assert dlq.size == 1

    def test_dequeue(self):
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "task.run"))
        item = dlq.dequeue()
        assert item is not None
        assert item.task_id == "t1"
        assert dlq.size == 0

    def test_dequeue_empty(self):
        dlq = DeadLetterQueue()
        assert dlq.dequeue() is None

    def test_peek(self):
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "task.a"))
        dlq.enqueue(DeadLetter("t2", "task.b"))
        items = dlq.peek(1)
        assert len(items) == 1
        assert dlq.size == 2  # not removed

    def test_max_size_eviction(self):
        dlq = DeadLetterQueue(max_size=2)
        dlq.enqueue(DeadLetter("t1", "task.a"))
        dlq.enqueue(DeadLetter("t2", "task.b"))
        dlq.enqueue(DeadLetter("t3", "task.c"))
        assert dlq.size == 2
        assert dlq.peek(1)[0].task_id == "t2"

    def test_retry_eligible(self):
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "task.a", max_retries=3, retry_count=0))
        dlq.enqueue(DeadLetter("t2", "task.b", max_retries=3, retry_count=3))
        eligible = dlq.retry_eligible()
        assert len(eligible) == 1
        assert eligible[0].task_id == "t1"

    def test_mark_retried(self):
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "task.a"))
        assert dlq.mark_retried("t1") is True
        assert dlq.mark_retried("nonexistent") is False

    def test_purge_all(self):
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "task.a"))
        dlq.enqueue(DeadLetter("t2", "task.b"))
        count = dlq.purge()
        assert count == 2
        assert dlq.size == 0

    def test_purge_by_age(self):
        dlq = DeadLetterQueue()
        old = DeadLetter("t1", "task.a")
        old.timestamp = time.time() - 3600
        dlq.enqueue(old)
        dlq.enqueue(DeadLetter("t2", "task.b"))
        count = dlq.purge(older_than=time.time() - 1800)
        assert count == 1
        assert dlq.size == 1

    def test_get_stats(self):
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "task.scan"))
        dlq.enqueue(DeadLetter("t2", "task.scan"))
        stats = dlq.get_stats()
        assert stats["size"] == 2
        assert stats["by_task"]["task.scan"] == 2


# ── ScanRecoveryManager ──────────────────────────────────────────────


class TestScanRecoveryManager:
    def test_save_and_get(self):
        mgr = ScanRecoveryManager()
        cp = ScanCheckpoint("s1", ScanPhase.SCANNING,
                            completed_modules=["mod_a"],
                            pending_modules=["mod_b", "mod_c"])
        mgr.save_checkpoint(cp)
        assert mgr.get_checkpoint("s1") is not None
        assert mgr.checkpoint_count == 1

    def test_get_missing(self):
        mgr = ScanRecoveryManager()
        assert mgr.get_checkpoint("missing") is None

    def test_recoverable_scans(self):
        mgr = ScanRecoveryManager()
        mgr.save_checkpoint(ScanCheckpoint("s1", ScanPhase.SCANNING))
        mgr.save_checkpoint(ScanCheckpoint("s2", ScanPhase.COMPLETED))
        mgr.save_checkpoint(ScanCheckpoint("s3", ScanPhase.FAILED))
        recoverable = mgr.get_recoverable_scans()
        assert len(recoverable) == 1
        assert recoverable[0].scan_id == "s1"

    def test_resume_plan(self):
        mgr = ScanRecoveryManager()
        mgr.save_checkpoint(ScanCheckpoint(
            "s1", ScanPhase.SCANNING,
            completed_modules=["mod_a"],
            pending_modules=["mod_b"],
            events_processed=42,
            last_event_id="ev-42",
        ))
        plan = mgr.resume_scan("s1")
        assert plan is not None
        assert plan["scan_id"] == "s1"
        assert plan["modules_to_run"] == ["mod_b"]
        assert plan["events_already_processed"] == 42

    def test_resume_completed_returns_none(self):
        mgr = ScanRecoveryManager()
        mgr.save_checkpoint(ScanCheckpoint("s1", ScanPhase.COMPLETED))
        assert mgr.resume_scan("s1") is None

    def test_resume_missing_returns_none(self):
        mgr = ScanRecoveryManager()
        assert mgr.resume_scan("missing") is None

    def test_mark_completed(self):
        mgr = ScanRecoveryManager()
        mgr.save_checkpoint(ScanCheckpoint("s1", ScanPhase.SCANNING))
        mgr.mark_completed("s1")
        cp = mgr.get_checkpoint("s1")
        assert cp.phase == ScanPhase.COMPLETED

    def test_delete_checkpoint(self):
        mgr = ScanRecoveryManager()
        mgr.save_checkpoint(ScanCheckpoint("s1", ScanPhase.SCANNING))
        assert mgr.delete_checkpoint("s1") is True
        assert mgr.delete_checkpoint("s1") is False
        assert mgr.checkpoint_count == 0


# ── DataRetentionManager ─────────────────────────────────────────────


class TestDataRetentionManager:
    def test_add_policy(self):
        mgr = DataRetentionManager()
        mgr.add_policy(RetentionPolicy("30day", 30, "scan_results"))
        assert mgr.policy_count == 1

    def test_evaluate_keeps_recent(self):
        mgr = DataRetentionManager()
        mgr.add_policy(RetentionPolicy("30day", 30, "*"))
        records = [{"type": "scan_results", "created_at": time.time()}]
        result = mgr.evaluate(records)
        assert len(result["keep"]) == 1
        assert len(result["prune"]) == 0

    def test_evaluate_prunes_old(self):
        mgr = DataRetentionManager()
        mgr.add_policy(RetentionPolicy("30day", 30, "*"))
        old_ts = time.time() - (31 * 86400)
        records = [{"type": "scan_results", "created_at": old_ts}]
        result = mgr.evaluate(records)
        assert len(result["prune"]) == 1
        assert len(mgr.audit_log) == 1

    def test_disabled_policy_ignored(self):
        mgr = DataRetentionManager()
        mgr.add_policy(RetentionPolicy("30day", 30, "*", enabled=False))
        old_ts = time.time() - (31 * 86400)
        records = [{"type": "scan_results", "created_at": old_ts}]
        result = mgr.evaluate(records)
        assert len(result["keep"]) == 1

    def test_type_filter(self):
        mgr = DataRetentionManager()
        mgr.add_policy(RetentionPolicy("logs", 7, "logs"))
        old_ts = time.time() - (10 * 86400)
        records = [
            {"type": "logs", "created_at": old_ts},
            {"type": "scan_results", "created_at": old_ts},
        ]
        result = mgr.evaluate(records)
        assert len(result["prune"]) == 1
        assert len(result["keep"]) == 1


# ── TenantIsolationValidator ─────────────────────────────────────────


class TestTenantIsolationValidator:
    def test_add_tenant(self):
        v = TenantIsolationValidator()
        v.add_tenant(TenantContext("t1", "Acme"))
        assert v.tenant_count == 1

    def test_validate_clean(self):
        v = TenantIsolationValidator()
        v.add_tenant(TenantContext("t1", "Acme"))
        results = [{"tenant_id": "t1", "data": "ok"}]
        report = v.validate_isolation("t1", results)
        assert report["valid"] is True
        assert report["violations"] == 0

    def test_validate_violation(self):
        v = TenantIsolationValidator()
        v.add_tenant(TenantContext("t1", "Acme"))
        v.add_tenant(TenantContext("t2", "Rival"))
        results = [
            {"tenant_id": "t1", "data": "ok"},
            {"tenant_id": "t2", "data": "leaked!"},
        ]
        report = v.validate_isolation("t1", results)
        assert report["valid"] is False
        assert report["violations"] == 1

    def test_add_scan(self):
        v = TenantIsolationValidator()
        v.add_tenant(TenantContext("t1", "Acme"))
        v.add_scan("t1", "scan-001")
        assert v.get_scan_owner("scan-001") == "t1"

    def test_scan_owner_not_found(self):
        v = TenantIsolationValidator()
        assert v.get_scan_owner("nonexistent") is None


# ── K8sConfigGenerator ───────────────────────────────────────────────


class TestK8sConfigGenerator:
    def test_defaults_loaded(self):
        gen = K8sConfigGenerator()
        assert gen.service_count == 3

    def test_generate_pdb(self):
        gen = K8sConfigGenerator()
        pdb = gen.generate_pdb("api")
        assert pdb["kind"] == "PodDisruptionBudget"
        assert pdb["spec"]["minAvailable"] == 1

    def test_generate_hpa(self):
        gen = K8sConfigGenerator()
        hpa = gen.generate_hpa("worker")
        assert hpa["kind"] == "HorizontalPodAutoscaler"
        assert hpa["spec"]["maxReplicas"] == 20

    def test_generate_resources(self):
        gen = K8sConfigGenerator()
        res = gen.generate_resources("api")
        assert res["resources"]["requests"]["cpu"] == "250m"
        assert res["resources"]["limits"]["memory"] == "1Gi"

    def test_missing_service(self):
        gen = K8sConfigGenerator()
        assert gen.generate_pdb("nonexistent") == {}
        assert gen.generate_hpa("nonexistent") == {}
        assert gen.generate_resources("nonexistent") == {}

    def test_add_service(self):
        gen = K8sConfigGenerator()
        gen.add_service(K8sServiceConfig("custom"))
        assert gen.service_count == 4
        pdb = gen.generate_pdb("custom")
        assert pdb["kind"] == "PodDisruptionBudget"


# ── LoadTestScenario ─────────────────────────────────────────────────


class TestLoadTestResult:
    def test_success_rate(self):
        r = LoadTestResult("test", total_requests=100,
                           successful=95, failed=5)
        assert r.success_rate == 95.0

    def test_success_rate_empty(self):
        r = LoadTestResult("test")
        assert r.success_rate == 0.0

    def test_to_dict(self):
        r = LoadTestResult("test", total_requests=10, successful=10)
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["success_rate"] == 100.0


class TestLoadTestScenario:
    def test_basic_flow(self):
        scenario = LoadTestScenario("api_test", concurrency=5)
        scenario.start()
        scenario.record_operation(10.0, True, events=5)
        scenario.record_operation(20.0, True, events=3)
        scenario.record_operation(100.0, False, events=0)
        result = scenario.finish()
        assert result.total_requests == 3
        assert result.successful == 2
        assert result.failed == 1
        assert result.avg_latency_ms == pytest.approx(43.33, abs=0.1)
        assert result.p99_latency_ms >= 100.0

    def test_empty_scenario(self):
        scenario = LoadTestScenario("empty")
        scenario.start()
        result = scenario.finish()
        assert result.total_requests == 0
        assert result.avg_latency_ms == 0.0


# ── SLOTracker ────────────────────────────────────────────────────────


class TestSLOTracker:
    def test_defaults_loaded(self):
        tracker = SLOTracker()
        assert tracker.slo_count == 4

    def test_meeting_lte(self):
        tracker = SLOTracker()
        tracker.record_measurement("api_p99_latency", 200.0)
        tracker.record_measurement("api_p99_latency", 300.0)
        assert tracker.evaluate("api_p99_latency") == SLOStatus.MEETING

    def test_breached_lte(self):
        tracker = SLOTracker()
        tracker.record_measurement("api_p99_latency", 800.0)
        tracker.record_measurement("api_p99_latency", 900.0)
        assert tracker.evaluate("api_p99_latency") == SLOStatus.BREACHED

    def test_meeting_gte(self):
        tracker = SLOTracker()
        tracker.record_measurement("events_throughput", 150.0)
        assert tracker.evaluate("events_throughput") == SLOStatus.MEETING

    def test_breached_gte(self):
        tracker = SLOTracker()
        tracker.record_measurement("events_throughput", 50.0)
        assert tracker.evaluate("events_throughput") == SLOStatus.BREACHED

    def test_at_risk_lte(self):
        tracker = SLOTracker()
        # target is 500, at-risk is 500-550
        tracker.record_measurement("api_p99_latency", 525.0)
        assert tracker.evaluate("api_p99_latency") == SLOStatus.AT_RISK

    def test_no_data(self):
        tracker = SLOTracker()
        assert tracker.evaluate("api_p99_latency") == SLOStatus.MEETING

    def test_unknown_slo(self):
        tracker = SLOTracker()
        assert tracker.evaluate("nonexistent") == SLOStatus.BREACHED

    def test_evaluate_all(self):
        tracker = SLOTracker()
        result = tracker.evaluate_all()
        assert len(result) == 4
        assert "scan_start_latency" in result

    def test_custom_slo(self):
        tracker = SLOTracker()
        tracker.add_slo(SLODefinition("custom", 99.9, "uptime", "gte"))
        assert tracker.slo_count == 5


# ── AlertManager ──────────────────────────────────────────────────────


class TestAlertManager:
    def test_defaults_loaded(self):
        mgr = AlertManager()
        assert mgr.rule_count == 4

    def test_no_alert_normal(self):
        mgr = AlertManager()
        alerts = mgr.evaluate({"scan_duration_min": 10.0})
        assert alerts == []

    def test_scan_stuck_alert(self):
        mgr = AlertManager()
        alerts = mgr.evaluate({"scan_duration_min": 45.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "scan_stuck"
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_error_rate_alert(self):
        mgr = AlertManager()
        alerts = mgr.evaluate({"error_rate_pct": 8.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "error_rate_high"

    def test_multiple_alerts(self):
        mgr = AlertManager()
        alerts = mgr.evaluate({
            "scan_duration_min": 45.0,
            "error_rate_pct": 8.0,
            "queue_depth": 15000.0,
        })
        assert len(alerts) == 3

    def test_db_pool_alert(self):
        mgr = AlertManager()
        alerts = mgr.evaluate({"db_free_connections": 0.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "db_pool_exhausted"

    def test_history(self):
        mgr = AlertManager()
        mgr.evaluate({"scan_duration_min": 45.0})
        mgr.evaluate({"error_rate_pct": 8.0})
        assert mgr.alert_count == 2
        criticals = mgr.get_history(AlertSeverity.CRITICAL)
        assert len(criticals) == 1

    def test_custom_rule(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule("cpu_high", "cpu_pct", "gt", 90.0,
                               AlertSeverity.WARNING))
        alerts = mgr.evaluate({"cpu_pct": 95.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "cpu_high"


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_health_circuit_breaker(self):
        """Health check with circuit breaker integration."""
        cb = CircuitBreaker("ext-api", failure_threshold=3)
        hc = HealthChecker()
        hc.register("ext-api", lambda: ComponentHealth(
            "ext-api",
            HealthStatus.HEALTHY if cb.state == CircuitState.CLOSED
            else HealthStatus.UNHEALTHY,
        ))

        report = hc.check_all()
        assert report["status"] == "healthy"

        for _ in range(3):
            cb.record_failure()

        report = hc.check_all()
        assert report["status"] == "unhealthy"

    def test_dlq_retry_flow(self):
        """DLQ enqueue, retry, and purge flow."""
        dlq = DeadLetterQueue()
        dlq.enqueue(DeadLetter("t1", "scan.run",
                               exception="timeout",
                               max_retries=2))
        dlq.enqueue(DeadLetter("t2", "scan.run",
                               exception="oom",
                               max_retries=2))

        eligible = dlq.retry_eligible()
        assert len(eligible) == 2

        dlq.mark_retried("t1")
        dlq.mark_retried("t1")
        eligible = dlq.retry_eligible()
        assert len(eligible) == 1  # t1 exhausted

        stats = dlq.get_stats()
        assert stats["total_retried"] == 2

    def test_scan_recovery_full_cycle(self):
        """Full scan recovery lifecycle."""
        mgr = ScanRecoveryManager()

        # Phase 1: Save initial checkpoint
        mgr.save_checkpoint(ScanCheckpoint(
            "s1", ScanPhase.SCANNING,
            completed_modules=["a", "b"],
            pending_modules=["c", "d"],
            events_processed=100,
        ))

        # Phase 2: Worker dies, new worker resumes
        plan = mgr.resume_scan("s1")
        assert plan["modules_to_run"] == ["c", "d"]

        # Phase 3: Update checkpoint after partial progress
        mgr.save_checkpoint(ScanCheckpoint(
            "s1", ScanPhase.SCANNING,
            completed_modules=["a", "b", "c"],
            pending_modules=["d"],
            events_processed=150,
        ))

        # Phase 4: Complete
        mgr.mark_completed("s1")
        assert mgr.resume_scan("s1") is None

    def test_slo_alert_integration(self):
        """SLOs trigger appropriate alerts."""
        tracker = SLOTracker()
        alerter = AlertManager()

        # Record poor performance
        tracker.record_measurement("api_p99_latency", 800.0)
        tracker.record_measurement("error_rate", 7.0)

        # Check SLOs
        status = tracker.evaluate("api_p99_latency")
        assert status == SLOStatus.BREACHED

        # Generate alerts based on same metrics
        alerts = alerter.evaluate({
            "scan_duration_min": 5.0,
            "error_rate_pct": 7.0,
        })
        assert len(alerts) == 1
        assert alerts[0].rule_name == "error_rate_high"

    def test_k8s_full_config(self):
        """Generate full K8s config for all services."""
        gen = K8sConfigGenerator()
        for svc_name in ["api", "worker", "scheduler"]:
            pdb = gen.generate_pdb(svc_name)
            hpa = gen.generate_hpa(svc_name)
            res = gen.generate_resources(svc_name)
            assert pdb["kind"] == "PodDisruptionBudget"
            assert hpa["kind"] == "HorizontalPodAutoscaler"
            assert "resources" in res
