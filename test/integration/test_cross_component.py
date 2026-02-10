"""Integration tests for cross-component interactions.

Tests verify that the major subsystems work together correctly:
event pipeline + filters, sandbox + metrics, orchestrator + policies,
correlation + pipeline, export with filtered events, etc.
"""
from __future__ import annotations

import time
import unittest
from spiderfoot.event_filter import (
    EventFilterChain, TypeFilter, RiskFilter,
)
from spiderfoot.event_pipeline import (
    EventPipeline, PipelineEvent, ValidatorStage, TransformStage,
    TaggingStage, RouterStage, FunctionStage, StageResult,
)
from spiderfoot.module_sandbox import (
    ModuleSandbox, SandboxManager, ResourceLimits, SandboxState,
)
from spiderfoot.module_metrics import MetricsCollector, MetricType
from spiderfoot.scan_orchestrator import ScanOrchestrator, ScanPhase
from spiderfoot.scan_policy import ScanPolicy, PolicyEngine, PolicyAction
from spiderfoot.correlation_rules import (
    CorrelationEngine, CorrelationRule, Condition, ConditionOp, MatchMode,
)
from spiderfoot.data_export import (
    ExportEvent, ExportOptions, ExportRegistry,
)
from spiderfoot.module_deps import ModuleDependencyResolver


class TestPipelineWithFilters(unittest.TestCase):
    """Test EventPipeline integrated with EventFilterChain."""

    def test_filter_stage_blocks_events(self):
        """A pipeline stage that uses a filter chain to drop events."""
        fchain = EventFilterChain()
        fchain.add(TypeFilter(allowed_types={"IP_ADDRESS", "DOMAIN_NAME"}))

        def filter_stage(event):
            passed = fchain.check(event.event_type, event.data)
            if not passed:
                event.drop()
            return StageResult.CONTINUE

        pipeline = EventPipeline()
        pipeline.add_stage(FunctionStage(filter_stage, name="filter"))

        e1 = PipelineEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        e2 = PipelineEvent("EMAIL_ADDRESS", "a@b.com", "sfp_email")

        pipeline.execute(e1)
        pipeline.execute(e2)

        self.assertFalse(e1.is_dropped)
        self.assertTrue(e2.is_dropped)

    def test_pipeline_validator_then_transform(self):
        """Validator + Transform stages in sequence."""
        pipeline = EventPipeline()
        pipeline.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS"}))
        pipeline.add_stage(TransformStage(lambda d: d.strip()))

        e = PipelineEvent("IP_ADDRESS", "  1.2.3.4  ", "sfp_dns")
        pipeline.execute(e)
        self.assertTrue(e.data == "1.2.3.4")

    def test_pipeline_tagging_and_routing(self):
        """Tagging + Routing stages chain together."""
        pipeline = EventPipeline()
        tag = TaggingStage()
        tag.add_rule("192.168.", "internal")  # substring match
        pipeline.add_stage(tag)

        router = RouterStage()
        router.add_route(lambda e: "internal" in e.tags, "internal_handler")
        pipeline.add_stage(router)

        e = PipelineEvent("IP_ADDRESS", "192.168.1.1", "sfp_dns")
        pipeline.execute(e)
        self.assertIn("internal", e.tags)
        self.assertIn("internal_handler", e.metadata.get("_routes", []))


class TestSandboxWithMetrics(unittest.TestCase):
    """Test ModuleSandbox with MetricsCollector."""

    def setUp(self):
        MetricsCollector.reset_instance()

    def test_sandbox_records_metrics(self):
        """Sandbox execution results are recorded to metrics."""
        collector = MetricsCollector.get_instance()
        sandbox = ModuleSandbox("sfp_dns", ResourceLimits(max_execution_seconds=5))

        def module_func(tracker):
            metrics = collector.get_module("sfp_dns")
            metrics.increment("events_produced", 10)
            metrics.record_time("execution_time", 0.5)
            for _ in range(10):
                tracker.record_event()
            return 10

        result = sandbox.execute(module_func)
        self.assertTrue(result.success)
        self.assertEqual(result.events_produced, 10)

        mod_metrics = collector.get_module("sfp_dns")
        d = mod_metrics.to_dict()
        self.assertIn("events_produced", d["metrics"])
        self.assertEqual(d["metrics"]["events_produced"]["value"], 10)

    def test_sandbox_failure_tracked_in_metrics(self):
        """Failed sandbox records error metrics."""
        collector = MetricsCollector.get_instance()

        def module_func(tracker):
            metrics = collector.get_module("sfp_bad")
            metrics.increment("errors")
            raise RuntimeError("module crash")

        sandbox = ModuleSandbox("sfp_bad")
        result = sandbox.execute(module_func)
        self.assertFalse(result.success)

        d = collector.get_module("sfp_bad").to_dict()
        self.assertIn("errors", d["metrics"])
        self.assertEqual(d["metrics"]["errors"]["value"], 1)


