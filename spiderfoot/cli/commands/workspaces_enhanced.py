"""
Comprehensive workspace management commands for SpiderFoot CLI.
"""

import shlex
import json

def workspaces_command(cli, line):
    """List all workspaces using the API. Usage: workspaces [--details]"""
    args = shlex.split(line)
    show_details = '--details' in args
    
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/workspaces'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No workspaces found.")
        return
    
    try:
        data = json.loads(resp) if hasattr(json, 'loads') else cli.json_loads(resp)
        workspaces = data.get('workspaces', []) if isinstance(data, dict) else data
        
        if not workspaces:
            cli.dprint("No workspaces found.")
            return
            
        cli.dprint("Workspaces:", plain=True)
        for ws in workspaces:
            if isinstance(ws, dict):
                name = ws.get('name', ws.get('id', 'Unknown'))
                status = ws.get('status', 'Unknown')
                scan_count = ws.get('scan_count', 0)
                if show_details:
                    description = ws.get('description', 'No description')
                    created = ws.get('created', 'Unknown')
                    cli.dprint(f"  • {name} ({status}) - {scan_count} scans", plain=True)
                    cli.dprint(f"    Description: {description}", plain=True)
                    cli.dprint(f"    Created: {created}", plain=True)
                else:
                    cli.dprint(f"  • {name} ({status}) - {scan_count} scans", plain=True)
            else:
                cli.dprint(f"  • {ws}", plain=True)
    except Exception as e:
        cli.edprint(f"Failed to parse workspace list: {e}")

def workspace_create_command(cli, line):
    """Create a new workspace. Usage: workspace_create <name> [description]"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: workspace_create <name> [description]")
        return
    
    name = args[0]
    description = ' '.join(args[1:]) if len(args) > 1 else ""
    
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/workspaces'
    payload = {"name": name, "description": description}
    resp = cli.request(url, post=payload)
    if resp:
        try:
            data = json.loads(resp)
            workspace_id = data.get('id', name)
            cli.dprint(f"Workspace '{name}' created successfully (ID: {workspace_id})")
        except:
            cli.dprint(f"Workspace '{name}' created successfully")
    else:
        cli.edprint("Failed to create workspace.")

def workspace_delete_command(cli, line):
    """Delete a workspace. Usage: workspace_delete <workspace_id>"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: workspace_delete <workspace_id>")
        return
    
    workspace_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}'
    resp = cli.request(url, delete=True)
    if resp:
        cli.dprint(f"Workspace '{workspace_id}' deleted successfully")
    else:
        cli.edprint(f"Failed to delete workspace '{workspace_id}'")

def workspace_info_command(cli, line):
    """Get detailed information about a workspace. Usage: workspace_info <workspace_id>"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: workspace_info <workspace_id>")
        return
    
    workspace_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}'
    resp = cli.request(url)
    if not resp:
        cli.edprint(f"Workspace '{workspace_id}' not found")
        return
    
    try:
        data = json.loads(resp)
        cli.dprint(f"Workspace: {data.get('name', workspace_id)}", plain=True)
        cli.dprint(f"  ID: {data.get('id', workspace_id)}", plain=True)
        cli.dprint(f"  Description: {data.get('description', 'No description')}", plain=True)
        cli.dprint(f"  Status: {data.get('status', 'Unknown')}", plain=True)
        cli.dprint(f"  Created: {data.get('created', 'Unknown')}", plain=True)
        cli.dprint(f"  Modified: {data.get('modified', 'Unknown')}", plain=True)
        cli.dprint(f"  Scan Count: {data.get('scan_count', 0)}", plain=True)
        cli.dprint(f"  Target Count: {data.get('target_count', 0)}", plain=True)
    except Exception as e:
        cli.edprint(f"Failed to parse workspace info: {e}")

def workspace_activate_command(cli, line):
    """Set a workspace as active. Usage: workspace_activate <workspace_id>"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: workspace_activate <workspace_id>")
        return
    
    workspace_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}/set-active'
    resp = cli.request(url, post={})
    if resp:
        cli.dprint(f"Workspace '{workspace_id}' is now active")
        # Update CLI config if possible
        if hasattr(cli.config, 'set'):
            cli.config.set('cli.active_workspace', workspace_id)
    else:
        cli.edprint(f"Failed to activate workspace '{workspace_id}'")

def workspace_export_command(cli, line):
    """Export workspace data. Usage: workspace_export <workspace_id> [format] [output_file]"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: workspace_export <workspace_id> [format] [output_file]")
        return
    
    workspace_id = args[0]
    format_type = args[1] if len(args) > 1 else 'json'
    output_file = args[2] if len(args) > 2 else None
    
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}/export'
    if format_type != 'json':
        url += f'?format={format_type}'
    
    resp = cli.request(url)
    if not resp:
        cli.edprint(f"Failed to export workspace '{workspace_id}'")
        return
    
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(resp)
            cli.dprint(f"Workspace exported to '{output_file}'")
        except Exception as e:
            cli.edprint(f"Failed to write to file: {e}")
    else:
        cli.dprint(resp, plain=True)

def workspace_clone_command(cli, line):
    """Clone a workspace. Usage: workspace_clone <source_workspace_id> <new_name>"""
    args = shlex.split(line)
    if len(args) < 2:
        cli.edprint("Usage: workspace_clone <source_workspace_id> <new_name>")
        return
    
    source_id = args[0]
    new_name = args[1]
    
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{source_id}/clone'
    payload = {"name": new_name}
    resp = cli.request(url, post=payload)
    if resp:
        try:
            data = json.loads(resp)
            new_id = data.get('id', new_name)
            cli.dprint(f"Workspace cloned successfully. New workspace ID: {new_id}")
        except:
            cli.dprint(f"Workspace cloned successfully")
    else:
        cli.edprint(f"Failed to clone workspace '{source_id}'")

def register(registry):
    """Register all workspace commands"""
    registry.register("workspaces", workspaces_command, 
                     help_text="List all workspaces. Use --details for more info.")
    registry.register("workspace_create", workspace_create_command, 
                     help_text="Create a new workspace.")
    registry.register("workspace_delete", workspace_delete_command, 
                     help_text="Delete a workspace.")
    registry.register("workspace_info", workspace_info_command, 
                     help_text="Get detailed information about a workspace.")
    registry.register("workspace_activate", workspace_activate_command, 
                     help_text="Set a workspace as active.")
    registry.register("workspace_export", workspace_export_command, 
                     help_text="Export workspace data.")
    registry.register("workspace_clone", workspace_clone_command, 
                     help_text="Clone a workspace.")
