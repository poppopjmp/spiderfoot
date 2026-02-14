from __future__ import annotations

"""FastAPI router for workspace management, target handling, and multi-scan operations."""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Body, UploadFile, File
from fastapi.responses import StreamingResponse
import json
from io import BytesIO
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot import SpiderFootHelpers
from ..dependencies import get_app_config, get_api_key, optional_auth
from ..models import WorkspaceRequest, TargetRequest, MultiScanRequest
from ..pagination import PaginationParams, paginate
from ..schemas import (
    WorkspaceCreateResponse, WorkspaceDetailResponse, WorkspaceUpdateResponse,
    WorkspaceDeleteResponse, WorkspaceCloneResponse,
    TargetAddResponse, TargetDeleteResponse,
)
import logging

router = APIRouter()
log = logging.getLogger(__name__)

api_key_dep = Depends(get_api_key)
optional_auth_dep = Depends(optional_auth)

metadata_body = Body(...)


@router.get("/workspaces")
async def list_workspaces(
    params: PaginationParams = Depends(),
    api_key: str = optional_auth_dep,
) -> dict:
    """List all workspaces with pagination support."""
    try:
        config = get_app_config()
        workspaces = SpiderFootWorkspace.list_workspaces(config.get_config())
        return paginate(workspaces, params)
    except Exception as e:
        log.error("Failed to list workspaces: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list workspaces") from e


@router.post("/workspaces", status_code=201, response_model=WorkspaceCreateResponse)
async def create_workspace(workspace_request: WorkspaceRequest, api_key: str = api_key_dep) -> WorkspaceCreateResponse:
    """Create a new workspace with the given name and description."""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), name=workspace_request.name)
        workspace.description = workspace_request.description
        workspace.save_workspace()
        return WorkspaceCreateResponse(
            workspace_id=workspace.workspace_id,
            name=workspace.name,
            description=workspace.description or "",
            created_time=workspace.created_time,
        )
    except Exception as e:
        log.error("Failed to create workspace: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create workspace") from e


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(workspace_id: str, api_key: str = optional_auth_dep) -> dict:
    """Retrieve workspace details including targets, scans, and metadata."""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        return {
            "workspace_id": workspace.workspace_id,
            "name": workspace.name,
            "description": workspace.description,
            "created_time": workspace.created_time,
            "modified_time": workspace.modified_time,
            "targets": workspace.get_targets(),
            "scans": workspace.get_scans(),
            "metadata": workspace.metadata
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to get workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to get workspace") from e


@router.put("/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    name: str | None = None,
    description: str | None = None,
    api_key: str = api_key_dep,
) -> dict:
    """
    Update workspace details (name, description).

    Args:
        workspace_id (str): Workspace ID.
        name (str | None): New workspace name.
        description (str | None): New workspace description.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        if name is not None:
            workspace.name = name
        if description is not None:
            workspace.description = description
        workspace.save_workspace()
        return {"success": True, "message": "Workspace updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to update workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to update workspace") from e


@router.get("/workspaces/{workspace_id}/summary")
async def get_workspace_summary(workspace_id: str, api_key: str = optional_auth_dep) -> dict:
    """
    Get workspace summary.

    Args:
        workspace_id (str): Workspace ID.
        api_key (str): API key for authentication.

    Returns:
        dict: Workspace summary.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        summary = workspace.get_workspace_summary()
        return {"success": True, "summary": summary}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to get workspace summary for %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to get workspace summary") from e


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str, api_key: str = api_key_dep) -> dict:
    """Delete a workspace by its ID."""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        workspace.delete_workspace()
        return {"message": "Workspace deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to delete workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete workspace") from e


