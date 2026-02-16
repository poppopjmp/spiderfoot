"""SpiderFoot module: dalfox - XSS parameter scanner.

Integrates Dalfox for reflected/stored XSS vulnerability detection
on URLs with parameters.

Requires: dalfox in PATH (go install github.com/hahwul/dalfox/v2@latest).
"""

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_dalfox(SpiderFootModernPlugin):
    """XSS vulnerability detection via Dalfox."""

    meta = {
        "name": "Tool - Dalfox",
        "summary": "Detect reflected and stored XSS vulnerabilities in web parameters.",
        "flags": ["tool", "slow", "invasive"],
        "useCases": ["Investigate"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "dalfox",
            "installUrl": "https://github.com/hahwul/dalfox",
        },
    }

    opts = {
        "dalfox_path": "",
        "timeout": 120,
        "max_targets": 50,
        "follow_redirect": True,
        "worker": 10,
        "blind_xss_url": "",
        "custom_payload": "",
        "only_discovery": False,
        "silence": True,
    }

    optdescs = {
        "dalfox_path": "Path to dalfox binary. Leave blank to use PATH.",
        "timeout": "Timeout in seconds per target.",
        "max_targets": "Maximum number of URLs to scan.",
        "follow_redirect": "Follow HTTP redirects.",
        "worker": "Number of concurrent workers.",
        "blind_xss_url": "Blind XSS callback URL (e.g. your Burp collaborator).",
        "custom_payload": "Path to custom XSS payload file.",
        "only_discovery": "Only discover parameters, don't test for XSS.",
        "silence": "Suppress banner output.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        self.sf = sfc
        self.results = self.tempStorage()
        if userOpts:
            for opt in list(self.opts.keys()):
                self.opts[opt] = userOpts.get(opt, self.opts[opt])

    def watchedEvents(self):
        return ["URL_FORM", "LINKED_URL_INTERNAL"]

    def producedEvents(self):
        return [
            "VULNERABILITY_GENERAL",
            "VULNERABILITY_CVE_HIGH",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("dalfox_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "dalfox")
            if os.path.isfile(candidate):
                return candidate
        for fallback in ("/usr/local/bin/dalfox", "/usr/bin/dalfox", "/opt/venv/bin/dalfox"):
            if os.path.isfile(fallback):
                return fallback
        return None

    def _has_params(self, url):
        """Only scan URLs that have query parameters."""
        return "?" in url and "=" in url

    def handleEvent(self, event):
        data = event.data
        if self.errorState:
            return
        if data in self.results:
            return
        self.results[data] = True

        # Only scan URLs with parameters
        if not self._has_params(data):
            return

        if sum(1 for v in self.results.values() if v) > self.opts["max_targets"]:
            return

        binary = self._find_binary()
        if not binary:
            self.error("dalfox not found. Install: go install github.com/hahwul/dalfox/v2@latest")
            self.errorState = True
            return

        output_path = tempfile.mktemp(suffix=".json")

        cmd = [
            binary, "url", data,
            "-o", output_path,
            "--format", "json",
            "-w", str(self.opts["worker"]),
            "--timeout", str(self.opts["timeout"]),
        ]

        if self.opts["follow_redirect"]:
            cmd.append("--follow-redirects")
        if self.opts["blind_xss_url"]:
            cmd.extend(["--blind", self.opts["blind_xss_url"]])
        if self.opts["custom_payload"]:
            cmd.extend(["--custom-payload", self.opts["custom_payload"]])
        if self.opts["only_discovery"]:
            cmd.append("--only-discovery")
        if self.opts["silence"]:
            cmd.append("--silence")

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"] + 30,
            )

            vuln_count = 0
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    content = f.read().strip()

                if content:
                    # Dalfox JSON output: one JSON object per line
                    for line in content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            result = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        vuln_type = result.get("type", "")
                        poc_url = result.get("proof_of_concept", result.get("poc", ""))
                        param = result.get("param", "")
                        inject_type = result.get("inject_type", "")
                        severity = result.get("severity", "").lower()

                        finding = f"XSS ({inject_type}) in parameter '{param}' at {data}"
                        if poc_url:
                            finding += f"\nPoC: {poc_url}"

                        # Reflected/stored XSS is high severity
                        if vuln_type in ("V", "verified") or severity == "high":
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_CVE_HIGH",
                                finding,
                                self.__name__,
                                event,
                            )
                        else:
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL",
                                finding,
                                self.__name__,
                                event,
                            )
                        self.notifyListeners(evt)
                        vuln_count += 1

            # Also parse stdout for any POC lines
            if proc.stdout:
                for line in proc.stdout.splitlines():
                    if "[POC]" in line or "[V]" in line:
                        clean = line.strip()
                        evt = self.sf.SpiderFootEvent(
                            "RAW_RIR_DATA",
                            f"Dalfox finding: {clean}",
                            self.__name__,
                            event,
                        )
                        self.notifyListeners(evt)

            self.info(f"dalfox found {vuln_count} XSS issues for {data}")

        except subprocess.TimeoutExpired:
            self.error(f"dalfox timed out for {data}")
        except Exception as e:
            self.error(f"dalfox error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
