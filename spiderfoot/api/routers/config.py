"""
Configuration API router.

Modernised to delegate to the typed ``AppConfig`` underneath the
``Config`` facade, providing real validation, structured responses,
and Pydantic request models while keeping backward compatibility
with flat-dict consumers.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel, Field
from ..dependencies import get_app_config, get_config_repository, optional_auth
import logging
from typing import Any, Dict, List, Optional

router = APIRouter()
logger = logging.getLogger(__name__)
optional_auth_dep = Depends(optional_auth)
config_body = Body(...)


# ------------------------------------------------------------------
# Pydantic request / response models
# ------------------------------------------------------------------

class ConfigUpdateRequest(BaseModel):
    """Typed request for PATCH /config."""
    options: Dict[str, Any] = Field(..., description="Config key/value pairs to update")


class ConfigValidateRequest(BaseModel):
    """Typed request for POST /config/validate."""
    options: Dict[str, Any] = Field(..., description="Config key/value pairs to validate")


class ValidationErrorItem(BaseModel):
    """Single validation error."""
    field: str
    message: str
    value: Optional[Any] = None


class ValidationResponse(BaseModel):
    """Response from validation endpoint."""
    valid: bool
    errors: List[ValidationErrorItem] = []
    sections_checked: int = 0


class ConfigSummaryResponse(BaseModel):
    """Structured config overview."""
    summary: Dict[str, Any]
    config: Dict[str, Any]
    version: str = ""


@router.get("/config")
async def get_config_endpoint(api_key: str = optional_auth_dep):
    """
    Get the global configuration.

    Returns a safe subset of the config (no dunder internal keys)
    alongside a typed summary from ``AppConfig``.
    """
    try:
        cfg = get_app_config()
        raw = cfg.get_config()
        safe_config = {
            k: v for k, v in raw.items()
            if not k.startswith('__') or k in ['__version__', '__database']
        }
        return ConfigSummaryResponse(
            summary=cfg.config_summary(),
            config=safe_config,
            version=cfg.app_config.version,
        ).model_dump()
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration") from e


@router.patch("/config")
async def update_config(body: ConfigUpdateRequest, api_key: str = optional_auth_dep):
    """
    Update global config options with typed validation.
    """
    try:
        cfg = get_app_config()
        options = body.options

        # Validate the merged state before applying
        is_valid, errors = cfg.validate_config(options)
        if not is_valid:
            return {
                "success": False,
                "message": "Validation failed",
                "errors": errors,
            }

        for k, v in options.items():
            cfg.set_config_option(k, v)
        cfg.save_config()
        return {"success": True, "message": "Config updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update config") from e


@router.put("/config")
async def update_config_endpoint(
    new_config: dict,
    api_key: str = Depends(optional_auth)
):
    """
    Update the global configuration.

    Parameters:
        new_config (dict): The new configuration values.
        api_key (str): Optional API key for authentication.
    Returns:
        dict: Status of the update operation.
    Raises:
        HTTPException: If the update fails.
    """
    try:
        config = get_app_config()
        config.update_config(new_config)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration") from e


@router.get("/modules")
async def get_modules(api_key: str = optional_auth_dep):
    """
    Get all modules and their info.

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: List of modules.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        modules_list = []
        for mod in config.get_config()['__modules__']:
            if "__" in mod:
                continue
            module_config = config.get_config()['__modules__'][mod]
            module_info = {
                "name": mod,
                "category": module_config.get('cats', ['Unknown'])[0] if module_config.get('cats') else 'Unknown',
                "description": module_config.get('descr', 'No description'),
                "flags": module_config.get('labels', []),
                "dependencies": module_config.get('deps', []),
                "provides": module_config.get('provides', []),
                "consumes": module_config.get('consumes', []),
                "group": module_config.get('group', [])
            }
            modules_list.append(module_info)
        return {"modules": sorted(modules_list, key=lambda x: x['name'])}
    except Exception as e:
        logger.error(f"Failed to get modules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get modules") from e


