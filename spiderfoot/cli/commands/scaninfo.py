"""
Scaninfo command for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sfcli import SpiderFootCli
    from spiderfoot.cli.commands.commands import CommandRegistry


def scaninfo_command(cli: SpiderFootCli, line: str) -> None:
    """Get scan info and config from the API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: scaninfo <scan_id>")
        return
    scan_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}'
    resp = cli.request(url)
    if not resp:
        cli.edprint("No response from API.")
        return
    try:
        data = cli.json_loads(resp) if hasattr(cli, 'json_loads') else __import__('json').loads(resp)
        out = [
            f"Name: {data.get('name', '')}",
            f"ID: {data.get('id', scan_id)}",
            f"Target: {data.get('target', '')}",
            f"Created: {data.get('created', '')}",
            f"Started: {data.get('started', '')}",
            f"Ended: {data.get('ended', '')}",
            f"Status: {data.get('status', '')}"
        ]
        cli.send_output("\n".join(out), line, total=False, raw=True)
    except Exception as e:
        cli.edprint(f"Failed to parse API response: {e}")

def register(registry: CommandRegistry) -> None:
    registry.register("scaninfo", scaninfo_command, help_text="Scan information from the API.")
