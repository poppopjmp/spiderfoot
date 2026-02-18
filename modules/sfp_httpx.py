"""SpiderFoot module: httpx - HTTP probing and technology detection.

Integrates ProjectDiscovery's httpx for fast HTTP probing, technology
fingerprinting, and web server analysis of discovered hosts.

Requires: httpx binary in PATH or configured via httpx_path option.
Install: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from spiderfoot import SpiderFootModernPlugin


class sfp_httpx(SpiderFootModernPlugin):
    """HTTP probing and technology detection via httpx."""

    meta = {
        "name": "Tool - httpx",
        "summary": "HTTP probing and technology detection using ProjectDiscovery httpx.",
        "flags": ["tool", "slow"],
        "useCases": ["Investigate", "Footprint", "Passive"],
        "categories": ["Content Analysis"],
        "toolDetails": {
            "binaryName": "httpx",
            "installUrl": "https://github.com/projectdiscovery/httpx",
        },
        "dataSource": {
            "website": "https://github.com/projectdiscovery/httpx",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/projectdiscovery/httpx"],
            "description": "Fast HTTP probing and technology detection tool by ProjectDiscovery.",
        },
    }

    opts = {
        "httpx_path": "",
        "threads": 25,
        "timeout": 10,
        "follow_redirects": True,
        "tech_detect": True,
        "status_code": True,
        "content_length": True,
        "title": True,
        "web_server": True,
        "cdn_check": True,
        "tls_grab": True,
        "method": "GET",
        "ports": "80,443,8080,8443",
        "rate_limit": 150,
        "max_hosts": 500,
    }

    optdescs = {
        "httpx_path": "Path to httpx binary. Leave blank to use PATH.",
        "threads": "Number of concurrent threads.",
        "timeout": "Timeout in seconds per request.",
        "follow_redirects": "Follow HTTP redirects.",
        "tech_detect": "Enable technology detection (Wappalyzer signatures).",
        "status_code": "Extract HTTP status codes.",
        "content_length": "Extract content length.",
        "title": "Extract page titles.",
        "web_server": "Extract web server headers.",
        "cdn_check": "Check if host is behind a CDN.",
        "tls_grab": "Grab TLS certificate information.",
        "method": "HTTP method to use.",
        "ports": "Ports to probe (comma-separated).",
        "rate_limit": "Maximum requests per second.",
        "max_hosts": "Maximum number of hosts to probe.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return [
            "INTERNET_NAME",
            "DOMAIN_NAME",
            "IP_ADDRESS",
            "LINKED_URL_INTERNAL",
        ]

    def producedEvents(self):
        return [
            "WEBSERVER_BANNER",
            "WEBSERVER_HTTPHEADERS",
            "WEBSERVER_TECHNOLOGY",
            "HTTP_CODE",
            "RAW_RIR_DATA",
            "URL_WEB",
            "TCP_PORT_OPEN",
            "LINKED_URL_INTERNAL",
            "SSL_CERTIFICATE_RAW",
            "CDN_DETECTED",
        ]

    def _find_httpx(self) -> str | None:
        """Find the httpx binary."""
        custom = self.opts.get("httpx_path", "")
        if custom and os.path.isfile(custom):
            return custom

        # Try PATH
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "httpx")
            if os.path.isfile(candidate):
                return candidate
            candidate_exe = candidate + ".exe"
            if os.path.isfile(candidate_exe):
                return candidate_exe

        return None

    def _build_cmd(self, httpx_path: str, input_file: str, output_file: str) -> list[str]:
        """Build httpx command line."""
        cmd = [
            httpx_path,
            "-l", input_file,
            "-o", output_file,
            "-json",
            "-silent",
            "-threads", str(self.opts["threads"]),
            "-timeout", str(self.opts["timeout"]),
            "-rate-limit", str(self.opts["rate_limit"]),
            "-method", self.opts["method"],
        ]

        if self.opts["ports"]:
            cmd.extend(["-ports", self.opts["ports"]])
        if self.opts["follow_redirects"]:
            cmd.append("-follow-redirects")
        if self.opts["tech_detect"]:
            cmd.append("-tech-detect")
        if self.opts["status_code"]:
            cmd.append("-status-code")
        if self.opts["content_length"]:
            cmd.append("-content-length")
        if self.opts["title"]:
            cmd.append("-title")
        if self.opts["web_server"]:
            cmd.append("-web-server")
        if self.opts["cdn_check"]:
            cmd.append("-cdn")
        if self.opts["tls_grab"]:
            cmd.append("-tls-grab")

        return cmd

    def _parse_result(self, line: str, parent_event: Any) -> None:
        """Parse a single httpx JSON result line."""
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            return

        url = result.get("url", "")
        host = result.get("host", "")
        status_code = result.get("status_code")
        title = result.get("title", "")
        web_server = result.get("webserver", "")
        technologies = result.get("tech", [])
        cdn = result.get("cdn", False)
        cdn_name = result.get("cdn_name", "")
        port = result.get("port", "")
        tls = result.get("tls", {})

        # URL
        if url:
            evt = self.sf.SpiderFootEvent("URL_WEB", url, self.__name__, parent_event)
            self.notifyListeners(evt)

        # HTTP status code
        if status_code:
            data = f"{url} [{status_code}]"
            if title:
                data += f" [{title}]"
            evt = self.sf.SpiderFootEvent("HTTP_CODE", data, self.__name__, parent_event)
            self.notifyListeners(evt)

        # Web server
        if web_server:
            evt = self.sf.SpiderFootEvent(
                "WEBSERVER_BANNER", f"{host}: {web_server}", self.__name__, parent_event
            )
            self.notifyListeners(evt)

        # Technologies
        if technologies:
            for tech in technologies:
                evt = self.sf.SpiderFootEvent(
                    "WEBSERVER_TECHNOLOGY", f"{host}: {tech}", self.__name__, parent_event
                )
                self.notifyListeners(evt)

        # Open port
        if port:
            evt = self.sf.SpiderFootEvent(
                "TCP_PORT_OPEN", f"{host}:{port}", self.__name__, parent_event
            )
            self.notifyListeners(evt)

        # CDN detection
        if cdn and cdn_name:
            evt = self.sf.SpiderFootEvent(
                "CDN_DETECTED", f"{host}: {cdn_name}", self.__name__, parent_event
            )
            self.notifyListeners(evt)

        # TLS certificate info
        if tls and tls.get("subject_dn"):
            tls_data = json.dumps(tls, indent=2)
            evt = self.sf.SpiderFootEvent(
                "SSL_CERTIFICATE_RAW", tls_data, self.__name__, parent_event
            )
            self.notifyListeners(evt)

        # Raw data for full record
        raw = json.dumps(result, indent=2)
        evt = self.sf.SpiderFootEvent("RAW_RIR_DATA", raw, self.__name__, parent_event)
        self.notifyListeners(evt)

    def handleEvent(self, event):
        data = event.data

        if self.errorState:
            return

        if data in self.results:
            self.debug(f"Skipping already-scanned target: {data}")
            return
        self.results[data] = True

        # Rate limit total targets
        if len(self.results) > self.opts["max_hosts"]:
            self.info("Max hosts reached, skipping")
            return

        httpx_path = self._find_httpx()
        if not httpx_path:
            self.error("httpx binary not found. Install from https://github.com/projectdiscovery/httpx")
            self.errorState = True
            return

        # Clean target
        target = data
        if target.startswith("http://") or target.startswith("https://"):
            pass  # URLs used as-is
        # else: hostname or IP

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as infile:
            infile.write(target + "\n")
            input_path = infile.name

        output_path = input_path + ".json"

        try:
            cmd = self._build_cmd(httpx_path, input_path, output_path)
            self.debug(f"Running: {' '.join(cmd)}")

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if proc.returncode != 0 and proc.stderr:
                self.debug(f"httpx stderr: {proc.stderr[:500]}")

            # Parse output
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self._parse_result(line, event)

        except subprocess.TimeoutExpired:
            self.error("httpx timed out")
        except Exception as e:
            self.error(f"httpx error: {e}")
        finally:
            for p in (input_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
