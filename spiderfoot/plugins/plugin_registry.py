#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         plugin_registry
# Purpose:      Plugin marketplace and registry for SpiderFoot.
#               Discover, install, update, and manage community modules
#               with dependency resolution and version compatibility.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Plugin Marketplace Registry

Manages module installation and discovery::

    from spiderfoot.plugin_registry import PluginRegistry

    registry = PluginRegistry(modules_dir="modules")

    # Search for plugins
    results = registry.search("shodan")

    # Install from registry
    registry.install("sfp_community_xyz", version="1.0.0")

    # List installed plugins
    installed = registry.list_installed()

    # Check for updates
    updates = registry.check_updates()
"""

import hashlib
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.plugin_registry")


class PluginStatus(str, Enum):
    """Plugin installation status."""
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    INCOMPATIBLE = "incompatible"
    DEPRECATED = "deprecated"


@dataclass
class PluginManifest:
    """Plugin metadata manifest (plugin.json)."""
    name: str                    # sfp_community_xyz
    display_name: str            # "Community XYZ Scanner"
    version: str                 # "1.0.0"
    description: str = ""
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""

    # Compatibility
    min_spiderfoot_version: str = "5.0.0"
    max_spiderfoot_version: str = ""
    python_requires: str = ">=3.9"
    dependencies: list[str] = field(default_factory=list)  # pip packages
    module_dependencies: list[str] = field(default_factory=list)  # other SF modules

    # Module info
    watched_events: list[str] = field(default_factory=list)
    produced_events: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)

    # Registry metadata
    download_url: str = ""
    sha256: str = ""
    size_bytes: int = 0
    downloads: int = 0
    rating: float = 0.0
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "min_spiderfoot_version": self.min_spiderfoot_version,
            "max_spiderfoot_version": self.max_spiderfoot_version,
            "python_requires": self.python_requires,
            "dependencies": self.dependencies,
            "module_dependencies": self.module_dependencies,
            "watched_events": self.watched_events,
            "produced_events": self.produced_events,
            "flags": self.flags,
            "categories": self.categories,
            "use_cases": self.use_cases,
            "download_url": self.download_url,
            "sha256": self.sha256,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        """Create a PluginManifest from a dictionary."""
        fields = {
            "name", "display_name", "version", "description",
            "author", "license", "homepage", "repository",
            "min_spiderfoot_version", "max_spiderfoot_version",
            "python_requires", "dependencies", "module_dependencies",
            "watched_events", "produced_events", "flags",
            "categories", "use_cases", "download_url", "sha256",
            "size_bytes", "downloads", "rating", "tags",
            "created_at", "updated_at",
        }
        filtered = {k: v for k, v in data.items() if k in fields}
        return cls(**filtered)


@dataclass
class InstalledPlugin:
    """Record of an installed plugin."""
    manifest: PluginManifest
    installed_at: float = field(default_factory=time.time)
    filepath: str = ""
    enabled: bool = True
    pinned_version: bool = False

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        d = self.manifest.to_dict()
        d["installed_at"] = self.installed_at
        d["filepath"] = self.filepath
        d["enabled"] = self.enabled
        d["pinned_version"] = self.pinned_version
        return d


class PluginRegistry:
    """Plugin marketplace registry for discovering and managing modules.

    Supports local (offline) and remote (registry API) sources.
    """

    REGISTRY_FILE = ".plugin_registry.json"
    STATE_FILE = ".plugin_state.json"

    def __init__(self, modules_dir: str = "modules", *,
                 registry_url: str = "") -> None:
        """
        Args:
            modules_dir: Path to modules directory.
            registry_url: URL of remote plugin registry API (optional).
        """
        self.modules_dir = os.path.abspath(modules_dir)
        self.registry_url = registry_url

        self._catalog: dict[str, PluginManifest] = {}
        self._installed: dict[str, InstalledPlugin] = {}

        # Load persisted state
        self._load_state()
        self._scan_installed()

    # ------------------------------------------------------------------
    # Catalog management
    # ------------------------------------------------------------------

    def add_to_catalog(self, manifest: PluginManifest) -> None:
        """Add a plugin manifest to the local catalog."""
        self._catalog[manifest.name] = manifest

    def load_catalog_file(self, filepath: str) -> int:
        """Load plugin catalog from a JSON file.

        Returns number of plugins loaded.
        """
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            plugins = data if isinstance(data, list) else data.get("plugins", [])
            count = 0
            for entry in plugins:
                try:
                    manifest = PluginManifest.from_dict(entry)
                    self._catalog[manifest.name] = manifest
                    count += 1
                except Exception as e:
                    log.debug("Invalid catalog entry: %s", e)

            log.info("Loaded %d plugins from catalog", count)
            return count
        except Exception as e:
            log.error("Failed to load catalog: %s", e)
            return 0

    def save_catalog(self, filepath: str | None = None) -> bool:
        """Save current catalog to JSON file."""
        path = filepath or os.path.join(
            self.modules_dir, self.REGISTRY_FILE)
        try:
            data = [m.to_dict() for m in self._catalog.values()]
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"plugins": data}, f, indent=2)
            return True
        except Exception as e:
            log.error("Failed to save catalog: %s", e)
            return False

    # ------------------------------------------------------------------
    # Search & Discovery
    # ------------------------------------------------------------------

    def search(self, query: str = "", *,
               tags: list[str] | None = None,
               categories: list[str] | None = None,
               author: str | None = None
               ) -> list[PluginManifest]:
        """Search the plugin catalog.

        Args:
            query: Text search across name, description, tags.
            tags: Filter by tags.
            categories: Filter by categories.
            author: Filter by author.
        """
        results = []
        query_lower = query.lower()

        for manifest in self._catalog.values():
            # Text search
            if query_lower:
                searchable = " ".join([
                    manifest.name,
                    manifest.display_name,
                    manifest.description,
                    " ".join(manifest.tags),
                ]).lower()
                if query_lower not in searchable:
                    continue

            # Tag filter
            if tags:
                if not set(tags).intersection(manifest.tags):
                    continue

            # Category filter
            if categories:
                if not set(categories).intersection(manifest.categories):
                    continue

            # Author filter
            if author and manifest.author.lower() != author.lower():
                continue

            results.append(manifest)

        return sorted(results, key=lambda m: m.downloads, reverse=True)

    def get_plugin(self, name: str) -> PluginManifest | None:
        """Get a specific plugin manifest from the catalog."""
        return self._catalog.get(name)

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def install(self, name: str, *,
                version: str | None = None,
                source_path: str | None = None,
                force: bool = False) -> bool:
        """Install a plugin.

        Args:
            name: Plugin name.
            version: Specific version (default: latest).
            source_path: Install from local file instead of registry.
            force: Overwrite if already installed.
        """
        # Check if already installed
        if name in self._installed and not force:
            log.warning("Plugin %s already installed (use force=True "
                       "to overwrite)", name)
            return False

        if source_path:
            return self._install_from_file(name, source_path)

        # Install from catalog
        manifest = self._catalog.get(name)
        if not manifest:
            log.error("Plugin %s not found in catalog", name)
            return False

        # Version compatibility check
        if not self._check_compatibility(manifest):
            log.error("Plugin %s is incompatible with this version",
                     name)
            return False

        # Check dependencies
        missing_deps = self._check_module_dependencies(manifest)
        if missing_deps:
            log.warning("Plugin %s requires modules: %s",
                       name, ", ".join(missing_deps))

        # Download/copy
        if manifest.download_url:
            log.info("Plugin %s requires download from: %s",
                    name, manifest.download_url)
            # In a full implementation, this would download the file
            # For now, we record the manifest
            self._installed[name] = InstalledPlugin(
                manifest=manifest,
                filepath=os.path.join(self.modules_dir, f"{name}.py"),
            )
            self._save_state()
            log.info("Registered plugin %s v%s (download pending)",
                    name, manifest.version)
            return True

        log.error("No source available for %s", name)
        return False

    def _install_from_file(self, name: str,
                           source_path: str) -> bool:
        """Install a plugin from a local file."""
        if not os.path.isfile(source_path):
            log.error("Source file not found: %s", source_path)
            return False

        # Validate Python syntax
        try:
            with open(source_path, encoding="utf-8") as f:
                source = f.read()
            compile(source, source_path, "exec")
        except SyntaxError as e:
            log.error("Plugin syntax error: %s", e)
            return False

        # Copy to modules directory
        dest = os.path.join(self.modules_dir, f"{name}.py")
        try:
            shutil.copy2(source_path, dest)
        except Exception as e:
            log.error("Failed to copy plugin: %s", e)
            return False

        # Compute hash
        sha256 = hashlib.sha256(source.encode()).hexdigest()

        # Look for manifest in catalog or create minimal
        manifest = self._catalog.get(name)
        if not manifest:
            manifest = PluginManifest(
                name=name,
                display_name=name,
                version="0.0.0",
                sha256=sha256,
            )

        self._installed[name] = InstalledPlugin(
            manifest=manifest,
            filepath=dest,
        )
        self._save_state()

        log.info("Installed plugin %s from %s", name, source_path)
        return True

    def uninstall(self, name: str, *,
                  remove_file: bool = False) -> bool:
        """Uninstall a plugin.

        Args:
            name: Plugin name.
            remove_file: Also delete the .py file.
        """
        installed = self._installed.pop(name, None)
        if not installed:
            log.warning("Plugin %s not installed", name)
            return False

        if remove_file and installed.filepath:
            try:
                if os.path.exists(installed.filepath):
                    os.remove(installed.filepath)
                    log.info("Removed file: %s", installed.filepath)
            except Exception as e:
                log.error("Failed to remove file: %s", e)

        self._save_state()
        log.info("Uninstalled plugin %s", name)
        return True

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    def check_updates(self) -> list[tuple[str, str, str]]:
        """Check for available updates.

        Returns list of (name, installed_version, available_version).
        """
        updates = []
        for name, installed in self._installed.items():
            catalog_entry = self._catalog.get(name)
            if not catalog_entry:
                continue

            if self._version_gt(catalog_entry.version,
                                installed.manifest.version):
                if not installed.pinned_version:
                    updates.append((
                        name,
                        installed.manifest.version,
                        catalog_entry.version,
                    ))

        return updates

    # ------------------------------------------------------------------
    # List / Status
    # ------------------------------------------------------------------

    def list_installed(self) -> list[InstalledPlugin]:
        """List all installed plugins."""
        return sorted(self._installed.values(),
                      key=lambda p: p.manifest.name)

    def is_installed(self, name: str) -> bool:
        """Check if a plugin is installed."""
        return name in self._installed

    def get_installed(self, name: str) -> InstalledPlugin | None:
        """Get an installed plugin by name."""
        return self._installed.get(name)

    def enable(self, name: str) -> bool:
        """Enable a plugin."""
        if name in self._installed:
            self._installed[name].enabled = True
            self._save_state()
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a plugin without uninstalling."""
        if name in self._installed:
            self._installed[name].enabled = False
            self._save_state()
            return True
        return False

    def pin_version(self, name: str, pin: bool = True) -> bool:
        """Pin a plugin to its current version (skip updates)."""
        if name in self._installed:
            self._installed[name].pinned_version = pin
            self._save_state()
            return True
        return False

    @property
    def stats(self) -> dict:
        """Return registry statistics."""
        return {
            "catalog_size": len(self._catalog),
            "installed_count": len(self._installed),
            "enabled_count": sum(1 for p in self._installed.values()
                                 if p.enabled),
            "updates_available": len(self.check_updates()),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _scan_installed(self) -> None:
        """Scan modules directory for installed plugins not yet tracked."""
        if not os.path.isdir(self.modules_dir):
            return

        import glob
        for filepath in glob.glob(
                os.path.join(self.modules_dir, "sfp_*.py")):
            name = os.path.basename(filepath).replace(".py", "")
            if name not in self._installed:
                # Already present but not tracked — register
                manifest = self._catalog.get(name)
                if not manifest:
                    manifest = PluginManifest(
                        name=name,
                        display_name=name,
                        version="0.0.0",
                    )
                self._installed[name] = InstalledPlugin(
                    manifest=manifest,
                    filepath=filepath,
                    installed_at=os.path.getmtime(filepath),
                )

    def _check_compatibility(self, manifest: PluginManifest) -> bool:
        """Check if a plugin is compatible with this SF version."""
        try:
            from spiderfoot import __version__
            current = __version__
        except ImportError:
            return True  # Can't check, assume compatible

        if manifest.min_spiderfoot_version:
            if self._version_gt(manifest.min_spiderfoot_version,
                                current):
                return False

        if manifest.max_spiderfoot_version:
            if self._version_gt(current,
                                manifest.max_spiderfoot_version):
                return False

        return True

    def _check_module_dependencies(self, manifest: PluginManifest
                                    ) -> list[str]:
        """Check which required modules are missing."""
        missing = []
        for dep in manifest.module_dependencies:
            dep_file = os.path.join(self.modules_dir, f"{dep}.py")
            if not os.path.exists(dep_file):
                missing.append(dep)
        return missing

    def _save_state(self) -> None:
        """Persist installation state."""
        path = os.path.join(self.modules_dir, self.STATE_FILE)
        try:
            data = {
                name: plugin.to_dict()
                for name, plugin in self._installed.items()
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.debug("Failed to save state: %s", e)

    def _load_state(self) -> None:
        """Load persisted installation state."""
        path = os.path.join(self.modules_dir, self.STATE_FILE)
        if not os.path.exists(path):
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            for name, info in data.items():
                manifest = PluginManifest.from_dict(info)
                self._installed[name] = InstalledPlugin(
                    manifest=manifest,
                    installed_at=info.get("installed_at", 0),
                    filepath=info.get("filepath", ""),
                    enabled=info.get("enabled", True),
                    pinned_version=info.get("pinned_version", False),
                )
        except Exception as e:
            log.debug("Failed to load state: %s", e)

    @staticmethod
    def _version_gt(v1: str, v2: str) -> bool:
        """Check if version v1 > v2 (simple numeric comparison)."""
        def _parse(v):
            return [int(x) for x in re.findall(r"\d+", v)]

        try:
            return _parse(v1) > _parse(v2)
        except (ValueError, IndexError):
            return False