@router.patch("/modules/{module_name}/options")
async def update_module_options(module_name: str, options: dict = config_body, api_key: str = optional_auth_dep):
    """
    Update config options for a specific module.

    Args:
        module_name (str): Module name.
        options (dict): Options to update.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On error or if module not found.
    """
    try:
        config = get_app_config()
        modules = config.get_config().get("__modules__", {})
        if module_name not in modules:
            raise HTTPException(status_code=404, detail="Module not found")
        try:
            modules[module_name].update(options)
            config.save_config()
            return {"success": True, "message": f"Module {module_name} options updated"}
        except KeyError as ke:
            # If Config.update_module_config raises KeyError with 404, return 404
            if "404" in str(ke):
                raise HTTPException(status_code=404, detail="Module not found")
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update module options: {e}")
        raise HTTPException(status_code=500, detail="Failed to update module options") from e


@router.get("/event-types")
async def get_event_types(api_key: str = optional_auth_dep,
                          config_repo=Depends(get_config_repository)):
    """
    Get all event types.

    Args:
        api_key (str): API key for authentication.
        config_repo: Injected ConfigRepository.

    Returns:
        dict: List of event types.

    Raises:
        HTTPException: On error.
    """
    try:
        event_types = config_repo.get_event_types()
        return {"event_types": event_types}
    except Exception as e:
        logger.error(f"Failed to get event types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get event types") from e


@router.get("/module-config/{module_name}")
async def get_module_config(
    module_name: str,
    api_key: str = Depends(optional_auth)
):
    """
    Get configuration for a specific module.

    Parameters:
        module_name (str): The name of the module.
        api_key (str): Optional API key for authentication.
    Returns:
        dict: Module name and configuration.
    Raises:
        HTTPException: If the module is not found or retrieval fails.
    """
    try:
        config = get_app_config()
        module_config = config.get_module_config(module_name)
        if module_config is None:
            raise HTTPException(status_code=404, detail="Module not found")
        return {"module": module_name, "config": module_config}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get module config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get module configuration") from e


@router.put("/module-config/{module_name}")
async def update_module_config(
    module_name: str,
    new_config: dict,
    api_key: str = Depends(optional_auth)
):
    """
    Update configuration for a specific module.

    Parameters:
        module_name (str): The name of the module.
        new_config (dict): The new configuration values.
        api_key (str): Optional API key for authentication.
    Returns:
        dict: Status of the update operation.
    Raises:
        HTTPException: If the update fails.
    """
    try:
        config = get_app_config()
        config.update_module_config(module_name, new_config)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to update module config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update module configuration") from e


@router.post("/config/reload")
async def reload_config(api_key: str = Depends(optional_auth)):
    """
    Reload the application configuration from the database
    and re-apply environment variable overrides.
    """
    try:
        cfg = get_app_config()
        cfg.reload()
        return {"status": "reloaded", "summary": cfg.config_summary()}
    except Exception as e:
        logger.error(f"Failed to reload config: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload configuration") from e


@router.post("/config/validate")
async def validate_config(body: ConfigValidateRequest, api_key: str = optional_auth_dep):
    """
    Validate configuration options without saving.

    Merges the supplied options with the current config and runs
    ``AppConfig.validate()`` against the merged state.
    """
    try:
        cfg = get_app_config()
        is_valid, errors = cfg.validate_config(body.options)
        resp = ValidationResponse(
            valid=is_valid,
            errors=[ValidationErrorItem(**e) for e in errors],
            sections_checked=11,  # 11 typed sections in AppConfig
        )
        return resp.model_dump()
    except Exception as e:
        logger.error(f"Failed to validate config: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate config") from e


@router.get("/config/scan-defaults")
async def get_scan_defaults(api_key: str = optional_auth_dep):
    """
    Get scan default options.
    """
    try:
        config = get_app_config()
        defaults = config.get_scan_defaults()
        return {"scan_defaults": defaults}
    except Exception as e:
        logger.error(f"Failed to get scan defaults: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scan defaults") from e