class TestOrchestratorWithPolicy(unittest.TestCase):
    """Test ScanOrchestrator with ScanPolicy enforcement."""

    def test_policy_blocks_module_registration(self):
        """Policy denies a module, orchestrator respects it."""
        policy = ScanPolicy("strict")
        policy.restrict_modules(denied=["sfp_malware"])

        orch = ScanOrchestrator("scan1", "example.com")

        # Check policy before registering
        check = policy.check_module("sfp_malware")
        self.assertFalse(check.allowed)

        check2 = policy.check_module("sfp_dns")
        self.assertTrue(check2.allowed)

        # Only register allowed modules
        if policy.check_module("sfp_dns").allowed:
            orch.register_module("sfp_dns", ScanPhase.DISCOVERY)
        if policy.check_module("sfp_malware").allowed:
            orch.register_module("sfp_malware", ScanPhase.ANALYSIS)

        # get_phase_modules returns List[str]
        modules = orch.get_phase_modules(ScanPhase.DISCOVERY)
        self.assertEqual(len(modules), 1)
        self.assertEqual(modules[0], "sfp_dns")

        analysis_modules = orch.get_phase_modules(ScanPhase.ANALYSIS)
        self.assertEqual(len(analysis_modules), 0)

    def test_policy_engine_multi_policy(self):
        """Multiple policies evaluated by PolicyEngine."""
        engine = PolicyEngine()
        p1 = ScanPolicy("no_dangerous").restrict_modules(denied=["sfp_exploit"])
        p2 = ScanPolicy("scope").exclude_targets(["*.internal.corp"])

        engine.add_policy(p1)
        engine.add_policy(p2)

        mod_result = engine.evaluate_module("sfp_exploit")
        self.assertFalse(mod_result.allowed)

        target_result = engine.evaluate_target("host.internal.corp")
        self.assertFalse(target_result.allowed)

        target_ok = engine.evaluate_target("example.com")
        self.assertTrue(target_ok.allowed)


class TestCorrelationWithPipeline(unittest.TestCase):
    """Test CorrelationEngine fed by EventPipeline."""

    def test_pipeline_feeds_correlation_engine(self):
        """Events flow through pipeline into correlation engine."""
        engine = CorrelationEngine()
        rule = CorrelationRule(name="Multiple IPs")
        rule.add_condition(Condition("type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.set_threshold(count=2, window_seconds=60.0)
        engine.add_rule(rule)

        matches = []
        engine.on_match(lambda m: matches.append(m))

        pipeline = EventPipeline()

        def correlate_stage(event):
            evt = {"type": event.event_type, "data": event.data}
            engine.process(evt)
            return StageResult.CONTINUE

        pipeline.add_stage(FunctionStage(correlate_stage, name="correlate"))

        for ip in ["1.1.1.1", "2.2.2.2", "3.3.3.3"]:
            e = PipelineEvent("IP_ADDRESS", ip, "sfp_dns")
            pipeline.execute(e)

        self.assertTrue(len(matches) > 0)

    def test_correlation_with_group_by(self):
        """Correlation groups by module field."""
        engine = CorrelationEngine()
        rule = CorrelationRule(name="Module Events")
        rule.add_condition(Condition("type", ConditionOp.EQUALS, "IP_ADDRESS"))
        rule.set_threshold(count=2, window_seconds=60.0)
        rule.set_group_by("module")
        engine.add_rule(rule)

        matches = []
        engine.on_match(lambda m: matches.append(m))

        engine.process({"type": "IP_ADDRESS", "data": "1.1.1.1", "module": "sfp_dns"})
        engine.process({"type": "IP_ADDRESS", "data": "2.2.2.2", "module": "sfp_dns"})
        engine.process({"type": "IP_ADDRESS", "data": "3.3.3.3", "module": "sfp_other"})

        # Threshold met for sfp_dns group
        self.assertTrue(len(matches) > 0)


class TestExportWithFiltering(unittest.TestCase):
    """Test ExportRegistry with filtered events."""

    def test_export_high_risk_only(self):
        """Export only high-risk events via JSON."""
        events = [
            ExportEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns", risk=9),
            ExportEvent("EMAIL_ADDRESS", "a@b.com", "sfp_email", risk=2),
            ExportEvent("DOMAIN_NAME", "evil.com", "sfp_dns", risk=8),
        ]

        registry = ExportRegistry()
        opts = ExportOptions(min_risk=7)
        output = registry.export("json", events, opts)
        self.assertIn("1.2.3.4", output)
        self.assertIn("evil.com", output)
        self.assertNotIn("a@b.com", output)

    def test_export_summary_with_risk_distribution(self):
        """Summary export shows risk distribution."""
        # Risk thresholds: >=90 critical, >=70 high, >=40 medium, >=10 low, <10 info
        events = [
            ExportEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns", risk=95),
            ExportEvent("IP_ADDRESS", "5.6.7.8", "sfp_dns", risk=50),
            ExportEvent("EMAIL_ADDRESS", "a@b.com", "sfp_email", risk=5),
        ]

        registry = ExportRegistry()
        output = registry.export("summary", events)
        self.assertIn("critical", output.lower())

    def test_export_csv_module_filter(self):
        """CSV export filtered to specific modules."""
        events = [
            ExportEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns", risk=5),
            ExportEvent("EMAIL_ADDRESS", "a@b.com", "sfp_email", risk=3),
        ]

        registry = ExportRegistry()
        opts = ExportOptions(modules={"sfp_dns"})
        output = registry.export("csv", events, opts)
        self.assertIn("1.2.3.4", output)
        self.assertNotIn("a@b.com", output)


class TestDependencyResolverWithOrchestrator(unittest.TestCase):
    """Test ModuleDependencyResolver influencing ScanOrchestrator."""

    def test_dependency_order_informs_scheduling(self):
        """Resolved order used for module scheduling."""
        resolver = ModuleDependencyResolver()
        resolver.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes=set())
        resolver.add_module("sfp_whois", produces={"WHOIS_INFO"}, consumes={"IP_ADDRESS"})
        resolver.add_module("sfp_geoip", produces={"GEO_INFO"}, consumes={"IP_ADDRESS"})

        result = resolver.resolve()
        self.assertTrue(result.load_order.index("sfp_dns") < result.load_order.index("sfp_whois"))
        self.assertTrue(result.load_order.index("sfp_dns") < result.load_order.index("sfp_geoip"))

        # Use resolved order to set priorities in orchestrator (higher priority = runs first)
        orch = ScanOrchestrator("scan1", "example.com")
        total = len(result.load_order)
        for i, mod in enumerate(result.load_order):
            orch.register_module(mod, ScanPhase.DISCOVERY, priority=total - i)

        # get_phase_modules returns List[str] sorted by descending priority
        modules = orch.get_phase_modules(ScanPhase.DISCOVERY)
        self.assertEqual(modules[0], "sfp_dns")


class TestSandboxManagerWorkflow(unittest.TestCase):
    """Test full sandbox manager workflow."""

    def test_multi_module_sandbox_execution(self):
        """Multiple modules execute in sandboxes and results are tracked."""
        mgr = SandboxManager(ResourceLimits(max_execution_seconds=5))

        results = []
        for mod_name in ["sfp_dns", "sfp_whois", "sfp_geoip"]:
            sb = mgr.get_sandbox(mod_name)
            r = sb.execute(lambda t: 3)
            mgr.record_result(r)
            results.append(r)

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))
        self.assertEqual(mgr.sandbox_count, 3)

        summary = mgr.summary()
        self.assertEqual(summary["total_sandboxes"], 3)
        self.assertEqual(summary["total_results"], 3)

    def test_mixed_success_failure(self):
        """Manager tracks mixed success/failure results."""
        mgr = SandboxManager()

        sb1 = mgr.get_sandbox("sfp_good")
        sb1.execute(lambda t: 1)

        sb2 = mgr.get_sandbox("sfp_bad")
        sb2.execute(lambda t: (_ for _ in ()).throw(ValueError("x")))

        failed = mgr.get_failed_modules()
        self.assertIn("sfp_bad", failed)
        self.assertNotIn("sfp_good", failed)


