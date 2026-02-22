"""SpiderFoot module: nikto - Web server vulnerability scanner.

Integrates Nikto for comprehensive web server scanning to detect
misconfigurations, outdated software, and known vulnerabilities.

Requires: nikto in PATH (apt install nikto).
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile

from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_nikto(SpiderFootAsyncPlugin):
    """Web server vulnerability scanning via Nikto."""

    meta = {
        "name": "Tool - Nikto",
        "summary": "Web server vulnerability scanner for misconfigurations and CVEs.",
        "flags": ["tool", "slow", "invasive"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "nikto",
            "installUrl": "https://github.com/sullo/nikto",
        },
        "dataSource": {
            "website": "https://github.com/sullo/nikto",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/sullo/nikto"],
            "description": "Web server vulnerability scanner.",
        },
    }

    opts = {
        "nikto_path": "",
        "timeout": 300,
        "tuning": "",
        "max_targets": 20,
        "port": "",
        "ssl": False,
        "no_ssl": False,
        "plugins": "",
    }

    optdescs = {
        "nikto_path": "Path to nikto. Leave blank to use PATH.",
        "timeout": "Scan timeout in seconds.",
        "tuning": "Nikto tuning options (e.g. '1234' for test types, blank=all).",
        "max_targets": "Maximum number of targets to scan.",
        "port": "Specific port to scan (blank=default 80/443).",
        "ssl": "Force SSL mode.",
        "no_ssl": "Disable SSL.",
        "plugins": "Specific Nikto plugins to run (comma-separated, blank=all).",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["DOMAIN_NAME", "IP_ADDRESS", "LINKED_URL_INTERNAL"]

    def producedEvents(self):
        return [
            "VULNERABILITY_GENERAL",
            "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_MEDIUM",
            "VULNERABILITY_CVE_LOW",
            "WEBSERVER_BANNER",
            "WEBSERVER_TECHNOLOGY",
            "INTERESTING_FILE",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("nikto_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("nikto", "nikto.pl"):
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

        if sum(1 for v in self.results.values() if v) > self.opts["max_targets"]:
            return

        binary = self._find_binary()
        if not binary:
            self.error("nikto not found. Install with: apt install nikto")
            self.errorState = True
            return

        # Determine target
        if data.startswith("http"):
            target = data
        else:
            target = data

        output_path = tempfile.mktemp(suffix=".csv")

        cmd = [binary, "-h", target, "-o", output_path, "-Format", "csv", "-nointeractive"]

        if self.opts["port"]:
            cmd.extend(["-p", self.opts["port"]])
        if self.opts["ssl"]:
            cmd.append("-ssl")
        if self.opts["no_ssl"]:
            cmd.append("-nossl")
        if self.opts["tuning"]:
            cmd.extend(["-Tuning", self.opts["tuning"]])
        if self.opts["plugins"]:
            cmd.extend(["-Plugins", self.opts["plugins"]])
        cmd.extend(["-timeout", str(self.opts["timeout"])])

        cve_re = re.compile(r'CVE-\d{4}-\d+', re.IGNORECASE)

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"] + 60,
            )

            # Parse CSV output
            vuln_count = 0
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    for line in f:
                        if self.checkForStop():
                            return
                        line = line.strip()
                        if not line or line.startswith('"Nikto') or line.startswith('"Host'):
                            continue

                        # CSV: "host","ip","port","ref","method","uri","description"
                        parts = line.replace('"', '').split(',', 6)
                        if len(parts) < 7:
                            continue

                        ref = parts[3].strip()
                        uri = parts[5].strip()
                        description = parts[6].strip()

                        if not description:
                            continue
                        vuln_count += 1

                        # Check for CVE references
                        cve_matches = cve_re.findall(description)

                        finding = f"{target}{uri}: {description}"

                        if cve_matches:
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_CVE_MEDIUM", finding, self.__name__, event
                            )
                        elif any(x in description.lower() for x in ("vuln", "exploit", "injection", "xss", "rce")):
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL", finding, self.__name__, event
                            )
                        elif any(x in description.lower() for x in ("interesting", "backup", "config", "admin")):
                            evt = self.sf.SpiderFootEvent(
                                "INTERESTING_FILE", finding, self.__name__, event
                            )
                        else:
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL", finding, self.__name__, event
                            )
                        self.notifyListeners(evt)

            # Also parse stdout for server info
            for line in (proc.stdout or "").splitlines():
                if "+ Server:" in line:
                    server = line.split("+ Server:", 1)[1].strip()
                    evt = self.sf.SpiderFootEvent(
                        "WEBSERVER_BANNER", f"{target}: {server}", self.__name__, event
                    )
                    self.notifyListeners(evt)

            self.info(f"nikto found {vuln_count} findings for {target}")

        except subprocess.TimeoutExpired:
            self.error(f"nikto timed out for {target}")
        except Exception as e:
            self.error(f"nikto error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
