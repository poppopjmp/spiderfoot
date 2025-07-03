"""
Summary command for SpiderFoot CLI.
"""

def summary_command(cli, line):
    """Summary of a scan using the API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: summary <scan_id>")
        return
    scan_id = args[0]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}/summary'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No results found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry):
    registry.register("summary", summary_command, help_text="Scan result summary using the API.")