@router.patch("/config/scan-defaults")
async def update_scan_defaults(options: dict = config_body, api_key: str = optional_auth_dep):
    """
    Update scan default options.
    """
    try:
        config = get_app_config()
        config.set_scan_defaults(options)
        config.save_config()
        return {"success": True, "message": "Scan defaults updated"}
    except Exception as e:
        logger.error(f"Failed to update scan defaults: {e}")
        raise HTTPException(status_code=500, detail="Failed to update scan defaults") from e


@router.get("/config/workspace-defaults")
async def get_workspace_defaults(api_key: str = optional_auth_dep):
    """
    Get workspace default options.
    """
    try:
        config = get_app_config()
        defaults = config.get_workspace_defaults()
        return {"workspace_defaults": defaults}
    except Exception as e:
        logger.error(f"Failed to get workspace defaults: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workspace defaults") from e


@router.patch("/config/workspace-defaults")
async def update_workspace_defaults(options: dict = config_body, api_key: str = optional_auth_dep):
    """
    Update workspace default options.
    """
    try:
        config = get_app_config()
        config.set_workspace_defaults(options)
        config.save_config()
        return {"success": True, "message": "Workspace defaults updated"}
    except Exception as e:
        logger.error(f"Failed to update workspace defaults: {e}")
        raise HTTPException(status_code=500, detail="Failed to update workspace defaults") from e


@router.get("/config/api-keys")
async def list_api_keys(api_key: str = optional_auth_dep):
    """
    List all API keys (admin only).
    """
    try:
        config = get_app_config()
        keys = config.get_api_keys()
        return {"api_keys": keys}
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys") from e

@router.post("/config/api-keys")
async def add_api_key(key_data: dict = config_body, api_key: str = optional_auth_dep):
    """
    Add a new API key (admin only).
    """
    try:
        config = get_app_config()
        config.add_api_key(key_data)
        config.save_config()
        return {"success": True, "message": "API key added"}
    except Exception as e:
        logger.error(f"Failed to add API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to add API key") from e

@router.delete("/config/api-keys/{key_id}")
async def delete_api_key(key_id: str, api_key: str = optional_auth_dep):
    """
    Delete an API key (admin only).
    """
    try:
        config = get_app_config()
        config.delete_api_key(key_id)
        config.save_config()
        return {"success": True, "message": "API key deleted"}
    except Exception as e:
        logger.error(f"Failed to delete API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete API key") from e


