"""SpiderFoot module: naabu - Fast port scanner.

Integrates ProjectDiscovery's Naabu for high-speed SYN/CONNECT port
scanning to discover open TCP ports on targets.

Requires: naabu in PATH (go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest).
Note: SYN scanning requires NET_RAW capability (setcap cap_net_raw+ep).
"""

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_naabu(SpiderFootModernPlugin):
    """Fast port scanning via Naabu."""

    meta = {
        "name": "Tool - Naabu",
        "summary": "High-speed port scanner for discovering open TCP ports.",
        "flags": ["tool", "invasive"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "naabu",
            "installUrl": "https://github.com/projectdiscovery/naabu",
        },
    }

    opts = {
        "naabu_path": "",
        "timeout": 300,
        "max_targets": 50,
        "ports": "top-100",
        "rate": 1000,
        "retries": 3,
        "scan_type": "s",
        "exclude_ports": "",
        "warm_up_time": 2,
    }

    optdescs = {
        "naabu_path": "Path to naabu. Leave blank to use PATH.",
        "timeout": "Scan timeout in seconds.",
        "max_targets": "Maximum number of hosts to scan.",
        "ports": "Ports to scan: 'top-100', 'top-1000', 'full', or custom like '80,443,8080' or '1-1000'.",
        "rate": "Packets per second rate limit.",
        "retries": "Number of retries for port verification.",
        "scan_type": "Scan type: 's' for SYN scan, 'c' for CONNECT scan.",
        "exclude_ports": "Ports to exclude (comma-separated).",
        "warm_up_time": "Warm-up time in seconds before scanning.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        self.sf = sfc
        self.results = self.tempStorage()
        if userOpts:
            for opt in list(self.opts.keys()):
                self.opts[opt] = userOpts.get(opt, self.opts[opt])

    def watchedEvents(self):
        return ["IP_ADDRESS", "INTERNET_NAME", "DOMAIN_NAME"]

    def producedEvents(self):
        return ["TCP_PORT_OPEN"]

    def _find_binary(self):
        custom = self.opts.get("naabu_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "naabu")
            if os.path.isfile(candidate):
                return candidate
        for fallback in ("/usr/local/bin/naabu", "/usr/bin/naabu"):
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
            self.error("naabu not found. Install: go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest")
            self.errorState = True
            return

        output_path = tempfile.mktemp(suffix=".json")

        cmd = [
            binary,
            "-host", data,
            "-json",
            "-o", output_path,
            "-rate", str(self.opts["rate"]),
            "-retries", str(self.opts["retries"]),
            "-warm-up-time", str(self.opts["warm_up_time"]),
            "-silent",
        ]

        # Port specification
        ports = self.opts["ports"]
        if ports == "top-100":
            cmd.extend(["-top-ports", "100"])
        elif ports == "top-1000":
            cmd.extend(["-top-ports", "1000"])
        elif ports == "full":
            cmd.extend(["-p", "-"])
        else:
            cmd.extend(["-p", ports])

        # Scan type
        if self.opts["scan_type"] == "c":
            cmd.append("-scan-type")
            cmd.append("c")

        if self.opts["exclude_ports"]:
            cmd.extend(["-exclude-ports", self.opts["exclude_ports"]])

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"],
            )

            port_count = 0
            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            result = json.loads(line)
                        except json.JSONDecodeError:
                            # Plain text format: host:port
                            if ":" in line:
                                parts = line.rsplit(":", 1)
                                if len(parts) == 2 and parts[1].isdigit():
                                    port_str = f"{parts[0]}:{parts[1]}"
                                    evt = self.sf.SpiderFootEvent(
                                        "TCP_PORT_OPEN", port_str, self.__name__, event
                                    )
                                    self.notifyListeners(evt)
                                    port_count += 1
                            continue

                        host = result.get("host", result.get("ip", data))
                        port = result.get("port", "")

                        if port:
                            port_str = f"{host}:{port}"
                            evt = self.sf.SpiderFootEvent(
                                "TCP_PORT_OPEN", port_str, self.__name__, event
                            )
                            self.notifyListeners(evt)
                            port_count += 1

            self.info(f"naabu found {port_count} open ports on {data}")

        except subprocess.TimeoutExpired:
            self.error(f"naabu timed out for {data}")
        except Exception as e:
            self.error(f"naabu error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
