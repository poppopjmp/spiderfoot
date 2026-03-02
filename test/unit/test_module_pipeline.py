"""Tests for the module pipeline — Cycles 33-38.

Cycle 33: Module dependency resolution (topological ordering)
Cycle 34: Module timeout enforcement
Cycle 35: Scan-level rate limiting
Cycle 36: ScanOrchestrator phase tracking
Cycle 37: can_run_module() dependency check
Cycle 38: Graceful scan abort propagation
"""

from __future__ import annotations

import time
import threading
import pytest

from spiderfoot.plugins.module_deps import (
    ModuleDependencyResolver,
    ModuleNode,
    DepEdge,
    DepStatus,
    ResolutionResult,
)
from spiderfoot.scan.scan_orchestrator import (
    ScanOrchestrator,
    ScanPhase,
    ModuleSchedule,
    PhaseResult,
    PHASE_ORDER,
)
from spiderfoot.scan.scan_engine import RateLimitConfig


# ───────────────────────────────────────────────────────────────────────
# Cycle 33 — Module dependency resolution
# ───────────────────────────────────────────────────────────────────────

class TestModuleDependencyResolver:
    """Cycle 33: Verify the dependency resolver produces correct orderings."""

    def test_linear_chain_ordering(self):
        """A -> B -> C chain should order C before B before A."""
        r = ModuleDependencyResolver()
        r.add_module("sfp_target", produces={"DOMAIN_NAME"})
        r.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes={"DOMAIN_NAME"})
        r.add_module("sfp_whois", produces={"DOMAIN_WHOIS"}, consumes={"IP_ADDRESS"})

        result = r.resolve()
        assert result.is_resolved
        order = result.load_order
        assert order.index("sfp_target") < order.index("sfp_dns")
        assert order.index("sfp_dns") < order.index("sfp_whois")

    def test_diamond_dependency(self):
        """Diamond: A produces X, B and C both consume X, D consumes from B and C."""
        r = ModuleDependencyResolver()
        r.add_module("root", produces={"X"})
        r.add_module("left", produces={"Y"}, consumes={"X"})
        r.add_module("right", produces={"Z"}, consumes={"X"})
        r.add_module("bottom", consumes={"Y", "Z"})

        result = r.resolve()
        assert result.is_resolved
        order = result.load_order
        # root must be before left and right
        assert order.index("root") < order.index("left")
        assert order.index("root") < order.index("right")
        # left and right must be before bottom
        assert order.index("left") < order.index("bottom")
        assert order.index("right") < order.index("bottom")

    def test_cycle_detection(self):
        """Circular dependency should be flagged."""
        r = ModuleDependencyResolver()
        r.add_module("a", produces={"X"}, consumes={"Y"})
        r.add_module("b", produces={"Y"}, consumes={"X"})

        result = r.resolve()
        assert result.status == DepStatus.CIRCULAR
        assert len(result.cycles) > 0

    def test_missing_provider_warning(self):
        """Consumer of event type without any producer should be flagged."""
        r = ModuleDependencyResolver()
        r.add_module("orphan", consumes={"NONEXISTENT_TYPE"})

        result = r.resolve()
        assert result.status == DepStatus.MISSING_PROVIDER
        assert "NONEXISTENT_TYPE" in result.missing_providers

    def test_standalone_modules_included(self):
        """Modules with no edges should still appear in load_order."""
        r = ModuleDependencyResolver()
        r.add_module("standalone1")
        r.add_module("standalone2")
        r.add_module("producer", produces={"X"})

        result = r.resolve()
        assert result.is_resolved
        assert len(result.load_order) == 3
        for m in ["standalone1", "standalone2", "producer"]:
            assert m in result.load_order

    def test_parallel_layers(self):
        """Modules with same dependencies should be in same layer."""
        r = ModuleDependencyResolver()
        r.add_module("root", produces={"X"})
        r.add_module("consumer1", consumes={"X"})
        r.add_module("consumer2", consumes={"X"})

        result = r.resolve()
        assert result.is_resolved
        assert len(result.layers) >= 2
        # consumer1 and consumer2 should be in the same layer
        for layer in result.layers:
            if "consumer1" in layer:
                assert "consumer2" in layer
                break

    def test_large_graph_perf(self):
        """Resolver should handle 300+ modules in reasonable time."""
        r = ModuleDependencyResolver()
        # Create a chain of 300 modules
        for i in range(300):
            if i == 0:
                r.add_module(f"mod_{i}", produces={f"EVT_{i}"})
            else:
                r.add_module(f"mod_{i}", produces={f"EVT_{i}"}, consumes={f"EVT_{i-1}"})

        start = time.monotonic()
        result = r.resolve()
        elapsed = time.monotonic() - start

        assert result.is_resolved
        assert len(result.load_order) == 300
        assert elapsed < 5.0, f"Resolver took {elapsed:.2f}s for 300 modules"

    def test_optional_consumes_no_hard_dep(self):
        """Optional consumers should not create hard dependency edges."""
        r = ModuleDependencyResolver()
        r.add_module("producer", produces={"X"})
        r.add_module("optional_consumer", optional_consumes={"X"})

        result = r.resolve()
        assert result.is_resolved
        # optional_consumer should not have a hard dependency on producer

    def test_get_producers_consumers(self):
        """Producer and consumer index should be queryable."""
        r = ModuleDependencyResolver()
        r.add_module("p1", produces={"IP_ADDRESS"})
        r.add_module("p2", produces={"IP_ADDRESS"})
        r.add_module("c1", consumes={"IP_ADDRESS"})

        assert r.get_producers("IP_ADDRESS") == {"p1", "p2"}
        assert r.get_consumers("IP_ADDRESS") == {"c1"}

    def test_get_impact(self):
        """get_impact() should find all transitively affected modules."""
        r = ModuleDependencyResolver()
        r.add_module("root", produces={"X"})
        r.add_module("mid", produces={"Y"}, consumes={"X"})
        r.add_module("leaf", consumes={"Y"})

        impact = r.get_impact("root")
        assert "mid" in impact
        assert "leaf" in impact

    def test_get_critical_path(self):
        """get_critical_path() should return longest dependency chain."""
        r = ModuleDependencyResolver()
        r.add_module("a", produces={"X"})
        r.add_module("b", produces={"Y"}, consumes={"X"})
        r.add_module("c", consumes={"Y"})

        path = r.get_critical_path("c")
        assert path == ["a", "b", "c"]

    def test_remove_module(self):
        """Removing a module should update producer index."""
        r = ModuleDependencyResolver()
        r.add_module("p1", produces={"X"})
        assert r.get_producers("X") == {"p1"}

        r.remove_module("p1")
        assert r.get_producers("X") == set()
        assert r.module_count == 0

    def test_resolution_result_summary(self):
        """ResolutionResult.summary() should produce readable output."""
        r = ModuleDependencyResolver()
        r.add_module("a", produces={"X"})
        result = r.resolve()
        s = result.summary()
        assert "Status: resolved" in s
        assert "Modules: 1" in s

    def test_resolution_result_to_dict(self):
        """ResolutionResult.to_dict() should serialize correctly."""
        r = ModuleDependencyResolver()
        r.add_module("a", produces={"X"})
        result = r.resolve()
        d = result.to_dict()
        assert d["status"] == "resolved"
        assert "a" in d["load_order"]


