"""SpiderFoot module: sslscan - SSL cipher and protocol scanner.

Integrates sslscan for quick SSL/TLS cipher suite enumeration
and certificate details.

Requires: sslscan in PATH (apt install sslscan).
"""

from __future__ import annotations

import os
import re
import subprocess

from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_sslscan(SpiderFootAsyncPlugin):
    """SSL cipher enumeration via sslscan."""

    meta = {
        "name": "Tool - sslscan",
        "summary": "Enumerate SSL/TLS cipher suites and detect weak configurations.",
        "flags": ["tool"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "sslscan",
            "installUrl": "https://github.com/rbsec/sslscan",
        },
        "dataSource": {
            "website": "https://github.com/rbsec/sslscan",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/rbsec/sslscan"],
            "description": "SSL/TLS cipher suite enumeration tool.",
        },
    }

    opts = {
        "sslscan_path": "",
        "timeout": 60,
        "max_targets": 50,
        "port": "443",
        "show_ciphers": True,
        "no_colour": True,
    }

    optdescs = {
        "sslscan_path": "Path to sslscan. Leave blank to use PATH.",
        "timeout": "Timeout in seconds per target.",
        "max_targets": "Maximum number of hosts to scan.",
        "port": "Default port for TLS connection.",
        "show_ciphers": "Show cipher suite details.",
        "no_colour": "Disable colour output for parsing.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["INTERNET_NAME", "IP_ADDRESS"]

    def producedEvents(self):
        return [
            "SSL_CERTIFICATE_RAW",
            "SSL_CERTIFICATE_ISSUED",
            "SSL_CERTIFICATE_ISSUER",
            "VULNERABILITY_GENERAL",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("sslscan_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "sslscan")
            if os.path.isfile(candidate):
                return candidate
        for fallback in ("/usr/local/bin/sslscan", "/usr/bin/sslscan"):
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
            self.error("sslscan not found. Install: apt install sslscan")
            self.errorState = True
            return

        target = f"{data}:{self.opts['port']}"

        cmd = [binary, "--no-colour", target]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"],
            )

            output = proc.stdout or ""
            if not output:
                self.debug(f"sslscan: no output for {data}")
                return

            weak_ciphers = []
            strong_ciphers = []
            protocols = []
            subject = ""
            issuer = ""
            vulns = []

            for line in output.splitlines():
                if self.checkForStop():
                    return
                line = line.strip()

                # Parse cipher suites
                # Format: "Accepted  TLSv1.2  256 bits  ECDHE-RSA-AES256-GCM-SHA384"
                cipher_match = re.match(
                    r'(Accepted|Preferred)\s+(SSLv[23]|TLSv1\.[0-3])\s+(\d+)\s+bits\s+(\S+)',
                    line,
                )
                if cipher_match:
                    status = cipher_match.group(1)
                    proto = cipher_match.group(2)
                    bits = int(cipher_match.group(3))
                    cipher_name = cipher_match.group(4)

                    cipher_info = f"{proto} {bits}bit {cipher_name}"

                    # Flag weak configurations
                    if proto in ("SSLv2", "SSLv3", "TLSv1.0"):
                        weak_ciphers.append(cipher_info)
                    elif bits < 128:
                        weak_ciphers.append(cipher_info)
                    elif "NULL" in cipher_name or "EXPORT" in cipher_name or "RC4" in cipher_name:
                        weak_ciphers.append(cipher_info)
                    else:
                        strong_ciphers.append(cipher_info)

                # Parse protocol support
                proto_match = re.match(r'(SSLv[23]|TLSv1\.[0-3])\s+(enabled|disabled)', line)
                if proto_match:
                    proto_name = proto_match.group(1)
                    proto_status = proto_match.group(2)
                    protocols.append(f"{proto_name}: {proto_status}")

                # Parse certificate subject
                if line.startswith("Subject:"):
                    subject = line.split("Subject:", 1)[1].strip()
                elif line.startswith("Issuer:"):
                    issuer = line.split("Issuer:", 1)[1].strip()

                # Check for known issues
                if "Heartbleed" in line and "vulnerable" in line.lower():
                    vulns.append("Heartbleed")
                if "compression" in line.lower() and "enabled" in line.lower():
                    vulns.append("TLS Compression enabled (CRIME)")

            # Emit certificate details
            if subject:
                # Extract CN from subject
                cn_match = re.search(r'CN=([^\s/,]+)', subject)
                if cn_match:
                    evt = self.sf.SpiderFootEvent(
                        "SSL_CERTIFICATE_ISSUED", cn_match.group(1), self.__name__, event
                    )
                    self.notifyListeners(evt)

            if issuer:
                evt = self.sf.SpiderFootEvent(
                    "SSL_CERTIFICATE_ISSUER", issuer, self.__name__, event
                )
                self.notifyListeners(evt)

            # Emit vulnerabilities for weak ciphers
            if weak_ciphers:
                evt = self.sf.SpiderFootEvent(
                    "VULNERABILITY_GENERAL",
                    f"{data}: {len(weak_ciphers)} weak cipher(s) accepted:\n" + "\n".join(weak_ciphers[:10]),
                    self.__name__,
                    event,
                )
                self.notifyListeners(evt)

            # Emit known vulnerabilities
            for vuln in vulns:
                evt = self.sf.SpiderFootEvent(
                    "VULNERABILITY_GENERAL",
                    f"{data}: {vuln}",
                    self.__name__,
                    event,
                )
                self.notifyListeners(evt)

            # Full raw output as data
            summary_lines = protocols + [
                f"Strong ciphers: {len(strong_ciphers)}",
                f"Weak ciphers: {len(weak_ciphers)}",
            ]
            if subject:
                summary_lines.append(f"Subject: {subject}")
            if issuer:
                summary_lines.append(f"Issuer: {issuer}")

            evt = self.sf.SpiderFootEvent(
                "RAW_RIR_DATA",
                f"sslscan results for {data}:\n" + "\n".join(summary_lines),
                self.__name__,
                event,
            )
            self.notifyListeners(evt)

        except subprocess.TimeoutExpired:
            self.error(f"sslscan timed out for {data}")
        except Exception as e:
            self.error(f"sslscan error: {e}")
