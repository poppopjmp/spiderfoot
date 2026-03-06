"""Tests for spiderfoot.ecosystem.ecosystem_tooling (Phase 7, Cycles 551-650)."""

import pytest
from spiderfoot.ecosystem.ecosystem_tooling import (
    SubmissionStatus,
    ModuleSubmission,
    ModuleSubmissionPipeline,
    ModuleSignature,
    ModuleSigner,
    ModuleDependency,
    DependencyResolver,
    ModuleVersion,
    ModuleRegistry,
    IntegrationTemplate,
    SDKEndpoint,
    SDKGenerator,
)


# ── ModuleSubmissionPipeline ──────────────────────────────────────────


class TestSubmissionStatus:
    def test_values(self):
        assert SubmissionStatus.PENDING.value == "pending"
        assert SubmissionStatus.APPROVED.value == "approved"
        assert SubmissionStatus.REJECTED.value == "rejected"


VALID_SOURCE = """
class sfp_test_module:
    def meta(self): pass
    def watchedEvents(self): pass
    def producedEvents(self): pass
    def handleEvent(self, event): pass
"""


class TestModuleSubmissionPipeline:
    def _pipeline(self) -> ModuleSubmissionPipeline:
        return ModuleSubmissionPipeline()

    def test_submit(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "author", "1.0.0", "desc", VALID_SOURCE
        ))
        assert sid == "sub-0001"
        assert p.count == 1

    def test_validate_valid(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "author", "1.0.0", "desc", VALID_SOURCE
        ))
        result = p.validate(sid)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_bad_name(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "bad-name", "author", "1.0.0", "desc", VALID_SOURCE
        ))
        result = p.validate(sid)
        assert result["valid"] is False
        assert any("pattern" in e for e in result["errors"])

    def test_validate_missing_method(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "author", "1.0.0", "desc", "class empty: pass"
        ))
        result = p.validate(sid)
        assert result["valid"] is False
        assert any("Missing required method" in e for e in result["errors"])

    def test_validate_dangerous_import(self):
        p = self._pipeline()
        code = VALID_SOURCE + "\nimport subprocess"
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "author", "1.0.0", "desc", code
        ))
        result = p.validate(sid)
        assert result["valid"] is False
        assert any("subprocess" in e for e in result["errors"])

    def test_validate_missing_author(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "", "1.0.0", "desc", VALID_SOURCE
        ))
        result = p.validate(sid)
        assert result["valid"] is False

    def test_validate_nonexistent(self):
        p = self._pipeline()
        result = p.validate("nonexistent")
        assert result["valid"] is False

    def test_approve(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "author", "1.0.0", "desc", VALID_SOURCE
        ))
        assert p.approve(sid, "LGTM") is True
        sub = p.get_submission(sid)
        assert sub.status == SubmissionStatus.APPROVED
        assert sub.review_notes == "LGTM"

    def test_reject(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "author", "1.0.0", "desc", VALID_SOURCE
        ))
        assert p.reject(sid, "Security issue") is True
        sub = p.get_submission(sid)
        assert sub.status == SubmissionStatus.REJECTED

    def test_approve_nonexistent(self):
        p = self._pipeline()
        assert p.approve("nonexistent") is False

    def test_get_by_status(self):
        p = self._pipeline()
        p.submit(ModuleSubmission(
            "sfp_mod_a", "a", "1.0.0", "desc", VALID_SOURCE
        ))
        sid2 = p.submit(ModuleSubmission(
            "sfp_mod_b", "b", "1.0.0", "desc", VALID_SOURCE
        ))
        p.approve(sid2)
        pending = p.get_by_status(SubmissionStatus.PENDING)
        approved = p.get_by_status(SubmissionStatus.APPROVED)
        assert len(pending) == 1
        assert len(approved) == 1

    def test_missing_description_warning(self):
        p = self._pipeline()
        sid = p.submit(ModuleSubmission(
            "sfp_test_mod", "author", "1.0.0", "", VALID_SOURCE
        ))
        result = p.validate(sid)
        assert any("description" in w.lower() for w in result["warnings"])


# ── ModuleSigner ──────────────────────────────────────────────────────


class TestModuleSigner:
    def test_sign_and_verify(self):
        signer = ModuleSigner()
        content = "class sfp_test: pass"
        sig = signer.sign("sfp_test", "1.0.0", content, "dev-team")
        result = signer.verify("sfp_test", "1.0.0", content)
        assert result["verified"] is True
        assert result["signer"] == "dev-team"

    def test_verify_modified(self):
        signer = ModuleSigner()
        signer.sign("sfp_test", "1.0.0", "original", "dev-team")
        result = signer.verify("sfp_test", "1.0.0", "modified")
        assert result["verified"] is False

    def test_verify_no_signature(self):
        signer = ModuleSigner()
        result = signer.verify("sfp_unknown", "1.0.0", "code")
        assert result["verified"] is False

    def test_compute_hash(self):
        h1 = ModuleSigner.compute_hash("hello")
        h2 = ModuleSigner.compute_hash("hello")
        h3 = ModuleSigner.compute_hash("world")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64  # SHA-256

    def test_signature_count(self):
        signer = ModuleSigner()
        signer.sign("a", "1.0", "code", "x")
        signer.sign("b", "1.0", "code", "y")
        assert signer.signature_count == 2


