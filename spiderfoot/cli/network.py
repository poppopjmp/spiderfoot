"""
Network communication utilities for SpiderFoot CLI.
"""
from __future__ import annotations

import requests

class SpiderFootApiClient:
    """HTTP client for communicating with the SpiderFoot API."""
    def __init__(self, config) -> None:
        self.config = config

    def request(self, url, post=None):
        headers = {
            "User-agent": "SpiderFoot-CLI/" + str(self.config.get('cli.version', '')),
            "Accept": "application/json"
        }
        try:
            if not post:
                r = requests.get(
                    url,
                    headers=headers,
                    verify=self.config.get('cli.ssl_verify', True),
                    auth=requests.auth.HTTPDigestAuth(
                        self.config.get('cli.username', ''),
                        self.config.get('cli.password', '')
                    )
                )
            else:
                r = requests.post(
                    url,
                    headers=headers,
                    verify=self.config.get('cli.ssl_verify', True),
                    auth=requests.auth.HTTPDigestAuth(
                        self.config.get('cli.username', ''),
                        self.config.get('cli.password', '')
                    ),
                    data=post
                )
            if r.status_code == requests.codes.ok:
                return r.text
            r.raise_for_status()
        except Exception as e:
            return None
