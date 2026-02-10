"""
CLI configuration management for SpiderFoot CLI.
"""

from __future__ import annotations

from typing import Any


class CLIConfig:
    """Configuration store for SpiderFoot CLI options."""
    def __init__(self) -> None:
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
        return self.options.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.options[key] = value

    def as_dict(self) -> dict:
        return dict(self.options)

    def update(self, d: dict) -> None:
        self.options.update(d)

    def __getitem__(self, key: str) -> Any:
        return self.options[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.options[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.options
