#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         module_graph
# Purpose:      Module dependency graph for SpiderFoot.
#               Analyzes watchedEvents/producedEvents to build a directed
#               graph of module dependencies, enabling topological ordering,
#               cycle detection, and selective module activation.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Module Dependency Graph

Builds a directed graph from module event type relationships:

    Module A produces EVENT_X → Module B watches EVENT_X

This graph supports:

    - Topological ordering for optimal module execution
    - Cycle detection for event loops
    - Dependency resolution (what modules are needed for a target type)
    - Selective module enabling based on desired output types
    - Visualization export (Mermaid, DOT/Graphviz)

Usage::

    from spiderfoot.plugins.module_graph import ModuleGraph

    graph = ModuleGraph()
    graph.load_modules("/path/to/modules")

    # What modules produce IP_ADDRESS?
    producers = graph.producers_of("IP_ADDRESS")

    # What's the minimal set of modules to get VULNERABILITY data?
    needed = graph.resolve_for_output(["VULNERABILITY_CVE_CRITICAL"])

    # Export as Mermaid diagram
    print(graph.to_mermaid())
"""

import glob
import importlib
import importlib.util
import logging
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("spiderfoot.module_graph")


@dataclass
class ModuleInfo:
    """Metadata about a SpiderFoot module."""
    name: str
    filename: str
    watched_events: list[str] = field(default_factory=list)
    produced_events: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Return the human-readable display name from module metadata."""
        return self.meta.get("name", self.name)

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "watched_events": self.watched_events,
            "produced_events": self.produced_events,
            "flags": self.flags,
            "categories": self.categories,
        }


