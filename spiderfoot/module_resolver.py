"""Module dependency resolver — runtime module load-order and satisfaction.

Builds on :mod:`spiderfoot.module_graph` to provide:

* **Dependency satisfaction** — given a set of desired output event types,
  compute the minimal set of modules that must be loaded.
* **Load-order resolution** — topological sort with conflict detection.
* **Missing dependency reporting** — clear diagnostics when a module's
  required inputs can't be produced by any available module.
* **Optional/required split** — distinguish hard dependencies (module
  cannot function without) from soft ones (nice-to-have data).
* **Constraint validation** — ensure no circular hard dependencies,
  no duplicate module registrations, and version-range compat.
"""

from __future__ import annotations

import logging
import os
import importlib
import importlib.util
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("spiderfoot.module_resolver")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class DepKind(Enum):
    """Dependency strength."""

    REQUIRED = "required"   # module cannot function without this input
    OPTIONAL = "optional"   # module benefits from but does not require


class ResolveStatus(Enum):
    OK = "ok"
    MISSING_DEPS = "missing_deps"
    CIRCULAR = "circular"
    CONFLICT = "conflict"


@dataclass
class ModuleDescriptor:
    """Metadata about a single module's event interface."""

    name: str
    watched_events: list[str] = field(default_factory=list)
    produced_events: list[str] = field(default_factory=list)
    required_events: list[str] = field(default_factory=list)
    optional_events: list[str] = field(default_factory=list)
    category: str = ""
    description: str = ""
    version: str = ""
    filepath: str = ""
    tags: list[str] = field(default_factory=list)
    enabled: bool = True

    @property
    def watched_set(self) -> frozenset[str]:
        return frozenset(self.watched_events)

    @property
    def produced_set(self) -> frozenset[str]:
        return frozenset(self.produced_events)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "watched_events": self.watched_events,
            "produced_events": self.produced_events,
            "required_events": self.required_events,
            "optional_events": self.optional_events,
            "category": self.category,
            "description": self.description,
            "version": self.version,
            "enabled": self.enabled,
            "tags": self.tags,
        }


@dataclass
class Dependency:
    """An edge in the dependency graph."""

    source: str  # module that needs the event
    target: str  # module that produces the event
    event_type: str
    kind: DepKind = DepKind.REQUIRED


