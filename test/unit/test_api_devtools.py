"""Tests for API Developer Experience Tooling (Phase 4, Cycles 271-290).

Tests cover:
- APIChangelog (Cycle 272): changelog entries, versioning, markdown
- APIIntrospector (Cycle 273): event types, categories, endpoints
- OpenAPIExampleGenerator (Cycle 271): example request/response pairs
- SDKStubGenerator (Cycle 275): Python and Go SDK stubs
- BulkScanRequest/Response (Cycle 276): bulk scan schemas
- ScanTemplate + ScanTemplateStore (Cycle 276): template CRUD
"""

from __future__ import annotations

import re

import pytest

from spiderfoot.api.api_devtools import (
    APIChangelog,
    APIIntrospector,
    BulkScanRequest,
    BulkScanResponse,
    ChangelogEntry,
    ChangeType,
    EndpointInfo,
    OpenAPIExampleGenerator,
    ScanTemplate,
    ScanTemplateStore,
    SDKStubGenerator,
    STANDARD_EVENT_TYPES,
    STANDARD_MODULE_CATEGORIES,
)


# ── ChangeType Enum ───────────────────────────────────────────────────


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_all_values(self):
        values = {ct.value for ct in ChangeType}
        assert "added" in values
        assert "changed" in values
        assert "deprecated" in values
        assert "removed" in values
        assert "fixed" in values
        assert "security" in values

    def test_string_enum(self):
        assert ChangeType.ADDED == "added"
        assert isinstance(ChangeType.ADDED, str)


# ── ChangelogEntry ────────────────────────────────────────────────────


class TestChangelogEntry:
    """Tests for ChangelogEntry dataclass."""

    def test_basic_entry(self):
        entry = ChangelogEntry("1.0.0", ChangeType.ADDED, "New feature")
        assert entry.version == "1.0.0"
        assert entry.change_type == ChangeType.ADDED
        assert entry.description == "New feature"

    def test_frozen(self):
        entry = ChangelogEntry("1.0.0", ChangeType.ADDED, "Test")
        with pytest.raises(AttributeError):
            entry.version = "2.0.0"

    def test_with_endpoint(self):
        entry = ChangelogEntry("1.0.0", ChangeType.ADDED, "Test", endpoint="/api/test")
        assert entry.endpoint == "/api/test"

    def test_breaking_default_false(self):
        entry = ChangelogEntry("1.0.0", ChangeType.ADDED, "Test")
        assert entry.breaking is False


# ── APIChangelog ──────────────────────────────────────────────────────


class TestAPIChangelog:
    """Tests for APIChangelog."""

    def test_builtin_entries(self):
        changelog = APIChangelog()
        assert changelog.entry_count > 0

    def test_get_history(self):
        changelog = APIChangelog()
        history = changelog.get_history()
        assert len(history) > 0
        assert all(isinstance(e, ChangelogEntry) for e in history)

    def test_get_history_by_version(self):
        changelog = APIChangelog()
        entries = changelog.get_history(version="6.0.0")
        assert all(e.version == "6.0.0" for e in entries)

    def test_get_history_by_type(self):
        changelog = APIChangelog()
        entries = changelog.get_history(change_type=ChangeType.ADDED)
        assert all(e.change_type == ChangeType.ADDED for e in entries)

    def test_get_breaking_changes(self):
        changelog = APIChangelog()
        breaking = changelog.get_breaking_changes()
        assert all(e.breaking for e in breaking)
        assert len(breaking) >= 2  # PostgreSQL + CherryPy removal

    def test_get_versions(self):
        changelog = APIChangelog()
        versions = changelog.get_versions()
        assert "6.0.0" in versions
        assert "6.1.0" in versions
        assert "6.2.0" in versions

    def test_add_entry(self):
        changelog = APIChangelog()
        initial_count = changelog.entry_count
        changelog.add("7.0.0", ChangeType.ADDED, "New feature", "/api/v1/new")
        assert changelog.entry_count == initial_count + 1
        entries = changelog.get_history(version="7.0.0")
        assert len(entries) == 1
        assert entries[0].description == "New feature"

    def test_to_markdown(self):
        changelog = APIChangelog()
        md = changelog.to_markdown()
        assert "# API Changelog" in md
        assert "## [6.0.0]" in md
        assert "### Added" in md

    def test_to_markdown_has_breaking(self):
        changelog = APIChangelog()
        md = changelog.to_markdown()
        assert "**BREAKING**" in md

    def test_versions_sorted_descending(self):
        changelog = APIChangelog()
        versions = changelog.get_versions()
        # Should be in descending order
        for i in range(len(versions) - 1):
            assert versions[i] >= versions[i + 1]


