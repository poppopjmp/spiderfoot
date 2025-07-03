"""
Delete command for SpiderFoot CLI.
"""

def delete_command(cli, line):
    """Delete a scan using the SpiderFoot API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: delete <scan_id>")
        return
    scan_id = args[0]
    import requests
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}'
    try:
        resp = requests.delete(url)
        if resp.status_code == 200:
            cli.dprint(f"Successfully deleted scan {scan_id}.")
        else:
            cli.edprint(f"Failed to delete scan {scan_id}: {resp.text}")
    except Exception as e:
        cli.edprint(f"Error deleting scan: {e}")

def register(registry):
    registry.register("delete", delete_command, help_text="Delete a scan using the SpiderFoot API.")
