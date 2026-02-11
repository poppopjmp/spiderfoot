"""Event Type Registry for SpiderFoot.

Provides a centralized, programmatic registry of all SpiderFoot event types,
with categorization, validation, and module dependency graph construction.

Features:
- Canonical event type definitions with metadata
- Category-based grouping (ENTITY, DESCRIPTOR, DATA, SUBENTITY, INTERNAL)
- Event type validation against the registry
- Module dependency graph built from watchedEvents/producedEvents
- Discover unused or orphaned event types

Usage::

    from spiderfoot.event_registry import EventTypeRegistry

    registry = EventTypeRegistry()
    registry.load_from_db_class()  # auto-load from SpiderFootDb

    # Check if a type is valid
    assert registry.is_valid("IP_ADDRESS")

    # Get metadata
    meta = registry.get("IP_ADDRESS")

    # List by category
    entities = registry.by_category("ENTITY")

    # Build module dependency graph
    graph = registry.build_module_graph(modules_dict)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("spiderfoot.event_registry")


@dataclass(frozen=True)
class EventTypeMeta:
    """Metadata for a single event type."""
    event_type: str
    description: str
    is_raw: bool  # True if the data is potentially large/raw
    category: str  # ENTITY, DESCRIPTOR, DATA, SUBENTITY, INTERNAL

    @property
    def is_entity(self) -> bool:
        """Check if this event type is in the ENTITY category."""
        return self.category == "ENTITY"

    @property
    def is_descriptor(self) -> bool:
        """Check if this event type is in the DESCRIPTOR category."""
        return self.category == "DESCRIPTOR"

    @property
    def is_data(self) -> bool:
        """Check if this event type is in the DATA category."""
        return self.category == "DATA"

    @property
    def is_subentity(self) -> bool:
        """Check if this event type is in the SUBENTITY category."""
        return self.category == "SUBENTITY"

    @property
    def is_internal(self) -> bool:
        """Check if this event type is in the INTERNAL category."""
        return self.category == "INTERNAL"


@dataclass
class ModuleNode:
    """A node in the module dependency graph."""
    module_name: str
    watches: frozenset[str] = field(default_factory=frozenset)
    produces: frozenset[str] = field(default_factory=frozenset)


class EventTypeRegistry:
    """Registry of all SpiderFoot event types.

    Provides lookup, validation, categorization and module
    dependency graph construction.
    """

    def __init__(self) -> None:
        """Initialize the EventTypeRegistry."""
        self._types: dict[str, EventTypeMeta] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, event_type: str, description: str,
                 is_raw: bool = False,
                 category: str = "ENTITY") -> None:
        """Register an event type.

        Args:
            event_type: Event type string (e.g. "IP_ADDRESS")
            description: Human-readable description
            is_raw: Whether it's raw/large data
            category: Category - ENTITY, DESCRIPTOR, DATA, SUBENTITY, INTERNAL
        """
        meta = EventTypeMeta(
            event_type=event_type,
            description=description,
            is_raw=is_raw,
            category=category,
        )
        self._types[event_type] = meta

        if category not in self._categories:
            self._categories[category] = []
        if event_type not in self._categories[category]:
            self._categories[category].append(event_type)

    def load_from_db_class(self) -> int:
        """Load event types from SpiderFootDb.eventDetails.

        Returns the number of event types loaded.
        """
        try:
            from spiderfoot.db import SpiderFootDb
        except ImportError:
            log.warning("Could not import SpiderFootDb for event type loading")
            return 0

        count = 0
        for entry in SpiderFootDb.eventDetails:
            event_type = entry[0]
            description = entry[1]
            is_raw = bool(entry[2])
            category = entry[3] if len(entry) > 3 else "ENTITY"
            self.register(event_type, description, is_raw, category)
            count += 1

        log.info("Loaded %d event types from SpiderFootDb", count)
        return count

    def load_from_list(self, event_details: list[list]) -> int:
        """Load event types from a list of [type, desc, raw, category].

        Args:
            event_details: List of [event_type, description, is_raw, category]

        Returns:
            Number of event types loaded
        """
        count = 0
        for entry in event_details:
            event_type = entry[0]
            description = entry[1]
            is_raw = bool(entry[2]) if len(entry) > 2 else False
            category = entry[3] if len(entry) > 3 else "ENTITY"
            self.register(event_type, description, is_raw, category)
            count += 1
        return count

    def is_valid(self, event_type: str) -> bool:
        """Check if an event type is registered."""
        return event_type in self._types

    def get(self, event_type: str) -> EventTypeMeta | None:
        """Get metadata for an event type."""
        return self._types.get(event_type)

    def all_types(self) -> list[str]:
        """Get all registered event type strings."""
        return sorted(self._types.keys())

    def by_category(self, category: str) -> list[str]:
        """Get event types in a category."""
        return sorted(self._categories.get(category, []))

    @property
    def categories(self) -> list[str]:
        """Get all categories."""
        return sorted(self._categories.keys())

    def __len__(self) -> int:
        """Return the number of registered event types."""
        return len(self._types)

    def __contains__(self, event_type: str) -> bool:
        """Check if an event type is registered."""
        return event_type in self._types

    def validate_module_events(self, module_name: str,
                               watched: list[str],
                               produced: list[str]) -> list[str]:
        """Validate that a module's watched/produced events are all registered.

        Returns a list of warning messages for unknown event types.
        """
        warnings = []
        for evt in watched:
            if evt not in self._types and evt != "*":
                warnings.append(
                    f"{module_name}: watches unknown event type '{evt}'"
                )
        for evt in produced:
            if evt not in self._types:
                warnings.append(
                    f"{module_name}: produces unknown event type '{evt}'"
                )
        return warnings

    def build_module_graph(
        self, modules: dict[str, dict[str, Any]]
    ) -> dict[str, ModuleNode]:
        """Build a module dependency graph from module metadata.

        Args:
            modules: Dict of module_name -> module dict with keys
                     'provides' (list of produced event types) and
                     'consumes' (list of watched event types).
                     Falls back to checking 'producedEvents' and
                     'watchedEvents' keys.

        Returns:
            Dict of module_name -> ModuleNode
        """
        graph: dict[str, ModuleNode] = {}

        for mod_name, mod_info in modules.items():
            produces = mod_info.get("provides") or mod_info.get("producedEvents", [])
            watches = mod_info.get("consumes") or mod_info.get("watchedEvents", [])

            graph[mod_name] = ModuleNode(
                module_name=mod_name,
                watches=frozenset(watches),
                produces=frozenset(produces),
            )

        return graph

    def find_producers(
        self, event_type: str,
        graph: dict[str, ModuleNode]
    ) -> list[str]:
        """Find all modules that produce a given event type."""
        return sorted(
            name for name, node in graph.items()
            if event_type in node.produces
        )

    def find_consumers(
        self, event_type: str,
        graph: dict[str, ModuleNode]
    ) -> list[str]:
        """Find all modules that watch a given event type."""
        return sorted(
            name for name, node in graph.items()
            if event_type in node.watches or "*" in node.watches
        )

    def find_orphaned_types(
        self, graph: dict[str, ModuleNode]
    ) -> list[str]:
        """Find event types that are registered but never produced by any module."""
        produced_types: set[str] = set()
        for node in graph.values():
            produced_types.update(node.produces)

        return sorted(
            t for t in self._types
            if t not in produced_types and t != "ROOT"
        )

    def find_unregistered_types(
        self, graph: dict[str, ModuleNode]
    ) -> list[str]:
        """Find event types used by modules but not in the registry."""
        used_types: set[str] = set()
        for node in graph.values():
            used_types.update(node.produces)
            used_types.update(node.watches)

        used_types.discard("*")

        return sorted(t for t in used_types if t not in self._types)

    def get_dependency_chain(
        self, target_type: str,
        graph: dict[str, ModuleNode],
        max_depth: int = 10
    ) -> list[list[str]]:
        """Trace the chain of modules needed to produce a target event type.

        Returns a list of chains (paths), each is a list of module names.
        """
        chains: list[list[str]] = []

        def _trace(evt_type: str, path: list[str], depth: int):
            if depth >= max_depth:
                return
            producers = self.find_producers(evt_type, graph)
            for prod in producers:
                if prod in path:
                    continue  # avoid cycles
                new_path = path + [prod]
                chains.append(new_path)
                # Trace what this producer needs
                node = graph[prod]
                for watched in node.watches:
                    if watched != "*":
                        _trace(watched, new_path, depth + 1)

        _trace(target_type, [], 0)
        return chains

    def to_dict(self) -> dict[str, Any]:
        """Export the registry as a dict."""
        return {
            "total_types": len(self._types),
            "categories": {
                cat: len(types) for cat, types in self._categories.items()
            },
            "types": {
                name: {
                    "description": meta.description,
                    "is_raw": meta.is_raw,
                    "category": meta.category,
                }
                for name, meta in sorted(self._types.items())
            },
        }


# Singleton
_registry: EventTypeRegistry | None = None


def get_event_registry() -> EventTypeRegistry:
    """Get the singleton event type registry."""
    global _registry
    if _registry is None:
        _registry = EventTypeRegistry()
    return _registry
