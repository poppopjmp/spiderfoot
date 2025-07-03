"""
Help command for SpiderFoot CLI.
"""

def help_command(cli, line):
    """Show help for all commands or a specific command."""
    c = cli.myparseline(line)
    if len(c[0]) == 0:
        # Show all commands
        helpmap = []
        for name in sorted(cli.registry.all_commands()):
            entry = cli.registry.get(name)
            helpmap.append([name, entry.get('help', '')])
        cli.send_output(
            __import__('json').dumps(helpmap),
            "",
            titles={"0": "Command", "1": "Description"},
            total=False
        )
    else:
        cmd = c[0][0]
        entry = cli.registry.get(cmd)
        if entry:
            cli.dprint(f"{cmd}: {entry.get('help', '')}", plain=True)
        else:
            cli.edprint(f"No help found for command '{cmd}'")

def register(registry):
    registry.register("help", help_command, help_text="This help output.")
