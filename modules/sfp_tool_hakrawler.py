"""SpiderFoot module: hakrawler - Simple, fast web crawler.

Integrates hakrawler for lightweight crawling that discovers
URLs, JavaScript files, and forms from web applications.

Requires: hakrawler binary in PATH or configured via hakrawler_path option.
Install: go install -v github.com/hakluke/hakrawler@latest
"""

import os
import subprocess

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_hakrawler(SpiderFootModernPlugin):
    """Simple web crawling and endpoint discovery via hakrawler."""

    meta = {
        "name": "Tool - hakrawler",
        "summary": "Simple, fast web crawler for URL and endpoint discovery.",
        "flags": ["tool", "slow", "invasive"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "hakrawler",
            "installUrl": "https://github.com/hakluke/hakrawler",
        },
    }

    opts = {
        "hakrawler_path": "",
        "depth": 2,
        "include_subs": True,
        "insecure": False,
        "timeout": 10,
        "max_results": 2000,
        "run_timeout": 180,
    }

    optdescs = {
        "hakrawler_path": "Path to hakrawler binary. Leave blank to use PATH.",
        "depth": "Maximum crawl depth.",
        "include_subs": "Include subdomains.",
        "insecure": "Skip TLS verification.",
        "timeout": "Request timeout in seconds.",
        "max_results": "Maximum URLs to return.",
        "run_timeout": "Total run timeout in seconds.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        self.sf = sfc
        self.results = self.tempStorage()
        if userOpts:
            for opt in list(self.opts.keys()):
                self.opts[opt] = userOpts.get(opt, self.opts[opt])

    def watchedEvents(self):
        return ["DOMAIN_NAME", "LINKED_URL_INTERNAL"]

    def producedEvents(self):
        return [
            "LINKED_URL_INTERNAL",
            "LINKED_URL_EXTERNAL",
            "URL_JAVASCRIPT",
            "URL_FORM",
        ]

    def _find_binary(self):
        custom = self.opts.get("hakrawler_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("hakrawler", "hakrawler.exe"):
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
            self.error("hakrawler binary not found.")
            self.errorState = True
            return

        target = data if data.startswith("http") else f"https://{data}"

        cmd = [
            binary,
            "-d", str(self.opts["depth"]),
            "-t", str(self.opts["timeout"]),
        ]
        if self.opts["include_subs"]:
            cmd.append("-subs")
        if self.opts["insecure"]:
            cmd.append("-insecure")

        try:
            proc = subprocess.run(
                cmd, input=target + "\n",
                capture_output=True, text=True,
                timeout=self.opts["run_timeout"],
            )

            domain = data.lower() if not data.startswith("http") else ""
            count = 0
            for line in proc.stdout.splitlines():
                if count >= self.opts["max_results"]:
                    break
                url = line.strip()
                if not url or not url.startswith("http") or url in self.results:
                    continue
                self.results[url] = True
                count += 1

                url_lower = url.lower()
                if url_lower.endswith(".js"):
                    evt_type = "URL_JAVASCRIPT"
                elif "?" in url and any(x in url_lower for x in ("form", "login", "search")):
                    evt_type = "URL_FORM"
                elif domain and domain in url_lower:
                    evt_type = "LINKED_URL_INTERNAL"
                else:
                    evt_type = "LINKED_URL_EXTERNAL"

                evt = self.sf.SpiderFootEvent(
                    evt_type, url, self.__name__, event
                )
                self.notifyListeners(evt)

            self.info(f"hakrawler found {count} URLs from {target}")

        except subprocess.TimeoutExpired:
            self.error(f"hakrawler timed out for {target}")
        except Exception as e:
            self.error(f"hakrawler error: {e}")