# ── DependencyResolver ───────────────────────────────────────────────


class TestDependencyResolver:
    def test_no_deps(self):
        r = DependencyResolver()
        r.register(ModuleDependency("sfp_a"))
        result = r.resolve("sfp_a")
        assert result["order"] == ["sfp_a"]
        assert result["missing"] == []

    def test_simple_chain(self):
        r = DependencyResolver()
        r.register(ModuleDependency("sfp_a", depends_on=["sfp_b"]))
        r.register(ModuleDependency("sfp_b"))
        result = r.resolve("sfp_a")
        assert result["order"] == ["sfp_b", "sfp_a"]

    def test_missing_dep(self):
        r = DependencyResolver()
        r.register(ModuleDependency("sfp_a", depends_on=["sfp_missing"]))
        result = r.resolve("sfp_a")
        assert "sfp_missing" in result["missing"]

    def test_cycle_detection(self):
        r = DependencyResolver()
        r.register(ModuleDependency("sfp_a", depends_on=["sfp_b"]))
        r.register(ModuleDependency("sfp_b", depends_on=["sfp_a"]))
        result = r.resolve("sfp_a")
        assert result["cycle_detected"] is True
        assert result["order"] == []

    def test_conflict_detection(self):
        r = DependencyResolver()
        r.register(ModuleDependency("sfp_a", depends_on=["sfp_b"],
                                    conflicts_with=["sfp_b"]))
        r.register(ModuleDependency("sfp_b"))
        result = r.resolve("sfp_a")
        assert "sfp_b" in result["conflicts"]

    def test_check_conflicts_set(self):
        r = DependencyResolver()
        r.register(ModuleDependency("sfp_a", conflicts_with=["sfp_b"]))
        r.register(ModuleDependency("sfp_b"))
        conflicts = r.check_conflicts(["sfp_a", "sfp_b"])
        assert len(conflicts) == 1

    def test_unregistered_module(self):
        r = DependencyResolver()
        result = r.resolve("sfp_unknown")
        assert result["order"] == ["sfp_unknown"]

    def test_diamond_deps(self):
        r = DependencyResolver()
        r.register(ModuleDependency("sfp_a", depends_on=["sfp_b", "sfp_c"]))
        r.register(ModuleDependency("sfp_b", depends_on=["sfp_d"]))
        r.register(ModuleDependency("sfp_c", depends_on=["sfp_d"]))
        r.register(ModuleDependency("sfp_d"))
        result = r.resolve("sfp_a")
        assert result["cycle_detected"] is False
        assert result["order"][0] == "sfp_d"
        assert result["order"][-1] == "sfp_a"


# ── ModuleRegistry ───────────────────────────────────────────────────


class TestModuleRegistry:
    def test_register_and_count(self):
        reg = ModuleRegistry()
        reg.register(ModuleVersion("sfp_test", "1.0.0"))
        assert reg.module_count == 1
        assert reg.total_versions == 1

    def test_get_versions(self):
        reg = ModuleRegistry()
        reg.register(ModuleVersion("sfp_test", "1.0.0"))
        reg.register(ModuleVersion("sfp_test", "1.1.0"))
        versions = reg.get_versions("sfp_test")
        assert len(versions) == 2

    def test_get_latest(self):
        reg = ModuleRegistry()
        v1 = ModuleVersion("sfp_test", "1.0.0")
        v1.released_at = 100.0
        v2 = ModuleVersion("sfp_test", "2.0.0")
        v2.released_at = 200.0
        reg.register(v1)
        reg.register(v2)
        latest = reg.get_latest("sfp_test")
        assert latest.version == "2.0.0"

    def test_get_latest_empty(self):
        reg = ModuleRegistry()
        assert reg.get_latest("nonexistent") is None

    def test_search(self):
        reg = ModuleRegistry()
        reg.register(ModuleVersion("sfp_dns_lookup", "1.0"))
        reg.register(ModuleVersion("sfp_port_scan", "1.0"))
        results = reg.search("dns")
        assert len(results) == 1
        assert results[0] == "sfp_dns_lookup"

    def test_get_changelog(self):
        reg = ModuleRegistry()
        v1 = ModuleVersion("sfp_test", "1.0.0", "Initial release")
        v1.released_at = 100.0
        v2 = ModuleVersion("sfp_test", "2.0.0", "Added new feature")
        v2.released_at = 200.0
        reg.register(v1)
        reg.register(v2)
        changelog = reg.get_changelog("sfp_test")
        assert "## 2.0.0" in changelog
        assert "## 1.0.0" in changelog
        assert "Added new feature" in changelog


# ── IntegrationTemplate ──────────────────────────────────────────────


