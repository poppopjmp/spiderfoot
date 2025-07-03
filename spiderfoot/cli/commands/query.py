"""
Query command for SpiderFoot CLI.
"""

def query_command(cli, line):
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

def register(registry):
    registry.register("query", query_command, help_text="Run SQL against the SpiderFoot API (if enabled).")
