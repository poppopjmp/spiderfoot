"""
Export command for SpiderFoot CLI.
"""

def export_command(cli, line):
    """Export data from a scan using the SpiderFoot API."""
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: export <scan_id> [-t format]")
        return
    scan_id = args[0]
    export_format = 'json'
    if '-t' in args:
        idx = args.index('-t')
        if idx + 1 < len(args):
            export_format = args[idx + 1]
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + f'/api/scans/{scan_id}/export?format={export_format}'
    resp = cli.request(url)
    if resp:
        cli.send_output(resp, line, titles=None, total=False, raw=True)
    else:
        cli.dprint("No results.")

def register(registry):
    registry.register("export", export_command, help_text="Export data from a scan using the SpiderFoot API.")
