"""
CLI configuration management for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import Any


class CLIConfig:
    """Configuration store for SpiderFoot CLI options."""
    def __init__(self) -> None:
        """Initialize the CLIConfig."""
        self.options = {
            "cli.debug": False,
            "cli.silent": False,
            "cli.color": True,
            "cli.output": "pretty",
            "cli.history": True,
            "cli.history_file": "",
            "cli.spool": False,
            "cli.spool_file": "",
            "cli.ssl_verify": True,
            "cli.username": "",
            "cli.password": "",
            "cli.server_baseurl": "http://127.0.0.1:8001"
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for the given config key, or default."""
        return self.options.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration option by key."""
        self.options[key] = value

    def as_dict(self) -> dict:
        """Return a dictionary copy of all configuration options."""
        return dict(self.options)

    def update(self, d: dict) -> None:
        """Update configuration options from a dictionary."""
        self.options.update(d)

    def __getitem__(self, key: str) -> Any:
        """Return the value for the given config key."""
        return self.options[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a configuration option by key."""
        self.options[key] = value

    def __contains__(self, key: str) -> bool:
        """Return True if the key exists in configuration."""
        return key in self.options
