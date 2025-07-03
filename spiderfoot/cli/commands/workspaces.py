"""
Workspace management commands for SpiderFoot CLI.
"""

import shlex

def workspaces_command(cli, line):
    """List all workspaces using the API."""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/workspaces'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No workspaces found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def workspace_create_command(cli, line):
    """Create a new workspace using the API. Usage: workspace_create <name> [description]"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: workspace_create <name> [description]")
        return
    name = args[0]
    description = args[1] if len(args) > 1 else ""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/workspaces'
    payload = {"name": name, "description": description}
    resp = cli.request(url, post=payload)
    if resp:
        cli.dprint(f"Workspace '{name}' created.")
    else:
        cli.edprint("Failed to create workspace.")

def workspace_delete_command(cli, line):
    """Delete a workspace using the API. Usage: workspace_delete <workspace_id>"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: workspace_delete <workspace_id>")
        return
    workspace_id = args[0]
    import requests
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}'
    try:
        resp = requests.delete(url)
        if resp.status_code == 200:
            cli.dprint(f"Workspace {workspace_id} deleted.")
        else:
            cli.edprint(f"Failed to delete workspace: {resp.text}")
    except Exception as e:
        cli.edprint(f"Error deleting workspace: {e}")

def register(registry):
    registry.register("workspaces", workspaces_command, help_text="List all workspaces using the API.")
    registry.register("workspace_create", workspace_create_command, help_text="Create a new workspace using the API.")
    registry.register("workspace_delete", workspace_delete_command, help_text="Delete a workspace using the API.")
