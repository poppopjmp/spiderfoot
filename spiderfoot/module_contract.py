"""
Formal interface contracts for SpiderFoot modules.

Provides:
- ``SpiderFootModuleProtocol`` — a runtime-checkable ``Protocol`` that
  defines the mandatory surface every module must implement.
- ``ModuleMeta`` — Pydantic model that validates the ``meta`` dict
  each module declares.
- ``validate_module()`` — helper that checks a loaded module class/instance
  against the protocol and meta schema, returning typed diagnostics.

These contracts are **structural** (duck-typed), so all 230+ existing
modules satisfy them automatically — no code changes required in
individual ``sfp_*.py`` files.

Usage (in module loader)::

    from spiderfoot.module_contract import validate_module
    errors = validate_module(module_class)
    if errors:
        log.warning("Module %s does not satisfy contract: %s", name, errors)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

log = logging.getLogger("spiderfoot.module_contract")


# ── Protocol ─────────────────────────────────────────────────────────

@runtime_checkable
class SpiderFootModuleProtocol(Protocol):
    """Structural typing contract that every SpiderFoot module must satisfy.

    This is a **runtime-checkable Protocol** — you can write::

        isinstance(my_module, SpiderFootModuleProtocol)

    and it will return ``True`` for any object whose class has the
    required attributes and methods, without inheriting from this class.
    """

    # ── Required class / instance attributes ──
    meta: Dict[str, Any]
    opts: Dict[str, Any]
    optdescs: Dict[str, str]
    errorState: bool

    # ── Lifecycle ──
    def setup(self, sf: Any, userOpts: dict = ...) -> None:  # type: ignore[assignment]
        """Initialise the module with the SpiderFoot facade and user options."""
        ...

    def watchedEvents(self) -> List[str]:
        """Return event types this module subscribes to."""
        ...

    def producedEvents(self) -> List[str]:
        """Return event types this module can emit."""
        ...

    def handleEvent(self, sfEvent: Any) -> None:
        """Process a single incoming event."""
        ...

    # ── Optional but expected ──
    def finish(self) -> None:
        """Clean up resources when the scan or module is shutting down."""
        ...

    def setTarget(self, target: Any) -> None:
        """Assign the scan target."""
        ...

    def setScanId(self, scanId: str) -> None:
        """Set the current scan instance ID."""
        ...

    def checkForStop(self) -> bool:
        """Return True if the scan has been aborted."""
        ...

    def notifyListeners(self, sfEvent: Any) -> None:
        """Fan-out an event to registered downstream listeners."""
        ...

    def registerListener(self, listener: Any) -> None:
        """Register a downstream module as a listener."""
        ...

    def clearListeners(self) -> None:
        """Remove all registered listeners."""
        ...

    def asdict(self) -> dict:
        """Serialise module metadata to a dict."""
        ...


# ── Module Metadata Schema ───────────────────────────────────────────

class DataSourceModel(BaseModel):
    """Optional data-source declaration for modules that call external APIs."""
    website: Optional[str] = None
    model: Optional[str] = None
    references: List[str] = Field(default_factory=list)
    apiKeyInstructions: Optional[str] = None
    favIcon: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None


class ModuleMeta(BaseModel):
    """Validated schema for the ``meta`` dict on every module class.

    Example valid meta::

        meta = {
            "name": "DNS Resolver",
            "summary": "Resolves hosts and IP addresses identified.",
            "flags": [],
            "useCases": ["Footprint", "Investigate"],
            "categories": ["DNS"],
        }
    """
    name: str = Field(..., min_length=1, description="Human-readable module name")
    summary: str = Field("", description="One-line description")
    flags: List[str] = Field(default_factory=list, description="Module flags: apikey, slow, errorprone, etc.")
    useCases: List[str] = Field(default_factory=list, description="Use-case categories")
    categories: List[str] = Field(default_factory=list, description="Module categories")
    dataSource: Optional[DataSourceModel] = None
    # Legacy fields that some modules still use
    descr: Optional[str] = Field(None, description="Legacy description field")

    @field_validator("flags", mode="before")
    @classmethod
    def ensure_flags_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)

    @field_validator("useCases", mode="before")
    @classmethod
    def ensure_use_cases_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)

    @field_validator("categories", mode="before")
    @classmethod
    def ensure_categories_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)

    model_config = {"extra": "allow"}  # Tolerate extra keys in meta dicts


# ── Validation Diagnostics ───────────────────────────────────────────

@dataclass
class ModuleValidationResult:
    """Result of validating a module against the contract."""
    module_name: str
    is_valid: bool = True
    protocol_errors: List[str] = field(default_factory=list)
    meta_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def all_errors(self) -> List[str]:
        return self.protocol_errors + self.meta_errors


def validate_module(
    module_class_or_instance: Any,
    *,
    name: Optional[str] = None,
    strict: bool = False,
) -> ModuleValidationResult:
    """Validate a module class or instance against the interface contract.

    Args:
        module_class_or_instance: A module class (``sfp_xyz``) or instance.
        name: Optional human-readable name for diagnostics.
        strict: If True, treat warnings as errors.

    Returns:
        ``ModuleValidationResult`` with categorised diagnostics.
    """
    mod = module_class_or_instance
    mod_name = name or getattr(mod, "__name__", None) or type(mod).__name__
    result = ModuleValidationResult(module_name=mod_name)

    # ── Protocol check ──
    is_class = isinstance(mod, type)
    check_target = mod if is_class else type(mod)

    required_methods = [
        "setup", "watchedEvents", "producedEvents", "handleEvent",
    ]
    required_attrs = ["meta", "opts", "optdescs"]

    for method in required_methods:
        if not callable(getattr(check_target, method, None)):
            result.protocol_errors.append(f"Missing required method: {method}()")

    for attr in required_attrs:
        if not hasattr(check_target, attr):
            # Check instance-level too for class-level dicts
            if is_class:
                result.protocol_errors.append(f"Missing required attribute: {attr}")
            elif not hasattr(mod, attr):
                result.protocol_errors.append(f"Missing required attribute: {attr}")

    # ── Optional but recommended methods ──
    optional_methods = ["finish", "setTarget", "setScanId", "checkForStop"]
    for method in optional_methods:
        if not callable(getattr(check_target, method, None)):
            result.warnings.append(f"Missing optional method: {method}()")

    # ── Meta dict validation ──
    meta_raw = getattr(mod, "meta", None)
    if meta_raw is None:
        result.meta_errors.append("Module has no 'meta' dict")
    elif not isinstance(meta_raw, dict):
        result.meta_errors.append(f"'meta' is {type(meta_raw).__name__}, expected dict")
    else:
        try:
            ModuleMeta(**meta_raw)
        except Exception as exc:
            result.meta_errors.append(f"Meta validation failed: {exc}")

    # ── Event declarations ──
    if not result.protocol_errors:
        try:
            instance = mod() if is_class else mod
            watched = instance.watchedEvents() if callable(getattr(instance, "watchedEvents", None)) else None
            produced = instance.producedEvents() if callable(getattr(instance, "producedEvents", None)) else None

            if watched is not None and not isinstance(watched, list):
                result.warnings.append(f"watchedEvents() returned {type(watched).__name__}, expected list")
            if produced is not None and not isinstance(produced, list):
                result.warnings.append(f"producedEvents() returned {type(produced).__name__}, expected list")
            if watched is not None and not watched:
                result.warnings.append("watchedEvents() returns empty list — module will receive no events")
            if produced is not None and not produced:
                result.warnings.append("producedEvents() returns empty list — module declares no output")
        except Exception:
            # Can't instantiate bare — that's fine, skip event checks
            pass

    # ── Finalise ──
    if strict:
        result.protocol_errors.extend(result.warnings)
        result.warnings = []

    result.is_valid = len(result.protocol_errors) == 0 and len(result.meta_errors) == 0
    return result


def validate_module_batch(
    modules: Dict[str, Any],
    *,
    strict: bool = False,
) -> List[ModuleValidationResult]:
    """Validate a batch of modules, returning results for each.

    Args:
        modules: Dict of module_name → class_or_instance.
        strict: Treat warnings as errors.
    """
    results = []
    for name, mod in modules.items():
        result = validate_module(mod, name=name, strict=strict)
        results.append(result)
        if not result.is_valid:
            log.warning(
                "Module %s failed contract validation: %s",
                name, "; ".join(result.all_errors),
            )
    valid_count = sum(1 for r in results if r.is_valid)
    log.info(
        "Module contract validation: %d/%d passed",
        valid_count, len(results),
    )
    return results
