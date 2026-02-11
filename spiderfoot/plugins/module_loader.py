"""
ModuleLoader — Registry-driven module loading with dependency-ordered execution.

Replaces the legacy ``__import__`` + ``_priority`` sort approach in the
scanner with ``ModuleRegistry`` for discovery / instantiation and
``ModuleGraph`` for topological ordering.  Falls back to the legacy path
transparently if the registry infrastructure fails.

Usage::

    from spiderfoot.plugins.module_loader import ModuleLoader

    loader = ModuleLoader.create()
    result = loader.load_modules(
        module_list=["sfp_dnsresolve", "sfp_shodan"],
        config=global_opts,
        sf=sf_instance,
        scan_id="scan-abc",
        dbh=db_handle,
        target=target,
        shared_pool=pool,
        event_queue=eq,
    )

    # result.modules  — OrderedDict in topological order
    # result.stats    — loading statistics
"""

from __future__ import annotations

import logging
import os
import queue
import time
import threading
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from spiderfoot.plugins.module_graph import ModuleGraph
    from spiderfoot.plugins.module_registry import ModuleRegistry

log = logging.getLogger("spiderfoot.module_loader")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class LoadResult:
    """Outcome of a ``load_modules()`` call."""

    modules: OrderedDict
    """Module instances keyed by name, in execution order."""

    loaded: int
    """Number of modules successfully loaded."""

    failed: int
    """Number of modules that failed to load."""

    skipped: int
    """Modules skipped (e.g. not in registry or disabled)."""

    errors: list[tuple[str, str]]
    """``(module_name, error_message)`` pairs."""

    order_method: str
    """``'topological'`` or ``'priority'`` — how modules were sorted."""

    cycles_detected: int
    """Number of dependency cycles found (0 if clean)."""

    duration: float
    """Wall-clock seconds for the entire load operation."""

    pruned: list[str] = field(default_factory=list)
    """Module names removed by minimal-set resolution."""

    def __repr__(self) -> str:
        """Return a string representation of the load result."""
        return (
            f"<LoadResult loaded={self.loaded} failed={self.failed} "
            f"order={self.order_method} cycles={self.cycles_detected} "
            f"duration={self.duration:.3f}s>"
        )


# ---------------------------------------------------------------------------
# ModuleLoader
# ---------------------------------------------------------------------------


