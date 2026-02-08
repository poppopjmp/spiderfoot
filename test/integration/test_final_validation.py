"""Final validation suite — cross-module integration tests for Cycles 89-98.

Tests interactions between the new infrastructure components:
event_taxonomy + event_store, scan_templates + scan_workflow,
result_cache + event_store, alert_rules + event_store,
module_versioning + scan_templates, and full pipeline compositions.
"""

import time
import pytest

from spiderfoot.event_taxonomy import EventCategory, RiskLevel, EventTaxonomy
from spiderfoot.scan_templates import TemplateCategory, ScanTemplate, TemplateRegistry
from spiderfoot.result_cache import ResultCache, ScanResultCache, EvictionPolicy
from spiderfoot.module_api_client import ModuleApiClient, RateLimiter, RequestConfig
from spiderfoot.alert_rules import (
    AlertSeverity, AlertConditionType, AlertCondition, AlertRule, AlertEngine,
)
from spiderfoot.scan_workflow import (
    StepStatus, ModuleStep, SequenceStep, ParallelStep,
    ConditionalStep, ScanWorkflow,
)
from spiderfoot.module_versioning import (
    SemanticVersion, VersionBump, ModuleVersionInfo, ModuleVersionRegistry,
)
from spiderfoot.event_store import (
    EventPriority, StoredEvent, EventQuery, RetentionPolicy, EventStore,
)


class TestTaxonomyWithEventStore:
    """Validate taxonomy-guided event storage."""

    def test_store_events_by_taxonomy_category(self):
        taxonomy = EventTaxonomy()
        store = EventStore()

        # Store events and validate types exist in taxonomy
        for etype in ["IP_ADDRESS", "DOMAIN_NAME", "EMAILADDR"]:
            assert taxonomy.exists(etype), f"{etype} should be in taxonomy"
            store.store(StoredEvent(
                event_id=f"e_{etype}",
                scan_id="s1",
                event_type=etype,
                module="sfp_test",
                data=f"test_{etype}",
                priority=EventPriority.MEDIUM,
            ))

        assert store.count() == 3
        types_in_store = store.get_event_types()
        for t in types_in_store:
            assert taxonomy.exists(t)

    def test_query_events_by_risk_level(self):
        taxonomy = EventTaxonomy()
        store = EventStore()

        store.store(StoredEvent("e1", "s1", "VULNERABILITY_CVE_CRITICAL",
                                "sfp_vuln", "CVE-2024-001", priority=EventPriority.CRITICAL))
        store.store(StoredEvent("e2", "s1", "IP_ADDRESS",
                                "sfp_dns", "1.2.3.4", priority=EventPriority.LOW))

        critical_events = store.query(EventQuery(min_priority=EventPriority.CRITICAL))
        assert len(critical_events) == 1
        assert critical_events[0].event_type == "VULNERABILITY_CVE_CRITICAL"


class TestTemplatesWithWorkflow:
    """Convert scan templates into executable workflows."""

    def test_template_to_workflow(self):
        registry = TemplateRegistry()
        template = registry.get("passive_recon")
        assert template is not None

        # Build workflow from template modules
        wf = ScanWorkflow(template.name, template.description)
        par = ParallelStep("modules")
        for mod in list(template.modules)[:3]:
            par.add_step(ModuleStep(mod, mod))
        wf.add_step(par)

        result = wf.execute()
        assert result.status == StepStatus.COMPLETED
        assert len(wf.steps) == 1  # the parallel step

    def test_template_chain_to_sequence(self):
        reg = TemplateRegistry()
        recon = reg.get("passive_recon")
        vuln = reg.get("vulnerability_scan")
        assert recon and vuln

        wf = ScanWorkflow("chained_scan")
        seq = SequenceStep("phases")
        seq.add_step(ModuleStep("phase1_recon", list(recon.modules)[0]))
        seq.add_step(ModuleStep("phase2_vuln", list(vuln.modules)[0]))
        wf.add_step(seq)

        result = wf.execute()
        assert result.status == StepStatus.COMPLETED


class TestCacheWithEventStore:
    """Validate result caching alongside event storage."""

    def test_cache_query_results(self):
        store = EventStore()
        cache = ScanResultCache()

        for i in range(10):
            store.store(StoredEvent(f"e{i}", "s1", "IP_ADDRESS",
                                    "sfp_dns", f"10.0.0.{i}"))

        # First query — cache miss
        results = store.query(EventQuery(scan_id="s1"))
        cache.store_result("s1", "sfp_dns", [e.to_dict() for e in results])
        assert cache.stats.sets == 1

        # Second access — cache hit
        cached = cache.get_result("s1", "sfp_dns")
        assert len(cached) == 10
        assert cache.stats.hits == 1

    def test_cache_invalidation_on_new_events(self):
        store = EventStore()
        cache = ScanResultCache()

        store.store(StoredEvent("e1", "s1", "IP", "sfp_dns", "1.1.1.1"))
        cache.store_result("s1", "sfp_dns", ["1.1.1.1"])

        # New event invalidates cache
        store.store(StoredEvent("e2", "s1", "IP", "sfp_dns", "2.2.2.2"))
        cache.invalidate_scan("s1")
        assert cache.get_result("s1", "sfp_dns") is None


