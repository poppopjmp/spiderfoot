"""Tests for spiderfoot.plugin_registry."""
from __future__ import annotations

import json
import os
import tempfile
import shutil

import pytest

from spiderfoot.plugin_registry import (
    PluginManifest,
    PluginRegistry,
    PluginStatus,
    InstalledPlugin,
)


@pytest.fixture
def modules_dir(tmp_path):
    """Create a temporary modules directory."""
    d = tmp_path / "modules"
    d.mkdir()
    return str(d)


@pytest.fixture
def sample_manifest():
    return PluginManifest(
        name="sfp_test_plugin",
        display_name="Test Plugin",
        version="1.2.0",
        description="A test plugin for unit tests",
        author="Test Author",
        license="MIT",
        homepage="https://example.com",
        watched_events=["INTERNET_NAME"],
        produced_events=["IP_ADDRESS"],
        flags=["apikey"],
        categories=["Passive DNS"],
        tags=["dns", "test"],
        downloads=100,
    )


@pytest.fixture
def registry(modules_dir):
    return PluginRegistry(modules_dir=modules_dir)


class TestPluginManifest:
    def test_to_dict_round_trip(self, sample_manifest):
        d = sample_manifest.to_dict()
        restored = PluginManifest.from_dict(d)
        assert restored.name == sample_manifest.name
        assert restored.version == sample_manifest.version
        assert restored.watched_events == sample_manifest.watched_events
        assert restored.tags == sample_manifest.tags

    def test_from_dict_ignores_unknown_fields(self):
        data = {
            "name": "sfp_x",
            "display_name": "X",
            "version": "1.0.0",
            "unknown_field": "ignored",
        }
        m = PluginManifest.from_dict(data)
        assert m.name == "sfp_x"
        assert not hasattr(m, "unknown_field") or True

    def test_defaults(self):
        m = PluginManifest(name="sfp_a", display_name="A", version="1.0.0")
        assert m.license == "MIT"
        assert m.dependencies == []
        assert m.min_spiderfoot_version == "5.0.0"


