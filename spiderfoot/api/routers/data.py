from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_app_config, optional_auth
from ..pagination import PaginationParams, paginate
from spiderfoot.sflib.core import SpiderFoot

router = APIRouter()
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
    import traceback
    try:
        config = get_app_config()
        sf = SpiderFoot(config.get_config())
        types = sf.getEventTypes()
        return {"entity_types": types}
    except Exception as e:
        print("EXCEPTION TRACEBACK:\n", traceback.format_exc())
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
    import traceback
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
        print("EXCEPTION TRACEBACK:\n", traceback.format_exc())
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


@router.get("/data/risk-levels")
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


# No data endpoints have been moved yet. Add data-related endpoints here as needed.
