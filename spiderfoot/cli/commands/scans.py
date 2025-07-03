"""
Scans command for SpiderFoot CLI.
"""

def scans_command(cli, line):
    """List all scans using the SpiderFoot API."""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/scans'
    resp = cli.request(url)
    if resp:
        try:
            data = cli.json_loads(resp) if hasattr(cli, 'json_loads') else __import__('json').loads(resp)
            scans = data.get('scans', [])
            if not scans:
                cli.dprint("No scans found.")
                return
            cli.dprint("Scans:", plain=True)
            for scan in scans:
                cli.dprint(f"- {scan.get('id', scan)}: {scan.get('name', '')} ({scan.get('status', '')})", plain=True)
        except Exception as e:
            cli.edprint(f"Failed to parse API response: {e}")
    else:
        cli.edprint("No response from API.")

def register(registry):
    registry.register("scans", scans_command, help_text="List all scans using the SpiderFoot API.")
