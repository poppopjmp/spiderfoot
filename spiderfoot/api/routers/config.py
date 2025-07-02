from fastapi import APIRouter, Depends, HTTPException, Body
from spiderfoot import SpiderFootDb
from ..dependencies import get_app_config, optional_auth
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
optional_auth_dep = Depends(optional_auth)
config_body = Body(...)


@router.get("/config")
async def get_config_endpoint(api_key: str = optional_auth_dep):
    """
    Get the global configuration (safe subset).

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: Safe config.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        safe_config = {
            k: v for k, v in config.get_config().items()
            if not k.startswith('__') or k in ['__version__', '__database']
        }
        return {"config": safe_config}
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration") from e


@router.patch("/config")
async def update_config(options: dict = config_body, api_key: str = optional_auth_dep):
    """
    Update global config options.

    Args:
        options (dict): Config options to update.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        for k, v in options.items():
            config.set_config_option(k, v)
        config.save_config()
        return {"success": True, "message": "Config updated"}
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
        modules[module_name].update(options)
        config.save_config()
        return {"success": True, "message": f"Module {module_name} options updated"}
    except Exception as e:
        logger.error(f"Failed to update module options: {e}")
        raise HTTPException(status_code=500, detail="Failed to update module options") from e


@router.get("/event-types")
async def get_event_types(api_key: str = optional_auth_dep):
    """
    Get all event types.

    Args:
        api_key (str): API key for authentication.

    Returns:
        dict: List of event types.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        db = SpiderFootDb(config.get_config())
        event_types = db.eventTypes()
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
async def reload_config(
    api_key: str = Depends(optional_auth)
):
    """
    Reload the application configuration from disk.

    Parameters:
        api_key (str): Optional API key for authentication.
    Returns:
        dict: Status of the reload operation.
    Raises:
        HTTPException: If the reload fails.
    """
    try:
        config = get_app_config()
        config.reload()
        return {"status": "reloaded"}
    except Exception as e:
        logger.error(f"Failed to reload config: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload configuration") from e


@router.post("/config/validate")
async def validate_config(options: dict = config_body, api_key: str = optional_auth_dep):
    """
    Validate configuration options without saving.

    Args:
        options (dict): Config options to validate.
        api_key (str): API key for authentication.

    Returns:
        dict: Validation result.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        # Assume config.validate_config returns (bool, errors)
        is_valid, errors = config.validate_config(options)
        return {"valid": is_valid, "errors": errors}
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
