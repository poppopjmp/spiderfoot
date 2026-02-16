"""SpiderFoot module: sslyze - Deep SSL/TLS analysis.

Integrates SSLyze for comprehensive SSL/TLS configuration analysis
including cipher suites, protocol support, and known vulnerabilities.

Requires: sslyze in PATH (pip install sslyze).
"""

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_sslyze(SpiderFootModernPlugin):
    """Deep SSL/TLS analysis via SSLyze."""

    meta = {
        "name": "Tool - SSLyze",
        "summary": "Comprehensive SSL/TLS configuration and vulnerability analysis.",
        "flags": ["tool", "slow"],
        "useCases": ["Investigate"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "sslyze",
            "installUrl": "https://github.com/nabla-c0d3/sslyze",
        },
    }

    opts = {
        "sslyze_path": "",
        "timeout": 120,
        "max_targets": 30,
        "port": "443",
        "heartbleed": True,
        "openssl_ccs": True,
        "robot": True,
        "certinfo": True,
    }

    optdescs = {
        "sslyze_path": "Path to sslyze. Leave blank to use PATH.",
        "timeout": "Timeout in seconds per target.",
        "max_targets": "Maximum number of hosts to scan.",
        "port": "Default port for TLS connection.",
        "heartbleed": "Check for Heartbleed vulnerability.",
        "openssl_ccs": "Check for OpenSSL CCS injection.",
        "robot": "Check for ROBOT vulnerability.",
        "certinfo": "Extract full certificate information.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        self.sf = sfc
        self.results = self.tempStorage()
        if userOpts:
            for opt in list(self.opts.keys()):
                self.opts[opt] = userOpts.get(opt, self.opts[opt])

    def watchedEvents(self):
        return ["INTERNET_NAME", "IP_ADDRESS"]

    def producedEvents(self):
        return [
            "SSL_CERTIFICATE_RAW",
            "SSL_CERTIFICATE_ISSUED",
            "SSL_CERTIFICATE_ISSUER",
            "SSL_CERTIFICATE_EXPIRED",
            "SSL_CERTIFICATE_EXPIRING",
            "VULNERABILITY_GENERAL",
            "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_CRITICAL",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("sslyze_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "sslyze")
            if os.path.isfile(candidate):
                return candidate
        for fallback in ("/opt/venv/bin/sslyze", "/usr/local/bin/sslyze", "/usr/bin/sslyze"):
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
            self.error("sslyze not found. Install: pip install sslyze")
            self.errorState = True
            return

        target = f"{data}:{self.opts['port']}"
        output_path = tempfile.mktemp(suffix=".json")

        cmd = [
            binary,
            target,
            "--json_out", output_path,
            "--quiet",
        ]

        if self.opts["heartbleed"]:
            cmd.append("--heartbleed")
        if self.opts["openssl_ccs"]:
            cmd.append("--openssl_ccs")
        if self.opts["robot"]:
            cmd.append("--robot")
        if self.opts["certinfo"]:
            cmd.append("--certinfo")

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"] + 30,
            )

            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    try:
                        report = json.load(f)
                    except json.JSONDecodeError:
                        self.debug(f"sslyze: could not parse JSON for {data}")
                        return

                # Process server scan results
                for server_result in report.get("server_scan_results", []):
                    scan_result = server_result.get("scan_result", {})

                    # Certificate info
                    certinfo = scan_result.get("certificate_info", {}).get("result", {})
                    if certinfo:
                        deployments = certinfo.get("certificate_deployments", [])
                        for deployment in deployments:
                            chain = deployment.get("received_certificate_chain", [])
                            if chain:
                                leaf = chain[0]
                                subject = leaf.get("subject", {}).get("rfc4514_string", "")
                                issuer = leaf.get("issuer", {}).get("rfc4514_string", "")
                                not_after = leaf.get("not_valid_after", "")
                                not_before = leaf.get("not_valid_before", "")

                                if subject:
                                    # Extract CN
                                    cn = ""
                                    for part in subject.split(","):
                                        if part.strip().startswith("CN="):
                                            cn = part.strip()[3:]
                                            break
                                    if cn:
                                        evt = self.sf.SpiderFootEvent(
                                            "SSL_CERTIFICATE_ISSUED", cn, self.__name__, event
                                        )
                                        self.notifyListeners(evt)

                                if issuer:
                                    evt = self.sf.SpiderFootEvent(
                                        "SSL_CERTIFICATE_ISSUER", issuer, self.__name__, event
                                    )
                                    self.notifyListeners(evt)

                            # Check leaf cert trust
                            leaf_trust = deployment.get("leaf_certificate_is_ev", False)
                            verified = deployment.get("verified_certificate_chain", None)

                            if not verified:
                                evt = self.sf.SpiderFootEvent(
                                    "VULNERABILITY_GENERAL",
                                    f"{data}: Certificate chain not trusted",
                                    self.__name__,
                                    event,
                                )
                                self.notifyListeners(evt)

                    # Heartbleed
                    heartbleed = scan_result.get("heartbleed", {}).get("result", {})
                    if heartbleed.get("is_vulnerable_to_heartbleed"):
                        evt = self.sf.SpiderFootEvent(
                            "VULNERABILITY_CVE_CRITICAL",
                            f"{data}: Vulnerable to Heartbleed (CVE-2014-0160)",
                            self.__name__,
                            event,
                        )
                        self.notifyListeners(evt)

                    # OpenSSL CCS
                    ccs = scan_result.get("openssl_ccs_injection", {}).get("result", {})
                    if ccs.get("is_vulnerable_to_ccs_injection"):
                        evt = self.sf.SpiderFootEvent(
                            "VULNERABILITY_CVE_HIGH",
                            f"{data}: Vulnerable to OpenSSL CCS Injection (CVE-2014-0224)",
                            self.__name__,
                            event,
                        )
                        self.notifyListeners(evt)

                    # ROBOT
                    robot = scan_result.get("robot", {}).get("result", {})
                    robot_result = robot.get("robot_result", "")
                    if "VULNERABLE" in str(robot_result).upper():
                        evt = self.sf.SpiderFootEvent(
                            "VULNERABILITY_CVE_HIGH",
                            f"{data}: Vulnerable to ROBOT attack ({robot_result})",
                            self.__name__,
                            event,
                        )
                        self.notifyListeners(evt)

                    # Check for weak protocols
                    for proto in ("ssl_2_0", "ssl_3_0", "tls_1_0"):
                        proto_result = scan_result.get(proto, {}).get("result", {})
                        accepted = proto_result.get("accepted_cipher_suites", [])
                        if accepted:
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL",
                                f"{data}: Accepts weak protocol {proto.replace('_', '.')} ({len(accepted)} cipher suites)",
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)

                    # Raw scan summary
                    tls_versions = []
                    for proto in ("ssl_2_0", "ssl_3_0", "tls_1_0", "tls_1_1", "tls_1_2", "tls_1_3"):
                        proto_result = scan_result.get(proto, {}).get("result", {})
                        accepted = proto_result.get("accepted_cipher_suites", [])
                        if accepted:
                            tls_versions.append(f"{proto}: {len(accepted)} ciphers")

                    if tls_versions:
                        evt = self.sf.SpiderFootEvent(
                            "RAW_RIR_DATA",
                            f"SSLyze scan for {data}:\n" + "\n".join(tls_versions),
                            self.__name__,
                            event,
                        )
                        self.notifyListeners(evt)

        except subprocess.TimeoutExpired:
            self.error(f"sslyze timed out for {data}")
        except Exception as e:
            self.error(f"sslyze error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