# ── Constants ─────────────────────────────────────────────────────────


class TestEventTypeConstants:
    """Tests for standard event type constants."""

    def test_event_types_populated(self):
        assert len(STANDARD_EVENT_TYPES) >= 60

    def test_domain_name_exists(self):
        assert "DOMAIN_NAME" in STANDARD_EVENT_TYPES

    def test_ip_address_exists(self):
        assert "IP_ADDRESS" in STANDARD_EVENT_TYPES

    def test_email_exists(self):
        assert "EMAILADDR" in STANDARD_EVENT_TYPES

    def test_all_have_descriptions(self):
        for name, desc in STANDARD_EVENT_TYPES.items():
            assert desc, f"{name} has no description"

    def test_no_duplicate_descriptions(self):
        descriptions = list(STANDARD_EVENT_TYPES.values())
        # Allow some duplicate descriptions but not excessive
        unique = set(descriptions)
        assert len(unique) > len(descriptions) * 0.8


class TestModuleCategoryConstants:
    """Tests for standard module category constants."""

    def test_categories_populated(self):
        assert len(STANDARD_MODULE_CATEGORIES) >= 10

    def test_dns_category(self):
        assert "DNS" in STANDARD_MODULE_CATEGORIES

    def test_social_media(self):
        assert "Social Media" in STANDARD_MODULE_CATEGORIES


# ── APIIntrospector ───────────────────────────────────────────────────


class TestAPIIntrospector:
    """Tests for APIIntrospector."""

    def test_get_event_types(self):
        intro = APIIntrospector()
        types = intro.get_event_types()
        assert len(types) >= 60

    def test_get_event_types_filtered(self):
        intro = APIIntrospector()
        types = intro.get_event_types(pattern="IP_ADDRESS")
        assert "IP_ADDRESS" in types
        assert "DOMAIN_NAME" not in types

    def test_get_event_types_regex(self):
        intro = APIIntrospector()
        types = intro.get_event_types(pattern="^VULNERABILITY")
        assert all(k.startswith("VULNERABILITY") for k in types)

    def test_get_module_categories(self):
        intro = APIIntrospector()
        cats = intro.get_module_categories()
        assert "DNS" in cats
        assert len(cats) >= 10

    def test_register_event_type(self):
        intro = APIIntrospector()
        intro.register_event_type("CUSTOM_EVENT", "Custom event type")
        types = intro.get_event_types()
        assert "CUSTOM_EVENT" in types
        assert types["CUSTOM_EVENT"] == "Custom event type"

    def test_register_category(self):
        intro = APIIntrospector()
        intro.register_category("Custom", "Custom category")
        cats = intro.get_module_categories()
        assert "Custom" in cats

    def test_get_api_summary(self):
        intro = APIIntrospector()
        summary = intro.get_api_summary()
        assert "event_type_count" in summary
        assert "category_count" in summary
        assert "endpoint_count" in summary
        assert summary["event_type_count"] >= 60
        assert summary["endpoint_count"] >= 15

    def test_get_endpoints(self):
        intro = APIIntrospector()
        endpoints = intro.get_endpoints()
        assert len(endpoints) >= 15

    def test_get_endpoints_by_method(self):
        intro = APIIntrospector()
        gets = intro.get_endpoints(method="GET")
        assert all(e.method.upper() == "GET" for e in gets)
        assert len(gets) >= 5

    def test_get_endpoints_by_tag(self):
        intro = APIIntrospector()
        scan_eps = intro.get_endpoints(tag="Scans")
        assert all("Scans" in e.tags for e in scan_eps)

    def test_add_endpoint(self):
        intro = APIIntrospector()
        initial = len(intro.get_endpoints())
        intro.add_endpoint(EndpointInfo("GET", "/api/v1/test", "Test"))
        assert len(intro.get_endpoints()) == initial + 1

    def test_endpoints_by_method_counts(self):
        intro = APIIntrospector()
        summary = intro.get_api_summary()
        by_method = summary["endpoints_by_method"]
        assert "GET" in by_method
        assert "POST" in by_method

    def test_endpoints_by_tag_counts(self):
        intro = APIIntrospector()
        summary = intro.get_api_summary()
        by_tag = summary["endpoints_by_tag"]
        assert "Scans" in by_tag


