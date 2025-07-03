"""
Find command for SpiderFoot CLI.
"""

def find_command(cli, line):
    """Search for data in scan events using the API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: find <scan_id> <value> [-t event_type]")
        return
    scan_id = args[0]
    value = args[1] if len(args) > 1 else None
    event_type = None
    if '-t' in args:
        idx = args.index('-t')
        if idx + 1 < len(args):
            event_type = args[idx + 1]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}/events?value={value}'
    if event_type:
        url += f'&event_types={event_type}'
    resp = cli.request(url)
    if not resp:
        cli.dprint("No results found.")
        return
    cli.send_output(resp, line, titles=None, total=True, raw=True)

def register(registry):
    registry.register("find", find_command, help_text="Search for data within scan results using the API.")
