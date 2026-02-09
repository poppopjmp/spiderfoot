from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_app_config, optional_auth
from ..pagination import PaginationParams, paginate
from ..schemas import RiskLevelsResponse
from spiderfoot.sflib.core import SpiderFoot
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
optional_auth_dep = Depends(optional_auth)


@router.get("/data/entity-types")
async def list_entity_types(api_key: str = optional_auth_dep):
    """
    List all supported entity/event types.

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: Entity types.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        types = sf.getEventTypes()
        return {"entity_types": types}
    except Exception as e:
        logger.exception("Failed to list entity types")
        raise HTTPException(status_code=500, detail=f"Failed to list entity types: {e}") from e


@router.get("/data/modules")
async def list_modules(
    params: PaginationParams = Depends(),
    api_key: str = optional_auth_dep,
):
    """
    List all available modules with pagination support.

    Args:
        params: Pagination parameters (page, page_size, sort_by, sort_order).
        api_key (str): API key for authentication.

    Returns:
        dict: Paginated modules.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        modules = sf.getModules()
        # modules may be a dict — convert to list for pagination
        if isinstance(modules, dict):
            module_list = [{"name": k, **v} if isinstance(v, dict) else {"name": k, "info": v} for k, v in modules.items()]
        else:
            module_list = list(modules) if modules else []
        return paginate(module_list, params)
    except Exception as e:
        logger.exception("Failed to list modules")
        raise HTTPException(status_code=500, detail=f"Failed to list modules: {e}") from e


@router.get("/data/sources")
async def list_sources(api_key: str = optional_auth_dep):
    """
    List all data sources.

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: Data sources.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        sources = sf.getDataSources()
        return {"sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list data sources") from e


@router.get("/data/modules/{module_name}")
async def get_module_details(module_name: str, api_key: str = optional_auth_dep):
    """
    Get details for a specific module.

    Args:
        module_name (str): The name of the module to retrieve details for.
        api_key (str): API key for authentication.

    Returns:
        dict: Details of the specified module.

    Raises:
        HTTPException: On error or if module not found.
    """
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        modules = sf.getModules()
        if module_name not in modules:
            raise HTTPException(status_code=404, detail="Module not found")
        return {"module": modules[module_name]}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get module details") from e


@router.get("/data/entity-types/{type_name}")
async def get_entity_type_details(type_name: str, api_key: str = optional_auth_dep):
    """
    Get details for a specific entity/event type.

    Args:
        type_name (str): The name of the entity type to retrieve details for.
        api_key (str): API key for authentication.

    Returns:
        dict: Details of the specified entity type.

    Raises:
        HTTPException: On error or if entity type not found.
    """
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        types = sf.getEventTypes()
        if type_name not in types:
            raise HTTPException(status_code=404, detail="Entity type not found")
        # Optionally, add more details if available
        return {"entity_type": type_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get entity type details") from e


@router.get("/data/global-options")
async def list_global_options(api_key: str = optional_auth_dep):
    """
    List global config options/descriptions.

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: Global options.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        opts = config.get_config().get("__globaloptdescs__", {})
        return {"global_options": opts}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list global options") from e


@router.get("/data/modules/{module_name}/options")
async def list_module_options(module_name: str, api_key: str = optional_auth_dep):
    """
    List config options for a specific module.

    Args:
        module_name (str): The name of the module to list options for.
        api_key (str): API key for authentication.

    Returns:
        dict: Config options for the specified module.

    Raises:
        HTTPException: On error or if module not found.
    """
    try:
        config = get_app_config()
        modules = config.get_config().get("__modules__", {})
        if module_name not in modules:
            raise HTTPException(status_code=404, detail="Module not found")
        options = modules[module_name].get("optdescs", {})
        return {"options": options}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list module options") from e


