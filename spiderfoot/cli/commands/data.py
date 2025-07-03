"""
Data command for SpiderFoot CLI.
"""

def data_command(cli, line):
    """Show the data from a scan using the API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: data <scan_id> [-t event_type]")
        return
    scan_id = args[0]
    event_type = None
    if '-t' in args:
        idx = args.index('-t')
        if idx + 1 < len(args):
            event_type = args[idx + 1]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}/events'
    if event_type:
        url += f'?event_types={event_type}'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No results.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry):
    registry.register("data", data_command, help_text="Show data from a scan's results using the API.")