# ── EndpointInfo ──────────────────────────────────────────────────────


class TestEndpointInfo:
    """Tests for EndpointInfo dataclass."""

    def test_operation_id(self):
        ep = EndpointInfo("GET", "/api/v1/scans", "List scans")
        assert ep.operation_id == "get_scans"

    def test_operation_id_with_params(self):
        ep = EndpointInfo("GET", "/api/v1/scans/{id}", "Get scan")
        assert ep.operation_id == "get_scans_id"

    def test_default_auth_required(self):
        ep = EndpointInfo("GET", "/api/v1/test", "Test")
        assert ep.auth_required is True

    def test_deprecated_default_false(self):
        ep = EndpointInfo("GET", "/api/v1/test", "Test")
        assert ep.deprecated is False


# ── OpenAPIExampleGenerator ───────────────────────────────────────────


class TestOpenAPIExampleGenerator:
    """Tests for OpenAPIExampleGenerator."""

    def test_generate_all(self):
        gen = OpenAPIExampleGenerator()
        examples = gen.generate_all()
        assert len(examples) > 0

    def test_endpoint_count(self):
        gen = OpenAPIExampleGenerator()
        assert gen.endpoint_count >= 8

    def test_for_endpoint_scan_create(self):
        gen = OpenAPIExampleGenerator()
        example = gen.for_endpoint("POST", "/api/v1/scans")
        assert example is not None
        assert "request" in example
        assert "target" in example["request"]
        assert "response" in example

    def test_for_endpoint_bulk_scan(self):
        gen = OpenAPIExampleGenerator()
        example = gen.for_endpoint("POST", "/api/v1/scans/bulk")
        assert example is not None
        assert "targets" in example["request"]

    def test_for_endpoint_modules(self):
        gen = OpenAPIExampleGenerator()
        example = gen.for_endpoint("GET", "/api/v1/modules")
        assert example is not None

    def test_for_endpoint_not_found(self):
        gen = OpenAPIExampleGenerator()
        example = gen.for_endpoint("GET", "/api/v1/nonexistent")
        assert example is None

    def test_add_example(self):
        gen = OpenAPIExampleGenerator()
        gen.add_example("GET", "/api/v1/custom",
                        response={"data": "test"})
        example = gen.for_endpoint("GET", "/api/v1/custom")
        assert example is not None
        assert example["response"]["data"] == "test"

    def test_scan_list(self):
        gen = OpenAPIExampleGenerator()
        example = gen.for_endpoint("GET", "/api/v1/scans")
        assert example is not None
        assert isinstance(example["response"], list)

    def test_event_types_example(self):
        gen = OpenAPIExampleGenerator()
        example = gen.for_endpoint("GET", "/api/v1/event-types")
        assert example is not None

    def test_changelog_example(self):
        gen = OpenAPIExampleGenerator()
        example = gen.for_endpoint("GET", "/api/v1/changelog")
        assert example is not None


# ── SDKStubGenerator ──────────────────────────────────────────────────


