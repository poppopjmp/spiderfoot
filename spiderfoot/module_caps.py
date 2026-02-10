"""Module Capability Declarations for SpiderFoot.

Formal system for declaring module capabilities, requirements,
and compatibility constraints. Enables dependency resolution,
conflict detection, and feature discovery.
"""

import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.module_caps")


class CapabilityCategory(Enum):
    """Categories of module capabilities."""
    NETWORK = "network"         # DNS, port scanning, web requests
    DATA_SOURCE = "data_source" # External API/data integrations
    ANALYSIS = "analysis"       # Data analysis and correlation
    ENRICHMENT = "enrichment"   # Data enrichment/augmentation
    STORAGE = "storage"         # Data persistence
    NOTIFICATION = "notification"  # Alerting and notifications
    TRANSFORM = "transform"     # Data transformation/conversion


@dataclass(frozen=True)
class Capability:
    """A capability that a module provides."""
    name: str
    category: CapabilityCategory
    description: str = ""
    version: str = "1.0"

    def __str__(self) -> str:
        return f"{self.category.value}:{self.name}"


@dataclass(frozen=True)
class Requirement:
    """A requirement that a module needs from the environment."""
    name: str
    required: bool = True  # False = optional/preferred
    description: str = ""

    def __str__(self) -> str:
        prefix = "required" if self.required else "optional"
        return f"{prefix}:{self.name}"


@dataclass
class ModuleCapabilityDeclaration:
    """Complete capability declaration for a module."""
    module_name: str
    provides: set[Capability] = field(default_factory=set)
    requires: set[Requirement] = field(default_factory=set)
    conflicts_with: set[str] = field(default_factory=set)  # Module names
    tags: set[str] = field(default_factory=set)
    priority: int = 50  # 0=highest, 100=lowest

    def add_capability(
        self,
        name: str,
        category: CapabilityCategory,
        description: str = "",
        version: str = "1.0",
    ) -> "ModuleCapabilityDeclaration":
        """Add a provided capability (chainable)."""
        self.provides.add(Capability(name, category, description, version))
        return self

    def add_requirement(
        self,
        name: str,
        required: bool = True,
        description: str = "",
    ) -> "ModuleCapabilityDeclaration":
        """Add a requirement (chainable)."""
        self.requires.add(Requirement(name, required, description))
        return self

    def add_conflict(self, module_name: str) -> "ModuleCapabilityDeclaration":
        """Declare conflict with another module (chainable)."""
        self.conflicts_with.add(module_name)
        return self

    def add_tag(self, tag: str) -> "ModuleCapabilityDeclaration":
        """Add a descriptive tag (chainable)."""
        self.tags.add(tag)
        return self

    @property
    def capability_names(self) -> set[str]:
        return {c.name for c in self.provides}

    @property
    def required_names(self) -> set[str]:
        return {r.name for r in self.requires if r.required}

    @property
    def optional_names(self) -> set[str]:
        return {r.name for r in self.requires if not r.required}

    def to_dict(self) -> dict:
        return {
            "module": self.module_name,
            "provides": [
                {"name": c.name, "category": c.category.value,
                 "description": c.description, "version": c.version}
                for c in self.provides
            ],
            "requires": [
                {"name": r.name, "required": r.required,
                 "description": r.description}
                for r in self.requires
            ],
            "conflicts_with": sorted(self.conflicts_with),
            "tags": sorted(self.tags),
            "priority": self.priority,
        }


