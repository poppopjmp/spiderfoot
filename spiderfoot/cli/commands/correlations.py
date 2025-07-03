"""
Correlations command for SpiderFoot CLI.
"""

def correlations_command(cli, line):
    """Show the correlation results from a scan using the API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: correlations <scan_id>")
        return
    scan_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}/correlations'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No results.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry):
    registry.register("correlations", correlations_command, help_text="Show correlation results from a scan using the API.")
