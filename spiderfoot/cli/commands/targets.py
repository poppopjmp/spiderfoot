"""
Target management commands for SpiderFoot CLI.
"""

import shlex

def targets_command(cli, line):
    """List all targets in a workspace. Usage: targets <workspace_id>"""
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: targets <workspace_id>")
        return
    workspace_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}/targets'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No targets found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def target_add_command(cli, line):
    """Add a target to a workspace. Usage: target_add <workspace_id> <target> <target_type> [metadata_json]"""
    import json
    args = shlex.split(line)
    if len(args) < 3:
        cli.edprint("Usage: target_add <workspace_id> <target> <target_type> [metadata_json]")
        return
    workspace_id, target, target_type = args[:3]
    metadata = json.loads(args[3]) if len(args) > 3 else {}
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}/targets'
    payload = {"target": target, "target_type": target_type, "metadata": metadata}
    resp = cli.request(url, post=payload)
    if resp:
        cli.dprint(f"Target '{target}' added to workspace {workspace_id}.")
    else:
        cli.edprint("Failed to add target.")

def target_delete_command(cli, line):
    """Delete a target from a workspace. Usage: target_delete <workspace_id> <target_id>"""
    args = shlex.split(line)
    if len(args) < 2:
        cli.edprint("Usage: target_delete <workspace_id> <target_id>")
        return
    workspace_id, target_id = args[:2]
    import requests
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/workspaces/{workspace_id}/targets/{target_id}'
    try:
        resp = requests.delete(url)
        if resp.status_code == 200:
            cli.dprint(f"Target {target_id} deleted from workspace {workspace_id}.")
        else:
            cli.edprint(f"Failed to delete target: {resp.text}")
    except Exception as e:
        cli.edprint(f"Error deleting target: {e}")

def register(registry):
    registry.register("targets", targets_command, help_text="List all targets in a workspace.")
    registry.register("target_add", target_add_command, help_text="Add a target to a workspace.")
    registry.register("target_delete", target_delete_command, help_text="Delete a target from a workspace.")
