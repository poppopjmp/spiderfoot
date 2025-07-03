"""
Correlation rules command for SpiderFoot CLI.
"""

def correlationrules_command(cli, line):
    """List all available correlation rules from the API."""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/config/correlationrules'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No correlation rules found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry):
    registry.register("correlationrules", correlationrules_command, help_text="List available correlation rules from the API.")