@router.post("/workspaces/{workspace_id}/targets", status_code=201)
async def add_target(workspace_id: str, target_request: TargetRequest, api_key: str = api_key_dep) -> dict:
    """Add a validated target to the specified workspace."""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        valid_type = SpiderFootHelpers.targetTypeFromString(target_request.target)
        if not valid_type or valid_type != target_request.target_type:
            raise HTTPException(status_code=422, detail="Invalid target type")
        target_id = workspace.add_target(
            target_request.target,
            target_request.target_type,
            target_request.metadata
        )
        return {
            "target_id": target_id,
            "message": "Target added successfully"
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to add target to workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to add target") from e


@router.get("/workspaces/{workspace_id}/targets")
async def list_targets(
    workspace_id: str,
    params: PaginationParams = Depends(),
    api_key: str = optional_auth_dep,
) -> dict:
    """List all targets in a workspace with pagination support."""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        targets = workspace.get_targets()
        return paginate(targets, params)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to list targets for workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to list targets") from e


@router.delete("/workspaces/{workspace_id}/targets/{target_id}")
async def remove_target(workspace_id: str, target_id: str, api_key: str = api_key_dep) -> dict:
    """Remove a target from the specified workspace."""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        success = workspace.remove_target(target_id)
        if not success:
            raise HTTPException(status_code=404, detail="Target not found")
        return {"message": "Target removed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to remove target %s from workspace %s: %s", target_id, workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to remove target") from e


@router.post("/workspaces/{workspace_id}/multi-scan")
async def start_multi_scan(
    workspace_id: str,
    multi_scan_request: MultiScanRequest,
    background_tasks: BackgroundTasks,
    api_key: str = api_key_dep
) -> dict:
    """Start a multi-target scan for all targets in the workspace."""
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        targets = multi_scan_request.targets
        if not targets:
            workspace_targets = workspace.get_targets()
            targets = [t['value'] for t in workspace_targets]
        if not targets:
            raise HTTPException(status_code=400, detail="No targets available for scanning")
        return {
            "targets": targets,
            "modules": multi_scan_request.modules,
            "message": f"Multi-target scan started for {len(targets)} targets"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to start multi-scan: %s", e)
        raise HTTPException(status_code=500, detail="Failed to start multi-scan") from e


@router.delete("/workspaces/{workspace_id}/scans/{scan_id}")
async def remove_scan_from_workspace(workspace_id: str, scan_id: str, api_key: str = api_key_dep) -> dict:
    """
    Remove a scan from a workspace.

    Args:
        workspace_id (str): Workspace ID.
        scan_id (str): Scan ID.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        success = workspace.remove_scan(scan_id)
        if not success:
            raise HTTPException(status_code=404, detail="Scan not found in workspace")
        return {"message": "Scan removed from workspace successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to remove scan %s from workspace %s: %s", scan_id, workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to remove scan from workspace") from e


@router.post("/workspaces/{workspace_id}/scans/{scan_id}")
async def link_scan_to_workspace(workspace_id: str, scan_id: str, api_key: str = api_key_dep) -> dict:
    """
    Link an existing scan to a workspace for cross-scan correlation.

    Args:
        workspace_id (str): Workspace ID.
        scan_id (str): Scan ID to link.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        success = workspace.import_single_scan(scan_id)
        if not success:
            return {"message": "Scan already linked to workspace"}
        return {"message": "Scan linked to workspace successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        log.error("Failed to link scan %s to workspace %s: %s", scan_id, workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to link scan to workspace") from e


@router.post("/workspaces/{workspace_id}/set-active")
async def set_active_workspace(workspace_id: str, api_key: str = api_key_dep) -> dict:
    """
    Set the active workspace for the current session/user.

    Args:
        workspace_id (str): Workspace ID.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        SpiderFootWorkspace(config.get_config(), workspace_id)
        return {"message": f"Workspace {workspace_id} set as active"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to set active workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to set active workspace") from e


@router.patch("/workspaces/{workspace_id}/metadata")
async def update_workspace_metadata(
    workspace_id: str,
    metadata: dict = metadata_body,
    api_key: str = api_key_dep
) -> dict:
    """
    Update workspace metadata (key/value pairs).

    Args:
        workspace_id (str): Workspace ID.
        metadata (dict): Metadata to update.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message and updated metadata.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        workspace = SpiderFootWorkspace(config.get_config(), workspace_id)
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=422, detail="Metadata must be a dictionary")
        workspace.metadata.update(metadata)
        workspace.save_workspace()
        return {"success": True, "metadata": workspace.metadata}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to update metadata for workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to update workspace metadata") from e


@router.post("/workspaces/{workspace_id}/clone", status_code=201)
async def clone_workspace(workspace_id: str, api_key: str = api_key_dep) -> dict:
    """
    Clone a workspace (name, description, metadata, and targets).

    Args:
        workspace_id (str): Workspace ID to clone.
        api_key (str): API key for authentication.

    Returns:
        dict: New workspace info.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        orig = SpiderFootWorkspace(config.get_config(), workspace_id)
        new_name = orig.name + " (Clone)"
        new_workspace = SpiderFootWorkspace(config.get_config(), name=new_name)
        new_workspace.description = orig.description
        new_workspace.metadata = dict(orig.metadata)
        new_workspace.save_workspace()
        # Clone targets
        for t in orig.get_targets():
            new_workspace.add_target(t['value'], t['type'], t.get('metadata', {}))
        return {
            "workspace_id": new_workspace.workspace_id,
            "name": new_workspace.name,
            "description": new_workspace.description,
            "created_time": new_workspace.created_time,
            "metadata": new_workspace.metadata,
            "message": "Workspace cloned successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to clone workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to clone workspace") from e


@router.get("/workspaces/{workspace_id}/export")
async def export_workspace(workspace_id: str, api_key: str = api_key_dep) -> StreamingResponse:
    """
    Export a workspace as a downloadable JSON file.

    Args:
        workspace_id (str): Workspace ID to export.
        api_key (str): API key for authentication.

    Returns:
        StreamingResponse: JSON file download.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        ws = SpiderFootWorkspace(config.get_config(), workspace_id)
        export_data = {
            "workspace_id": ws.workspace_id,
            "name": ws.name,
            "description": ws.description,
            "created_time": ws.created_time,
            "modified_time": ws.modified_time,
            "metadata": ws.metadata,
            "targets": ws.get_targets(),
        }
        file_bytes = BytesIO(json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8"))
        file_bytes.seek(0)
        return StreamingResponse(
            file_bytes,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=workspace-{ws.workspace_id}.json",
                "Pragma": "no-cache"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to export workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to export workspace") from e


@router.post("/workspaces/import", status_code=201)
async def import_workspace(
    file: UploadFile = File(...),
    api_key: str = api_key_dep
) -> dict:
    """
    Import a workspace from a JSON file upload.

    Args:
        file (UploadFile): JSON file to import.
        api_key (str): API key for authentication.

    Returns:
        dict: New workspace info.

    Raises:
        HTTPException: On error.
    """
    try:
        content = await file.read()
        data = json.loads(content)
        config = get_app_config()
        name = data.get("name", "Imported Workspace")
        description = data.get("description", "")
        metadata = data.get("metadata", {})
        targets = data.get("targets", [])
        new_workspace = SpiderFootWorkspace(config.get_config(), name=name)
        new_workspace.description = description
        new_workspace.metadata = dict(metadata)
        new_workspace.save_workspace()
        for t in targets:
            new_workspace.add_target(t['value'], t['type'], t.get('metadata', {}))
        return {
            "workspace_id": new_workspace.workspace_id,
            "name": new_workspace.name,
            "description": new_workspace.description,
            "created_time": new_workspace.created_time,
            "metadata": new_workspace.metadata,
            "message": "Workspace imported successfully"
        }
    except Exception as e:
        log.error("Failed to import workspace: %s", e)
        raise HTTPException(status_code=400, detail="Failed to import workspace") from e


@router.post("/workspaces/{workspace_id}/clear")
async def clear_workspace(workspace_id: str, api_key: str = api_key_dep) -> dict:
    """
    Remove all scans and targets from a workspace.

    Args:
        workspace_id (str): Workspace ID to clear.
        api_key (str): API key for authentication.

    Returns:
        dict: Success message.

    Raises:
        HTTPException: On error.
    """
    try:
        config = get_app_config()
        ws = SpiderFootWorkspace(config.get_config(), workspace_id)
        # Remove all scans
        for scan_id in list(ws.get_scans()):
            ws.remove_scan(scan_id)
        # Remove all targets
        for target in list(ws.get_targets()):
            ws.remove_target(target['id'])
        ws.save_workspace()
        return {"success": True, "message": "Workspace cleared (all scans and targets removed)"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to clear workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to clear workspace") from e


@router.post("/workspaces/{workspace_id}/archive")
async def archive_workspace(workspace_id: str, api_key: str = api_key_dep) -> dict:
    """
    Archive a workspace (set archived flag in metadata).
    """
    try:
        config = get_app_config()
        ws = SpiderFootWorkspace(config.get_config(), workspace_id)
        ws.metadata['archived'] = True
        ws.save_workspace()
        return {"success": True, "message": "Workspace archived"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to archive workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to archive workspace") from e


@router.post("/workspaces/{workspace_id}/unarchive")
async def unarchive_workspace(workspace_id: str, api_key: str = api_key_dep) -> dict:
    """
    Unarchive a workspace (unset archived flag in metadata).
    """
    try:
        config = get_app_config()
        ws = SpiderFootWorkspace(config.get_config(), workspace_id)
        ws.metadata['archived'] = False
        ws.save_workspace()
        return {"success": True, "message": "Workspace unarchived"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Workspace not found") from e
    except Exception as e:
        log.error("Failed to unarchive workspace %s: %s", workspace_id, e)
        raise HTTPException(status_code=500, detail="Failed to unarchive workspace") from e
