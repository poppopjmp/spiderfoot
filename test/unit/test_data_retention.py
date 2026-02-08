"""Tests for spiderfoot.data_retention."""

import os
import time

import pytest

from spiderfoot.data_retention import (
    FileResourceAdapter,
    InMemoryResourceAdapter,
    RetentionAction,
    RetentionCandidate,
    RetentionManager,
    RetentionResult,
    RetentionRule,
)


@pytest.fixture
def adapter():
    return InMemoryResourceAdapter()


@pytest.fixture
def manager(adapter):
    return RetentionManager(adapter=adapter)


def make_candidates(resource, count, age_days=0, size=100):
    """Generate test candidates."""
    now = time.time()
    items = []
    for i in range(count):
        items.append(RetentionCandidate(
            resource=resource,
            identifier=f"{resource}_{i}",
            age_days=age_days + i,
            size_bytes=size,
            created_at=now - (age_days + i) * 86400,
        ))
    return items


class TestRetentionRule:
    def test_defaults(self):
        r = RetentionRule(name="test", resource="scans")
        assert r.max_age_days == 0
        assert r.max_count == 0
        assert r.action == RetentionAction.DELETE
        assert r.enabled is True

    def test_to_dict_from_dict(self):
        r = RetentionRule(
            name="test", resource="scans",
            max_age_days=30, max_count=10,
            action=RetentionAction.ARCHIVE,
        )
        d = r.to_dict()
        restored = RetentionRule.from_dict(d)
        assert restored.name == "test"
        assert restored.max_age_days == 30
        assert restored.action == RetentionAction.ARCHIVE


class TestInMemoryAdapter:
    def test_add_and_list(self, adapter):
        items = make_candidates("scans", 3)
        adapter.add_items("scans", items)
        listed = adapter.list_items("scans")
        assert len(listed) == 3

    def test_delete(self, adapter):
        items = make_candidates("scans", 2)
        adapter.add_items("scans", items)
        assert adapter.delete_item(items[0]) is True
        assert len(adapter.list_items("scans")) == 1

    def test_delete_nonexistent(self, adapter):
        c = RetentionCandidate(resource="x", identifier="ghost")
        assert adapter.delete_item(c) is False


