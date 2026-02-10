"""
Command registry and base command logic for SpiderFoot CLI.
"""

from __future__ import annotations

import importlib
import pkgutil
import os
import sys
from typing import Any


class CommandRegistry:
    """Registry for CLI command handlers."""
    def __init__(self) -> None:
        self.commands = {}

    def register(self, name, func, help_text=None) -> None:
        self.commands[name] = {'func': func, 'help': help_text}

    def get(self, name) -> dict | None:
        return self.commands.get(name)

    def all_commands(self) -> Any:
        return self.commands.keys()

    def help(self, name) -> str:
        cmd = self.get(name)
        if cmd:
            return cmd.get('help', '')
        return ''

class BaseCommand:
    """
    Optional base class for CLI commands.
    """
    def __init__(self, cli) -> None:
        self.cli = cli
    def run(self, *args, **kwargs) -> None:
        raise NotImplementedError("Command must implement run()")

def load_all_commands(registry, commands_pkg="spiderfoot.cli.commands") -> None:
    """
    Dynamically import and register all command modules in the commands package.
    Each command module must define a 'register' function.
    Handles both package and module import contexts.
    Skips non-command files (banner, output, config, __init__, commands, history, network).
    """
    skip_modules = {"__init__", "commands", "banner", "output", "config", "history", "network"}
    try:
        package = importlib.import_module(commands_pkg)
        if hasattr(package, "__path__"):
            package_path = package.__path__[0]
        else:
            package_path = os.path.dirname(os.path.abspath(__file__))
        for _, name, is_pkg in pkgutil.iter_modules([package_path]):
            if is_pkg or name in skip_modules:
                continue
            mod = importlib.import_module(f"{commands_pkg}.{name}")
            if hasattr(mod, "register"):
                mod.register(registry)
    except Exception as e:
        print(f"[ERROR] Could not load CLI commands: {e}", file=sys.stderr)
