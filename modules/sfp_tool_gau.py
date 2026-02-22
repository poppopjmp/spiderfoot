"""SpiderFoot module: gau - Fetch known URLs from web archives.

Integrates gau (Get All URLs) for discovering historic and current URLs
from AlienVault OTX, Wayback Machine, Common Crawl, and URLScan.io.

Requires: gau binary in PATH or configured via gau_path option.
Install: go install -v github.com/lc/gau/v2/cmd/gau@latest
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_gau(SpiderFootAsyncPlugin):
    """Fetch known URLs from web archives via gau."""

    meta = {
        "name": "Tool - gau",
        "summary": "Discover known URLs from web archives (Wayback, CommonCrawl, OTX, URLScan).",
        "flags": ["tool"],
        "useCases": ["Investigate", "Footprint", "Passive"],
        "categories": ["Search Engines"],
        "toolDetails": {
            "binaryName": "gau",
            "installUrl": "https://github.com/lc/gau",
        },
        "dataSource": {
            "website": "https://github.com/lc/gau",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/lc/gau"],
            "description": "Get All URLs tool fetching known URLs from web archives.",
        },
    }

    opts = {
        "gau_path": "",
        "threads": 5,
        "providers": "wayback,commoncrawl,otx,urlscan",
        "blacklist_extensions": "png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot,css",
        "fetch_subs": True,
        "max_results": 5000,
        "timeout": 300,
    }

    optdescs = {
        "gau_path": "Path to gau binary. Leave blank to use PATH.",
        "threads": "Number of concurrent threads.",
        "providers": "Comma-separated providers: wayback,commoncrawl,otx,urlscan.",
        "blacklist_extensions": "File extensions to exclude (comma-separated).",
        "fetch_subs": "Include subdomains in results.",
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
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("gau_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("gau", "gau.exe"):
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate):
                    return candidate
        return None

    def _classify_url(self, url, domain):
        """Classify URL and return appropriate event type."""
        url_lower = url.lower()
        if ".js" in url_lower or "javascript" in url_lower:
            return "URL_JAVASCRIPT"
        if any(x in url_lower for x in ("?", "form", "login", "signup", "register")):
            return "URL_FORM"
        if domain.lower() in url_lower:
            return "LINKED_URL_INTERNAL"
        return "LINKED_URL_EXTERNAL"

    def handleEvent(self, event):
        data = event.data
        if self.errorState:
            return
        if data in self.results:
            return
        self.results[data] = True

        binary = self._find_binary()
        if not binary:
            self.error("gau binary not found.")
            self.errorState = True
            return

        output_path = tempfile.mktemp(suffix=".txt")

        cmd = [
            binary,
            "--threads", str(self.opts["threads"]),
            "--providers", self.opts["providers"],
            "-o", output_path,
        ]

        if self.opts["blacklist_extensions"]:
            cmd.extend(["--blacklist", self.opts["blacklist_extensions"]])
        if self.opts["fetch_subs"]:
            cmd.append("--subs")

        cmd.append(data)

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"],
            )

            count = 0
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    for line in f:
                        if count >= self.opts["max_results"]:
                            break
                        url = line.strip()
                        if not url or url in self.results:
                            continue
                        self.results[url] = True
                        count += 1

                        evt_type = self._classify_url(url, data)
                        evt = self.sf.SpiderFootEvent(
                            evt_type, url, self.__name__, event
                        )
                        self.notifyListeners(evt)

            self.info(f"gau found {count} URLs for {data}")

        except subprocess.TimeoutExpired:
            self.error(f"gau timed out for {data}")
        except Exception as e:
            self.error(f"gau error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
