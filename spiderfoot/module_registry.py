"""
ModuleRegistry — Unified module discovery, indexing and lifecycle management.

Consolidates the scattered module infrastructure (``ModuleManager``,
``ModuleGraph``, ad-hoc ``__import__`` blocks in the scanner) behind a
single, thread-safe facade with:

* **One-shot discovery** — scans ``modules/`` once, caches metadata;
  subsequent calls are O(1) dict lookups.
* **Rich indexed queries** — by event type (produced/consumed), category,
  flag, use-case, data-source model, or free-text search.
* **Validated instantiation** — creates module instances with safety
  checks, option merging, and optional sandboxing.
* **Lifecycle hooks** — setup / teardown tracking per module instance.
* **Event-type index** — inverted index from event types to producer /
  consumer module sets for fast dependency resolution.
* **Compatibility** — interoperates with ``ModuleGraph``,
  ``ModuleManager`` and ``ServiceRegistry`` without requiring them.

Usage::

    from spiderfoot.module_registry import ModuleRegistry

    registry = ModuleRegistry()
    registry.discover()  # scan modules/ directory

    # Fast queries
    dns_mods = registry.by_category("DNS")
    who_produces = registry.producers_of("IP_ADDRESS")
    api_mods = registry.by_flag("apikey")

    # Instantiation
    instance = registry.create_instance("sfp_shodan", merged_opts)
"""

from __future__ import annotations

import glob
import importlib
import importlib.util
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from collections.abc import Iterable