class TestRetentionManager:
    def test_add_remove_rule(self, manager):
        rule = RetentionRule(name="r1", resource="scans",
                            max_age_days=30)
        manager.add_rule(rule)
        assert manager.get_rule("r1") is not None
        assert manager.remove_rule("r1") is True
        assert manager.remove_rule("r1") is False

    def test_list_rules(self, manager):
        manager.add_rule(RetentionRule(name="a", resource="scans"))
        manager.add_rule(RetentionRule(name="b", resource="logs"))
        assert len(manager.list_rules()) == 2

    def test_age_based_cleanup(self, manager, adapter):
        items = make_candidates("scans", 5, age_days=10)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="old_scans", resource="scans",
            max_age_days=12,
        ))

        preview = manager.preview()
        assert len(preview) == 1
        # Items aged 12, 13, 14 should be candidates
        assert preview[0].candidates_found == 3
        assert preview[0].dry_run is True

        # Enforce
        results = manager.enforce()
        assert results[0].items_processed == 3
        assert len(adapter.list_items("scans")) == 2

    def test_count_based_cleanup(self, manager, adapter):
        items = make_candidates("scans", 10)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="max_scans", resource="scans",
            max_count=5,
        ))

        results = manager.enforce()
        assert results[0].items_processed == 5
        assert len(adapter.list_items("scans")) == 5

    def test_size_based_cleanup(self, manager, adapter):
        # 10 items at 1MB each = 10MB total
        items = make_candidates("logs", 10, size=1024 * 1024)
        adapter.add_items("logs", items)

        manager.add_rule(RetentionRule(
            name="log_size", resource="logs",
            max_size_mb=5.0,
        ))

        results = manager.enforce()
        remaining = adapter.list_items("logs")
        total_remaining = sum(i.size_bytes for i in remaining)
        assert total_remaining <= 5 * 1024 * 1024

    def test_archive_action(self, manager, adapter):
        items = make_candidates("scans", 3, age_days=100)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="archive_old", resource="scans",
            max_age_days=50,
            action=RetentionAction.ARCHIVE,
        ))

        results = manager.enforce()
        assert results[0].items_processed == 3

    def test_disabled_rule(self, manager, adapter):
        items = make_candidates("scans", 5, age_days=100)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="disabled", resource="scans",
            max_age_days=10,
            enabled=False,
        ))

        results = manager.enforce()
        assert len(results) == 0  # Disabled rules skipped

    def test_specific_rule(self, manager, adapter):
        items = make_candidates("scans", 5, age_days=100)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="r1", resource="scans", max_count=3))
        manager.add_rule(RetentionRule(
            name="r2", resource="scans", max_count=1))

        results = manager.enforce(rule_name="r1")
        assert len(results) == 1
        assert results[0].rule_name == "r1"

    def test_exclude_pattern(self, manager, adapter):
        items = [
            RetentionCandidate(
                resource="scans", identifier="scan_important",
                age_days=100, created_at=time.time() - 100 * 86400),
            RetentionCandidate(
                resource="scans", identifier="scan_normal",
                age_days=100, created_at=time.time() - 100 * 86400),
        ]
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="cleanup", resource="scans",
            max_age_days=30,
            exclude_pattern="important",
        ))

        results = manager.enforce()
        assert results[0].items_processed == 1
        remaining = adapter.list_items("scans")
        assert any("important" in r.identifier for r in remaining)

    def test_preview_does_not_modify(self, manager, adapter):
        items = make_candidates("scans", 5, age_days=100)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="r1", resource="scans", max_age_days=10))

        manager.preview()
        assert len(adapter.list_items("scans")) == 5  # Unchanged

    def test_history(self, manager, adapter):
        items = make_candidates("scans", 3, age_days=100)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="r1", resource="scans", max_age_days=10))
        manager.enforce()

        assert len(manager.history) == 1
        assert manager.history[0].rule_name == "r1"

    def test_stats(self, manager, adapter):
        items = make_candidates("scans", 5, age_days=100, size=500)
        adapter.add_items("scans", items)

        manager.add_rule(RetentionRule(
            name="r1", resource="scans", max_age_days=10))
        manager.enforce()

        s = manager.stats
        assert s["rules"] == 1
        assert s["enforcement_runs"] == 1
        assert s["total_items_processed"] == 5
        assert s["total_bytes_freed"] == 2500

    def test_result_to_dict(self):
        r = RetentionResult(
            rule_name="test",
            candidates_found=5,
            items_processed=3,
            bytes_freed=1024,
        )
        d = r.to_dict()
        assert d["rule_name"] == "test"
        assert d["items_processed"] == 3

    def test_empty_resource(self, manager, adapter):
        manager.add_rule(RetentionRule(
            name="r1", resource="empty", max_count=5))
        results = manager.enforce()
        assert results[0].candidates_found == 0


class TestFileResourceAdapter:
    def test_list_items(self, tmp_path):
        # Create test files
        for i in range(3):
            f = tmp_path / f"file_{i}.txt"
            f.write_text(f"content {i}")

        adapter = FileResourceAdapter(
            directories={"logs": str(tmp_path)})
        items = adapter.list_items("logs")
        assert len(items) == 3

    def test_delete_item(self, tmp_path):
        f = tmp_path / "delete_me.txt"
        f.write_text("bye")

        adapter = FileResourceAdapter()
        c = RetentionCandidate(
            resource="logs", identifier=str(f))
        assert adapter.delete_item(c) is True
        assert not f.exists()

    def test_archive_item(self, tmp_path):
        f = tmp_path / "archive_me.txt"
        f.write_text("archive")

        adapter = FileResourceAdapter()
        c = RetentionCandidate(
            resource="logs", identifier=str(f))
        assert adapter.archive_item(c) is True
        assert not f.exists()
        assert (tmp_path / ".archive" / "archive_me.txt").exists()

    def test_list_nonexistent_dir(self):
        adapter = FileResourceAdapter(
            directories={"x": "/nonexistent/path"})
        assert adapter.list_items("x") == []

    def test_set_directory(self, tmp_path):
        adapter = FileResourceAdapter()
        adapter.set_directory("logs", str(tmp_path))
        assert adapter.list_items("logs") is not None