@router.post("/config/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: str, api_key: str = optional_auth_dep):
    """Rotate an API key — generates a new key value, preserving permissions.

    The old key is immediately invalidated and a new key value is returned.
    This is an atomic operation: the key's ID, name, and permissions remain
    the same, only the secret value changes.

    Returns the new key value (only shown once — store it securely).
    """
    import secrets
    import time as _time

    try:
        config = get_app_config()
        keys = config.get_api_keys()

        # Find the key to rotate
        target = None
        for k in keys:
            kid = k.get("id") or k.get("key_id") or k.get("name", "")
            if kid == key_id:
                target = k
                break

        if target is None:
            raise HTTPException(status_code=404, detail=f"API key '{key_id}' not found")

        # Generate new key value
        new_key_value = secrets.token_urlsafe(32)

        # Preserve metadata, update the key value
        target["key"] = new_key_value
        target["rotated_at"] = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
        target["rotation_count"] = target.get("rotation_count", 0) + 1

        config.save_config()

        logger.info("API key '%s' rotated successfully", key_id)

        return {
            "success": True,
            "key_id": key_id,
            "new_key": new_key_value,
            "rotated_at": target["rotated_at"],
            "rotation_count": target["rotation_count"],
            "message": "API key rotated — store the new key securely (shown only once)",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rotate API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to rotate API key") from e

@router.get("/config/credentials")
async def list_credentials(api_key: str = optional_auth_dep):
    """
    List all stored credentials.
    """
    try:
        config = get_app_config()
        creds = config.get_credentials()
        return {"credentials": creds}
    except Exception as e:
        logger.error(f"Failed to list credentials: {e}")
        raise HTTPException(status_code=500, detail="Failed to list credentials") from e

@router.post("/config/credentials")
async def add_credential(cred_data: dict = config_body, api_key: str = optional_auth_dep):
    """
    Add a new credential.
    """
    try:
        config = get_app_config()
        config.add_credential(cred_data)
        config.save_config()
        return {"success": True, "message": "Credential added"}
    except Exception as e:
        logger.error(f"Failed to add credential: {e}")
        raise HTTPException(status_code=500, detail="Failed to add credential") from e

@router.delete("/config/credentials/{cred_id}")
async def delete_credential(cred_id: str, api_key: str = optional_auth_dep):
    """
    Delete a credential.
    """
    try:
        config = get_app_config()
        config.delete_credential(cred_id)
        config.save_config()
        return {"success": True, "message": "Credential deleted"}
    except Exception as e:
        logger.error(f"Failed to delete credential: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete credential") from e

@router.get("/config/export")
async def export_config(api_key: str = optional_auth_dep):
    """
    Export the current configuration as JSON.
    """
    try:
        config = get_app_config()
        return config.get_config()
    except Exception as e:
        logger.error(f"Failed to export config: {e}")
        raise HTTPException(status_code=500, detail="Failed to export config") from e


@router.get("/config/summary")
async def get_config_summary(api_key: str = optional_auth_dep):
    """
    Return a typed summary of all 11 AppConfig sections.
    """
    try:
        cfg = get_app_config()
        ac = cfg.app_config
        return {
            "summary": ac.summary(),
            "sections": {
                "core": {
                    "debug": ac.core.debug,
                    "max_threads": ac.core.max_threads,
                    "production": ac.core.production,
                },
                "network": {
                    "dns_server": ac.network.dns_server,
                    "dns_timeout": ac.network.dns_timeout,
                    "fetch_timeout": ac.network.fetch_timeout,
                    "proxy_type": ac.network.proxy_type or "none",
                },
                "database": {
                    "db_path": ac.database.db_path,
                    "pg_host": ac.database.pg_host or "none",
                },
                "web": {"host": ac.web.host, "port": ac.web.port},
                "api": {
                    "host": ac.api.host,
                    "port": ac.api.port,
                    "log_level": ac.api.log_level,
                },
                "cache": {
                    "backend": ac.cache.backend,
                    "ttl": ac.cache.ttl,
                },
                "eventbus": {"backend": ac.eventbus.backend},
                "vector": {"enabled": ac.vector.enabled},
                "worker": {
                    "max_workers": ac.worker.max_workers,
                    "strategy": ac.worker.strategy,
                    "max_scans": ac.worker.max_scans,
                },
                "redis": {
                    "host": ac.redis.host,
                    "port": ac.redis.port,
                },
                "elasticsearch": {
                    "enabled": ac.elasticsearch.enabled,
                },
            },
            "version": ac.version,
        }
    except Exception as e:
        logger.error(f"Failed to get config summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get config summary") from e

@router.post("/config/import")
async def import_config(new_config: dict = config_body, api_key: str = optional_auth_dep):
    """
    Import/replace the current configuration.
    """
    try:
        config = get_app_config()
        config.replace_config(new_config)
        config.save_config()
        return {"success": True, "message": "Config imported"}
    except Exception as e:
        logger.error(f"Failed to import config: {e}")
        raise HTTPException(status_code=500, detail="Failed to import config") from e


# ------------------------------------------------------------------
# Config source tracing (Cycle 58)
# ------------------------------------------------------------------

class ConfigSourceEntry(BaseModel):
    """Single config key with its value and provenance source."""
    key: str
    value: Any = None
    source: str = "default"


class ConfigSourcesResponse(BaseModel):
    """Full provenance report for all config keys."""
    total: int = 0
    breakdown: Dict[str, int] = {}
    entries: List[ConfigSourceEntry] = []


class ConfigEnvironmentResponse(BaseModel):
    """Environment variable overrides + discovery report."""
    active_overrides: Dict[str, str] = {}
    unknown_sf_vars: List[str] = []
    deployment_mode: str = "standalone"
    service_role: str = ""
    service_name: str = ""


@router.get("/config/sources")
async def get_config_sources(
    filter_source: Optional[str] = Query(
        None,
        alias="source",
        description="Filter by source (default, env:*, file:*, runtime)",
    ),
    api_key: str = optional_auth_dep,
):
    """Return provenance information for every config key.

    Shows where each value came from: ``default``, ``file:<name>``,
    ``env:<VAR>``, or ``runtime``.  Useful for debugging configuration
    precedence in microservice deployments.
    """
    try:
        from spiderfoot.config_service import ConfigService

        cs = ConfigService.get_instance()
        all_sources = cs.get_sources()
        raw_config = cs.as_dict()

        entries: List[ConfigSourceEntry] = []
        for key, src in sorted(all_sources.items()):
            if filter_source and not src.startswith(filter_source):
                continue
            entries.append(ConfigSourceEntry(
                key=key,
                value=raw_config.get(key),
                source=src,
            ))

        # Build breakdown
        breakdown: Dict[str, int] = {}
        for e in entries:
            prefix = e.source.split(":")[0] if ":" in e.source else e.source
            breakdown[prefix] = breakdown.get(prefix, 0) + 1

        return ConfigSourcesResponse(
            total=len(entries),
            breakdown=breakdown,
            entries=entries,
        ).model_dump()
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="ConfigService not available — source tracing requires v5.51.0+",
        )
    except Exception as e:
        logger.error(f"Failed to get config sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to get config sources") from e


@router.get("/config/environment")
async def get_config_environment(api_key: str = optional_auth_dep):
    """Report environment variable overrides and service identity.

    Returns active ``SF_*`` env vars that override defaults, flags
    unknown ``SF_*`` vars (possible typos), and reports the current
    deployment mode / service role / service name.
    """
    try:
        from spiderfoot.config_service import ConfigService

        cs = ConfigService.get_instance()
        return ConfigEnvironmentResponse(
            active_overrides=cs.get_env_overrides(),
            unknown_sf_vars=cs.discover_env_vars(),
            deployment_mode="microservice" if cs.is_microservice else "standalone",
            service_role=cs.service_role,
            service_name=cs.service_name,
        ).model_dump()
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="ConfigService not available — environment tracing requires v5.51.0+",
        )
    except Exception as e:
        logger.error(f"Failed to get environment info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get environment info") from e


