"""SpiderFoot module: waybackurls - Wayback Machine URL fetcher.

Fetches URLs from the Wayback Machine for a given domain, revealing
historical endpoints, parameters, and application structure.

Requires: waybackurls binary in PATH or configured via waybackurls_path option.
Install: go install -v github.com/tomnomnom/waybackurls@latest
"""

from __future__ import annotations

import os
import subprocess

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_waybackurls(SpiderFootModernPlugin):
    """Fetch historical URLs from Wayback Machine via waybackurls."""

    meta = {
        "name": "Tool - waybackurls",
        "summary": "Fetch historical URLs from the Wayback Machine.",
        "flags": ["tool"],
        "useCases": ["Investigate", "Footprint", "Passive"],
        "categories": ["Search Engines"],
        "toolDetails": {
            "binaryName": "waybackurls",
            "installUrl": "https://github.com/tomnomnom/waybackurls",
        },
        "dataSource": {
            "website": "https://github.com/tomnomnom/waybackurls",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/tomnomnom/waybackurls"],
            "description": "Fetch historical URLs from the Wayback Machine.",
        },
    }

    opts = {
        "waybackurls_path": "",
        "get_versions": False,
        "no_subs": False,
        "max_results": 5000,
        "timeout": 180,
    }

    optdescs = {
        "waybackurls_path": "Path to waybackurls binary. Leave blank to use PATH.",
        "get_versions": "Fetch all archived versions of each URL.",
        "no_subs": "Exclude subdomains from results.",
        "max_results": "Maximum URLs to return.",
        "timeout": "Timeout in seconds.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["DOMAIN_NAME"]

    def producedEvents(self):
        return [
            "LINKED_URL_INTERNAL",
            "LINKED_URL_EXTERNAL",
            "URL_FORM",
            "URL_JAVASCRIPT",
        ]

    def _find_binary(self):
        custom = self.opts.get("waybackurls_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("waybackurls", "waybackurls.exe"):
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate):
                    return candidate
        return None

    def handleEvent(self, event):
        data = event.data
        if self.errorState:
            return
        if data in self.results:
            return
        self.results[data] = True

        binary = self._find_binary()
        if not binary:
            self.error("waybackurls binary not found.")
            self.errorState = True
            return

        cmd = [binary]
        if self.opts["get_versions"]:
            cmd.append("-get-versions")
        if self.opts["no_subs"]:
            cmd.append("-no-subs")

        try:
            proc = subprocess.run(
                cmd, input=data + "\n",
                capture_output=True, text=True,
                timeout=self.opts["timeout"],
            )

            count = 0
            for line in proc.stdout.splitlines():
                if count >= self.opts["max_results"]:
                    break
                url = line.strip()
                if not url or url in self.results:
                    continue
                self.results[url] = True
                count += 1

                url_lower = url.lower()
                if ".js" in url_lower:
                    evt_type = "URL_JAVASCRIPT"
                elif "?" in url_lower:
                    evt_type = "URL_FORM"
                elif data.lower() in url_lower:
                    evt_type = "LINKED_URL_INTERNAL"
                else:
                    evt_type = "LINKED_URL_EXTERNAL"

                evt = self.sf.SpiderFootEvent(
                    evt_type, url, self.__name__, event
                )
                self.notifyListeners(evt)

            self.info(f"waybackurls found {count} URLs for {data}")

        except subprocess.TimeoutExpired:
            self.error(f"waybackurls timed out for {data}")
        except Exception as e:
            self.error(f"waybackurls error: {e}")
