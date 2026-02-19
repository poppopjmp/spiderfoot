"""SpiderFoot module: massdns - High-performance DNS stub resolver.

Integrates massdns for extremely fast bulk DNS resolution. Useful for
resolving large lists of subdomains discovered by other modules.

Requires: massdns binary in PATH or configured via massdns_path option.
Install: git clone https://github.com/blechschmidt/massdns && cd massdns && make
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_massdns(SpiderFootModernPlugin):
    """High-performance bulk DNS resolution via massdns."""

    meta = {
        "name": "Tool - massdns",
        "summary": "High-performance bulk DNS resolution using massdns.",
        "flags": ["tool", "slow"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["DNS"],
        "toolDetails": {
            "binaryName": "massdns",
            "installUrl": "https://github.com/blechschmidt/massdns",
        },
        "dataSource": {
            "website": "https://github.com/blechschmidt/massdns",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/blechschmidt/massdns"],
            "description": "High-performance DNS stub resolver for bulk lookups.",
        },
    }

    opts = {
        "massdns_path": "",
        "resolvers_file": "/tools/wordlists/resolvers.txt",
        "concurrent": 1000,
        "record_type": "A",
        "max_hosts": 10000,
    }

    optdescs = {
        "massdns_path": "Path to massdns binary. Leave blank to use PATH.",
        "resolvers_file": "Path to DNS resolvers list file.",
        "concurrent": "Number of concurrent lookups.",
        "record_type": "DNS record type to resolve (A, AAAA, CNAME, etc.).",
        "max_hosts": "Maximum number of hosts to resolve per run.",
    }

    results = None
    _batch = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()
        self._batch = []

    def watchedEvents(self):
        return ["INTERNET_NAME_UNRESOLVED"]

    def producedEvents(self):
        return ["IP_ADDRESS", "IPV6_ADDRESS", "INTERNET_NAME"]

    def _find_binary(self):
        custom = self.opts.get("massdns_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("massdns", "massdns.exe"):
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
            self.error("massdns binary not found.")
            self.errorState = True
            return

        resolvers = self.opts["resolvers_file"]
        if not os.path.isfile(resolvers):
            self.error(f"Resolvers file not found: {resolvers}")
            self.errorState = True
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as inf:
            inf.write(data + "\n")
            input_path = inf.name
        output_path = input_path + ".out"

        cmd = [
            binary,
            "-r", resolvers,
            "-t", self.opts["record_type"],
            "-o", "S",  # simple output: name type value
            "-w", output_path,
            "-s", str(self.opts["concurrent"]),
            "--quiet",
            input_path,
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )

            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) < 3:
                            continue
                        _name, rtype, value = parts[0].rstrip("."), parts[1], parts[2].rstrip(".")

                        if rtype == "A" and value not in self.results:
                            self.results[value] = True
                            evt = self.sf.SpiderFootEvent(
                                "IP_ADDRESS", value, self.__name__, event
                            )
                            self.notifyListeners(evt)

                            # Promote the unresolved name to resolved
                            evt = self.sf.SpiderFootEvent(
                                "INTERNET_NAME", data, self.__name__, event
                            )
                            self.notifyListeners(evt)

                        elif rtype == "AAAA" and value not in self.results:
                            self.results[value] = True
                            evt = self.sf.SpiderFootEvent(
                                "IPV6_ADDRESS", value, self.__name__, event
                            )
                            self.notifyListeners(evt)

        except subprocess.TimeoutExpired:
            self.error(f"massdns timed out")
        except Exception as e:
            self.error(f"massdns error: {e}")
        finally:
            for p in (input_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
