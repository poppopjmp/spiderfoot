"""
Types command for SpiderFoot CLI.
"""

def types_command(cli, line):
    """List all available element types from the API."""
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + '/api/config/event-types'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No types found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry):
    registry.register("types", types_command, help_text="List available data types from the API.")
