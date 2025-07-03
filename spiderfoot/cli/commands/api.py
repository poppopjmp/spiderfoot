"""
API command for SpiderFoot CLI: interact with the API directly.
"""

def api_command(cli, line):
    """
    Usage: api <endpoint> [POST <json_data>]
    Example: api /scans
    Example: api /scan/start POST '{"target": "example.com"}'
    """
    import json
    import shlex
    args = shlex.split(line)
    if not args:
        cli.edprint("Usage: api <endpoint> [POST <json_data>]")
        return
    endpoint = args[0]
    method = "GET"
    data = None
    if len(args) > 1 and args[1].upper() == "POST":
        method = "POST"
        if len(args) > 2:
            try:
                data = json.loads(args[2])
            except Exception as e:
                cli.edprint(f"Invalid JSON for POST data: {e}")
                return
    url = cli.config.get('cli.server_baseurl', 'http://127.0.0.1:5001') + endpoint
    cli.dprint(f"[API] {method} {url}")
    resp = cli.request(url, post=data) if method == "POST" else cli.request(url)
    if resp:
        cli.dprint(resp, plain=True)
    else:
        cli.edprint("No response from API.")

def register(registry):
    registry.register("api", api_command, help_text="Interact with the SpiderFoot API directly. Usage: api <endpoint> [POST <json_data>]")
