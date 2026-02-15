"""
Ping command for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sfcli import SpiderFootCli
    from spiderfoot.cli.commands.commands import CommandRegistry


def ping_command(cli: SpiderFootCli, line: str) -> None:
    """Ping the SpiderFoot API server."""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/health'
    resp = cli.request(url)
    if resp:
        try:
            data = cli.json_loads(resp) if hasattr(cli, 'json_loads') else __import__('json').loads(resp)
            if data.get('status') == 'ok':
                cli.dprint(f"API server is healthy. Version: {data.get('version')}")
            else:
                cli.edprint("API health check failed.")
        except Exception as e:
            cli.edprint(f"Failed to parse API response: {e}")
    else:
        cli.edprint("No response from API.")

def register(registry: CommandRegistry) -> None:
    """Register the ping command with the CLI registry."""
    registry.register("ping", ping_command, help_text="Test connectivity to the SpiderFoot API server.")
