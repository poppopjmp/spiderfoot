"""
Stop command for SpiderFoot CLI.
"""

from __future__ import annotations


def stop_command(cli, line) -> None:
    """Stop a running scan using the SpiderFoot API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: stop <scan_id>")
        return
    scan_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}/stop'
    resp = cli.request(url, post={})
    if resp:
        cli.dprint(f"Requested scan {scan_id} to stop.")
    else:
        cli.edprint("No response from API.")

def register(registry) -> None:
    registry.register("stop", stop_command, help_text="Stop a scan using the SpiderFoot API.")