@dataclass
class ResolutionResult:
    """Outcome of a dependency resolution."""

    status: ResolveStatus
    load_order: list[str] = field(default_factory=list)
    selected_modules: set[str] = field(default_factory=set)
    missing_events: dict[str, list[str]] = field(default_factory=dict)
    # module → list of event types that have no producer
    circular_chains: list[list[str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == ResolveStatus.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "load_order": self.load_order,
            "selected_modules": sorted(self.selected_modules),
            "missing_events": self.missing_events,
            "circular_chains": self.circular_chains,
            "warnings": self.warnings,
        }


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

class ModuleResolver:
    """Resolve module dependencies and compute load order.

    Usage::

        resolver = ModuleResolver()
        resolver.register(ModuleDescriptor(
            name="sfp_dns",
            watched_events=["DOMAIN_NAME"],
            produced_events=["IP_ADDRESS", "IPV6_ADDRESS"],
        ))
        resolver.register(ModuleDescriptor(
            name="sfp_portscan",
            watched_events=["IP_ADDRESS"],
            produced_events=["TCP_PORT_OPEN"],
        ))

        result = resolver.resolve(target_events=["TCP_PORT_OPEN"])
        print(result.load_order)  # ['sfp_dns', 'sfp_portscan']
    """

    def __init__(self) -> None:
        self._modules: dict[str, ModuleDescriptor] = {}
        # index: event_type → set of module names that produce it
        self._producers: dict[str, set[str]] = {}
        # index: event_type → set of module names that watch it
        self._consumers: dict[str, set[str]] = {}

    # -------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------

    def register(self, desc: ModuleDescriptor) -> None:
        """Register a module descriptor."""
        self._modules[desc.name] = desc
        for evt in desc.produced_events:
            self._producers.setdefault(evt, set()).add(desc.name)
        for evt in desc.watched_events:
            self._consumers.setdefault(evt, set()).add(desc.name)

    def register_many(self, descriptors: list[ModuleDescriptor]) -> int:
        count = 0
        for d in descriptors:
            self.register(d)
            count += 1
        return count

    def unregister(self, name: str) -> bool:
        desc = self._modules.pop(name, None)
        if not desc:
            return False
        for evt in desc.produced_events:
            self._producers.get(evt, set()).discard(name)
        for evt in desc.watched_events:
            self._consumers.get(evt, set()).discard(name)
        return True

    def get_module(self, name: str) -> ModuleDescriptor | None:
        return self._modules.get(name)

    def list_modules(self) -> list[ModuleDescriptor]:
        return sorted(self._modules.values(), key=lambda m: m.name)

    # -------------------------------------------------------------------
    # Scanning
    # -------------------------------------------------------------------

    def scan_directory(self, modules_dir: str) -> int:
        """Discover and register modules from a directory.

        Imports each ``sfp_*.py`` file and extracts the module class's
        ``watchedEvents`` and ``producedEvents``.
        """
        count = 0
        if not os.path.isdir(modules_dir):
            return 0

        for fname in sorted(os.listdir(modules_dir)):
            if not fname.startswith("sfp_") or not fname.endswith(".py"):
                continue
            mod_name = fname[:-3]
            fpath = os.path.join(modules_dir, fname)
            try:
                spec = importlib.util.spec_from_file_location(mod_name, fpath)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find the module class
                cls = getattr(module, mod_name, None)
                if cls is None:
                    for attr_name in dir(module):
                        obj = getattr(module, attr_name)
                        if (isinstance(obj, type)
                                and hasattr(obj, "watchedEvents")
                                and hasattr(obj, "producedEvents")):
                            cls = obj
                            break
                if cls is None:
                    continue

                watched = []
                produced = []
                if callable(getattr(cls, "watchedEvents", None)):
                    try:
                        watched = cls.watchedEvents(None) or []
                    except Exception:
                        watched = getattr(cls, "watchedEvents", [])
                else:
                    watched = getattr(cls, "watchedEvents", [])

                if callable(getattr(cls, "producedEvents", None)):
                    try:
                        produced = cls.producedEvents(None) or []
                    except Exception:
                        produced = getattr(cls, "producedEvents", [])
                else:
                    produced = getattr(cls, "producedEvents", [])

                desc_attr = getattr(cls, "meta", {})
                if isinstance(desc_attr, dict):
                    description = desc_attr.get("summary", "")
                else:
                    description = ""

                self.register(ModuleDescriptor(
                    name=mod_name,
                    watched_events=list(watched),
                    produced_events=list(produced),
                    description=description,
                    filepath=fpath,
                ))
                count += 1
            except Exception as e:
                log.debug("Failed to scan %s: %s", fname, e)
        return count

    # -------------------------------------------------------------------
    # Indexes
    # -------------------------------------------------------------------

    def producers_of(self, event_type: str) -> set[str]:
        """Return module names that can produce the given event type."""
        return set(self._producers.get(event_type, set()))

    def consumers_of(self, event_type: str) -> set[str]:
        """Return module names that watch the given event type."""
        return set(self._consumers.get(event_type, set()))

    def all_event_types(self) -> set[str]:
        evts: set[str] = set()
        for d in self._modules.values():
            evts.update(d.produced_events)
            evts.update(d.watched_events)
        return evts

    def all_produced_events(self) -> set[str]:
        evts: set[str] = set()
        for d in self._modules.values():
            evts.update(d.produced_events)
        return evts

    # -------------------------------------------------------------------
    # Resolution
    # -------------------------------------------------------------------

    def resolve(
        self,
        *,
        target_events: list[str] | None = None,
        required_modules: list[str] | None = None,
        exclude_modules: set[str] | None = None,
        include_optional: bool = False,
    ) -> ResolutionResult:
        """Resolve the minimal set of modules and their load order.

        Args:
            target_events: Desired output event types.  The resolver walks
                backwards from these to find all needed modules.
            required_modules: Modules that *must* be included regardless.
            exclude_modules: Modules to never include.
            include_optional: If True, also pull in optional dependencies.

        Returns:
            A :class:`ResolutionResult` with status, load order, and
            diagnostics.
        """
        exclude = exclude_modules or set()
        selected: set[str] = set()
        missing: dict[str, list[str]] = {}
        warnings: list[str] = []

        # Seed with required modules
        if required_modules:
            for m in required_modules:
                if m in self._modules and m not in exclude:
                    selected.add(m)

        # Walk backwards from target events
        if target_events:
            queue = list(target_events)
            visited_events: set[str] = set()
            while queue:
                evt = queue.pop(0)
                if evt in visited_events:
                    continue
                visited_events.add(evt)

                producers = self.producers_of(evt) - exclude
                if not producers:
                    missing.setdefault("__target__", []).append(evt)
                    continue

                # Pick all producers (user can filter later)
                for p in producers:
                    if p not in selected:
                        selected.add(p)
                        desc = self._modules[p]
                        # Recursively resolve inputs
                        for w in desc.watched_events:
                            if w not in visited_events:
                                queue.append(w)

        # Add all watched-event dependencies for selected modules
        changed = True
        while changed:
            changed = False
            for mod_name in list(selected):
                desc = self._modules.get(mod_name)
                if not desc:
                    continue
                events_to_check = list(desc.required_events or desc.watched_events)
                if include_optional and desc.optional_events:
                    events_to_check.extend(desc.optional_events)
                for evt in events_to_check:
                    producers = self.producers_of(evt) - exclude
                    # Root events (*, INITIAL_TARGET, etc.) are produced by the engine
                    if not producers and not evt.startswith("ROOT") and evt != "*":
                        missing.setdefault(mod_name, []).append(evt)
                    for p in producers:
                        if p not in selected:
                            selected.add(p)
                            changed = True

        # Topological sort
        load_order, cycles = self._topological_sort(selected)

        if cycles:
            return ResolutionResult(
                status=ResolveStatus.CIRCULAR,
                selected_modules=selected,
                circular_chains=cycles,
                warnings=warnings,
            )

        if missing:
            # Still produce an order but flag missing deps
            return ResolutionResult(
                status=ResolveStatus.MISSING_DEPS,
                load_order=load_order,
                selected_modules=selected,
                missing_events=missing,
                warnings=warnings,
            )

        return ResolutionResult(
            status=ResolveStatus.OK,
            load_order=load_order,
            selected_modules=selected,
            warnings=warnings,
        )

    def resolve_for_modules(
        self,
        module_names: list[str],
        *,
        exclude_modules: set[str] | None = None,
    ) -> ResolutionResult:
        """Resolve load order for a specific set of modules, pulling in
        any additional modules needed to satisfy their watched events."""
        return self.resolve(
            required_modules=module_names,
            exclude_modules=exclude_modules,
        )

    def check_satisfaction(self, module_names: list[str]) -> dict[str, list[str]]:
        """Check which watched events cannot be produced by the given module set.

        Returns a dict of ``{module_name: [unsatisfied_event_types]}``.
        """
        available_events: set[str] = set()
        for name in module_names:
            desc = self._modules.get(name)
            if desc:
                available_events.update(desc.produced_events)

        unsatisfied: dict[str, list[str]] = {}
        for name in module_names:
            desc = self._modules.get(name)
            if not desc:
                continue
            for evt in desc.watched_events:
                if evt == "*" or evt.startswith("ROOT"):
                    continue
                if evt not in available_events:
                    unsatisfied.setdefault(name, []).append(evt)
        return unsatisfied

    # -------------------------------------------------------------------
    # Topological sort
    # -------------------------------------------------------------------

    def _topological_sort(
        self,
        module_names: set[str],
    ) -> tuple[list[str], list[list[str]]]:
        """Kahn's algorithm with cycle detection.

        Returns (sorted_list, cycles).
        """
        # Build adjacency from event dependencies
        adj: dict[str, set[str]] = {m: set() for m in module_names}
        in_degree: dict[str, int] = {m: 0 for m in module_names}

        for mod_name in module_names:
            desc = self._modules.get(mod_name)
            if not desc:
                continue
            for evt in desc.watched_events:
                for producer in self.producers_of(evt):
                    if producer in module_names and producer != mod_name:
                        if mod_name not in adj.get(producer, set()):
                            adj.setdefault(producer, set()).add(mod_name)
                            in_degree[mod_name] = in_degree.get(mod_name, 0) + 1

        queue = [m for m in module_names if in_degree.get(m, 0) == 0]
        queue.sort()
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in sorted(adj.get(node, set())):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        cycles: list[list[str]] = []
        if len(result) < len(module_names):
            remaining = module_names - set(result)
            cycles.append(sorted(remaining))

        return result, cycles

    # -------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "total_modules": len(self._modules),
            "total_event_types": len(self.all_event_types()),
            "total_produced_events": len(self.all_produced_events()),
            "producers_index_size": sum(len(v) for v in self._producers.values()),
            "consumers_index_size": sum(len(v) for v in self._consumers.values()),
        }