class ModuleLoader:
    """Registry-driven module loading with dependency-ordered execution.

    Wraps ``ModuleRegistry`` and ``ModuleGraph`` to provide a single
    ``load_modules()`` call that the scanner can use as a drop-in
    replacement for its ``__import__`` loop.

    The loader is designed to be **safe** — if any registry/graph
    operation fails, it falls back to legacy loading automatically.
    """

    def __init__(
        self,
        registry: ModuleRegistry | None = None,
        graph: ModuleGraph | None = None,
        *,
        enable_topological: bool = True,
        enable_pruning: bool = False,
    ) -> None:
        """
        Args:
            registry: A ``ModuleRegistry`` instance (or None for legacy-only).
            graph: A ``ModuleGraph`` instance (or None to skip topo-sort).
            enable_topological: Use topological ordering when graph is
                available.  Disable to keep legacy ``_priority`` sort.
            enable_pruning: When True and ``desired_output_types`` are
                provided, prune modules not needed for those types.
        """
        self._registry = registry
        self._graph = graph
        self._enable_topological = enable_topological
        self._enable_pruning = enable_pruning
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        modules_dir: str | None = None,
        *,
        enable_topological: bool = True,
        enable_pruning: bool = False,
    ) -> "ModuleLoader":
        """Create a loader with fresh registry and graph.

        Args:
            modules_dir: Path containing ``sfp_*.py`` files.  Defaults
                to ``<project_root>/modules``.
            enable_topological: Use dependency-ordered execution.
            enable_pruning: Enable minimal-set module pruning.

        Returns:
            Configured ``ModuleLoader`` instance.
        """
        if modules_dir is None:
            # __file__ is spiderfoot/plugins/module_loader.py
            # Go up 3 levels: plugins/ -> spiderfoot/ -> project_root/
            project_root = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                )
            )
            modules_dir = os.path.join(project_root, "modules")

        registry = None
        graph = None

        # Try to build registry
        try:
            from spiderfoot.plugins.module_registry import ModuleRegistry
            registry = ModuleRegistry()
            result = registry.discover(modules_dir)
            log.info(
                "ModuleLoader registry: %d loaded, %d failed",
                result.loaded,
                result.failed,
            )
        except Exception as exc:
            log.warning("ModuleLoader registry init failed: %s", exc)
            registry = None

        # Try to build graph
        try:
            from spiderfoot.plugins.module_graph import ModuleGraph
            graph = ModuleGraph()
            count = graph.load_modules(modules_dir)
            log.info("ModuleLoader graph: %d modules", count)
        except Exception as exc:
            log.warning("ModuleLoader graph init failed: %s", exc)
            graph = None

        return cls(
            registry=registry,
            graph=graph,
            enable_topological=enable_topological,
            enable_pruning=enable_pruning,
        )

    # ------------------------------------------------------------------
    # Core loading
    # ------------------------------------------------------------------

    def load_modules(
        self,
        module_list: list[str],
        config: dict[str, Any],
        *,
        sf: Any = None,
        scan_id: str | None = None,
        dbh: Any = None,
        target: Any = None,
        shared_pool: Any = None,
        event_queue: Any = None,
        desired_output_types: list[str] | None = None,
    ) -> LoadResult:
        """Load, wire, and order all modules.

        This is the main entry-point.  It mirrors the scanner's legacy
        ``__import__`` loop but uses the registry for instantiation and
        the graph for ordering.

        Args:
            module_list: Module names requested for this scan.
            config: Global SpiderFoot config dict (includes
                ``__modules__``).
            sf: ``SpiderFoot`` facade instance.
            scan_id: Current scan ID.
            dbh: Database handle.
            target: ``SpiderFootTarget``.
            shared_pool: ``SpiderFootThreadPool``.
            event_queue: Outgoing event queue for modules.
            desired_output_types: Optional list of event types the user
                actually wants.  When ``enable_pruning`` is True, modules
                not needed for these types are skipped.

        Returns:
            ``LoadResult`` with the loaded modules in execution order.
        """
        t0 = time.monotonic()
        loaded_count = 0
        failed_count = 0
        skipped_count = 0
        errors: list[tuple[str, str]] = []
        instances: dict[str, Any] = {}
        pruned: list[str] = []

        # Optional pruning
        effective_list = list(module_list)
        if (
            self._enable_pruning
            and desired_output_types
            and self._registry is not None
        ):
            try:
                needed = self._registry.resolve_for_output(desired_output_types)
                before = set(effective_list)
                effective_list = [m for m in effective_list if m in needed]
                pruned = sorted(before - set(effective_list))
                if pruned:
                    log.info(
                        "Pruned %d modules not needed for desired output: %s",
                        len(pruned),
                        ", ".join(pruned[:10]),
                    )
            except Exception as exc:
                log.warning("Module pruning failed, using full list: %s", exc)
                effective_list = list(module_list)

        # Load each module
        for mod_name in effective_list:
            if not mod_name:
                continue

            try:
                instance = self._load_single(
                    mod_name, config, sf=sf, scan_id=scan_id,
                    dbh=dbh, target=target, shared_pool=shared_pool,
                    event_queue=event_queue,
                )
                if instance is not None:
                    instances[mod_name] = instance
                    loaded_count += 1
                else:
                    skipped_count += 1
            except Exception as exc:
                err_msg = f"{type(exc).__name__}: {exc}"
                errors.append((mod_name, err_msg))
                failed_count += 1
                if sf:
                    sf.error(f"Module {mod_name} load failed: {err_msg}")

        # Order modules
        order_method = "priority"
        cycles_detected = 0

        if instances:
            ordered, order_method, cycles_detected = self._order_modules(
                instances
            )
        else:
            ordered = OrderedDict()

        duration = time.monotonic() - t0
        log.info(
            "ModuleLoader: %d loaded, %d failed, %d skipped, "
            "order=%s, cycles=%d, %.3fs",
            loaded_count, failed_count, skipped_count,
            order_method, cycles_detected, duration,
        )

        return LoadResult(
            modules=ordered,
            loaded=loaded_count,
            failed=failed_count,
            skipped=skipped_count,
            errors=errors,
            order_method=order_method,
            cycles_detected=cycles_detected,
            duration=duration,
            pruned=pruned,
        )

    # ------------------------------------------------------------------
    # Single module loading
    # ------------------------------------------------------------------

    def _load_single(
        self,
        mod_name: str,
        config: dict[str, Any],
        *,
        sf: Any = None,
        scan_id: str | None = None,
        dbh: Any = None,
        target: Any = None,
        shared_pool: Any = None,
        event_queue: Any = None,
    ) -> Any:
        """Load and wire a single module.

        Tries the registry first; falls back to legacy ``__import__``.
        Returns the wired module instance, or None if skipped.
        Raises on hard failures (both registry and legacy fail).
        """
        # Validate module is in config
        modules_config = config.get("__modules__", {})
        if mod_name not in modules_config:
            log.warning("Module %s not in __modules__ config — skipping", mod_name)
            return None

        # Try registry-based loading first
        instance = None
        if self._registry is not None and mod_name in self._registry:
            try:
                instance = self._registry.create_instance(mod_name)
                log.debug("Loaded %s via registry", mod_name)
            except Exception as exc:
                log.debug(
                    "Registry load failed for %s, falling back: %s",
                    mod_name, exc,
                )

        # Fallback to legacy __import__
        if instance is None:
            instance = self._legacy_import(mod_name)

        if instance is None:
            raise RuntimeError(f"Failed to load module {mod_name}")

        # Wire the module (same as scanner's original code)
        self._wire_module(
            instance, mod_name, config, modules_config,
            sf=sf, scan_id=scan_id, dbh=dbh,
            target=target, shared_pool=shared_pool,
            event_queue=event_queue,
        )

        return instance

    @staticmethod
    def _legacy_import(mod_name: str) -> Any:
        """Legacy module loading via ``__import__``."""
        try:
            module = __import__(
                "modules." + mod_name, globals(), locals(), [mod_name]
            )
        except ImportError:
            log.error("Legacy import failed for %s", mod_name)
            return None

        try:
            instance = getattr(module, mod_name)()
            instance.__name__ = mod_name
            return instance
        except Exception as exc:
            log.error("Legacy instantiation failed for %s: %s", mod_name, exc)
            return None

    @staticmethod
    def _wire_module(
        instance: Any,
        mod_name: str,
        config: dict[str, Any],
        modules_config: dict[str, Any],
        *,
        sf: Any = None,
        scan_id: str | None = None,
        dbh: Any = None,
        target: Any = None,
        shared_pool: Any = None,
        event_queue: Any = None,
    ) -> None:
        """Wire lifecycle dependencies into a module instance.

        Mirrors the scanner's original setup block: config merging,
        setScanId, setDbh, setup, setTarget, queue assignment.

        Raises on fatal errors so the caller can record them.
        """
        # Ensure __name__ is set
        if not getattr(instance, "__name__", None):
            instance.__name__ = mod_name

        # Defensive config handling
        modcfg = modules_config.get(mod_name)
        if not isinstance(modcfg, dict):
            modcfg = {}
            modules_config[mod_name] = modcfg
        if "opts" not in modcfg or modcfg["opts"] is None:
            modcfg["opts"] = {}
        if not isinstance(modcfg["opts"], dict):
            raise TypeError(f"Module {mod_name} 'opts' is not a dict")

        # Merge config
        mod_opts = deepcopy(modcfg["opts"])
        for opt in list(config.keys()):
            mod_opts[opt] = deepcopy(config[opt])

        # Standard setup sequence
        instance.clearListeners()

        if scan_id is not None:
            instance.setScanId(scan_id)
        if shared_pool is not None:
            instance.setSharedThreadPool(shared_pool)
        if dbh is not None:
            instance.setDbh(dbh)
        if sf is not None:
            instance.setup(sf, mod_opts)

        # Wire services into module (no-op for legacy)
        try:
            from spiderfoot.service_integration import wire_module_services
            wire_module_services(instance, config)
        except Exception as e:
            log.debug("Failed to wire services for %s: %s", mod_name, e)

        # SOCKS proxy
        if config.get("_socks1type", ""):
            try:
                import socket as _socket
                instance._updateSocket(_socket)
            except Exception as e:
                log.debug("Failed to set SOCKS proxy for %s: %s", mod_name, e)

        # Output filter
        output_filter = config.get("__outputfilter")
        if output_filter:
            try:
                instance.setOutputFilter(output_filter)
            except Exception as e:
                log.debug("Failed to set output filter for %s: %s", mod_name, e)

        # Target enrichment + assignment
        if target is not None:
            try:
                new_target = instance.enrichTarget(target)
                if new_target is not None:
                    target = new_target
            except Exception as e:
                log.debug("Failed to enrich target for %s: %s", mod_name, e)

            instance.setTarget(target)

        # Queue assignment
        if event_queue is not None:
            instance.outgoingEventQueue = event_queue
            instance.incomingEventQueue = queue.Queue()

            if (
                instance.incomingEventQueue is None
                or instance.outgoingEventQueue is None
            ):
                raise RuntimeError(
                    f"Module {mod_name} queue validation failed"
                )

    # ------------------------------------------------------------------
    # Ordering
    # ------------------------------------------------------------------

    def _order_modules(
        self,
        instances: dict[str, Any],
    ) -> tuple[OrderedDict, str, int]:
        """Order loaded modules — topological if graph available, else priority.

        Returns:
            ``(ordered_dict, method_name, cycles_detected)``
        """
        # Try topological ordering
        if self._enable_topological and self._graph is not None:
            try:
                return self._topological_order(instances)
            except Exception as exc:
                log.warning(
                    "Topological ordering failed, falling back to priority: %s",
                    exc,
                )

        # Fallback: legacy _priority sort
        ordered = OrderedDict(
            sorted(
                instances.items(),
                key=lambda m: getattr(m[1], "_priority", 3),
            )
        )
        return ordered, "priority", 0

    def _topological_order(
        self,
        instances: dict[str, Any],
    ) -> tuple[OrderedDict, str, int]:
        """Apply topological ordering from the dependency graph.

        Modules not in the graph are appended at the end, sorted by
        ``_priority``.
        """
        full_order = self._graph.topological_order()
        cycles = self._graph.detect_cycles()
        cycles_detected = len(cycles)

        if cycles_detected > 0:
            log.warning(
                "Dependency graph has %d cycle(s) — modules in cycles "
                "may execute in arbitrary order",
                cycles_detected,
            )

        # Filter to our actual modules, preserving topological order
        ordered_names = [m for m in full_order if m in instances]

        # Any modules not in the graph go at the end
        ungraphed = sorted(
            (n for n in instances if n not in ordered_names),
            key=lambda n: getattr(instances[n], "_priority", 3),
        )
        ordered_names.extend(ungraphed)

        ordered = OrderedDict(
            (name, instances[name]) for name in ordered_names
        )
        return ordered, "topological", cycles_detected

    # ------------------------------------------------------------------
    # Dependency queries (delegated to registry/graph)
    # ------------------------------------------------------------------

    def resolve_minimal_set(
        self,
        desired_output_types: list[str],
        available_modules: list[str] | None = None,
    ) -> set[str]:
        """Find the minimal set of modules needed for desired output.

        Args:
            desired_output_types: Event types the user wants.
            available_modules: Restrict to these modules (or all).

        Returns:
            Set of module names that should be enabled.
        """
        if self._registry is not None:
            needed = self._registry.resolve_for_output(desired_output_types)
        elif self._graph is not None:
            needed = self._graph.resolve_for_output(desired_output_types)
        else:
            raise RuntimeError("No registry or graph available for resolution")

        if available_modules is not None:
            needed &= set(available_modules)

        return needed

    def get_topological_order(
        self,
        module_names: list[str] | None = None,
    ) -> list[str]:
        """Get modules in dependency order.

        Args:
            module_names: Subset to order (or all if None).

        Returns:
            List of module names in topological order.
        """
        if self._graph is None:
            raise RuntimeError("No graph available for topological ordering")

        full_order = self._graph.topological_order()

        if module_names is None:
            return full_order

        name_set = set(module_names)
        return [m for m in full_order if m in name_set]

    def dependency_info(self, module_name: str) -> dict[str, Any]:
        """Get dependency information for a module.

        Returns:
            Dict with ``depends_on``, ``depended_on_by``, ``watched``,
            ``produced`` event types.
        """
        info: dict[str, Any] = {
            "module": module_name,
            "depends_on": [],
            "depended_on_by": [],
            "watched_events": [],
            "produced_events": [],
        }

        if self._registry is not None:
            desc = self._registry.get(module_name)
            if desc:
                info["depends_on"] = sorted(
                    self._registry.dependencies_of(module_name)
                )
                info["depended_on_by"] = sorted(
                    self._registry.dependents_of(module_name)
                )
                info["watched_events"] = sorted(desc.watched_events)
                info["produced_events"] = sorted(desc.produced_events)
        elif self._graph is not None:
            mod_info = self._graph.modules.get(module_name)
            if mod_info:
                info["depends_on"] = sorted(
                    self._graph.dependencies_of(module_name)
                )
                info["depended_on_by"] = sorted(
                    self._graph.dependents_of(module_name)
                )
                info["watched_events"] = mod_info.watched_events
                info["produced_events"] = mod_info.produced_events

        return info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def has_registry(self) -> bool:
        """Whether a working registry is available."""
        return self._registry is not None

    @property
    def has_graph(self) -> bool:
        """Whether a working dependency graph is available."""
        return self._graph is not None

    @property
    def registry(self) -> ModuleRegistry | None:
        """The underlying ``ModuleRegistry`` (or None)."""
        return self._registry

    @property
    def graph(self) -> ModuleGraph | None:
        """The underlying ``ModuleGraph`` (or None)."""
        return self._graph

    def stats(self) -> dict[str, Any]:
        """Combined statistics from registry and graph."""
        result: dict[str, Any] = {
            "has_registry": self.has_registry,
            "has_graph": self.has_graph,
            "enable_topological": self._enable_topological,
            "enable_pruning": self._enable_pruning,
        }
        if self._registry:
            result["registry"] = self._registry.stats()
        if self._graph:
            result["graph"] = self._graph.stats()
        return result

    def __repr__(self) -> str:
        """Return a string representation of the module loader."""
        return (
            f"<ModuleLoader registry={self.has_registry} "
            f"graph={self.has_graph} "
            f"topo={self._enable_topological} "
            f"prune={self._enable_pruning}>"
        )


# ---------------------------------------------------------------------------
# Module-level convenience (singleton-ish)
# ---------------------------------------------------------------------------

_global_loader: ModuleLoader | None = None
_global_lock = threading.Lock()


def get_module_loader() -> ModuleLoader | None:
    """Return the global ``ModuleLoader`` singleton, or None."""
    return _global_loader


def init_module_loader(
    modules_dir: str | None = None,
    *,
    enable_topological: bool = True,
    enable_pruning: bool = False,
) -> ModuleLoader:
    """Initialize the global ``ModuleLoader``.

    Thread-safe; subsequent calls return the same instance unless
    ``reset_module_loader()`` is called first.
    """
    global _global_loader
    with _global_lock:
        if _global_loader is None:
            _global_loader = ModuleLoader.create(
                modules_dir,
                enable_topological=enable_topological,
                enable_pruning=enable_pruning,
            )
        return _global_loader


def reset_module_loader() -> None:
    """Reset the global loader (for testing)."""
    global _global_loader
    with _global_lock:
        _global_loader = None
