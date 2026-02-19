"""SpiderFoot module: amass - OWASP attack surface mapping.

Integrates OWASP Amass for comprehensive subdomain enumeration and
attack surface discovery using passive and active techniques.

Requires: amass binary in PATH or configured via amass_path option.
Install: go install -v github.com/owasp-amass/amass/v4/...@master
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_amass(SpiderFootModernPlugin):
    """Attack surface mapping and subdomain discovery via OWASP Amass."""

    meta = {
        "name": "Tool - Amass",
        "summary": "Comprehensive attack surface mapping using OWASP Amass.",
        "flags": ["tool", "slow"],
        "useCases": ["Investigate", "Footprint", "Passive"],
        "categories": ["Passive DNS"],
        "toolDetails": {
            "binaryName": "amass",
            "installUrl": "https://github.com/owasp-amass/amass",
        },
        "dataSource": {
            "website": "https://github.com/owasp-amass/amass",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/owasp-amass/amass"],
            "description": "OWASP attack surface mapping and subdomain enumeration.",
        },
    }

    opts = {
        "amass_path": "",
        "mode": "enum",
        "passive_only": True,
        "timeout": 30,
        "max_dns_queries": 0,
        "max_results": 5000,
    }

    optdescs = {
        "amass_path": "Path to amass binary. Leave blank to use PATH.",
        "mode": "Amass mode: enum (subdomain enumeration).",
        "passive_only": "Use passive-only mode (no DNS brute-forcing).",
        "timeout": "Timeout in minutes.",
        "max_dns_queries": "Max DNS queries per second (0=unlimited).",
        "max_results": "Maximum number of results to process.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["DOMAIN_NAME", "ROOT"]

    def producedEvents(self):
        return [
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "DOMAIN_NAME",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("amass_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("amass", "amass.exe"):
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate):
                    return candidate
        return None

    def handleEvent(self, event):
        data = event.data
        if self.errorState:
            return

        if event.eventType == "ROOT":
            target = self.sf.targetValue
            if not target:
                return
            data = target

        if data in self.results:
            return
        self.results[data] = True

        binary = self._find_binary()
        if not binary:
            self.error("amass binary not found. Install from https://github.com/owasp-amass/amass")
            self.errorState = True
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_path = f.name

        cmd = [
            binary, "enum",
            "-d", data,
            "-json", output_path,
            "-timeout", str(self.opts["timeout"]),
        ]

        if self.opts["passive_only"]:
            cmd.append("-passive")
        if self.opts["max_dns_queries"] > 0:
            cmd.extend(["-max-dns-queries", str(self.opts["max_dns_queries"])])

        try:
            self.debug(f"Running: {' '.join(cmd)}")
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=(self.opts["timeout"] + 5) * 60,
            )
            if proc.returncode != 0 and proc.stderr:
                self.debug(f"amass stderr: {proc.stderr[:500]}")

            count = 0
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    for line in f:
                        if count >= self.opts["max_results"]:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        name = entry.get("name", "").strip().lower()
                        if not name or name in self.results:
                            continue
                        self.results[name] = True
                        count += 1

                        evt = self.sf.SpiderFootEvent(
                            "INTERNET_NAME", name, self.__name__, event
                        )
                        self.notifyListeners(evt)

                        for addr in entry.get("addresses", []):
                            ip = addr.get("ip", "")
                            if ip and ip not in self.results:
                                self.results[ip] = True
                                evt_type = "IPV6_ADDRESS" if ":" in ip else "IP_ADDRESS"
                                evt = self.sf.SpiderFootEvent(
                                    evt_type, ip, self.__name__, event
                                )
                                self.notifyListeners(evt)

            self.info(f"amass found {count} names for {data}")

        except subprocess.TimeoutExpired:
            self.error(f"amass timed out for {data}")
        except Exception as e:
            self.error(f"amass error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