class TestSDKStubGenerator:
    """Tests for SDKStubGenerator."""

    def _sample_endpoints(self) -> list[EndpointInfo]:
        return [
            EndpointInfo("GET", "/api/v1/scans", "List scans", tags=["Scans"]),
            EndpointInfo("POST", "/api/v1/scans", "Create scan", tags=["Scans"]),
            EndpointInfo("GET", "/api/v1/scans/{id}", "Get scan", tags=["Scans"]),
            EndpointInfo("DELETE", "/api/v1/scans/{id}", "Delete scan", tags=["Scans"]),
        ]

    def test_generate_python_has_class(self):
        gen = SDKStubGenerator()
        stub = gen.generate_python(self._sample_endpoints())
        assert "class SpiderFootClient:" in stub

    def test_generate_python_has_methods(self):
        gen = SDKStubGenerator()
        stub = gen.generate_python(self._sample_endpoints())
        assert "def get_scans" in stub
        assert "def post_scans" in stub
        assert "def get_scans_id" in stub
        assert "def delete_scans_id" in stub

    def test_generate_python_has_imports(self):
        gen = SDKStubGenerator()
        stub = gen.generate_python(self._sample_endpoints())
        assert "import httpx" in stub

    def test_generate_python_has_init(self):
        gen = SDKStubGenerator()
        stub = gen.generate_python(self._sample_endpoints())
        assert "__init__" in stub
        assert "base_url" in stub
        assert "api_key" in stub

    def test_generate_python_post_has_data(self):
        gen = SDKStubGenerator()
        stub = gen.generate_python(self._sample_endpoints())
        # POST method should accept data parameter
        assert "data: dict" in stub

    def test_generate_python_compiles(self):
        """Generated Python stub must be valid syntax."""
        gen = SDKStubGenerator()
        stub = gen.generate_python(self._sample_endpoints())
        compile(stub, "<test>", "exec")

    def test_generate_go_has_struct(self):
        gen = SDKStubGenerator()
        stub = gen.generate_go(self._sample_endpoints())
        assert "type Client struct" in stub

    def test_generate_go_has_functions(self):
        gen = SDKStubGenerator()
        stub = gen.generate_go(self._sample_endpoints())
        assert "func (c *Client)" in stub

    def test_generate_go_has_constructor(self):
        gen = SDKStubGenerator()
        stub = gen.generate_go(self._sample_endpoints())
        assert "func NewClient" in stub

    def test_generate_go_has_package(self):
        gen = SDKStubGenerator()
        stub = gen.generate_go(self._sample_endpoints())
        assert "package spiderfoot" in stub

    def test_empty_endpoints(self):
        gen = SDKStubGenerator()
        python_stub = gen.generate_python([])
        assert "class SpiderFootClient:" in python_stub

    def test_go_empty_endpoints(self):
        gen = SDKStubGenerator()
        go_stub = gen.generate_go([])
        assert "type Client struct" in go_stub


# ── BulkScanRequest ──────────────────────────────────────────────────


class TestBulkScanRequest:
    """Tests for BulkScanRequest."""

    def test_valid_request(self):
        req = BulkScanRequest(targets=["example.com"])
        errors = req.validate()
        assert errors == []

    def test_empty_targets(self):
        req = BulkScanRequest(targets=[])
        errors = req.validate()
        assert len(errors) > 0

    def test_too_many_targets(self):
        req = BulkScanRequest(targets=[f"target-{i}.com" for i in range(101)])
        errors = req.validate()
        assert any("100" in e for e in errors)

    def test_empty_target_value(self):
        req = BulkScanRequest(targets=["example.com", ""])
        errors = req.validate()
        assert any("Empty" in e for e in errors)

    def test_with_modules(self):
        req = BulkScanRequest(
            targets=["example.com"],
            modules=["sfp_dnsresolve"],
        )
        assert req.modules == ["sfp_dnsresolve"]

    def test_with_template(self):
        req = BulkScanRequest(
            targets=["example.com"],
            template_id="tmpl-001",
        )
        assert req.template_id == "tmpl-001"


class TestBulkScanResponse:
    """Tests for BulkScanResponse."""

    def test_success_count(self):
        resp = BulkScanResponse(
            scans=[
                {"scan_id": "s1", "target": "t1"},
                {"scan_id": "s2", "target": "t2"},
            ],
            total=2,
        )
        assert resp.success_count == 2

    def test_empty_response(self):
        resp = BulkScanResponse()
        assert resp.success_count == 0
        assert resp.total == 0


# ── ScanTemplate ──────────────────────────────────────────────────────


class TestScanTemplate:
    """Tests for ScanTemplate."""

    def test_valid_template(self):
        tmpl = ScanTemplate(name="Quick DNS", modules=["sfp_dnsresolve"])
        errors = tmpl.validate()
        assert errors == []

    def test_missing_name(self):
        tmpl = ScanTemplate(modules=["sfp_dnsresolve"])
        errors = tmpl.validate()
        assert any("name" in e for e in errors)

    def test_missing_modules(self):
        tmpl = ScanTemplate(name="Empty")
        errors = tmpl.validate()
        assert any("module" in e for e in errors)

    def test_with_options(self):
        tmpl = ScanTemplate(
            name="With Options",
            modules=["sfp_dnsresolve"],
            options={"_maxthreads": 10},
        )
        assert tmpl.options["_maxthreads"] == 10


# ── ScanTemplateStore ─────────────────────────────────────────────────