@router.post("/data/modules/{module_name}/validate-config")
async def validate_module_config(
    module_name: str,
    proposed_config: dict = {},
    api_key: str = optional_auth_dep,
):
    """Validate proposed configuration for a module.

    Checks that all required API keys are set, option values have valid
    types, and any constraints (e.g. numeric ranges) are satisfied.
    Returns a list of warnings and errors.
    """
    try:
        config = get_app_config()
        all_config = config.get_config()
        modules = all_config.get("__modules__", {})

        if module_name not in modules:
            raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

        mod_meta = modules[module_name]
        mod_opts = mod_meta.get("opts", {})
        mod_descs = mod_meta.get("optdescs", {})

        issues = []
        warnings = []

        # Merge proposed on top of defaults
        effective = dict(mod_opts)
        effective.update(proposed_config)

        # Check for unknown options
        for key in proposed_config:
            if key not in mod_opts:
                warnings.append({
                    "field": key,
                    "severity": "warning",
                    "message": f"Unknown option '{key}' — not in module defaults",
                })

        # Type checks: compare proposed values against default types
        for key, value in proposed_config.items():
            if key in mod_opts and mod_opts[key] is not None:
                expected_type = type(mod_opts[key])
                if not isinstance(value, expected_type):
                    # Allow int/float interchange
                    if expected_type in (int, float) and isinstance(value, (int, float)):
                        continue
                    issues.append({
                        "field": key,
                        "severity": "error",
                        "message": f"Type mismatch: expected {expected_type.__name__}, got {type(value).__name__}",
                        "expected": expected_type.__name__,
                        "actual": type(value).__name__,
                    })

        # Check for API key requirements
        flags = mod_meta.get("flags", [])
        if isinstance(flags, list) and "apikey" in flags:
            # Module requires an API key — check if any string option
            # with "api" in the name has a value set
            has_api_key = False
            for key, value in effective.items():
                if "api" in key.lower() and "key" in key.lower() and value:
                    has_api_key = True
                    break
            if not has_api_key:
                warnings.append({
                    "field": "api_key",
                    "severity": "warning",
                    "message": "Module requires an API key but none appears to be configured",
                })

        # Check boolean options
        for key, value in proposed_config.items():
            if key in mod_opts and isinstance(mod_opts[key], bool):
                if not isinstance(value, bool):
                    issues.append({
                        "field": key,
                        "severity": "error",
                        "message": f"Expected boolean, got {type(value).__name__}",
                    })

        valid = len(issues) == 0
        return {
            "module": module_name,
            "valid": valid,
            "errors": issues,
            "warnings": warnings,
            "effective_config": {k: str(v)[:100] for k, v in effective.items()},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate config for %s: %s", module_name, e)
        raise HTTPException(status_code=500, detail="Failed to validate module config") from e


@router.get("/data/module-categories")
async def list_module_categories(api_key: str = optional_auth_dep):
    """
    List all module categories/tags.

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: Module categories.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        modules = config.get_config().get("__modules__", {})
        categories = set()
        for mod in modules.values():
            for cat in mod.get("categories", []):
                categories.add(cat)
        return {"module_categories": sorted(categories)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list module categories") from e


@router.get("/data/module-types")
async def list_module_types(api_key: str = optional_auth_dep):
    """
    List all module types (e.g., passive, active).

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: Module types.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        modules = config.get_config().get("__modules__", {})
        types = set()
        for mod in modules.values():
            mtype = mod.get("type")
            if mtype:
                types.add(mtype)
        return {"module_types": sorted(types)}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list module types") from e


@router.get("/data/risk-levels", response_model=RiskLevelsResponse)
async def list_risk_levels(api_key: str = optional_auth_dep):
    """
    List all risk levels.

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: Risk levels.

    Raises:
        HTTPException: On error.
    """
    try:
        # These are typically static, but can be made dynamic if needed
        risk_levels = ["info", "low", "medium", "high", "critical"]
        return {"risk_levels": risk_levels}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list risk levels") from e


@router.get("/data/modules/stats")
async def get_module_stats(api_key: str = optional_auth_dep):
    """Runtime module statistics aggregating timeout, output validation, and health data.

    Returns a consolidated view of per-module performance metrics from:
    - ModuleTimeoutGuard (timeout counts)
    - ModuleOutputValidator (undeclared event violations)
    - ModuleHealthMonitor (healthy/degraded/unhealthy status)
    """
    result = {"modules": {}}

    # 1. Timeout statistics
    try:
        from spiderfoot.module_timeout import get_timeout_guard
        guard = get_timeout_guard()
        stats = guard.stats()
        result["timeout"] = {
            "default_timeout_s": guard.default_timeout,
            "total_guarded": stats.get("total_guarded", 0),
            "total_timeouts": stats.get("total_timeouts", 0),
        }
        # Per-module timeouts if available
        for mod_name, mod_stats in stats.get("per_module", {}).items():
            result["modules"].setdefault(mod_name, {})["timeout"] = mod_stats
    except ImportError:
        result["timeout"] = {"available": False}
    except Exception:
        result["timeout"] = {"available": False}

    # 2. Output validation statistics
    try:
        from spiderfoot.module_output_validator import get_output_validator
        validator = get_output_validator()
        all_stats = validator.get_all_stats()
        result["output_validation"] = {
            "mode": validator.mode,
            "modules_tracked": len(all_stats),
            "modules_with_violations": sum(1 for s in all_stats.values() if s.get("undeclared", 0) > 0),
        }
        for mod_name, mod_stats in all_stats.items():
            result["modules"].setdefault(mod_name, {})["output_validation"] = mod_stats
    except ImportError:
        result["output_validation"] = {"available": False}
    except Exception:
        result["output_validation"] = {"available": False}

    # 3. Module health
    try:
        from spiderfoot.module_health import get_health_monitor
        monitor = get_health_monitor()
        report = monitor.get_report()
        result["health"] = report.get("summary", {})
        for mod_name, mod_health in report.get("modules", {}).items():
            result["modules"].setdefault(mod_name, {})["health"] = mod_health
    except ImportError:
        result["health"] = {"available": False}
    except Exception:
        result["health"] = {"available": False}

    result["module_count"] = len(result["modules"])
    return result


@router.get("/data/modules/dependencies")
async def get_module_dependencies(
    api_key: str = optional_auth_dep,
):
    """Module dependency graph showing which modules produce/consume which event types.

    Returns a dependency map useful for understanding the module pipeline:
    - **nodes**: Each module with its produced and consumed event types
    - **edges**: Directed edges from producer module to consumer module via event type
    - **event_types**: For each event type, which modules produce and consume it

    Use ``?format=mermaid`` to get a Mermaid diagram string.
    """
    from fastapi import Query as Q
    from spiderfoot import SpiderFootHelpers
    from spiderfoot.sflib.core import SpiderFoot

    fmt = "json"  # default
    try:
        sf = SpiderFoot({})
        module_list = sf.modulesProducing([])  # returns dict of all modules
    except Exception:
        module_list = {}

    # Build nodes and event type maps
    nodes = {}
    event_type_map = {}  # event_type -> {producers: [], consumers: []}
    edges = []

    # Load all modules to get their produces/consumes
    try:
        config = get_app_config()
        cfg = config.get_config()
        sf = SpiderFoot(cfg)
        mod_dir = sf.modulesPath()

        # Load module metadata
        all_mods = sf.moduleMeta(mod_dir)

        for mod_name, meta in all_mods.items():
            produces = []
            consumes = []

            if isinstance(meta, dict):
                produces = meta.get("produces", [])
                consumes = meta.get("consumes", [])
            elif hasattr(meta, "producedEvents"):
                produces = meta.producedEvents() if callable(meta.producedEvents) else []
                consumes = meta.watchedEvents() if callable(getattr(meta, "watchedEvents", None)) else []

            nodes[mod_name] = {
                "produces": sorted(produces) if produces else [],
                "consumes": sorted(consumes) if consumes else [],
            }

            for et in (produces or []):
                event_type_map.setdefault(et, {"producers": [], "consumers": []})
                event_type_map[et]["producers"].append(mod_name)

            for et in (consumes or []):
                event_type_map.setdefault(et, {"producers": [], "consumers": []})
                event_type_map[et]["consumers"].append(mod_name)

    except Exception as e:
        logger.error("Failed to load module dependencies: %s", e)
        # Try a simpler approach using data service
        try:
            svc = get_data_service()
            modules = svc.list_modules()
            if isinstance(modules, dict):
                modules = list(modules.values())
            for mod in modules:
                name = mod.get("name", mod.get("module", ""))
                if not name:
                    continue
                produces = mod.get("produces", mod.get("producedEvents", []))
                consumes = mod.get("consumes", mod.get("watchedEvents", []))
                nodes[name] = {
                    "produces": sorted(produces) if produces else [],
                    "consumes": sorted(consumes) if consumes else [],
                }
                for et in (produces or []):
                    event_type_map.setdefault(et, {"producers": [], "consumers": []})
                    event_type_map[et]["producers"].append(name)
                for et in (consumes or []):
                    event_type_map.setdefault(et, {"producers": [], "consumers": []})
                    event_type_map[et]["consumers"].append(name)
        except Exception:
            pass

    # Build edges: producer_module -> consumer_module via event_type
    for et, info in event_type_map.items():
        for producer in info["producers"]:
            for consumer in info["consumers"]:
                if producer != consumer:
                    edges.append({
                        "from": producer,
                        "to": consumer,
                        "event_type": et,
                    })

    return {
        "nodes": nodes,
        "edges": edges,
        "event_types": {
            k: v for k, v in sorted(event_type_map.items())
        },
        "summary": {
            "total_modules": len(nodes),
            "total_event_types": len(event_type_map),
            "total_edges": len(edges),
            "orphan_producers": sorted([
                et for et, info in event_type_map.items()
                if info["producers"] and not info["consumers"]
            ]),
            "orphan_consumers": sorted([
                et for et, info in event_type_map.items()
                if info["consumers"] and not info["producers"]
            ]),
        },
    }


# ── Module enable / disable management ────────────────────────────────
# Runtime in-memory set of disabled module names.  Scans check this set
# before loading modules so operators can disable problematic modules
# without restarting the service.

_disabled_modules: set = set()
_disabled_modules_lock = __import__("threading").Lock()


def get_disabled_modules() -> set:
    """Return a frozen copy of the disabled-module set (thread-safe)."""
    with _disabled_modules_lock:
        return frozenset(_disabled_modules)


@router.get("/data/modules/status")
async def get_module_status(api_key: str = optional_auth_dep):
    """Return the enable/disable status of all modules.

    Modules not in the disabled set are considered enabled.
    """
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        modules = sf.getModules() or {}

        disabled = get_disabled_modules()
        status_list = []
        for name in sorted(modules.keys()):
            status_list.append({
                "module": name,
                "enabled": name not in disabled,
            })

        return {
            "total": len(status_list),
            "enabled": sum(1 for s in status_list if s["enabled"]),
            "disabled": sum(1 for s in status_list if not s["enabled"]),
            "modules": status_list,
        }
    except Exception as e:
        logger.error("Failed to get module status: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get module status") from e


@router.post("/data/modules/{module_name}/disable")
async def disable_module(module_name: str, api_key: str = optional_auth_dep):
    """Disable a module at runtime.

    Disabled modules will be excluded from future scans.
    Currently running scans are not affected.
    """
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        modules = sf.getModules() or {}
        if module_name not in modules:
            raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

        with _disabled_modules_lock:
            already = module_name in _disabled_modules
            _disabled_modules.add(module_name)

        logger.info("Module disabled: %s (was_already=%s)", module_name, already)
        return {
            "module": module_name,
            "enabled": False,
            "message": "already disabled" if already else "disabled",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to disable module %s: %s", module_name, e)
        raise HTTPException(status_code=500, detail="Failed to disable module") from e


@router.post("/data/modules/{module_name}/enable")
async def enable_module(module_name: str, api_key: str = optional_auth_dep):
    """Re-enable a previously disabled module."""
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        modules = sf.getModules() or {}
        if module_name not in modules:
            raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

        with _disabled_modules_lock:
            was_disabled = module_name in _disabled_modules
            _disabled_modules.discard(module_name)

        logger.info("Module enabled: %s (was_disabled=%s)", module_name, was_disabled)
        return {
            "module": module_name,
            "enabled": True,
            "message": "enabled" if was_disabled else "already enabled",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to enable module %s: %s", module_name, e)
        raise HTTPException(status_code=500, detail="Failed to enable module") from e


@router.post("/data/modules/bulk-disable")
async def bulk_disable_modules(
    module_names: list = [],
    api_key: str = optional_auth_dep,
):
    """Disable multiple modules at once.

    Body: list of module name strings.
    """
    if not module_names:
        raise HTTPException(status_code=400, detail="Provide a list of module names")

    config = get_app_config()
    sf = SpiderFoot(config.get_config())
    modules = sf.getModules() or {}

    results = []
    with _disabled_modules_lock:
        for name in module_names:
            if name not in modules:
                results.append({"module": name, "status": "not_found"})
                continue
            already = name in _disabled_modules
            _disabled_modules.add(name)
            results.append({
                "module": name,
                "status": "already_disabled" if already else "disabled",
            })

    logger.info("Bulk disabled %d modules", len(module_names))
    return {
        "results": results,
        "disabled_count": len(_disabled_modules),
    }
