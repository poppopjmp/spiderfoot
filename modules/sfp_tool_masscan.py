"""SpiderFoot module: masscan - Mass IP port scanner.

Integrates Masscan for ultra-fast port scanning across IP ranges
and network blocks.

Requires: masscan in PATH (built from source or installed via package manager).
Note: Requires NET_RAW capability (setcap cap_net_raw+ep) and typically root.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_masscan(SpiderFootAsyncPlugin):
    """Mass port scanning via Masscan."""

    meta = {
        "name": "Tool - Masscan",
        "summary": "Ultra-fast mass port scanner for IP addresses and network blocks.",
        "flags": ["tool", "invasive", "slow"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "masscan",
            "installUrl": "https://github.com/robertdavidgraham/masscan",
        },
        "dataSource": {
            "website": "https://github.com/robertdavidgraham/masscan",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/robertdavidgraham/masscan"],
            "description": "Ultra-fast mass port scanner.",
        },
    }

    opts = {
        "masscan_path": "",
        "timeout": 600,
        "max_targets": 20,
        "ports": "80,443,8080,8443,21,22,23,25,53,110,143,993,995,3306,3389,5432,6379,8000,8888,9200",
        "rate": 1000,
        "max_rate": 10000,
        "banners": True,
        "wait": 5,
    }

    optdescs = {
        "masscan_path": "Path to masscan binary. Leave blank to use PATH.",
        "timeout": "Scan timeout in seconds.",
        "max_targets": "Maximum number of targets to scan.",
        "ports": "Ports to scan (comma-separated or range like 1-1000).",
        "rate": "Packets per second (default: 1000).",
        "max_rate": "Maximum rate cap to prevent network issues.",
        "banners": "Attempt to grab service banners.",
        "wait": "Seconds to wait after sending last packet.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["IP_ADDRESS", "NETBLOCK_OWNER"]

    def producedEvents(self):
        return [
            "TCP_PORT_OPEN",
            "WEBSERVER_BANNER",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("masscan_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "masscan")
            if os.path.isfile(candidate):
                return candidate
        for fallback in ("/usr/local/bin/masscan", "/usr/bin/masscan"):
            if os.path.isfile(fallback):
                return fallback
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
            self.error("masscan not found. Build from: https://github.com/robertdavidgraham/masscan")
            self.errorState = True
            return

        # Ensure rate doesn't exceed cap
        rate = min(self.opts["rate"], self.opts["max_rate"])

        output_path = tempfile.mktemp(suffix=".json")

        cmd = [
            binary,
            data,
            "-p", self.opts["ports"],
            "--rate", str(rate),
            "--wait", str(self.opts["wait"]),
            "-oJ", output_path,
        ]

        if self.opts["banners"]:
            cmd.append("--banners")

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"],
            )

            port_count = 0
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    content = f.read().strip()

                if content:
                    # Masscan JSON is an array (may have trailing commas)
                    # Clean up: remove trailing comma before ]
                    content = content.rstrip().rstrip(",")
                    if not content.endswith("]"):
                        content += "]"
                    if not content.startswith("["):
                        content = "[" + content

                    try:
                        results = json.loads(content)
                    except json.JSONDecodeError:
                        # Try line-by-line parsing
                        results = []
                        for line in content.splitlines():
                            line = line.strip().rstrip(",").strip("[]")
                            if not line:
                                continue
                            try:
                                results.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue

                    for result in results:
                        ip = result.get("ip", data)
                        ports = result.get("ports", [])

                        for port_info in ports:
                            port = port_info.get("port", "")
                            proto = port_info.get("proto", "tcp")
                            status = port_info.get("status", "")
                            service = port_info.get("service", {})
                            banner = service.get("banner", "")

                            if status != "open":
                                continue

                            port_str = f"{ip}:{port}"
                            evt = self.sf.SpiderFootEvent(
                                "TCP_PORT_OPEN", port_str, self.__name__, event
                            )
                            self.notifyListeners(evt)
                            port_count += 1

                            if banner:
                                evt = self.sf.SpiderFootEvent(
                                    "WEBSERVER_BANNER",
                                    f"{port_str}: {banner}",
                                    self.__name__,
                                    event,
                                )
                                self.notifyListeners(evt)

            self.info(f"masscan found {port_count} open ports on {data}")

        except subprocess.TimeoutExpired:
            self.error(f"masscan timed out for {data}")
        except Exception as e:
            self.error(f"masscan error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