class TestScanTemplateStore:
    """Tests for ScanTemplateStore."""

    def test_create(self):
        store = ScanTemplateStore()
        tmpl = store.create(ScanTemplate(name="Test", modules=["sfp_test"]))
        assert tmpl.template_id.startswith("tmpl-")
        assert tmpl.created_at != ""

    def test_get(self):
        store = ScanTemplateStore()
        created = store.create(ScanTemplate(name="Test", modules=["sfp_test"]))
        found = store.get(created.template_id)
        assert found is not None
        assert found.name == "Test"

    def test_get_not_found(self):
        store = ScanTemplateStore()
        assert store.get("nonexistent") is None

    def test_list(self):
        store = ScanTemplateStore()
        store.create(ScanTemplate(name="A", modules=["sfp_a"]))
        store.create(ScanTemplate(name="B", modules=["sfp_b"]))
        assert len(store.list()) == 2

    def test_update(self):
        store = ScanTemplateStore()
        created = store.create(ScanTemplate(name="Original", modules=["sfp_test"]))
        updated = store.update(created.template_id, name="Updated")
        assert updated is not None
        assert updated.name == "Updated"

    def test_update_not_found(self):
        store = ScanTemplateStore()
        assert store.update("nonexistent", name="Test") is None

    def test_delete(self):
        store = ScanTemplateStore()
        created = store.create(ScanTemplate(name="Test", modules=["sfp_test"]))
        assert store.delete(created.template_id) is True
        assert store.get(created.template_id) is None

    def test_delete_not_found(self):
        store = ScanTemplateStore()
        assert store.delete("nonexistent") is False

    def test_count(self):
        store = ScanTemplateStore()
        assert store.count == 0
        store.create(ScanTemplate(name="Test", modules=["sfp_test"]))
        assert store.count == 1

    def test_sequential_ids(self):
        store = ScanTemplateStore()
        t1 = store.create(ScanTemplate(name="A", modules=["sfp_a"]))
        t2 = store.create(ScanTemplate(name="B", modules=["sfp_b"]))
        assert t1.template_id == "tmpl-0001"
        assert t2.template_id == "tmpl-0002"


# ── Integration ───────────────────────────────────────────────────────


class TestIntegration:
    """Integration tests across API devtools components."""

    def test_changelog_to_markdown_complete(self):
        """Changelog markdown has all sections."""
        changelog = APIChangelog()
        md = changelog.to_markdown()
        assert "6.0.0" in md
        assert "6.1.0" in md
        assert "6.2.0" in md

    def test_introspector_endpoint_coverage(self):
        """All endpoint tags have at least one endpoint."""
        intro = APIIntrospector()
        summary = intro.get_api_summary()
        by_tag = summary["endpoints_by_tag"]
        assert len(by_tag) >= 5

    def test_sdk_from_introspector(self):
        """Generate SDK from introspector endpoints."""
        intro = APIIntrospector()
        endpoints = intro.get_endpoints()
        gen = SDKStubGenerator()
        stub = gen.generate_python(endpoints)
        assert "class SpiderFootClient:" in stub
        assert "def get_scans" in stub

    def test_examples_cover_main_endpoints(self):
        """Examples exist for core endpoints."""
        gen = OpenAPIExampleGenerator()
        assert gen.for_endpoint("POST", "/api/v1/scans") is not None
        assert gen.for_endpoint("GET", "/api/v1/scans") is not None
        assert gen.for_endpoint("GET", "/api/v1/modules") is not None

    def test_template_workflow(self):
        """Full template CRUD workflow."""
        store = ScanTemplateStore()

        # Create
        tmpl = store.create(ScanTemplate(
            name="DNS Scan",
            modules=["sfp_dnsresolve", "sfp_dnsbrute"],
            options={"_maxthreads": 5},
        ))
        assert tmpl.template_id != ""

        # Read
        found = store.get(tmpl.template_id)
        assert found.name == "DNS Scan"

        # Update
        store.update(tmpl.template_id, name="Updated DNS Scan")
        found = store.get(tmpl.template_id)
        assert found.name == "Updated DNS Scan"

        # Delete
        assert store.delete(tmpl.template_id) is True
        assert store.count == 0

    def test_bulk_scan_validation_workflow(self):
        """Full bulk scan validation workflow."""
        # Valid request
        req = BulkScanRequest(
            targets=["example.com", "test.org"],
            modules=["sfp_dnsresolve"],
        )
        assert req.validate() == []

        # Create response
        resp = BulkScanResponse(
            scans=[
                {"scan_id": "b1", "target": "example.com"},
                {"scan_id": "b2", "target": "test.org"},
            ],
            total=2,
        )
        assert resp.success_count == 2