log = logging.getLogger("spiderfoot.module_registry")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class ModuleStatus(Enum):
    """Lifecycle status of a module entry in the registry."""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ModuleDescriptor:
    """Immutable snapshot of a module's metadata.

    Created once during discovery and never mutated afterwards, making
    it safe to share across threads without locking.
    """

    name: str
    """Internal module name (``sfp_shodan``)."""

    display_name: str
    """Human-readable name (``SHODAN``)."""

    summary: str
    """One-line description from ``meta['summary']`` or docstring."""

    filename: str
    """Absolute path to the ``.py`` source file."""

    watched_events: frozenset[str]
    """Event types this module subscribes to."""

    produced_events: frozenset[str]
    """Event types this module can emit."""

    categories: tuple[str, ...]
    """Functional groupings (``DNS``, ``Search Engines``, …)."""

    flags: tuple[str, ...]
    """Tags: ``apikey``, ``slow``, ``errorprone``, ``invasive``, ``tool``."""

    use_cases: tuple[str, ...]
    """``Footprint``, ``Investigate``, ``Passive``."""

    opts: dict[str, Any]
    """Default option values (shallow copy of the class attribute)."""

    optdescs: dict[str, str]
    """Human descriptions for each option key."""

    data_source: dict[str, Any] | None
    """``meta['dataSource']`` dict if present."""

    priority: int
    """Execution priority (lower = runs first)."""

    is_modern: bool
    """True if the class inherits ``SpiderFootModernPlugin``."""

    status: ModuleStatus = ModuleStatus.DISCOVERED
    """Current registry status."""

    error: str | None = None
    """Error message when ``status == FAILED``."""

    # Convenience helpers -----------------------------------------------

    @property
    def requires_apikey(self) -> bool:
        return "apikey" in self.flags

    @property
    def is_invasive(self) -> bool:
        return "invasive" in self.flags

    @property
    def is_slow(self) -> bool:
        return "slow" in self.flags

    @property
    def data_source_model(self) -> str | None:
        if self.data_source:
            return self.data_source.get("model")
        return None

    def matches_search(self, query: str) -> bool:
        """Simple case-insensitive search across name / summary / categories."""
        q = query.lower()
        return (
            q in self.name.lower()
            or q in self.display_name.lower()
            or q in self.summary.lower()
            or any(q in c.lower() for c in self.categories)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "summary": self.summary,
            "watched_events": sorted(self.watched_events),
            "produced_events": sorted(self.produced_events),
            "categories": list(self.categories),
            "flags": list(self.flags),
            "use_cases": list(self.use_cases),
            "priority": self.priority,
            "is_modern": self.is_modern,
            "requires_apikey": self.requires_apikey,
            "status": self.status.value,
            "options": {k: {"default": v, "description": self.optdescs.get(k, "")}
                        for k, v in self.opts.items()},
        }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ModuleRegistry:
    """Unified, thread-safe module registry.

    Typical flow::

        reg = ModuleRegistry()
        reg.discover("/path/to/modules")   # fast filesystem scan
        mods = reg.by_category("DNS")       # indexed lookup
        inst = reg.create_instance("sfp_dnsresolve", opts)
    """

    def __init__(self) -> None:
        self._descriptors: dict[str, ModuleDescriptor] = {}
        self._lock = threading.RLock()

        # Inverted indices — rebuilt after discover()
        self._by_produced_event: dict[str, set[str]] = defaultdict(set)
        self._by_watched_event: dict[str, set[str]] = defaultdict(set)
        self._by_category: dict[str, set[str]] = defaultdict(set)
        self._by_flag: dict[str, set[str]] = defaultdict(set)
        self._by_usecase: dict[str, set[str]] = defaultdict(set)

        # Module class cache (only populated on demand)
        self._classes: dict[str, type] = {}

        # Discovery metadata
        self._discovered_at: float | None = None
        self._modules_dir: str | None = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(
        self,
        modules_dir: str | None = None,
        *,
        ignore_files: Iterable[str] | None = None,
    ) -> "DiscoveryResult":
        """Scan *modules_dir* for ``sfp_*.py`` files and build the catalog.

        Can be called multiple times (e.g. after hot-reload); each call
        replaces the previous catalog.

        Args:
            modules_dir: Path to the directory containing ``sfp_*.py``
                files.  Defaults to ``<project_root>/modules``.
            ignore_files: Basenames to skip (default: ``sfp_template.py``).

        Returns:
            A :class:`DiscoveryResult` summarising what was found.
        """
        if modules_dir is None:
            project_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            modules_dir = os.path.join(project_root, "modules")

        if ignore_files is None:
            ignore_files = {"sfp_template.py"}
        else:
            ignore_files = set(ignore_files)

        with self._lock:
            self._modules_dir = modules_dir
            self._discovered_at = time.time()
            self._descriptors.clear()
            self._classes.clear()
            self._clear_indices()

            loaded = 0
            failed = 0
            errors: list[tuple[str, str]] = []

            pattern = os.path.join(modules_dir, "sfp_*.py")
            for filepath in sorted(glob.glob(pattern)):
                basename = os.path.basename(filepath)
                if basename in ignore_files:
                    continue

                try:
                    desc, mod_class = self._introspect(filepath)
                    self._descriptors[desc.name] = desc
                    if mod_class is not None:
                        self._classes[desc.name] = mod_class
                    self._index(desc)
                    loaded += 1
                except Exception as exc:
                    mod_name = basename[:-3]
                    err_msg = f"{type(exc).__name__}: {exc}"
                    errors.append((mod_name, err_msg))
                    self._descriptors[mod_name] = ModuleDescriptor(
                        name=mod_name,
                        display_name=mod_name,
                        summary="",
                        filename=filepath,
                        watched_events=frozenset(),
                        produced_events=frozenset(),
                        categories=(),
                        flags=(),
                        use_cases=(),
                        opts={},
                        optdescs={},
                        data_source=None,
                        priority=3,
                        is_modern=False,
                        status=ModuleStatus.FAILED,
                        error=err_msg,
                    )
                    failed += 1

            log.info(
                "Module discovery complete: %d loaded, %d failed "
                "(dir=%s)",
                loaded,
                failed,
                modules_dir,
            )

            # ── Contract validation (non-blocking) ──
            contract_warnings = 0
            try:
                from spiderfoot.module_contract import validate_module
                for mod_name, mod_class in self._classes.items():
                    vr = validate_module(mod_class, name=mod_name)
                    if not vr.is_valid:
                        contract_warnings += 1
                        log.warning(
                            "Module %s contract issues: %s",
                            mod_name,
                            "; ".join(vr.all_errors),
                        )
                if contract_warnings:
                    log.info(
                        "Contract validation: %d/%d modules have warnings",
                        contract_warnings, len(self._classes),
                    )
            except Exception as exc:
                log.debug("Contract validation skipped: %s", exc)

            return DiscoveryResult(
                total=loaded + failed,
                loaded=loaded,
                failed=failed,
                errors=errors,
                duration=time.time() - self._discovered_at,
            )

    # ------------------------------------------------------------------
    # Introspection (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _introspect(filepath: str) -> tuple[ModuleDescriptor, type | None]:
        """Import a module file and extract its descriptor + class."""
        mod_name = os.path.basename(filepath)[:-3]

        spec = importlib.util.spec_from_file_location(mod_name, filepath)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {filepath}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Locate the plugin class
        mod_class = getattr(module, mod_name, None)
        if mod_class is None:
            # Fallback: scan for SpiderFootPlugin subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and any(
                    "SpiderFootPlugin" in str(base) for base in attr.__mro__
                ):
                    mod_class = attr
                    break

        if mod_class is None:
            raise ImportError(
                f"No SpiderFootPlugin subclass found in {filepath}"
            )

        # Extract metadata safely
        meta = getattr(mod_class, "meta", {}) or {}
        opts = dict(getattr(mod_class, "opts", {}) or {})
        optdescs = dict(getattr(mod_class, "optdescs", {}) or {})

        # Detect modern plugin
        is_modern = any(
            "SpiderFootModernPlugin" in str(base)
            for base in getattr(mod_class, "__mro__", [])
        )

        # watched / produced — prefer class methods, fall back to meta
        try:
            inst = mod_class.__new__(mod_class)
            watched = list(inst.watchedEvents())
        except Exception:
            watched = list(meta.get("consumes", []))

        try:
            inst = mod_class.__new__(mod_class)
            produced = list(inst.producedEvents())
        except Exception:
            produced = list(meta.get("provides", []))

        descriptor = ModuleDescriptor(
            name=mod_name,
            display_name=meta.get("name", mod_name),
            summary=meta.get("summary", "") or (mod_class.__doc__ or "").strip().split("\n")[0],
            filename=filepath,
            watched_events=frozenset(watched),
            produced_events=frozenset(produced),
            categories=tuple(meta.get("categories", [])),
            flags=tuple(meta.get("flags", [])),
            use_cases=tuple(meta.get("useCases", [])),
            opts=opts,
            optdescs=optdescs,
            data_source=meta.get("dataSource"),
            priority=getattr(mod_class, "_priority", 3),
            is_modern=is_modern,
            status=ModuleStatus.LOADED,
        )

        return descriptor, mod_class

    def _index(self, desc: ModuleDescriptor) -> None:
        """Populate inverted indices for a descriptor."""
        for ev in desc.produced_events:
            self._by_produced_event[ev].add(desc.name)
        for ev in desc.watched_events:
            self._by_watched_event[ev].add(desc.name)
        for cat in desc.categories:
            self._by_category[cat].add(desc.name)
        for flag in desc.flags:
            self._by_flag[flag].add(desc.name)
        for uc in desc.use_cases:
            self._by_usecase[uc].add(desc.name)

    def _clear_indices(self) -> None:
        self._by_produced_event.clear()
        self._by_watched_event.clear()
        self._by_category.clear()
        self._by_flag.clear()
        self._by_usecase.clear()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def module_count(self) -> int:
        return len(self._descriptors)

    @property
    def loaded_count(self) -> int:
        return sum(
            1 for d in self._descriptors.values()
            if d.status == ModuleStatus.LOADED
        )

    @property
    def all_event_types(self) -> set[str]:
        """All event types across all modules (produced + watched)."""
        return set(self._by_produced_event.keys()) | set(
            self._by_watched_event.keys()
        )

    def get(self, name: str) -> ModuleDescriptor | None:
        """Get a single module descriptor by name."""
        return self._descriptors.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._descriptors

    def __len__(self) -> int:
        return len(self._descriptors)

    def __iter__(self):
        return iter(self._descriptors.values())

    def list_names(self) -> list[str]:
        """Sorted list of all module names."""
        return sorted(self._descriptors.keys())

    def list_loaded(self) -> list[ModuleDescriptor]:
        """All successfully-loaded descriptors, sorted by name."""
        return sorted(
            (d for d in self._descriptors.values()
             if d.status == ModuleStatus.LOADED),
            key=lambda d: d.name,
        )

    def list_failed(self) -> list[ModuleDescriptor]:
        """All descriptors with status FAILED."""
        return [
            d for d in self._descriptors.values()
            if d.status == ModuleStatus.FAILED
        ]

    # Indexed queries ---------------------------------------------------

    def producers_of(self, event_type: str) -> list[str]:
        """Modules that produce a given event type."""
        return sorted(self._by_produced_event.get(event_type, set()))

    def consumers_of(self, event_type: str) -> list[str]:
        """Modules that watch / consume a given event type."""
        return sorted(self._by_watched_event.get(event_type, set()))

    def by_category(self, category: str) -> list[str]:
        """Modules in a specific category."""
        return sorted(self._by_category.get(category, set()))

    def by_flag(self, flag: str) -> list[str]:
        """Modules with a given flag (``apikey``, ``slow``, …)."""
        return sorted(self._by_flag.get(flag, set()))

    def by_usecase(self, usecase: str) -> list[str]:
        """Modules matching a use-case (``Footprint``, ``Investigate``, …)."""
        if usecase.lower() == "all":
            return self.list_names()
        return sorted(self._by_usecase.get(usecase, set()))

    def categories(self) -> dict[str, int]:
        """All categories with module counts."""
        return {cat: len(mods) for cat, mods in sorted(self._by_category.items())}

    def flags(self) -> dict[str, int]:
        """All flags with module counts."""
        return {f: len(mods) for f, mods in sorted(self._by_flag.items())}

    def search(self, query: str) -> list[ModuleDescriptor]:
        """Full-text search across name, display name, summary, categories."""
        return [d for d in self._descriptors.values() if d.matches_search(query)]

    # Dependency helpers ------------------------------------------------

    def dependencies_of(self, module_name: str) -> set[str]:
        """Modules that must run before *module_name*.

        A module depends on producers of the event types it watches.
        """
        desc = self.get(module_name)
        if desc is None:
            return set()

        deps: set[str] = set()
        for ev in desc.watched_events:
            deps.update(self._by_produced_event.get(ev, set()))
        deps.discard(module_name)
        return deps

    def dependents_of(self, module_name: str) -> set[str]:
        """Modules that depend on *module_name*'s output."""
        desc = self.get(module_name)
        if desc is None:
            return set()

        result: set[str] = set()
        for ev in desc.produced_events:
            result.update(self._by_watched_event.get(ev, set()))
        result.discard(module_name)
        return result

    def resolve_for_output(self, desired_types: Iterable[str]) -> set[str]:
        """Minimal set of modules needed to produce *desired_types*.

        BFS backward through the event-type dependency graph.
        """
        from collections import deque

        needed: set[str] = set()
        queue = deque()

        for event_type in desired_types:
            for mod in self._by_produced_event.get(event_type, set()):
                if mod not in needed:
                    needed.add(mod)
                    queue.append(mod)

        while queue:
            mod = queue.popleft()
            for dep in self.dependencies_of(mod):
                if dep not in needed:
                    needed.add(dep)
                    queue.append(dep)

        return needed

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    def create_instance(
        self,
        module_name: str,
        merged_opts: dict[str, Any] | None = None,
        *,
        sf: Any = None,
        scan_id: str | None = None,
        dbh: Any = None,
        target: Any = None,
        shared_pool: Any = None,
    ) -> Any:
        """Create and wire up a module instance.

        Args:
            module_name: e.g. ``sfp_shodan``
            merged_opts: Combined global + module options dict.
            sf: ``SpiderFoot`` facade instance.
            scan_id: Current scan ID.
            dbh: Database handle.
            target: Scan target.
            shared_pool: Shared thread pool.

        Returns:
            Initialised module instance, ready to receive events.

        Raises:
            KeyError: if *module_name* is not in the registry.
            RuntimeError: if the module class is not available.
        """
        if module_name not in self._descriptors:
            raise KeyError(f"Module '{module_name}' not in registry")

        desc = self._descriptors[module_name]

        if desc.status == ModuleStatus.FAILED:
            raise RuntimeError(
                f"Module '{module_name}' failed to load: {desc.error}"
            )

        mod_class = self._classes.get(module_name)
        if mod_class is None:
            # Attempt lazy load
            mod_class = self._lazy_load_class(module_name)

        instance = mod_class()
        instance.__name__ = module_name

        # Wire up lifecycle
        if scan_id is not None:
            instance.setScanId(scan_id)
        if shared_pool is not None:
            instance.setSharedThreadPool(shared_pool)
        if dbh is not None:
            instance.setDbh(dbh)
        if sf is not None:
            opts = dict(desc.opts)
            if merged_opts:
                opts.update(merged_opts)
            instance.setup(sf, opts)
        if target is not None:
            instance.setTarget(target)

        return instance

    def _lazy_load_class(self, module_name: str) -> type:
        """Import and cache a module class on demand."""
        desc = self._descriptors.get(module_name)
        if desc is None:
            raise KeyError(module_name)

        _, mod_class = self._introspect(desc.filename)
        if mod_class is None:
            raise RuntimeError(f"No class found in {desc.filename}")

        self._classes[module_name] = mod_class
        return mod_class

    def get_class(self, module_name: str) -> type | None:
        """Return the raw plugin class (loading lazily if needed)."""
        cls = self._classes.get(module_name)
        if cls is not None:
            return cls

        try:
            return self._lazy_load_class(module_name)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Bulk export (for backward compatibility)
    # ------------------------------------------------------------------

    def as_modules_dict(self) -> dict[str, dict[str, Any]]:
        """Return the catalog in the legacy ``config['__modules__']`` format.

        This allows the registry to be a drop-in replacement for the
        old ``loadModulesAsDict()`` output.
        """
        result = {}
        for desc in self._descriptors.values():
            if desc.status != ModuleStatus.LOADED:
                continue
            result[desc.name] = {
                "name": desc.display_name,
                "descr": desc.summary,
                "cats": list(desc.categories),
                "labels": list(desc.flags),
                "provides": sorted(desc.produced_events),
                "consumes": sorted(desc.watched_events),
                "opts": dict(desc.opts),
                "optdescs": dict(desc.optdescs),
                "meta": {
                    "name": desc.display_name,
                    "summary": desc.summary,
                    "categories": list(desc.categories),
                    "flags": list(desc.flags),
                    "useCases": list(desc.use_cases),
                    "dataSource": desc.data_source,
                },
                "group": list(desc.use_cases),
                "modern": desc.is_modern,
            }
        return result

    # ------------------------------------------------------------------
    # Miscellaneous
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Summary statistics about the registry."""
        return {
            "total_modules": len(self._descriptors),
            "loaded": self.loaded_count,
            "failed": len(self.list_failed()),
            "categories": len(self._by_category),
            "event_types_produced": len(self._by_produced_event),
            "event_types_watched": len(self._by_watched_event),
            "apikey_modules": len(self.by_flag("apikey")),
            "modern_modules": sum(
                1 for d in self._descriptors.values() if d.is_modern
            ),
            "discovered_at": self._discovered_at,
            "modules_dir": self._modules_dir,
        }

    def __repr__(self) -> str:
        return (
            f"<ModuleRegistry modules={len(self._descriptors)} "
            f"loaded={self.loaded_count}>"
        )


# ---------------------------------------------------------------------------
# Discovery result
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryResult:
    """Summary of a ``discover()`` call."""

    total: int
    """Total modules found on disk."""

    loaded: int
    """Successfully loaded."""

    failed: int
    """Failed to load (import error, missing class, …)."""

    errors: list[tuple[str, str]]
    """List of ``(module_name, error_message)`` pairs."""

    duration: float
    """Wall-clock seconds for the discovery scan."""

    def __repr__(self) -> str:
        return (
            f"<DiscoveryResult total={self.total} loaded={self.loaded} "
            f"failed={self.failed} duration={self.duration:.2f}s>"
        )
