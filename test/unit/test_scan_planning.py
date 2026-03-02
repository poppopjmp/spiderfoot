"""Tests for spiderfoot.research.scan_planning (Phase 8a, Cycles 651-700, 851-900)."""

import pytest
from spiderfoot.research.scan_planning import (
    AssetType,
    Asset,
    AttackSurface,
    ModuleCapability,
    ModuleKnowledgeBase,
    ScanObjective,
    ScanPlan,
    ScanPhase,
    AutonomousScanPlanner,
    InstanceRegion,
    ScanInstance,
    ScanShard,
    FederatedScanCoordinator,
)


# ── AttackSurface ─────────────────────────────────────────────────────


class TestAssetType:
    def test_values(self):
        assert AssetType.DOMAIN.value == "domain"
        assert AssetType.IP_ADDRESS.value == "ip_address"
        assert AssetType.EMAIL.value == "email"


class TestAsset:
    def test_key(self):
        a = Asset(AssetType.DOMAIN, "example.com")
        assert a.key == "domain:example.com"

    def test_defaults(self):
        a = Asset(AssetType.IP_ADDRESS, "1.2.3.4")
        assert a.confidence == 1.0
        assert a.source_module == ""


class TestAttackSurface:
    def test_add_new(self):
        s = AttackSurface()
        assert s.add_asset(Asset(AssetType.DOMAIN, "example.com")) is True
        assert s.total_assets == 1

    def test_add_duplicate(self):
        s = AttackSurface()
        s.add_asset(Asset(AssetType.DOMAIN, "example.com"))
        assert s.add_asset(Asset(AssetType.DOMAIN, "example.com")) is False

    def test_get_by_type(self):
        s = AttackSurface()
        s.add_asset(Asset(AssetType.DOMAIN, "example.com"))
        s.add_asset(Asset(AssetType.IP_ADDRESS, "1.2.3.4"))
        assert len(s.get_assets(AssetType.DOMAIN)) == 1

    def test_get_by_confidence(self):
        s = AttackSurface()
        s.add_asset(Asset(AssetType.DOMAIN, "a.com", confidence=0.9))
        s.add_asset(Asset(AssetType.DOMAIN, "b.com", confidence=0.3))
        assert len(s.get_assets(min_confidence=0.5)) == 1

    def test_type_counts(self):
        s = AttackSurface()
        s.add_asset(Asset(AssetType.DOMAIN, "a.com"))
        s.add_asset(Asset(AssetType.DOMAIN, "b.com"))
        s.add_asset(Asset(AssetType.IP_ADDRESS, "1.2.3.4"))
        counts = s.get_type_counts()
        assert counts["domain"] == 2
        assert counts["ip_address"] == 1

    def test_has_type(self):
        s = AttackSurface()
        s.add_asset(Asset(AssetType.DOMAIN, "a.com"))
        assert s.has_type(AssetType.DOMAIN) is True
        assert s.has_type(AssetType.EMAIL) is False

    def test_summary(self):
        s = AttackSurface()
        s.add_asset(Asset(AssetType.DOMAIN, "a.com"))
        summary = s.get_summary()
        assert summary["total_assets"] == 1
        assert "domain" in summary["asset_types"]


# ── ModuleKnowledgeBase ───────────────────────────────────────────────


class TestModuleKnowledgeBase:
    def test_defaults(self):
        kb = ModuleKnowledgeBase()
        assert kb.module_count == 8

    def test_find_by_input(self):
        kb = ModuleKnowledgeBase()
        dns_mods = kb.find_by_input("domain")
        assert len(dns_mods) > 0
        assert any(m.module_name == "sfp_dns" for m in dns_mods)

    def test_find_by_output(self):
        kb = ModuleKnowledgeBase()
        email_mods = kb.find_by_output("email")
        assert any(m.module_name == "sfp_whois" for m in email_mods)

    def test_find_by_tag(self):
        kb = ModuleKnowledgeBase()
        dns_mods = kb.find_by_tag("dns")
        assert len(dns_mods) >= 1

    def test_custom_register(self):
        kb = ModuleKnowledgeBase()
        kb.register(ModuleCapability("sfp_custom", input_types=["domain"]))
        assert kb.get("sfp_custom") is not None
        assert kb.module_count == 9


