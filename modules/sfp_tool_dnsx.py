"""SpiderFoot module: dnsx - Fast DNS resolver and brute-forcer.

Integrates ProjectDiscovery's dnsx for bulk DNS resolution,
wildcard filtering, and record type enumeration.

Requires: dnsx binary in PATH or configured via dnsx_path option.
Install: go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_dnsx(SpiderFootModernPlugin):
    """Fast DNS resolution and record enumeration via dnsx."""

    meta = {
        "name": "Tool - dnsx",
        "summary": "DNS resolution and record enumeration using ProjectDiscovery dnsx.",
        "flags": ["tool"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["DNS"],
        "toolDetails": {
            "binaryName": "dnsx",
            "installUrl": "https://github.com/projectdiscovery/dnsx",
        },
        "dataSource": {
            "website": "https://github.com/projectdiscovery/dnsx",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/projectdiscovery/dnsx"],
            "description": "DNS resolution and record enumeration tool by ProjectDiscovery.",
        },
    }

    opts = {
        "dnsx_path": "",
        "threads": 100,
        "retries": 2,
        "record_types": "A,AAAA,CNAME,MX,NS,TXT,SOA",
        "wildcard_filter": True,
        "rate_limit": 0,
        "timeout": 5,
        "max_hosts": 5000,
    }

    optdescs = {
        "dnsx_path": "Path to dnsx binary. Leave blank to use PATH.",
        "threads": "Number of concurrent threads.",
        "retries": "Number of DNS retries.",
        "record_types": "Comma-separated DNS record types to query.",
        "wildcard_filter": "Filter wildcard DNS responses.",
        "rate_limit": "Max DNS queries per second (0=unlimited).",
        "timeout": "DNS query timeout in seconds.",
        "max_hosts": "Maximum hosts to resolve.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["INTERNET_NAME", "INTERNET_NAME_UNRESOLVED", "DOMAIN_NAME"]

    def producedEvents(self):
        return [
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "DNS_TEXT",
            "DNS_SPF",
            "DNS_SRV",
            "PROVIDER_DNS",
            "PROVIDER_MAIL",
            "RAW_DNS_RECORDS",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("dnsx_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("dnsx", "dnsx.exe"):
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

        if len(self.results) > self.opts["max_hosts"]:
            return

        binary = self._find_binary()
        if not binary:
            self.error("dnsx binary not found.")
            self.errorState = True
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as inf:
            inf.write(data + "\n")
            input_path = inf.name
        output_path = input_path + ".json"

        cmd = [
            binary,
            "-l", input_path,
            "-o", output_path,
            "-json",
            "-silent",
            "-threads", str(self.opts["threads"]),
            "-retry", str(self.opts["retries"]),
            "-timeout", str(self.opts["timeout"]),
        ]

        for rtype in self.opts["record_types"].split(","):
            rtype = rtype.strip().lower()
            if rtype:
                cmd.append(f"-{rtype}")

        if self.opts["wildcard_filter"]:
            cmd.append("-wd")
        if self.opts["rate_limit"] > 0:
            cmd.extend(["-rl", str(self.opts["rate_limit"])])

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            if proc.returncode != 0 and proc.stderr:
                self.debug(f"dnsx stderr: {proc.stderr[:500]}")

            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            result = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # A records
                        for ip in result.get("a", []):
                            if ip not in self.results:
                                self.results[ip] = True
                                evt = self.sf.SpiderFootEvent(
                                    "IP_ADDRESS", ip, self.__name__, event
                                )
                                self.notifyListeners(evt)

                        # AAAA records
                        for ip6 in result.get("aaaa", []):
                            if ip6 not in self.results:
                                self.results[ip6] = True
                                evt = self.sf.SpiderFootEvent(
                                    "IPV6_ADDRESS", ip6, self.__name__, event
                                )
                                self.notifyListeners(evt)

                        # MX records
                        for mx in result.get("mx", []):
                            evt = self.sf.SpiderFootEvent(
                                "PROVIDER_MAIL", mx, self.__name__, event
                            )
                            self.notifyListeners(evt)

                        # NS records
                        for ns in result.get("ns", []):
                            evt = self.sf.SpiderFootEvent(
                                "PROVIDER_DNS", ns, self.__name__, event
                            )
                            self.notifyListeners(evt)

                        # TXT records
                        for txt in result.get("txt", []):
                            evt_type = "DNS_SPF" if "v=spf1" in txt.lower() else "DNS_TEXT"
                            evt = self.sf.SpiderFootEvent(
                                evt_type, txt, self.__name__, event
                            )
                            self.notifyListeners(evt)

                        # Raw record data
                        raw = json.dumps(result, indent=2)
                        evt = self.sf.SpiderFootEvent(
                            "RAW_DNS_RECORDS", raw, self.__name__, event
                        )
                        self.notifyListeners(evt)

        except subprocess.TimeoutExpired:
            self.error(f"dnsx timed out for {data}")
        except Exception as e:
            self.error(f"dnsx error: {e}")
        finally:
            for p in (input_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