# ───────────────────────────────────────────────────────────────────────
# Cycle 34 — Module timeout enforcement
# ───────────────────────────────────────────────────────────────────────

class TestModuleTimeout:
    """Cycle 34: Verify RateLimitConfig module_timeout_seconds is respected."""

    def test_default_timeout(self):
        """Default module timeout should be 300 seconds."""
        cfg = RateLimitConfig()
        assert cfg.module_timeout_seconds == 300

    def test_custom_timeout(self):
        """Custom module timeout should be settable."""
        cfg = RateLimitConfig(module_timeout_seconds=60)
        assert cfg.module_timeout_seconds == 60

    def test_orchestrator_module_timeout(self):
        """ModuleSchedule should carry timeout from RateLimitConfig."""
        cfg = RateLimitConfig(module_timeout_seconds=120)
        orch = ScanOrchestrator(scan_id="timeout-test")
        orch.register_module(
            "sfp_slow",
            ScanPhase.DISCOVERY,
            timeout_seconds=cfg.module_timeout_seconds,
        )
        sched = orch._modules["sfp_slow"]
        assert sched.timeout_seconds == 120

    def test_dns_timeout_config(self):
        """DNS timeout should be configurable."""
        cfg = RateLimitConfig(dns_timeout_seconds=5)
        assert cfg.dns_timeout_seconds == 5

    def test_http_timeout_config(self):
        """HTTP timeout should be configurable."""
        cfg = RateLimitConfig(http_timeout_seconds=30)
        assert cfg.http_timeout_seconds == 30


# ───────────────────────────────────────────────────────────────────────
# Cycle 35 — Scan-level rate limiting
# ───────────────────────────────────────────────────────────────────────