class TestIntegrationTemplate:
    def test_burp_extension(self):
        code = IntegrationTemplate.burp_extension()
        assert "IBurpExtender" in code
        assert "localhost:5001" in code

    def test_burp_custom_url(self):
        code = IntegrationTemplate.burp_extension("https://sf.example.com")
        assert "sf.example.com" in code

    def test_maltego_transform(self):
        code = IntegrationTemplate.maltego_transform()
        assert "DiscoverableTransform" in code
        assert "create_entities" in code

    def test_github_actions(self):
        code = IntegrationTemplate.github_actions_workflow()
        assert "spiderfoot-scan" in code
        assert "actions/upload-artifact" in code

    def test_vscode_extension(self):
        manifest = IntegrationTemplate.vscode_extension_manifest()
        assert manifest["name"] == "spiderfoot-module-dev"
        assert "commands" in manifest["contributes"]
        assert len(manifest["contributes"]["commands"]) == 2


# ── SDKGenerator ─────────────────────────────────────────────────────


class TestSDKGenerator:
    def test_defaults(self):
        gen = SDKGenerator()
        assert gen.endpoint_count == 7

    def test_python_sdk(self):
        gen = SDKGenerator()
        code = gen.generate_python()
        assert "class SpiderFootClient:" in code
        assert "def get_health(" in code
        assert "def create_scan(" in code
        assert "import httpx" in code

    def test_javascript_sdk(self):
        gen = SDKGenerator()
        code = gen.generate_javascript()
        assert "class SpiderFootClient" in code
        assert "async get_health" in code
        assert "async create_scan" in code
        assert "module.exports" in code

    def test_go_sdk(self):
        gen = SDKGenerator()
        code = gen.generate_go()
        assert "package spiderfoot" in code
        assert "func" in code
        assert "http.NewRequest" in code

    def test_custom_base_url(self):
        gen = SDKGenerator(base_url="https://sf.example.com")
        code = gen.generate_python()
        assert "sf.example.com" in code

    def test_custom_endpoint(self):
        gen = SDKGenerator(endpoints=[
            SDKEndpoint("GET", "/api/custom", "get_custom", "Custom"),
        ])
        assert gen.endpoint_count == 1
        code = gen.generate_python()
        assert "def get_custom(" in code

    def test_python_path_params(self):
        gen = SDKGenerator()
        code = gen.generate_python()
        # get_scan has {scan_id} path param
        assert "scan_id: str" in code

    def test_javascript_path_params(self):
        gen = SDKGenerator()
        code = gen.generate_javascript()
        assert "async get_scan(scan_id)" in code

    def test_go_path_params(self):
        gen = SDKGenerator()
        code = gen.generate_go()
        assert "scan_id string" in code


# ── Integration Tests ─────────────────────────────────────────────────


class TestIntegration:
    def test_submit_validate_sign_approve(self):
        """Full module lifecycle: submit → validate → sign → approve."""
        pipeline = ModuleSubmissionPipeline()
        signer = ModuleSigner()

        sid = pipeline.submit(ModuleSubmission(
            "sfp_community_mod", "Alice", "1.0.0",
            "A community module", VALID_SOURCE,
        ))

        result = pipeline.validate(sid)
        assert result["valid"] is True

        # Sign the module
        sig = signer.sign("sfp_community_mod", "1.0.0",
                           VALID_SOURCE, "Alice")
        verify = signer.verify("sfp_community_mod", "1.0.0",
                                VALID_SOURCE)
        assert verify["verified"] is True

        # Approve
        pipeline.approve(sid, "Validated and signed")
        sub = pipeline.get_submission(sid)
        assert sub.status == SubmissionStatus.APPROVED

    def test_dependency_then_registry(self):
        """Register deps → resolve → register versions."""
        resolver = DependencyResolver()
        resolver.register(ModuleDependency("sfp_dns", depends_on=["sfp_base"]))
        resolver.register(ModuleDependency("sfp_base"))

        result = resolver.resolve("sfp_dns")
        assert result["order"] == ["sfp_base", "sfp_dns"]

        registry = ModuleRegistry()
        for mod in result["order"]:
            registry.register(ModuleVersion(mod, "1.0.0", "Initial"))
        assert registry.module_count == 2

    def test_sdk_all_languages(self):
        """Generate SDKs for all supported languages."""
        gen = SDKGenerator()
        py = gen.generate_python()
        js = gen.generate_javascript()
        go = gen.generate_go()

        assert "SpiderFootClient" in py
        assert "SpiderFootClient" in js
        assert "Client struct" in go

    def test_integration_templates_all(self):
        """All integration templates generate non-empty output."""
        burp = IntegrationTemplate.burp_extension()
        maltego = IntegrationTemplate.maltego_transform()
        gh = IntegrationTemplate.github_actions_workflow()
        vscode = IntegrationTemplate.vscode_extension_manifest()

        assert len(burp) > 100
        assert len(maltego) > 100
        assert len(gh) > 100
        assert len(vscode) > 3
