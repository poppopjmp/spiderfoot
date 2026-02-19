"""SpiderFoot module: gospider - Fast web spidering.

Integrates gospider for crawling websites to discover links, subdomains,
JavaScript files, forms, and other endpoints.

Requires: gospider binary in PATH or configured via gospider_path option.
Install: go install -v github.com/jaeles-project/gospider@latest
"""

from __future__ import annotations

import os
import re
import subprocess

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_gospider(SpiderFootModernPlugin):
    """Fast web spidering and link discovery via gospider."""

    meta = {
        "name": "Tool - gospider",
        "summary": "Fast web spidering for links, JS files, and subdomains.",
        "flags": ["tool", "slow", "invasive"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "gospider",
            "installUrl": "https://github.com/jaeles-project/gospider",
        },
        "dataSource": {
            "website": "https://github.com/jaeles-project/gospider",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/jaeles-project/gospider"],
            "description": "Fast web spider for link and JavaScript discovery.",
        },
    }

    opts = {
        "gospider_path": "",
        "depth": 2,
        "concurrent": 5,
        "threads": 5,
        "timeout": 10,
        "include_subs": True,
        "include_other_sources": True,
        "user_agent": "",
        "max_results": 3000,
        "run_timeout": 300,
    }

    optdescs = {
        "gospider_path": "Path to gospider binary. Leave blank to use PATH.",
        "depth": "Maximum crawl depth.",
        "concurrent": "Number of concurrent sites to crawl.",
        "threads": "Threads per site.",
        "timeout": "Request timeout in seconds.",
        "include_subs": "Include subdomains in crawl.",
        "include_other_sources": "Include 3rd-party sources (Wayback, CommonCrawl).",
        "user_agent": "Custom User-Agent string (blank=default).",
        "max_results": "Maximum results to process.",
        "run_timeout": "Total run timeout in seconds.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["DOMAIN_NAME", "LINKED_URL_INTERNAL"]

    def producedEvents(self):
        return [
            "LINKED_URL_INTERNAL",
            "LINKED_URL_EXTERNAL",
            "URL_JAVASCRIPT",
            "URL_FORM",
            "INTERNET_NAME",
            "EMAILADDR",
        ]

    def _find_binary(self):
        custom = self.opts.get("gospider_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("gospider", "gospider.exe"):
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
            self.error("gospider binary not found.")
            self.errorState = True
            return

        # Build target URL
        if event.eventType == "DOMAIN_NAME":
            target = f"https://{data}"
        else:
            target = data

        cmd = [
            binary,
            "-s", target,
            "-d", str(self.opts["depth"]),
            "-c", str(self.opts["concurrent"]),
            "-t", str(self.opts["threads"]),
            "--timeout", str(self.opts["timeout"]),
            "--no-redirect",
            "-q",  # quiet
        ]

        if self.opts["include_subs"]:
            cmd.append("--include-subs")
        if self.opts["include_other_sources"]:
            cmd.append("--include-other-source")
        if self.opts["user_agent"]:
            cmd.extend(["-u", self.opts["user_agent"]])

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["run_timeout"],
            )

            # Extract the domain for classification
            domain = data.lower() if event.eventType == "DOMAIN_NAME" else ""
            email_re = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

            count = 0
            for line in proc.stdout.splitlines():
                if count >= self.opts["max_results"]:
                    break
                line = line.strip()
                if not line:
                    continue

                # gospider output format: [source] - URL
                # or [source] - [tag] - URL
                parts = line.split(" - ", maxsplit=2)
                url = parts[-1].strip() if parts else line

                if not url.startswith("http"):
                    # Check for emails
                    for email in email_re.findall(url):
                        if email not in self.results:
                            self.results[email] = True
                            evt = self.sf.SpiderFootEvent(
                                "EMAILADDR", email, self.__name__, event
                            )
                            self.notifyListeners(evt)
                    continue

                if url in self.results:
                    continue
                self.results[url] = True
                count += 1

                url_lower = url.lower()
                if url_lower.endswith(".js") or "/js/" in url_lower:
                    evt_type = "URL_JAVASCRIPT"
                elif "?" in url and any(x in url_lower for x in ("login", "form", "search", "register")):
                    evt_type = "URL_FORM"
                elif domain and domain in url_lower:
                    evt_type = "LINKED_URL_INTERNAL"
                else:
                    evt_type = "LINKED_URL_EXTERNAL"

                evt = self.sf.SpiderFootEvent(
                    evt_type, url, self.__name__, event
                )
                self.notifyListeners(evt)

            self.info(f"gospider found {count} URLs from {target}")

        except subprocess.TimeoutExpired:
            self.error(f"gospider timed out for {target}")
        except Exception as e:
            self.error(f"gospider error: {e}")
