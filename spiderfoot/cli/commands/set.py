"""
Set command for SpiderFoot CLI.
"""

def set_command(cli, line):
    """Set a configuration variable in SpiderFoot."""
    c = cli.myparseline(line, replace=False)
    cfg = None
    val = None
    if len(c[0]) > 0:
        cfg = c[0][0]
    if len(c[0]) > 2:
        try:
            val = c[0][2]
        except Exception:
            cli.edprint("Invalid syntax.")
            return
    # Local CLI config
    if cfg and val:
        if cfg.startswith('$'):
            cli.config[cfg] = val
            cli.dprint(f"{cfg} set to {val}")
            return
        if cfg in cli.config:
            if isinstance(cli.config[cfg], bool):
                if val.lower() == "false" or val == "0":
                    val = False
                else:
                    val = True
            cli.config[cfg] = val
            cli.dprint(f"{cfg} set to {val}")
            return
    # Get the server-side config
    d = cli.request(cli.config['cli.server_baseurl'] + "/optsraw")
    if not d:
        cli.edprint("Unable to obtain SpiderFoot server-side config.")
        return
    j = __import__('json').loads(d)
    if j[0] == "ERROR":
        cli.edprint("Error fetching SpiderFoot server-side config.")
        return
    serverconfig = j[1]['data']
    token = j[1]['token']
    # Printing current config, not setting a value
    if not cfg or not val:
        ks = list(cli.config.keys())
        ks.sort()
        output = list()
        for k in ks:
            cval = cli.config[k]
            if isinstance(cval, bool):
                cval = str(cval)
            if not cfg:
                output.append({'opt': k, 'val': cval})
                continue
            if cfg == k:
                cli.dprint(f"{k} = {cval}", plain=True)
        for k in sorted(serverconfig.keys()):
            if isinstance(serverconfig[k], list):
                serverconfig[k] = ','.join(serverconfig[k])
            if not cfg:
                output.append({'opt': k, 'val': str(serverconfig[k])})
                continue
            if cfg == k:
                cli.dprint(f"{k} = {serverconfig[k]}", plain=True)
        if len(output) > 0:
            cli.send_output(
                __import__('json').dumps(output),
                line,
                {'opt': "Option", 'val': "Value"},
                total=False
            )
        return
    if val:
        # submit all non-CLI vars to the SF server
        confdata = dict()
        found = False
        for k in serverconfig:
            if k == cfg:
                serverconfig[k] = val
                if isinstance(val, str):
                    if val.lower() == "true":
                        serverconfig[k] = "1"
                    if val.lower() == "false":
                        serverconfig[k] = "0"
                found = True
        if not found:
            cli.edprint("Variable not found, so not set.")
            return
        # Sanitize the data before sending it to the server
        for k in serverconfig:
            optstr = ":".join(k.split(".")[1:])
            if isinstance(serverconfig[k], bool):
                confdata[optstr] = "1" if serverconfig[k] else "0"
            if isinstance(serverconfig[k], list):
                confdata[optstr] = ','.join(serverconfig[k])
            if isinstance(serverconfig[k], int):
                confdata[optstr] = str(serverconfig[k])
            if isinstance(serverconfig[k], str):
                confdata[optstr] = serverconfig[k]
        d = cli.request(
            cli.config['cli.server_baseurl'] + "/savesettingsraw",
            post={'token': token, 'allopts': __import__('json').dumps(confdata)}
        )
        if not d:
            cli.edprint("Unable to set SpiderFoot server-side config.")
            return
        j = __import__('json').loads(d)
        if j[0] == "ERROR":
            cli.edprint(f"Error setting SpiderFoot server-side config: {j[1]}")
            return
        cli.dprint(f"{cfg} set to {val}")
        return
    if cfg not in cli.config:
        cli.edprint(
            "Variable not found, so not set. Did you mean to use a $ variable?")
        return

def register(registry):
    registry.register("set", set_command, help_text="Set variables and configuration settings.")
