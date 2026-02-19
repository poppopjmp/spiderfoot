"""SpiderFoot module: tlsx - TLS certificate analyser.

Integrates ProjectDiscovery's tlsx for fast TLS certificate
grabbing, version detection, and cipher enumeration.

Requires: tlsx in PATH (go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_tlsx(SpiderFootModernPlugin):
    """TLS certificate analysis via tlsx."""

    meta = {
        "name": "Tool - tlsx",
        "summary": "Fast TLS certificate grabbing, version and cipher analysis.",
        "flags": ["tool"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "tlsx",
            "installUrl": "https://github.com/projectdiscovery/tlsx",
        },
        "dataSource": {
            "website": "https://github.com/projectdiscovery/tlsx",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/projectdiscovery/tlsx"],
            "description": "Fast TLS certificate grabber by ProjectDiscovery.",
        },
    }

    opts = {
        "tlsx_path": "",
        "timeout": 60,
        "max_targets": 100,
        "port": "443",
        "scan_mode": "auto",
        "min_version": "",
        "max_version": "",
    }

    optdescs = {
        "tlsx_path": "Path to tlsx. Leave blank to use PATH.",
        "timeout": "Connection timeout in seconds.",
        "max_targets": "Maximum number of hosts to scan.",
        "port": "Default port for TLS connection (can be overridden by TCP_PORT_OPEN).",
        "scan_mode": "Scan mode: 'auto', 'ctls', 'ztls'.",
        "min_version": "Minimum TLS version to test (e.g. 'tls10').",
        "max_version": "Maximum TLS version to test (e.g. 'tls13').",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["INTERNET_NAME", "IP_ADDRESS", "TCP_PORT_OPEN"]

    def producedEvents(self):
        return [
            "SSL_CERTIFICATE_RAW",
            "SSL_CERTIFICATE_ISSUED",
            "SSL_CERTIFICATE_ISSUER",
            "SSL_CERTIFICATE_EXPIRED",
            "SSL_CERTIFICATE_EXPIRING",
            "VULNERABILITY_GENERAL",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("tlsx_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "tlsx")
            if os.path.isfile(candidate):
                return candidate
        for fallback in ("/usr/local/bin/tlsx", "/usr/bin/tlsx"):
            if os.path.isfile(fallback):
                return fallback
        return None

    def _parse_target(self, event):
        """Extract host:port from event data."""
        data = event.data
        if event.eventType == "TCP_PORT_OPEN":
            # Format: host:port
            return data
        # For hostname/IP, use default port
        return f"{data}:{self.opts['port']}"

    def handleEvent(self, event):
        target = self._parse_target(event)
        if self.errorState:
            return

        # For TCP_PORT_OPEN, only scan TLS-likely ports
        if event.eventType == "TCP_PORT_OPEN":
            port = target.rsplit(":", 1)[-1] if ":" in target else ""
            tls_ports = {"443", "8443", "993", "995", "465", "636", "989", "990", "5061", "6697"}
            if port and port not in tls_ports:
                return

        if target in self.results:
            return
        self.results[target] = True

        if sum(1 for v in self.results.values() if v) > self.opts["max_targets"]:
            return

        binary = self._find_binary()
        if not binary:
            self.error("tlsx not found. Install: go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest")
            self.errorState = True
            return

        output_path = tempfile.mktemp(suffix=".json")

        cmd = [
            binary,
            "-u", target,
            "-json",
            "-o", output_path,
            "-silent",
            "-timeout", str(self.opts["timeout"]),
            "-ce",  # Certificate info
            "-ci",  # Cipher info
            "-ve",  # Version enum
        ]

        if self.opts["scan_mode"] != "auto":
            cmd.extend(["-sm", self.opts["scan_mode"]])
        if self.opts["min_version"]:
            cmd.extend(["-min-version", self.opts["min_version"]])
        if self.opts["max_version"]:
            cmd.extend(["-max-version", self.opts["max_version"]])

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"] + 30,
            )

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

                        host = result.get("host", target)
                        tls_version = result.get("tls_version", "")
                        cipher = result.get("cipher", "")
                        cert = result.get("certificate", "")
                        subject_cn = result.get("subject_cn", "")
                        subject_an = result.get("subject_an", [])
                        issuer_cn = result.get("issuer_cn", "")
                        issuer_org = result.get("issuer_org", "")
                        not_before = result.get("not_before", "")
                        not_after = result.get("not_after", "")
                        expired = result.get("expired", False)
                        self_signed = result.get("self_signed", False)
                        mismatched = result.get("mismatched", False)
                        jarm = result.get("jarm", "")
                        ja3s = result.get("ja3s", "")

                        # Certificate subject
                        if subject_cn:
                            names = [subject_cn] + (subject_an or [])
                            for name in names:
                                evt = self.sf.SpiderFootEvent(
                                    "SSL_CERTIFICATE_ISSUED",
                                    name,
                                    self.__name__,
                                    event,
                                )
                                self.notifyListeners(evt)

                        # Certificate issuer
                        if issuer_cn:
                            issuer_str = issuer_cn
                            if issuer_org:
                                issuer_str = f"{issuer_cn} ({issuer_org})"
                            evt = self.sf.SpiderFootEvent(
                                "SSL_CERTIFICATE_ISSUER",
                                issuer_str,
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)

                        # Expired certificate
                        if expired:
                            evt = self.sf.SpiderFootEvent(
                                "SSL_CERTIFICATE_EXPIRED",
                                f"{host}: Certificate expired (not_after: {not_after})",
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)

                        # Weak TLS version
                        if tls_version and tls_version in ("tls10", "tls11", "ssl30"):
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL",
                                f"{host}: Weak TLS version {tls_version}",
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)

                        # Self-signed certificate
                        if self_signed:
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL",
                                f"{host}: Self-signed certificate",
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)

                        # Mismatched certificate
                        if mismatched:
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL",
                                f"{host}: Certificate hostname mismatch",
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)

                        # Full TLS details as raw data
                        details = [f"Host: {host}"]
                        if tls_version:
                            details.append(f"TLS Version: {tls_version}")
                        if cipher:
                            details.append(f"Cipher: {cipher}")
                        if jarm:
                            details.append(f"JARM: {jarm}")
                        if ja3s:
                            details.append(f"JA3S: {ja3s}")
                        if not_before:
                            details.append(f"Valid From: {not_before}")
                        if not_after:
                            details.append(f"Valid Until: {not_after}")

                        evt = self.sf.SpiderFootEvent(
                            "RAW_RIR_DATA",
                            "\n".join(details),
                            self.__name__,
                            event,
                        )
                        self.notifyListeners(evt)

        except subprocess.TimeoutExpired:
            self.error(f"tlsx timed out for {target}")
        except Exception as e:
            self.error(f"tlsx error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