class ModuleGraph:
    """Directed graph of module event-type dependencies."""

    def __init__(self) -> None:
        """Initialize the ModuleGraph."""
        self.modules: dict[str, ModuleInfo] = {}

        # event_type -> set of module names that produce it
        self._producers: dict[str, set[str]] = defaultdict(set)

        # event_type -> set of module names that watch it
        self._consumers: dict[str, set[str]] = defaultdict(set)

        # module -> set of modules it depends on (via event types)
        self._edges: dict[str, set[str]] = defaultdict(set)

    def load_modules(self, modules_dir: str = "modules") -> int:
        """Load all module metadata from a directory.

        Returns the number of modules loaded.
        """
        if not os.path.isdir(modules_dir):
            log.warning("Modules directory not found: %s", modules_dir)
            return 0

        pattern = os.path.join(modules_dir, "sfp_*.py")
        count = 0

        for filepath in sorted(glob.glob(pattern)):
            try:
                info = self._load_module_info(filepath)
                if info:
                    self.add_module(info)
                    count += 1
            except Exception as e:
                log.debug("Failed to load %s: %s",
                          os.path.basename(filepath), e)

        self._build_edges()
        log.info("Loaded %d modules into dependency graph", count)
        return count

    def add_module(self, info: ModuleInfo) -> None:
        """Add a module to the graph."""
        self.modules[info.name] = info

        for event_type in info.produced_events:
            self._producers[event_type].add(info.name)

        for event_type in info.watched_events:
            self._consumers[event_type].add(info.name)

    def _build_edges(self) -> None:
        """Build directed edges: producer → consumer."""
        self._edges.clear()

        for event_type, consumers in self._consumers.items():
            producers = self._producers.get(event_type, set())
            for producer in producers:
                for consumer in consumers:
                    if producer != consumer:
                        self._edges[producer].add(consumer)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def producers_of(self, event_type: str) -> list[str]:
        """Get modules that produce a specific event type."""
        return sorted(self._producers.get(event_type, set()))

    def consumers_of(self, event_type: str) -> list[str]:
        """Get modules that watch a specific event type."""
        return sorted(self._consumers.get(event_type, set()))

    def dependencies_of(self, module_name: str) -> set[str]:
        """Get modules that must run before this module.

        A module depends on producers of its watched event types.
        """
        info = self.modules.get(module_name)
        if not info:
            return set()

        deps = set()
        for event_type in info.watched_events:
            deps.update(self._producers.get(event_type, set()))

        deps.discard(module_name)
        return deps

    def dependents_of(self, module_name: str) -> set[str]:
        """Get modules that depend on this module's output."""
        return self._edges.get(module_name, set()).copy()

    def resolve_for_output(self, desired_types: list[str]) -> set[str]:
        """Find the minimal set of modules needed to produce desired types.

        Uses BFS backward through the dependency graph.
        """
        needed = set()
        queue = deque()

        # Start with direct producers
        for event_type in desired_types:
            for mod in self._producers.get(event_type, set()):
                if mod not in needed:
                    needed.add(mod)
                    queue.append(mod)

        # Walk backward through dependencies
        while queue:
            mod = queue.popleft()
            for dep in self.dependencies_of(mod):
                if dep not in needed:
                    needed.add(dep)
                    queue.append(dep)

        return needed

    def topological_order(self) -> list[str]:
        """Get modules in topological order (dependencies first).

        Returns a list where each module appears after its dependencies.
        Cycles are broken arbitrarily.
        """
        # Compute in-degree based on reverse edges
        in_degree: dict[str, int] = {m: 0 for m in self.modules}
        reverse_edges: dict[str, set[str]] = defaultdict(set)

        for producer, consumers in self._edges.items():
            for consumer in consumers:
                if consumer in self.modules:
                    in_degree[consumer] = in_degree.get(consumer, 0) + 1
                    reverse_edges[consumer].add(producer)

        # Kahn's algorithm
        queue = deque(
            m for m, deg in in_degree.items() if deg == 0
        )
        order = []

        while queue:
            mod = queue.popleft()
            order.append(mod)
            for consumer in self._edges.get(mod, set()):
                if consumer in in_degree:
                    in_degree[consumer] -= 1
                    if in_degree[consumer] == 0:
                        queue.append(consumer)

        # Add any remaining (cycles)
        remaining = set(self.modules.keys()) - set(order)
        order.extend(sorted(remaining))

        return order

    def detect_cycles(self) -> list[list[str]]:
        """Detect cycles in the module dependency graph.

        Returns list of cycles, each as a list of module names.
        """
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def _dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._edges.get(node, set()):
                if neighbor not in visited:
                    _dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found cycle
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for mod in self.modules:
            if mod not in visited:
                _dfs(mod)

        return cycles

    def all_event_types(self) -> set[str]:
        """Get all known event types."""
        types = set()
        for info in self.modules.values():
            types.update(info.produced_events)
            types.update(info.watched_events)
        return types

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Get graph statistics."""
        edge_count = sum(len(v) for v in self._edges.values())
        return {
            "module_count": len(self.modules),
            "event_type_count": len(self.all_event_types()),
            "edge_count": edge_count,
            "producer_types": len(self._producers),
            "consumer_types": len(self._consumers),
            "cycles": len(self.detect_cycles()),
        }

    # ------------------------------------------------------------------
    # Visualization
    # ------------------------------------------------------------------

    def to_mermaid(self, max_modules: int = 50) -> str:
        """Export as Mermaid flowchart.

        Args:
            max_modules: Maximum modules to include (-1 for all).
        """
        lines = ["graph LR;"]
        modules_list = list(self.modules.keys())

        if 0 < max_modules < len(modules_list):
            modules_list = modules_list[:max_modules]

        module_set = set(modules_list)

        for producer in modules_list:
            consumers = self._edges.get(producer, set())
            for consumer in consumers:
                if consumer in module_set:
                    lines.append(f"    {producer} --> {consumer};")

        # Add orphans (no edges)
        mentioned = set()
        for line in lines[1:]:
            parts = line.strip().rstrip(";").split(" --> ")
            mentioned.update(parts)

        for mod in modules_list:
            if mod not in mentioned:
                lines.append(f"    {mod};")

        return "\n".join(lines)

    def to_dot(self) -> str:
        """Export as DOT (Graphviz) format."""
        lines = [
            "digraph SpiderFootModules {",
            '    rankdir=LR;',
            '    node [shape=box, style=filled, fillcolor=lightblue];',
        ]

        for producer, consumers in self._edges.items():
            for consumer in consumers:
                lines.append(f'    "{producer}" -> "{consumer}";')

        lines.append("}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Module loading internals
    # ------------------------------------------------------------------

    def _load_module_info(self, filepath: str) -> ModuleInfo | None:
        """Load module info by importing the module."""
        module_name = os.path.basename(filepath).replace(".py", "")

        spec = importlib.util.spec_from_file_location(
            module_name, filepath)
        if spec is None or spec.loader is None:
            return None

        mod = importlib.util.module_from_spec(spec)

        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            return None

        # Find the plugin class
        cls = getattr(mod, module_name, None)
        if cls is None:
            return None

        try:
            instance = cls()
            watched = (instance.watchedEvents()
                       if hasattr(instance, "watchedEvents") else [])
            produced = (instance.producedEvents()
                        if hasattr(instance, "producedEvents") else [])
            meta = getattr(instance, "meta", {})
            flags = meta.get("flags", [])
            categories = meta.get("categories", [])
        except Exception as e:
            # Fallback: parse from class attributes
            watched = []
            produced = []
            meta = getattr(cls, "meta", {})
            flags = meta.get("flags", [])
            categories = meta.get("categories", [])

        return ModuleInfo(
            name=module_name,
            filename=filepath,
            watched_events=list(watched),
            produced_events=list(produced),
            meta=meta,
            flags=flags,
            categories=categories,
        )