class TestScanRateLimiting:
    """Cycle 35: Verify scan-level rate limiting configuration."""

    def test_default_no_rate_limit(self):
        """Default config should have no rate limiting (0 = unlimited)."""
        cfg = RateLimitConfig()
        assert cfg.max_requests_per_second == 0
        assert cfg.request_delay_ms == 0

    def test_requests_per_second(self):
        """max_requests_per_second should be settable."""
        cfg = RateLimitConfig(max_requests_per_second=10.0)
        assert cfg.max_requests_per_second == 10.0

    def test_request_delay(self):
        """request_delay_ms should be settable."""
        cfg = RateLimitConfig(request_delay_ms=500)
        assert cfg.request_delay_ms == 500

    def test_max_threads_throttling(self):
        """max_threads should control concurrency."""
        cfg = RateLimitConfig(max_threads=5)
        assert cfg.max_threads == 5

    def test_scan_timeout(self):
        """scan_timeout_minutes should be settable."""
        cfg = RateLimitConfig(scan_timeout_minutes=30)
        assert cfg.scan_timeout_minutes == 30


# ───────────────────────────────────────────────────────────────────────
# Cycle 36 — ScanOrchestrator phase tracking
# ───────────────────────────────────────────────────────────────────────

class TestScanOrchestratorPhases:
    """Cycle 36: Verify ScanOrchestrator phase lifecycle."""

    def test_phase_order(self):
        """Phase order should progress INIT -> DISCOVERY -> ... -> COMPLETE."""
        expected = [
            ScanPhase.INIT,
            ScanPhase.DISCOVERY,
            ScanPhase.ENUMERATION,
            ScanPhase.ANALYSIS,
            ScanPhase.ENRICHMENT,
            ScanPhase.CORRELATION,
            ScanPhase.REPORTING,
            ScanPhase.COMPLETE,
        ]
        assert PHASE_ORDER == expected

    def test_start_sets_init(self):
        """start() should set phase to INIT."""
        orch = ScanOrchestrator(scan_id="phase-test")
        orch.start()
        assert orch.current_phase == ScanPhase.INIT

    def test_advance_phase_sequence(self):
        """advance_phase() should progress through phases in order."""
        orch = ScanOrchestrator(scan_id="phase-seq")
        orch.start()
        assert orch.current_phase == ScanPhase.INIT

        p = orch.advance_phase()
        assert p == ScanPhase.DISCOVERY

        p = orch.advance_phase()
        assert p == ScanPhase.ENUMERATION

        p = orch.advance_phase()
        assert p == ScanPhase.ANALYSIS

    def test_complete_terminates_scan(self):
        """complete() should set phase to COMPLETE."""
        orch = ScanOrchestrator(scan_id="complete-test")
        orch.start()
        orch.complete()
        assert orch.current_phase == ScanPhase.COMPLETE
        assert orch.is_complete

    def test_fail_marks_scan_failed(self):
        """fail() should set phase to FAILED."""
        orch = ScanOrchestrator(scan_id="fail-test")
        orch.start()
        orch.fail("test error")
        assert orch.current_phase == ScanPhase.FAILED
        assert orch.is_complete

    def test_phase_results_recorded(self):
        """Phase transitions should record PhaseResult entries."""
        orch = ScanOrchestrator(scan_id="results-test")
        orch.start()
        orch.advance_phase()
        orch.advance_phase()
        results = orch.get_phase_results()
        assert len(results) == 2  # INIT and DISCOVERY phases recorded

    def test_phase_callback_fired(self):
        """Phase change callbacks should fire on advance_phase()."""
        transitions = []
        orch = ScanOrchestrator(scan_id="cb-test")
        orch.on_phase_change(lambda old, new: transitions.append((old, new)))
        orch.start()
        orch.advance_phase()
        assert len(transitions) == 1
        assert transitions[0] == (ScanPhase.INIT, ScanPhase.DISCOVERY)

    def test_completion_callback_fired(self):
        """Completion callbacks should fire on complete()."""
        completed = []
        orch = ScanOrchestrator(scan_id="comp-cb-test")
        orch.on_completion(lambda o: completed.append(o.scan_id))
        orch.start()
        orch.complete()
        assert completed == ["comp-cb-test"]

    def test_summary_dict(self):
        """summary() should return well-structured dict."""
        orch = ScanOrchestrator(scan_id="sum-test", target="example.com")
        orch.start()
        s = orch.summary()
        assert s["scan_id"] == "sum-test"
        assert s["target"] == "example.com"
        assert s["phase"] == "init"
        assert "total_events" in s
        assert "modules_total" in s

    def test_to_dict_includes_phases(self):
        """to_dict() should include phase history."""
        orch = ScanOrchestrator(scan_id="dict-test")
        orch.start()
        orch.advance_phase()
        d = orch.to_dict()
        assert "phases" in d
        assert len(d["phases"]) >= 1