# ── AutonomousScanPlanner ─────────────────────────────────────────────


class TestAutonomousScanPlanner:
    def test_classify_domain(self):
        p = AutonomousScanPlanner()
        assert p._classify_target("example.com") == "domain"

    def test_classify_ip(self):
        p = AutonomousScanPlanner()
        assert p._classify_target("1.2.3.4") == "ip_address"

    def test_classify_email(self):
        p = AutonomousScanPlanner()
        assert p._classify_target("user@example.com") == "email"

    def test_classify_url(self):
        p = AutonomousScanPlanner()
        assert p._classify_target("https://example.com/path") == "url"

    def test_plan_full_recon(self):
        p = AutonomousScanPlanner()
        plan = p.plan("example.com", ScanObjective.FULL_RECON)
        assert plan.target == "example.com"
        assert plan.total_modules > 0
        assert len(plan.phases) > 0

    def test_plan_passive_only(self):
        p = AutonomousScanPlanner()
        plan = p.plan("example.com", ScanObjective.PASSIVE_ONLY)
        assert plan.passive_only is True

    def test_plan_email_harvest(self):
        p = AutonomousScanPlanner()
        plan = p.plan("example.com", ScanObjective.EMAIL_HARVEST)
        assert plan.total_modules > 0

    def test_plan_has_reasoning(self):
        p = AutonomousScanPlanner()
        plan = p.plan("example.com")
        assert len(plan.reasoning) >= 2

    def test_plan_ip_target(self):
        p = AutonomousScanPlanner()
        plan = p.plan("192.168.1.1")
        assert plan.total_modules > 0

    def test_plan_time_budget(self):
        p = AutonomousScanPlanner(max_duration_seconds=10.0)
        plan = p.plan("example.com")
        assert plan.estimated_duration_seconds <= 10.0

    def test_plan_with_api_keys(self):
        p = AutonomousScanPlanner(available_api_keys=["sfp_shodan"])
        plan = p.plan("example.com")
        modules = []
        for phase in plan.phases:
            modules.extend(phase.modules)
        assert "sfp_shodan" in modules

    def test_plan_without_api_keys(self):
        p = AutonomousScanPlanner(available_api_keys=[])
        plan = p.plan("example.com")
        modules = []
        for phase in plan.phases:
            modules.extend(phase.modules)
        assert "sfp_shodan" not in modules

    def test_plan_to_dict(self):
        p = AutonomousScanPlanner()
        plan = p.plan("example.com")
        d = plan.to_dict()
        assert d["target"] == "example.com"
        assert isinstance(d["phases"], list)

    def test_adapt_plan(self):
        p = AutonomousScanPlanner()
        plan = p.plan("example.com")
        surface = AttackSurface()
        surface.add_asset(Asset(AssetType.IP_ADDRESS, "93.184.216.34"))
        adapted = p.adapt_plan(plan, surface)
        assert adapted.total_modules >= plan.total_modules

    def test_phases_ordered(self):
        p = AutonomousScanPlanner()
        plan = p.plan("example.com", ScanObjective.FULL_RECON)
        if len(plan.phases) > 1:
            orders = [ph.order for ph in plan.phases]
            assert orders == sorted(orders)


# ── FederatedScanCoordinator ─────────────────────────────────────────


def _make_instance(iid: str, region: InstanceRegion, cap: int = 10) -> ScanInstance:
    return ScanInstance(
        instance_id=iid,
        region=region,
        base_url=f"https://{iid}.example.com",
        capacity=cap,
        is_healthy=True,
    )


