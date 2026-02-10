"""
Query command for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sfcli import SpiderFootCli
    from spiderfoot.cli.commands.commands import CommandRegistry


def query_command(cli: SpiderFootCli, line: str) -> None:
    """Run SQL against the SpiderFoot API (if enabled)."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: query <SQL>")
        return
    query = ' '.join(args)
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/query'
    resp = cli.request(url, post={"query": query})
    if not resp:
        cli.dprint("No results.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry: CommandRegistry) -> None:
    """Register the query command with the CLI registry."""
    registry.register("query", query_command, help_text="Run SQL against the SpiderFoot API (if enabled).")