class TestAlertRulesWithEventStore:
    """Alert engine reacting to stored events."""

    def test_alerts_on_critical_events(self):
        store = EventStore()
        engine = AlertEngine()

        rule = AlertRule("critical_finding", severity=AlertSeverity.CRITICAL,
                         message_template="Critical: {event_type}")
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 90))
        engine.add_rule(rule)

        event = StoredEvent("e1", "s1", "VULNERABILITY_CVE_CRITICAL",
                           "sfp_vuln", "CVE-2024-999", priority=EventPriority.CRITICAL)
        store.store(event)

        alerts = engine.process_event({
            "event_type": event.event_type,
            "risk_score": 95,
            "data": event.data,
        })
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_no_alert_for_low_risk(self):
        engine = AlertEngine()
        rule = AlertRule("high_risk", severity=AlertSeverity.HIGH)
        rule.add_condition(AlertCondition(AlertConditionType.SEVERITY, 70))
        engine.add_rule(rule)

        alerts = engine.process_event({"risk_score": 30})
        assert len(alerts) == 0


class TestVersioningWithTemplates:
    """Module versioning validates template module compatibility."""

    def test_template_modules_versioned(self):
        reg = ModuleVersionRegistry()
        template = TemplateRegistry().get("passive_recon")
        assert template is not None

        # Register all template modules with versions
        for mod in template.modules:
            reg.register(mod, "1.0.0")

        assert len(reg.list_modules()) == len(template.modules)

        # Bump one module
        info = reg.get(list(template.modules)[0])
        info.bump(VersionBump.MINOR, "New feature")
        assert str(info.current_version) == "1.1.0"

    def test_dependency_check_across_modules(self):
        reg = ModuleVersionRegistry()
        dns_info = reg.register("sfp_dns", "2.0.0")
        reg.register("sfp_resolver", "1.5.0")
        dns_info.add_dependency("sfp_resolver", ">=1.0.0")

        assert reg.check_compatibility("sfp_dns", "sfp_resolver", "1.5.0")
        assert not reg.check_compatibility("sfp_dns", "sfp_resolver", "0.5.0")


class TestApiClientWithCache:
    """API client with result caching."""

    def test_cache_api_responses(self):
        client = ModuleApiClient(base_url="https://api.example.com")
        cache = ResultCache(default_ttl=60)

        url = client.build_url("/lookup", {"q": "example.com"})
        key = cache._make_key(url)

        # Simulate a cached response
        cache.set(key, {"result": "data"})
        cached = cache.get(key)
        assert cached == {"result": "data"}

    def test_api_client_stats(self):
        client = ModuleApiClient()
        client.get("https://example.com/a")
        client.get("https://example.com/b")
        stats = client.get_stats()
        assert stats["total"] == 2


class TestWorkflowWithAlerts:
    """Workflow that triggers alerts on specific conditions."""

    def test_conditional_alert_workflow(self):
        engine = AlertEngine()
        rule = AlertRule("scan_complete", severity=AlertSeverity.INFO,
                         message_template="Scan completed")
        rule.add_condition(AlertCondition(AlertConditionType.CUSTOM,
                                         lambda ctx: ctx.get("scan_done", False)))
        engine.add_rule(rule)

        wf = ScanWorkflow("alert_wf")
        wf.add_step(ModuleStep("dns", "sfp_dns"))
        wf.add_step(ConditionalStep(
            "check_results",
            condition=lambda ctx: True,
            if_true=ModuleStep("deep", "sfp_deep"),
        ))
        result = wf.execute()

        # After workflow, fire alert
        alerts = engine.process_event({"scan_done": True})
        assert len(alerts) == 1
        assert result.status == StepStatus.COMPLETED


class TestFullPipeline:
    """End-to-end: template → workflow → store → cache → alert."""

    def test_end_to_end(self):
        # 1. Pick a template
        template = TemplateRegistry().get("passive_recon")
        assert template is not None

        # 2. Version the modules
        ver_reg = ModuleVersionRegistry()
        for mod in list(template.modules)[:3]:
            ver_reg.register(mod, "1.0.0")

        # 3. Build workflow from template
        wf = ScanWorkflow(template.name)
        par = ParallelStep("modules")
        for mod in list(template.modules)[:3]:
            par.add_step(ModuleStep(mod, mod))
        wf.add_step(par)

        # 4. Execute workflow
        result = wf.execute()
        assert result.status == StepStatus.COMPLETED

        # 5. Store results in event store
        store = EventStore()
        for i, mod in enumerate(list(template.modules)[:3]):
            store.store(StoredEvent(
                event_id=f"e{i}", scan_id="scan_001",
                event_type="IP_ADDRESS", module=mod,
                data=f"result_{i}", priority=EventPriority.MEDIUM,
            ))

        assert store.count() == 3

        # 6. Cache the results
        cache = ScanResultCache()
        events = store.query(EventQuery(scan_id="scan_001"))
        cache.store_result("scan_001", "all", [e.to_dict() for e in events])
        assert cache.has_result("scan_001", "all")

        # 7. Set up alerting
        engine = AlertEngine()
        rule = AlertRule("findings_alert", severity=AlertSeverity.MEDIUM,
                         message_template="Found {count} events")
        rule.add_condition(AlertCondition(AlertConditionType.COUNT, 2))
        engine.add_rule(rule)

        alerts = engine.process_event({"count": store.count()})
        assert len(alerts) == 1
        assert "3" in alerts[0].message