class TestEndToEndScanWorkflow(unittest.TestCase):
    """End-to-end workflow test combining multiple subsystems."""

    def test_full_scan_lifecycle(self):
        """Simulate a complete scan: policy check -> orchestrate -> pipeline -> export."""
        # 1. Policy check
        policy = ScanPolicy("default")
        policy.restrict_modules(denied=["sfp_exploit"])
        target_check = policy.check_target("example.com")
        self.assertTrue(target_check.allowed)

        # 2. Resolve dependencies
        resolver = ModuleDependencyResolver()
        resolver.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes=set())
        resolver.add_module("sfp_whois", produces={"WHOIS_INFO"}, consumes={"IP_ADDRESS"})
        result = resolver.resolve()
        self.assertEqual(result.load_order[0], "sfp_dns")

        # 3. Set up orchestrator
        orch = ScanOrchestrator("scan_001", "example.com")
        total = len(result.load_order)
        for i, mod in enumerate(result.load_order):
            if policy.check_module(mod).allowed:
                orch.register_module(mod, ScanPhase.DISCOVERY, priority=total - i)

        orch.start()

        # 4. Set up pipeline
        pipeline = EventPipeline()
        pipeline.add_stage(ValidatorStage(allowed_types={"IP_ADDRESS", "WHOIS_INFO"}))
        pipeline.add_stage(TransformStage(lambda d: d.strip()))

        # 5. Process events through pipeline
        collected_events = []
        e = PipelineEvent("IP_ADDRESS", "  93.184.216.34  ", "sfp_dns")
        pipeline.execute(e)
        if not e.is_dropped:
            collected_events.append(
                ExportEvent(e.event_type, e.data, e.module, risk=5)
            )

        # 6. Advance orchestrator
        orch.advance_phase()  # DISCOVERY -> ENUMERATION
        self.assertEqual(orch.current_phase, ScanPhase.ENUMERATION)

        # 7. Export results
        registry = ExportRegistry()
        json_output = registry.export("json", collected_events)
        self.assertIn("93.184.216.34", json_output)

        summary_output = registry.export("summary", collected_events)
        self.assertIn("1", summary_output)  # 1 event


if __name__ == "__main__":
    unittest.main()
