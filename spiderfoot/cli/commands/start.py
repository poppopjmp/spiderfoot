"""
Start command for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sfcli import SpiderFootCli
    from spiderfoot.cli.commands.commands import CommandRegistry


def start_command(cli: SpiderFootCli, line: str) -> None:
    """Start a new scan using the SpiderFoot API."""
    import shlex, json
    args = shlex.split(line)
    if len(args) < 2:
        cli.edprint("Usage: start <name> <target> [modules...]")
        return
    name, target, *modules = args
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/scans'
    payload = {
        "name": name,
        "target": target,
        "modules": modules if modules else None
    }
    resp = cli.request(url, post=payload)
    if resp:
        try:
            data = cli.json_loads(resp) if hasattr(cli, 'json_loads') else __import__('json').loads(resp)
            cli.dprint(f"Scan started: {data.get('id', '')} ({data.get('status', '')})")
        except Exception as e:
            cli.edprint(f"Failed to parse API response: {e}")
    else:
        cli.edprint("No response from API.")

def register(registry: CommandRegistry) -> None:
    registry.register("start", start_command, help_text="Start a new scan using the SpiderFoot API.")