class TestFederatedScanCoordinator:
    def test_register_instance(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        assert fc.instance_count == 1

    def test_remove_instance(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        assert fc.remove_instance("i1") is True
        assert fc.remove_instance("i1") is False

    def test_healthy_instances(self):
        fc = FederatedScanCoordinator()
        i1 = _make_instance("i1", InstanceRegion.US_EAST)
        i2 = _make_instance("i2", InstanceRegion.EU_WEST)
        i2.is_healthy = False
        fc.register_instance(i1)
        fc.register_instance(i2)
        assert len(fc.get_healthy_instances()) == 1

    def test_filter_by_region(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        fc.register_instance(_make_instance("i2", InstanceRegion.EU_WEST))
        us = fc.get_healthy_instances(region=InstanceRegion.US_EAST)
        assert len(us) == 1

    def test_round_robin(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        fc.register_instance(_make_instance("i2", InstanceRegion.EU_WEST))
        shards = fc.distribute_round_robin(
            ["mod1", "mod2", "mod3", "mod4"],
            ["example.com"],
        )
        assert len(shards) == 4
        i1_count = sum(1 for s in shards if s.instance_id == "i1")
        assert i1_count == 2

    def test_capacity_based(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST, 2))
        fc.register_instance(_make_instance("i2", InstanceRegion.EU_WEST, 10))
        shards = fc.distribute_capacity(
            ["mod1", "mod2", "mod3"],
            ["example.com"],
        )
        assert len(shards) == 3
        # Most should go to i2 (higher capacity)
        i2_count = sum(1 for s in shards if s.instance_id == "i2")
        assert i2_count >= 2

    def test_region_affinity(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        fc.register_instance(_make_instance("i2", InstanceRegion.EU_WEST))
        shards = fc.distribute_region_affinity(
            ["mod1", "mod2"],
            ["example.com"],
            InstanceRegion.EU_WEST,
        )
        assert all(s.instance_id == "i2" for s in shards)

    def test_region_affinity_fallback(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        shards = fc.distribute_region_affinity(
            ["mod1"],
            ["example.com"],
            InstanceRegion.ASIA_EAST,  # No instances here
        )
        assert len(shards) == 1
        assert shards[0].instance_id == "i1"

    def test_no_healthy_instances(self):
        fc = FederatedScanCoordinator()
        shards = fc.distribute_round_robin(["mod1"], ["example.com"])
        assert shards == []

    def test_update_shard_status(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        shards = fc.distribute_round_robin(["mod1"], ["target"])
        sid = shards[0].shard_id
        assert fc.update_shard_status(sid, "running") is True
        assert fc.update_shard_status(sid, "completed", results_count=42) is True
        shard = fc.get_shard(sid)
        assert shard.status == "completed"
        assert shard.results_count == 42

    def test_federation_status(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        fc.distribute_round_robin(["mod1"], ["target"])
        status = fc.get_federation_status()
        assert status["instances"]["total"] == 1
        assert status["shards"]["total"] == 1

    def test_merge_results(self):
        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        shards = fc.distribute_round_robin(["mod1"], ["target"])
        fc.update_shard_status(shards[0].shard_id, "completed", 10)
        merged = fc.merge_results()
        assert len(merged) == 1


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_plan_then_federate(self):
        """Plan a scan then distribute across instances."""
        planner = AutonomousScanPlanner()
        plan = planner.plan("example.com", ScanObjective.PASSIVE_ONLY)

        fc = FederatedScanCoordinator()
        fc.register_instance(_make_instance("i1", InstanceRegion.US_EAST))
        fc.register_instance(_make_instance("i2", InstanceRegion.EU_WEST))

        all_mods = []
        for phase in plan.phases:
            all_mods.extend(phase.modules)

        shards = fc.distribute_round_robin(all_mods, [plan.target])
        assert len(shards) == len(all_mods)

    def test_surface_driven_replanning(self):
        """Attack surface discovery triggers replanning."""
        planner = AutonomousScanPlanner()
        plan1 = planner.plan("example.com")

        surface = AttackSurface()
        surface.add_asset(Asset(AssetType.IP_ADDRESS, "93.184.216.34"))
        surface.add_asset(Asset(AssetType.SUBDOMAIN, "mail.example.com"))

        plan2 = planner.adapt_plan(plan1, surface)
        assert plan2.total_modules >= plan1.total_modules