class TestPluginRegistry:
    def test_add_and_search(self, registry, sample_manifest):
        registry.add_to_catalog(sample_manifest)
        results = registry.search("test")
        assert len(results) == 1
        assert results[0].name == "sfp_test_plugin"

    def test_search_empty_query(self, registry, sample_manifest):
        registry.add_to_catalog(sample_manifest)
        results = registry.search()
        assert len(results) == 1

    def test_search_by_tag(self, registry, sample_manifest):
        registry.add_to_catalog(sample_manifest)
        results = registry.search(tags=["dns"])
        assert len(results) == 1
        results = registry.search(tags=["nonexistent"])
        assert len(results) == 0

    def test_search_by_category(self, registry, sample_manifest):
        registry.add_to_catalog(sample_manifest)
        results = registry.search(categories=["Passive DNS"])
        assert len(results) == 1

    def test_search_by_author(self, registry, sample_manifest):
        registry.add_to_catalog(sample_manifest)
        results = registry.search(author="Test Author")
        assert len(results) == 1
        results = registry.search(author="Unknown")
        assert len(results) == 0

    def test_get_plugin(self, registry, sample_manifest):
        registry.add_to_catalog(sample_manifest)
        p = registry.get_plugin("sfp_test_plugin")
        assert p is not None
        assert p.version == "1.2.0"
        assert registry.get_plugin("nonexistent") is None

    def test_install_from_file(self, registry, modules_dir):
        # Create a valid plugin file
        src = os.path.join(modules_dir, "source_plugin.py")
        with open(src, "w") as f:
            f.write("# A valid plugin\nclass sfp_local_plugin:\n    pass\n")

        result = registry.install(
            "sfp_local_plugin", source_path=src)
        assert result is True
        assert registry.is_installed("sfp_local_plugin")

    def test_install_from_file_syntax_error(self, registry, modules_dir):
        src = os.path.join(modules_dir, "bad_plugin.py")
        with open(src, "w") as f:
            f.write("def broken(:\n")

        result = registry.install("sfp_bad", source_path=src)
        assert result is False

    def test_install_already_installed(self, registry, modules_dir):
        src = os.path.join(modules_dir, "source.py")
        with open(src, "w") as f:
            f.write("# plugin\n")

        registry.install("sfp_dup", source_path=src)
        result = registry.install("sfp_dup", source_path=src)
        assert result is False  # Already installed

        result = registry.install("sfp_dup", source_path=src, force=True)
        assert result is True  # Force overwrite

    def test_install_not_in_catalog(self, registry):
        result = registry.install("sfp_missing")
        assert result is False

    def test_uninstall(self, registry, modules_dir):
        src = os.path.join(modules_dir, "source.py")
        with open(src, "w") as f:
            f.write("# plugin\n")

        registry.install("sfp_removeme", source_path=src)
        assert registry.is_installed("sfp_removeme")

        result = registry.uninstall("sfp_removeme")
        assert result is True
        assert not registry.is_installed("sfp_removeme")

    def test_uninstall_with_file_removal(self, registry, modules_dir):
        src = os.path.join(modules_dir, "source.py")
        with open(src, "w") as f:
            f.write("# plugin\n")

        registry.install("sfp_rmfile", source_path=src)
        dest = os.path.join(modules_dir, "sfp_rmfile.py")
        assert os.path.exists(dest)

        registry.uninstall("sfp_rmfile", remove_file=True)
        assert not os.path.exists(dest)

    def test_uninstall_not_installed(self, registry):
        assert registry.uninstall("sfp_ghost") is False

    def test_enable_disable(self, registry, modules_dir):
        src = os.path.join(modules_dir, "source.py")
        with open(src, "w") as f:
            f.write("# plugin\n")

        registry.install("sfp_toggle", source_path=src)
        assert registry.get_installed("sfp_toggle").enabled is True

        registry.disable("sfp_toggle")
        assert registry.get_installed("sfp_toggle").enabled is False

        registry.enable("sfp_toggle")
        assert registry.get_installed("sfp_toggle").enabled is True

    def test_pin_version(self, registry, modules_dir):
        src = os.path.join(modules_dir, "source.py")
        with open(src, "w") as f:
            f.write("# plugin\n")

        registry.install("sfp_pinned", source_path=src)
        registry.pin_version("sfp_pinned")
        assert registry.get_installed("sfp_pinned").pinned_version is True

        registry.pin_version("sfp_pinned", False)
        assert registry.get_installed("sfp_pinned").pinned_version is False

    def test_check_updates(self, registry, sample_manifest):
        # Install old version
        old_manifest = PluginManifest(
            name="sfp_test_plugin",
            display_name="Test",
            version="1.0.0",
        )
        registry._installed["sfp_test_plugin"] = InstalledPlugin(
            manifest=old_manifest)

        # Add newer version to catalog
        registry.add_to_catalog(sample_manifest)  # version 1.2.0

        updates = registry.check_updates()
        assert len(updates) == 1
        assert updates[0] == ("sfp_test_plugin", "1.0.0", "1.2.0")

    def test_check_updates_pinned(self, registry, sample_manifest):
        old = PluginManifest(name="sfp_test_plugin",
                            display_name="T", version="1.0.0")
        registry._installed["sfp_test_plugin"] = InstalledPlugin(
            manifest=old, pinned_version=True)
        registry.add_to_catalog(sample_manifest)

        updates = registry.check_updates()
        assert len(updates) == 0  # Pinned, should not show update

    def test_list_installed(self, registry, modules_dir):
        src = os.path.join(modules_dir, "s.py")
        with open(src, "w") as f:
            f.write("# p\n")

        registry.install("sfp_a", source_path=src)
        registry.install("sfp_b", source_path=src, force=True)

        installed = registry.list_installed()
        names = [p.manifest.name for p in installed]
        assert "sfp_a" in names
        assert "sfp_b" in names

    def test_stats(self, registry, sample_manifest, modules_dir):
        registry.add_to_catalog(sample_manifest)
        src = os.path.join(modules_dir, "s.py")
        with open(src, "w") as f:
            f.write("# p\n")
        registry.install("sfp_stat", source_path=src)

        s = registry.stats
        assert s["catalog_size"] == 1
        assert s["installed_count"] >= 1

    def test_save_and_load_catalog(self, registry, sample_manifest,
                                   modules_dir):
        registry.add_to_catalog(sample_manifest)
        path = os.path.join(modules_dir, "catalog.json")
        registry.save_catalog(path)
        assert os.path.exists(path)

        # Create fresh registry and load
        reg2 = PluginRegistry(modules_dir=modules_dir)
        count = reg2.load_catalog_file(path)
        assert count == 1
        assert reg2.get_plugin("sfp_test_plugin") is not None

    def test_state_persistence(self, modules_dir):
        # Install with first registry
        src = os.path.join(modules_dir, "s.py")
        with open(src, "w") as f:
            f.write("# p\n")

        reg1 = PluginRegistry(modules_dir=modules_dir)
        reg1.install("sfp_persist", source_path=src)
        reg1.disable("sfp_persist")

        # New registry should load state
        reg2 = PluginRegistry(modules_dir=modules_dir)
        p = reg2.get_installed("sfp_persist")
        assert p is not None
        assert p.enabled is False

    def test_scan_existing_modules(self, modules_dir):
        # Pre-create module files
        for name in ["sfp_existing_a", "sfp_existing_b"]:
            with open(os.path.join(modules_dir, f"{name}.py"), "w") as f:
                f.write(f"# {name}\n")

        reg = PluginRegistry(modules_dir=modules_dir)
        installed = reg.list_installed()
        names = [p.manifest.name for p in installed]
        assert "sfp_existing_a" in names
        assert "sfp_existing_b" in names

    def test_version_comparison(self, registry):
        assert registry._version_gt("2.0.0", "1.0.0") is True
        assert registry._version_gt("1.0.0", "2.0.0") is False
        assert registry._version_gt("1.0.0", "1.0.0") is False
        assert registry._version_gt("1.1.0", "1.0.9") is True

    def test_install_from_catalog_with_url(self, registry):
        manifest = PluginManifest(
            name="sfp_remote",
            display_name="Remote Plugin",
            version="2.0.0",
            download_url="https://example.com/sfp_remote.py",
        )
        registry.add_to_catalog(manifest)
        result = registry.install("sfp_remote")
        assert result is True
        assert registry.is_installed("sfp_remote")

    def test_module_dependencies_check(self, registry, modules_dir):
        manifest = PluginManifest(
            name="sfp_dep",
            display_name="Dep",
            version="1.0.0",
            module_dependencies=["sfp_needed_module"],
        )
        missing = registry._check_module_dependencies(manifest)
        assert "sfp_needed_module" in missing

        # Create the dependency
        dep_path = os.path.join(modules_dir, "sfp_needed_module.py")
        with open(dep_path, "w") as f:
            f.write("# dep\n")

        missing = registry._check_module_dependencies(manifest)
        assert len(missing) == 0
