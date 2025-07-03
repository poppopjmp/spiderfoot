"""
CLI configuration management for SpiderFoot CLI.
"""

class CLIConfig:
    def __init__(self):
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

    def get(self, key, default=None):
        return self.options.get(key, default)

    def set(self, key, value):
        self.options[key] = value

    def as_dict(self):
        return dict(self.options)

    def update(self, d):
        self.options.update(d)

    def __getitem__(self, key):
        return self.options[key]

    def __setitem__(self, key, value):
        self.options[key] = value

    def __contains__(self, key):
        return key in self.options