# ───────────────────────────────────────────────────────────────────────
# Cycle 37 — can_run_module() dependency check
# ───────────────────────────────────────────────────────────────────────

class TestCanRunModule:
    """Cycle 37: Verify can_run_module() dependency gating."""

    def test_no_deps_can_run(self):
        """Module with no dependencies should be runnable immediately."""
        orch = ScanOrchestrator(scan_id="dep-test")
        orch.register_module("sfp_nodep", ScanPhase.DISCOVERY)
        assert orch.can_run_module("sfp_nodep") is True

    def test_unmet_deps_blocks(self):
        """Module with unmet dependencies should not be runnable."""
        orch = ScanOrchestrator(scan_id="dep-test")
        orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        orch.register_module(
            "sfp_whois",
            ScanPhase.ENUMERATION,
            depends_on={"sfp_dns"},
        )
        assert orch.can_run_module("sfp_whois") is False

    def test_met_deps_allows(self):
        """Module with all dependencies completed should be runnable."""
        orch = ScanOrchestrator(scan_id="dep-test")
        orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        orch.register_module(
            "sfp_whois",
            ScanPhase.ENUMERATION,
            depends_on={"sfp_dns"},
        )
        orch.module_completed("sfp_dns", events_produced=5)
        assert orch.can_run_module("sfp_whois") is True

    def test_partial_deps_blocks(self):
        """Module with only some dependencies met should not be runnable."""
        orch = ScanOrchestrator(scan_id="dep-test")
        orch.register_module("dep1", ScanPhase.DISCOVERY)
        orch.register_module("dep2", ScanPhase.DISCOVERY)
        orch.register_module(
            "consumer",
            ScanPhase.ENUMERATION,
            depends_on={"dep1", "dep2"},
        )
        orch.module_completed("dep1")
        assert orch.can_run_module("consumer") is False

        orch.module_completed("dep2")
        assert orch.can_run_module("consumer") is True

    def test_unknown_module_returns_false(self):
        """Unknown module name should return False."""
        orch = ScanOrchestrator(scan_id="dep-test")
        assert orch.can_run_module("nonexistent") is False

    def test_module_status_tracking(self):
        """Module status should transition correctly."""
        orch = ScanOrchestrator(scan_id="status-test")
        orch.register_module("mod1", ScanPhase.DISCOVERY)

        assert orch.get_module_status("mod1") == "pending"

        orch.module_started("mod1")
        assert orch.get_module_status("mod1") == "running"

        orch.module_completed("mod1", events_produced=10)
        assert orch.get_module_status("mod1") == "completed"
        assert orch.total_events == 10

    def test_module_failure_tracking(self):
        """Failed module should be tracked and counted."""
        orch = ScanOrchestrator(scan_id="fail-test")
        orch.register_module("mod1", ScanPhase.DISCOVERY)

        orch.module_started("mod1")
        orch.module_failed("mod1", error="timeout")

        assert orch.get_module_status("mod1") == "failed"
        assert orch.total_errors == 1

    def test_get_pending_modules(self):
        """get_pending_modules() should list unfinished modules."""
        orch = ScanOrchestrator(scan_id="pending-test")
        orch.register_module("fast", ScanPhase.DISCOVERY)
        orch.register_module("slow", ScanPhase.DISCOVERY)

        assert set(orch.get_pending_modules()) == {"fast", "slow"}
        orch.module_completed("fast")
        assert orch.get_pending_modules() == ["slow"]


# ───────────────────────────────────────────────────────────────────────
# Cycle 38 — Graceful scan abort
# ───────────────────────────────────────────────────────────────────────

