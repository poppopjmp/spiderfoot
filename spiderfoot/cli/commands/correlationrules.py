"""
Correlation rules command for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sfcli import SpiderFootCli
    from spiderfoot.cli.commands.commands import CommandRegistry


def correlationrules_command(cli: SpiderFootCli, line: str) -> None:
    """List all available correlation rules from the API."""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/config/correlationrules'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No correlation rules found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry: CommandRegistry) -> None:
    """Register the correlationrules command with the CLI registry."""
    registry.register(
        help_text="List available correlation rules from the API.",
    )
