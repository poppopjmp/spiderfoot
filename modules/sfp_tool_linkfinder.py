"""SpiderFoot module: linkfinder - JavaScript endpoint extractor.

Integrates LinkFinder to discover API endpoints, relative URLs,
and paths embedded in JavaScript files.

Requires: linkfinder in PATH (pip install linkfinder).
"""

from __future__ import annotations

import os
import re
import subprocess

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_linkfinder(SpiderFootModernPlugin):
    """JavaScript endpoint extraction via LinkFinder."""

    meta = {
        "name": "Tool - LinkFinder",
        "summary": "Extract API endpoints and paths from JavaScript files.",
        "flags": ["tool"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "linkfinder",
            "installUrl": "https://github.com/GerbenJavado/LinkFinder",
        },
        "dataSource": {
            "website": "https://github.com/GerbenJav);avado/LinkFinder",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/GerbenJavado/LinkFinder"],
            "description": "JavaScript endpoint and API path extractor.",
        },
    }

    opts = {
        "linkfinder_path": "",
        "timeout": 60,
        "max_targets": 100,
    }

    optdescs = {
        "linkfinder_path": "Path to linkfinder script. Leave blank to use PATH.",
        "timeout": "Timeout in seconds per JS file.",
        "max_targets": "Maximum number of JS files to scan.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["URL_JAVASCRIPT"]

    def producedEvents(self):
        return [
            "LINKED_URL_INTERNAL",
            "LINKED_URL_EXTERNAL",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("linkfinder_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("linkfinder", "linkfinder.py"):
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate):
                    return candidate
        for fallback in (
            "/opt/venv/bin/linkfinder",
            "/usr/local/bin/linkfinder",
            "/opt/tools/LinkFinder/linkfinder.py",
        ):
            if os.path.isfile(fallback):
                return fallback
        return None

    def _extract_domain(self, url):
        """Get the domain from a URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.hostname or ""
        except Exception:
            return ""

    def _is_internal(self, found_url, source_domain):
        """Check if found URL belongs to the same domain."""
        if found_url.startswith("/") and not found_url.startswith("//"):
            return True
        found_domain = self._extract_domain(found_url)
        if not found_domain:
            return True  # Relative paths are internal
        return found_domain == source_domain or found_domain.endswith(f".{source_domain}")

    def handleEvent(self, event):
        data = event.data
        if self.errorState:
            return
        if data in self.results:
            return
        self.results[data] = True

        if sum(1 for v in self.results.values() if v) > self.opts["max_targets"]:
            return

        binary = self._find_binary()
        if not binary:
            self.error("linkfinder not found. Install: pip install linkfinder")
            self.errorState = True
            return

        source_domain = self._extract_domain(data)

        # Determine if binary is a Python script
        if binary.endswith(".py"):
            cmd = ["python3", binary, "-i", data, "-o", "cli"]
        else:
            cmd = [binary, "-i", data, "-o", "cli"]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"],
            )

            if proc.returncode != 0 and not proc.stdout:
                self.debug(f"linkfinder returned no output for {data}")
                return

            endpoint_count = 0
            seen = set()

            for line in (proc.stdout or "").splitlines():
                if self.checkForStop():
                    return
                line = line.strip()
                if not line:
                    continue
                # Skip linkfinder banner/info lines
                if line.startswith("[") or line.startswith("Running") or line.startswith("Usage"):
                    continue

                # Clean the endpoint
                endpoint = line.strip()

                # Skip obvious non-endpoints
                if len(endpoint) < 2 or endpoint in seen:
                    continue
                if endpoint in (".", "..", "/"):
                    continue
                seen.add(endpoint)

                # Resolve relative URLs to full URLs
                if endpoint.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(data)
                    full_url = f"{parsed.scheme}://{parsed.netloc}{endpoint}"
                elif endpoint.startswith("http"):
                    full_url = endpoint
                else:
                    # Skip non-URL strings (variable names, etc.)
                    if not re.match(r'^[a-zA-Z0-9/._\-?&=]+$', endpoint):
                        continue
                    from urllib.parse import urlparse
                    parsed = urlparse(data)
                    full_url = f"{parsed.scheme}://{parsed.netloc}/{endpoint}"

                if self._is_internal(full_url, source_domain):
                    evt = self.sf.SpiderFootEvent(
                        "LINKED_URL_INTERNAL", full_url, self.__name__, event
                    )
                else:
                    evt = self.sf.SpiderFootEvent(
                        "LINKED_URL_EXTERNAL", full_url, self.__name__, event
                    )
                self.notifyListeners(evt)
                endpoint_count += 1

            self.info(f"linkfinder found {endpoint_count} endpoints in {data}")

        except subprocess.TimeoutExpired:
            self.error(f"linkfinder timed out for {data}")
        except Exception as e:
            self.error(f"linkfinder error: {e}")
