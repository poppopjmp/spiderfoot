"""
Types command for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sfcli import SpiderFootCli
    from spiderfoot.cli.commands.commands import CommandRegistry


def types_command(cli: SpiderFootCli, line: str) -> None:
    """List all available element types from the API."""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/config/event-types'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No types found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry: CommandRegistry) -> None:
    registry.register("types", types_command, help_text="List available data types from the API.")