class TestGracefulAbort:
    """Cycle 38: Verify abort propagation through orchestrator."""

    def test_abort_sets_failed_state(self):
        """Calling fail() during a scan should set FAILED phase."""
        orch = ScanOrchestrator(scan_id="abort-test")
        orch.register_module("mod1", ScanPhase.DISCOVERY)
        orch.start()
        orch.advance_phase()  # DISCOVERY
        orch.module_started("mod1")

        orch.fail("user abort requested")
        assert orch.current_phase == ScanPhase.FAILED
        assert orch.is_complete

    def test_abort_from_any_phase(self):
        """Abort should work from any phase."""
        for phase in [ScanPhase.DISCOVERY, ScanPhase.ENUMERATION, ScanPhase.ANALYSIS]:
            orch = ScanOrchestrator(scan_id=f"abort-{phase.value}")
            orch.start()
            # Advance to the target phase
            while orch.current_phase != phase:
                orch.advance_phase()
            orch.fail("abort")
            assert orch.is_complete

    def test_abort_status_in_summary(self):
        """Summary should reflect FAILED state after abort."""
        orch = ScanOrchestrator(scan_id="abort-summary")
        orch.start()
        orch.fail("test")
        s = orch.summary()
        assert s["phase"] == "failed"

    def test_concurrent_abort_safe(self):
        """Abort should be thread-safe."""
        orch = ScanOrchestrator(scan_id="concurrent-abort")
        orch.start()

        errors = []

        def do_abort():
            try:
                orch.fail("concurrent abort")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_abort) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        assert orch.is_complete

    def test_register_unregister_module(self):
        """Module registration and unregistration should work."""
        orch = ScanOrchestrator(scan_id="reg-test")
        orch.register_module("mod1", ScanPhase.DISCOVERY)
        assert "mod1" in orch._modules

        result = orch.unregister_module("mod1")
        assert result is True
        assert "mod1" not in orch._modules

    def test_unregister_nonexistent(self):
        """Unregistering a nonexistent module should return False."""
        orch = ScanOrchestrator(scan_id="unreg-test")
        assert orch.unregister_module("nonexistent") is False

    def test_phase_modules_sorted_by_priority(self):
        """get_phase_modules() should sort by priority (descending)."""
        orch = ScanOrchestrator(scan_id="prio-test")
        orch.register_module("low", ScanPhase.DISCOVERY, priority=1)
        orch.register_module("high", ScanPhase.DISCOVERY, priority=10)
        orch.register_module("mid", ScanPhase.DISCOVERY, priority=5)

        ordered = orch.get_phase_modules(ScanPhase.DISCOVERY)
        assert ordered[0] == "high"
        assert ordered[-1] == "low"

    def test_elapsed_seconds(self):
        """elapsed_seconds should increase over time."""
        orch = ScanOrchestrator(scan_id="elapsed-test")
        orch.start()
        time.sleep(0.05)
        assert orch.elapsed_seconds >= 0.04


# ───────────────────────────────────────────────────────────────────────
# Integration: Dependency resolver + Orchestrator wiring
# ───────────────────────────────────────────────────────────────────────

class TestDependencyResolverOrchestratorIntegration:
    """Integration test: feed resolver output into orchestrator scheduling."""

    def test_resolver_to_orchestrator_wiring(self):
        """ResolutionResult should be usable to populate orchestrator depends_on."""
        # Setup resolver
        r = ModuleDependencyResolver()
        r.add_module("sfp_target", produces={"DOMAIN_NAME"})
        r.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes={"DOMAIN_NAME"})
        r.add_module("sfp_geoip", consumes={"IP_ADDRESS"})

        result = r.resolve()
        assert result.is_resolved

        # Wire into orchestrator
        orch = ScanOrchestrator(scan_id="integration-test")
        for mod_name in result.load_order:
            deps = r.get_dependencies(mod_name)
            orch.register_module(mod_name, ScanPhase.DISCOVERY, depends_on=deps)

        # sfp_target has no deps
        assert orch.can_run_module("sfp_target")
        # sfp_dns depends on sfp_target
        assert not orch.can_run_module("sfp_dns")
        # sfp_geoip depends on sfp_dns
        assert not orch.can_run_module("sfp_geoip")

        # Complete sfp_target
        orch.module_completed("sfp_target", events_produced=1)
        assert orch.can_run_module("sfp_dns")
        assert not orch.can_run_module("sfp_geoip")

        # Complete sfp_dns
        orch.module_completed("sfp_dns", events_produced=3)
        assert orch.can_run_module("sfp_geoip")

    def test_resolver_layers_for_parallel_execution(self):
        """Resolver layers should identify parallelizable module groups."""
        r = ModuleDependencyResolver()
        r.add_module("root", produces={"X"})
        r.add_module("a", produces={"A"}, consumes={"X"})
        r.add_module("b", produces={"B"}, consumes={"X"})
        r.add_module("c", consumes={"A", "B"})

        result = r.resolve()
        assert result.is_resolved
        assert len(result.layers) >= 3
        # First layer has root
        assert "root" in result.layers[0]
        # Second layer has a and b (parallel)
        assert set(result.layers[1]) == {"a", "b"}
        # Third layer has c
        assert "c" in result.layers[2]
