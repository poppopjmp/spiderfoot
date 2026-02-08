"""Module Dependency Resolver for SpiderFoot.

Resolves module load and execution order based on event type
production/consumption dependencies. Detects circular dependencies,
identifies missing providers, and computes optimal execution order.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.module_deps")


class DepStatus(Enum):
    """Dependency resolution status."""
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    CIRCULAR = "circular"
    MISSING_PROVIDER = "missing_provider"


@dataclass(frozen=True)
class ModuleNode:
    """Represents a module in the dependency graph."""
    name: str
    produces: FrozenSet[str] = frozenset()
    consumes: FrozenSet[str] = frozenset()
    optional_consumes: FrozenSet[str] = frozenset()


@dataclass
class DepEdge:
    """An edge representing a dependency between two modules."""
    consumer: str
    producer: str
    event_type: str
    optional: bool = False


@dataclass
class ResolutionResult:
    """Result of dependency resolution."""
    status: DepStatus
    load_order: List[str] = field(default_factory=list)
    cycles: List[List[str]] = field(default_factory=list)
    missing_providers: Dict[str, List[str]] = field(default_factory=dict)
    edges: List[DepEdge] = field(default_factory=list)
    layers: List[List[str]] = field(default_factory=list)

    @property
    def is_resolved(self) -> bool:
        return self.status == DepStatus.RESOLVED

    def summary(self) -> str:
        lines = [f"Status: {self.status.value}"]
        lines.append(f"Modules: {len(self.load_order)}")
        lines.append(f"Layers: {len(self.layers)}")
        if self.cycles:
            lines.append(f"Cycles: {len(self.cycles)}")
            for c in self.cycles:
                lines.append(f"  {' -> '.join(c)}")
        if self.missing_providers:
            lines.append(f"Missing providers: {len(self.missing_providers)}")
            for et, consumers in self.missing_providers.items():
                lines.append(f"  {et}: needed by {', '.join(consumers)}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "load_order": self.load_order,
            "layers": self.layers,
            "cycles": self.cycles,
            "missing_providers": self.missing_providers,
            "edge_count": len(self.edges),
        }


class ModuleDependencyResolver:
    """Resolves module dependencies based on event type production/consumption.

    Builds a directed acyclic graph (DAG) from module declarations and
    computes topological ordering for optimal execution sequence.

    Usage:
        resolver = ModuleDependencyResolver()
        resolver.add_module("sfp_dns", produces={"IP_ADDRESS"}, consumes={"DOMAIN_NAME"})
        resolver.add_module("sfp_whois", produces={"DOMAIN_WHOIS"}, consumes={"DOMAIN_NAME"})
        resolver.add_module("sfp_target", produces={"DOMAIN_NAME"})

        result = resolver.resolve()
        print(result.load_order)  # ['sfp_target', 'sfp_dns', 'sfp_whois']
    """

    def __init__(self):
        self._modules: Dict[str, ModuleNode] = {}
        self._producer_index: Dict[str, Set[str]] = defaultdict(set)

    def add_module(
        self,
        name: str,
        produces: Optional[Set[str]] = None,
        consumes: Optional[Set[str]] = None,
        optional_consumes: Optional[Set[str]] = None,
    ) -> "ModuleDependencyResolver":
        """Register a module with its event type dependencies (chainable)."""
        prod = frozenset(produces or set())
        cons = frozenset(consumes or set())
        opt = frozenset(optional_consumes or set())

        node = ModuleNode(name=name, produces=prod, consumes=cons, optional_consumes=opt)
        self._modules[name] = node

        for et in prod:
            self._producer_index[et].add(name)

        return self

    def remove_module(self, name: str) -> bool:
        """Remove a module from the resolver."""
        node = self._modules.pop(name, None)
        if node is None:
            return False
        for et in node.produces:
            self._producer_index[et].discard(name)
        return True

    def get_producers(self, event_type: str) -> Set[str]:
        """Get all modules that produce a given event type."""
        return set(self._producer_index.get(event_type, set()))

    def get_consumers(self, event_type: str) -> Set[str]:
        """Get all modules that consume a given event type."""
        return {
            name
            for name, node in self._modules.items()
            if event_type in node.consumes or event_type in node.optional_consumes
        }

    def get_dependencies(self, module_name: str) -> Set[str]:
        """Get all modules that the given module depends on (its providers)."""
        node = self._modules.get(module_name)
        if node is None:
            return set()

        deps = set()
        for et in node.consumes | node.optional_consumes:
            deps.update(self._producer_index.get(et, set()))
        deps.discard(module_name)
        return deps

    def get_dependents(self, module_name: str) -> Set[str]:
        """Get all modules that depend on the given module."""
        node = self._modules.get(module_name)
        if node is None:
            return set()

        dependents = set()
        for et in node.produces:
            for name, n in self._modules.items():
                if name != module_name and (et in n.consumes or et in n.optional_consumes):
                    dependents.add(name)
        return dependents

    def _build_edges(self) -> Tuple[List[DepEdge], Dict[str, List[str]]]:
        """Build dependency edges and find missing providers."""
        edges = []
        missing: Dict[str, List[str]] = defaultdict(list)

        for name, node in self._modules.items():
            for et in node.consumes:
                providers = self._producer_index.get(et, set())
                if not providers:
                    missing[et].append(name)
                for provider in providers:
                    if provider != name:
                        edges.append(DepEdge(consumer=name, producer=provider, event_type=et))

            for et in node.optional_consumes:
                providers = self._producer_index.get(et, set())
                for provider in providers:
                    if provider != name:
                        edges.append(
                            DepEdge(consumer=name, producer=provider, event_type=et, optional=True)
                        )

        return edges, dict(missing)

    def _detect_cycles(self, adj: Dict[str, Set[str]]) -> List[List[str]]:
        """Detect all cycles in the dependency graph using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {name: WHITE for name in self._modules}
        cycles = []
        path: List[str] = []

        def dfs(u: str) -> None:
            color[u] = GRAY
            path.append(u)
            for v in adj.get(u, set()):
                if color.get(v) == GRAY:
                    # Found cycle: extract it
                    idx = path.index(v)
                    cycle = path[idx:] + [v]
                    cycles.append(cycle)
                elif color.get(v) == WHITE:
                    dfs(v)
            path.pop()
            color[u] = BLACK

        for name in self._modules:
            if color[name] == WHITE:
                dfs(name)

        return cycles

    def _topological_sort(self, adj: Dict[str, Set[str]]) -> Tuple[List[str], List[List[str]]]:
        """Kahn's algorithm for topological sort with layer detection.

        Returns (ordered_list, layers) where layers groups modules
        that can be loaded/executed in parallel.
        """
        in_degree: Dict[str, int] = {name: 0 for name in self._modules}
        for u, neighbors in adj.items():
            for v in neighbors:
                if v in in_degree:
                    in_degree[v] += 1

        queue = deque(name for name, deg in in_degree.items() if deg == 0)
        order: List[str] = []
        layers: List[List[str]] = []

        while queue:
            layer = sorted(queue)
            layers.append(layer)
            queue.clear()

            for u in layer:
                order.append(u)
                for v in adj.get(u, set()):
                    if v in in_degree:
                        in_degree[v] -= 1
                        if in_degree[v] == 0:
                            queue.append(v)

        return order, layers

    def resolve(self) -> ResolutionResult:
        """Resolve module dependencies and compute load order.

        Returns a ResolutionResult with:
        - load_order: topological order for loading modules
        - layers: groups of modules that can run in parallel
        - cycles: any circular dependencies detected
        - missing_providers: event types with no provider
        """
        if not self._modules:
            return ResolutionResult(status=DepStatus.RESOLVED)

        edges, missing = self._build_edges()

        # Build adjacency: producer -> consumer (consumer depends on producer)
        adj: Dict[str, Set[str]] = defaultdict(set)
        for edge in edges:
            if not edge.optional:
                adj[edge.producer].add(edge.consumer)

        cycles = self._detect_cycles(adj)
        if cycles:
            return ResolutionResult(
                status=DepStatus.CIRCULAR,
                cycles=cycles,
                edges=edges,
                missing_providers=missing,
            )

        if missing:
            log.warning("Missing providers for event types: %s", list(missing.keys()))

        order, layers = self._topological_sort(adj)

        # Include modules with no edges (standalone)
        standalone = [n for n in self._modules if n not in order]
        if standalone:
            order.extend(sorted(standalone))
            if layers:
                layers[0] = sorted(layers[0] + standalone)
            else:
                layers.append(sorted(standalone))

        status = DepStatus.RESOLVED if not missing else DepStatus.MISSING_PROVIDER
        return ResolutionResult(
            status=status,
            load_order=order,
            layers=layers,
            edges=edges,
            missing_providers=missing,
        )

    def get_impact(self, module_name: str) -> Set[str]:
        """Get all modules transitively affected if this module is removed."""
        node = self._modules.get(module_name)
        if node is None:
            return set()

        affected = set()
        queue = deque([module_name])

        while queue:
            current = queue.popleft()
            for dep in self.get_dependents(current):
                if dep not in affected:
                    affected.add(dep)
                    queue.append(dep)

        return affected

    def get_critical_path(self, module_name: str) -> List[str]:
        """Get the longest dependency chain ending at the given module."""
        node = self._modules.get(module_name)
        if node is None:
            return []

        memo: Dict[str, List[str]] = {}

        def longest(name: str, visited: Set[str]) -> List[str]:
            if name in memo:
                return memo[name]
            if name in visited:
                return [name]

            visited.add(name)
            deps = self.get_dependencies(name)
            if not deps:
                memo[name] = [name]
                return [name]

            best: List[str] = []
            for d in deps:
                chain = longest(d, visited)
                if len(chain) > len(best):
                    best = chain

            result = best + [name]
            memo[name] = result
            visited.discard(name)
            return result

        return longest(module_name, set())

    @property
    def module_count(self) -> int:
        return len(self._modules)

    @property
    def module_names(self) -> List[str]:
        return sorted(self._modules.keys())

    def to_dict(self) -> dict:
        return {
            "modules": {
                name: {
                    "produces": sorted(node.produces),
                    "consumes": sorted(node.consumes),
                    "optional_consumes": sorted(node.optional_consumes),
                }
                for name, node in self._modules.items()
            },
            "producer_index": {et: sorted(mods) for et, mods in self._producer_index.items()},
        }