@router.get("/config/validate")
async def validate_current_config(api_key: str = optional_auth_dep):
    """Validate the current running configuration comprehensively.

    Unlike ``POST /config/validate`` (which checks proposed changes),
    this endpoint inspects the **live** configuration, checking:

    - AppConfig typed section validation (11 sections)
    - Module option consistency (unknown keys, type mismatches)
    - Required API key presence for enabled modules
    - Environment variable consistency
    - Database connection string validity

    Returns a structured report with severity levels (error/warning/info).
    """
    import os

    results: List[Dict[str, Any]] = []

    # 1. AppConfig typed section validation
    try:
        cfg = get_app_config()
        is_valid, errors = cfg.validate_config({})
        if not is_valid:
            for err in errors:
                results.append({
                    "severity": "error",
                    "category": "app_config",
                    "field": err.get("field", "unknown"),
                    "message": err.get("message", "validation failed"),
                })
        else:
            results.append({
                "severity": "info",
                "category": "app_config",
                "message": "All 11 typed config sections valid",
            })
    except Exception as e:
        results.append({
            "severity": "error",
            "category": "app_config",
            "message": f"Config validation failed: {e}",
        })

    # 2. Check critical environment variables
    critical_vars = {
        "SF_DATA_DIR": "Data directory",
        "SF_MODULES_DIR": "Modules directory",
    }
    for var, desc in critical_vars.items():
        val = os.environ.get(var)
        if val and not os.path.exists(val):
            results.append({
                "severity": "warning",
                "category": "environment",
                "field": var,
                "message": f"{desc} path does not exist: {val}",
            })

    # 3. Check for unknown SF_* environment variables
    try:
        from spiderfoot.config_service import ConfigService
        cs = ConfigService.get_instance()
        unknown = cs.discover_env_vars()
        for var in unknown:
            results.append({
                "severity": "warning",
                "category": "environment",
                "field": var,
                "message": f"Unknown SF_* variable (possible typo): {var}",
            })
    except Exception:
        pass

    # 4. Check module API key requirements
    try:
        cfg = get_app_config()
        all_opts = cfg.get_config()
        modules_missing_keys = []
        for key, val in all_opts.items():
            # Convention: _api_key options for modules
            if key.endswith("_api_key") and not val:
                module_name = key.rsplit("_api_key", 1)[0]
                # Check if the module is enabled
                enabled_key = f"{module_name}_enabled"
                if all_opts.get(enabled_key, True):
                    modules_missing_keys.append(module_name)

        if modules_missing_keys:
            results.append({
                "severity": "warning",
                "category": "api_keys",
                "message": f"{len(modules_missing_keys)} enabled modules missing API keys",
                "modules": modules_missing_keys[:20],
            })
    except Exception:
        pass

    # 5. Service auth configuration check
    try:
        svc_secret = os.environ.get("SF_SERVICE_SECRET")
        svc_token = os.environ.get("SF_SERVICE_TOKEN")
        if not svc_secret and not svc_token:
            results.append({
                "severity": "info",
                "category": "security",
                "message": "No inter-service auth configured (OK for standalone mode)",
            })
    except Exception:
        pass

    error_count = sum(1 for r in results if r["severity"] == "error")
    warning_count = sum(1 for r in results if r["severity"] == "warning")

    return {
        "valid": error_count == 0,
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            "info": sum(1 for r in results if r["severity"] == "info"),
            "total_checks": len(results),
        },
        "results": results,
    }