class CapabilityRegistry:
    """Central registry for module capability declarations.

    Usage:
        registry = CapabilityRegistry()

        decl = ModuleCapabilityDeclaration(module_name="sfp_dns")
        decl.add_capability("dns_resolution", CapabilityCategory.NETWORK)
        decl.add_requirement("network_access")

        registry.register(decl)

        # Find modules that provide DNS resolution
        modules = registry.find_providers("dns_resolution")

        # Check for conflicts
        conflicts = registry.find_conflicts(["sfp_dns", "sfp_portscan"])
    """

    def __init__(self):
        self._declarations: dict[str, ModuleCapabilityDeclaration] = {}
        self._capability_index: dict[str, set[str]] = {}  # cap_name → module_names
        self._lock = threading.Lock()

    def register(self, declaration: ModuleCapabilityDeclaration) -> None:
        """Register a module's capability declaration."""
        with self._lock:
            self._declarations[declaration.module_name] = declaration
            for cap in declaration.provides:
                if cap.name not in self._capability_index:
                    self._capability_index[cap.name] = set()
                self._capability_index[cap.name].add(declaration.module_name)

    def unregister(self, module_name: str) -> None:
        """Remove a module's declaration."""
        with self._lock:
            decl = self._declarations.pop(module_name, None)
            if decl:
                for cap in decl.provides:
                    providers = self._capability_index.get(cap.name, set())
                    providers.discard(module_name)
                    if not providers:
                        self._capability_index.pop(cap.name, None)

    def get(self, module_name: str) -> Optional[ModuleCapabilityDeclaration]:
        """Get a module's declaration."""
        with self._lock:
            return self._declarations.get(module_name)

    def find_providers(self, capability_name: str) -> list[str]:
        """Find modules that provide a specific capability."""
        with self._lock:
            return sorted(self._capability_index.get(capability_name, set()))

    def find_by_category(self, category: CapabilityCategory) -> list[str]:
        """Find modules with capabilities in a specific category."""
        with self._lock:
            result = set()
            for decl in self._declarations.values():
                for cap in decl.provides:
                    if cap.category == category:
                        result.add(decl.module_name)
            return sorted(result)

    def find_by_tag(self, tag: str) -> list[str]:
        """Find modules with a specific tag."""
        with self._lock:
            return sorted(
                name for name, decl in self._declarations.items()
                if tag in decl.tags
            )

    def find_conflicts(self, module_names: list[str]) -> list[tuple[str, str]]:
        """Find conflicting pairs among a set of modules.

        Returns list of (module_a, module_b) conflict pairs.
        """
        with self._lock:
            conflicts = []
            name_set = set(module_names)
            for name in module_names:
                decl = self._declarations.get(name)
                if decl:
                    for conflict in decl.conflicts_with:
                        if conflict in name_set:
                            pair = tuple(sorted([name, conflict]))
                            if pair not in conflicts:
                                conflicts.append(pair)
            return conflicts

    def check_requirements(
        self, module_names: list[str]
    ) -> dict[str, list[str]]:
        """Check which requirements are unmet for each module.

        Returns dict of module_name → list of unmet required requirement names.
        """
        with self._lock:
            # Build set of all capabilities provided by selected modules
            all_caps = set()
            for name in module_names:
                decl = self._declarations.get(name)
                if decl:
                    all_caps.update(c.name for c in decl.provides)

            unmet = {}
            for name in module_names:
                decl = self._declarations.get(name)
                if decl:
                    missing = []
                    for req in decl.requires:
                        if req.required and req.name not in all_caps:
                            missing.append(req.name)
                    if missing:
                        unmet[name] = missing
            return unmet

    def get_dependency_order(self, module_names: list[str]) -> list[str]:
        """Order modules by priority (lower priority number = earlier).

        Modules with fewer requirements are scheduled earlier.
        """
        with self._lock:
            decorated = []
            for name in module_names:
                decl = self._declarations.get(name)
                priority = decl.priority if decl else 50
                req_count = len(decl.required_names) if decl else 0
                decorated.append((priority, req_count, name))
            decorated.sort()
            return [name for _, _, name in decorated]

    def get_all_capabilities(self) -> dict[str, list[str]]:
        """Get all registered capabilities and their providers."""
        with self._lock:
            return {
                cap: sorted(providers)
                for cap, providers in self._capability_index.items()
            }

    def get_all_tags(self) -> dict[str, int]:
        """Get all tags and their usage counts."""
        with self._lock:
            tags: dict[str, int] = {}
            for decl in self._declarations.values():
                for tag in decl.tags:
                    tags[tag] = tags.get(tag, 0) + 1
            return tags

    @property
    def module_count(self) -> int:
        with self._lock:
            return len(self._declarations)

    @property
    def capability_count(self) -> int:
        with self._lock:
            return len(self._capability_index)

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "modules": {
                    name: decl.to_dict()
                    for name, decl in self._declarations.items()
                },
                "capabilities": {
                    cap: sorted(providers)
                    for cap, providers in self._capability_index.items()
                },
                "module_count": len(self._declarations),
                "capability_count": len(self._capability_index),
            }


# Singleton
_global_registry: Optional[CapabilityRegistry] = None
_registry_lock = threading.Lock()


def get_capability_registry() -> CapabilityRegistry:
    """Get the global capability registry singleton."""
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = CapabilityRegistry()
    return _global_registry