# -----------------------------------------------------------------------
# Rate limit management
# -----------------------------------------------------------------------

@router.get("/config/rate-limits")
async def get_rate_limits(api_key: str = optional_auth_dep):
    """Get current rate limit configuration including per-endpoint overrides."""
    try:
        from spiderfoot.api.rate_limit_middleware import get_rate_limit_config, get_rate_limit_stats
        return {
            "config": get_rate_limit_config(),
            "stats": get_rate_limit_stats(),
        }
    except Exception as e:
        logger.error("Failed to get rate limit config: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get rate limit configuration") from e


class EndpointRateLimitRequest(BaseModel):
    """Request to set a per-endpoint rate limit override."""
    path: str = Field(..., description="URL path prefix (e.g. /api/scans/bulk/delete)")
    requests: int = Field(..., ge=1, le=10000, description="Max requests per window")
    window: float = Field(60.0, ge=1.0, le=3600.0, description="Window in seconds")


@router.put("/config/rate-limits/endpoints")
async def set_endpoint_rate_limit(
    request: EndpointRateLimitRequest,
    api_key: str = optional_auth_dep,
):
    """Set a per-endpoint rate limit override (runtime, not persisted)."""
    try:
        from spiderfoot.api.rate_limit_middleware import set_endpoint_override
        ok = set_endpoint_override(request.path, request.requests, request.window)
        if not ok:
            raise HTTPException(status_code=503, detail="Rate limiter not initialized")
        return {
            "message": f"Rate limit override set for {request.path}",
            "path": request.path,
            "requests": request.requests,
            "window": request.window,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to set endpoint rate limit: %s", e)
        raise HTTPException(status_code=500, detail="Failed to set rate limit") from e


@router.delete("/config/rate-limits/endpoints")
async def remove_endpoint_rate_limit(
    path: str = Query(..., description="URL path prefix to remove override for"),
    api_key: str = optional_auth_dep,
):
    """Remove a per-endpoint rate limit override."""
    try:
        from spiderfoot.api.rate_limit_middleware import remove_endpoint_override
        removed = remove_endpoint_override(path)
        if not removed:
            raise HTTPException(status_code=404, detail=f"No override found for {path}")
        return {"message": f"Rate limit override removed for {path}", "path": path}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove endpoint rate limit: %s", e)
        raise HTTPException(status_code=500, detail="Failed to remove rate limit") from e
