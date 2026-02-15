from __future__ import annotations

"""SpiderFoot plug-in module: Nuclei vulnerability scanner integration.

Runs ProjectDiscovery's Nuclei scanner against discovered web endpoints
and IP addresses, parsing template-based findings into SpiderFoot events.

Nuclei must be installed on the system or available in the Docker image.
Templates are auto-updated via `nuclei -ut` on first run.

Event flow:
  IN:  INTERNET_NAME, DOMAIN_NAME, IP_ADDRESS, LINKED_URL_INTERNAL
  OUT: VULNERABILITY_GENERAL, VULNERABILITY_CVE_CRITICAL,
       VULNERABILITY_CVE_HIGH, VULNERABILITY_CVE_MEDIUM,
       VULNERABILITY_CVE_LOW, RAW_RIR_DATA, WEBSERVER_TECHNOLOGY
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_nuclei(SpiderFootModernPlugin):
    """Nuclei — fast, template-based vulnerability scanner by ProjectDiscovery."""

    meta = {
        'name': "Nuclei Scanner",
        'summary': "Run ProjectDiscovery Nuclei templates against discovered targets to find vulnerabilities, misconfigurations, and exposed services.",
        'flags': ["slow", "invasive"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Crawling and Scanning"],
        'toolDetails': {
            'name': "Nuclei",
            'description': "Fast and customisable vulnerability scanner based on simple YAML-based templates.",
            'website': 'https://nuclei.projectdiscovery.io/',
            'repository': 'https://github.com/projectdiscovery/nuclei',
        },
        'dataSource': {
            'website': "https://nuclei.projectdiscovery.io/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://docs.projectdiscovery.io/tools/nuclei/overview",
                "https://github.com/projectdiscovery/nuclei-templates",
            ],
            'favIcon': "https://nuclei.projectdiscovery.io/favicon.ico",
            'logo': "https://nuclei.projectdiscovery.io/static/nuclei-logo.png",
            'description': "Nuclei is a fast scanner for modern web applications, "
            "infrastructure, cloud platforms, and networks using a large library "
            "of community-maintained YAML templates.",
        },
    }

    opts = {
        'nuclei_path': 'nuclei',
        'severity_filter': 'info,low,medium,high,critical',
        'template_tags': '',
        'template_exclude_tags': 'dos,fuzz',
        'custom_templates_dir': '',
        'rate_limit': 50,
        'bulk_size': 25,
        'concurrency': 10,
        'timeout': 10,
        'max_scan_duration': 600,
        'auto_update_templates': True,
        'scan_urls': True,
        'scan_ips': True,
        'include_info_findings': False,
    }

    optdescs = {
        'nuclei_path': "Path to the nuclei binary (default: 'nuclei' assumes it's in PATH).",
        'severity_filter': "Comma-separated severity levels to include (info,low,medium,high,critical).",
        'template_tags': "Only run templates with these tags (comma-separated, empty = all).",
        'template_exclude_tags': "Exclude templates with these tags (comma-separated).",
        'custom_templates_dir': "Path to a custom templates directory to scan (in addition to defaults).",
        'rate_limit': "Max requests per second sent by Nuclei.",
        'bulk_size': "Max hosts to scan per Nuclei invocation.",
        'concurrency': "Number of templates to run concurrently.",
        'timeout': "HTTP timeout per request in seconds.",
        'max_scan_duration': "Max total time in seconds for a single Nuclei invocation.",
        'auto_update_templates': "Automatically update Nuclei templates on first use.",
        'scan_urls': "Scan discovered URLs in addition to hostnames.",
        'scan_ips': "Scan discovered IP addresses.",
        'include_info_findings': "Include informational-severity findings (can be noisy).",
    }

    results = None
    errorState = False
    _nuclei_checked = False
    _nuclei_available = False

    def setup(self, sfc, userOpts=None):
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self._nuclei_checked = False
        self._nuclei_available = False

    def watchedEvents(self):
        """Events consumed by this module."""
        events = ["INTERNET_NAME", "DOMAIN_NAME"]
        if self.opts.get('scan_ips', True):
            events.append("IP_ADDRESS")
        if self.opts.get('scan_urls', True):
            events.append("LINKED_URL_INTERNAL")
        return events

    def producedEvents(self):
        """Events produced by this module."""
        return [
            "VULNERABILITY_GENERAL",
            "VULNERABILITY_CVE_CRITICAL",
            "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_MEDIUM",
            "VULNERABILITY_CVE_LOW",
            "RAW_RIR_DATA",
            "WEBSERVER_TECHNOLOGY",
        ]

    def _check_nuclei(self) -> bool:
        """Verify that nuclei is installed and accessible."""
        if self._nuclei_checked:
            return self._nuclei_available

        self._nuclei_checked = True
        nuclei_path = self.opts.get('nuclei_path', 'nuclei')
        try:
            result = subprocess.run(
                [nuclei_path, '-version'],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                version = result.stdout.strip() or result.stderr.strip()
                self.info(f"Nuclei available: {version}")
                self._nuclei_available = True

                # Auto-update templates
                if self.opts.get('auto_update_templates', True):
                    self._update_templates(nuclei_path)
            else:
                self.error(f"Nuclei returned error: {result.stderr}")
                self._nuclei_available = False
        except FileNotFoundError:
            self.error(f"Nuclei binary not found at '{nuclei_path}'. "
                       "Install from https://github.com/projectdiscovery/nuclei")
            self._nuclei_available = False
        except subprocess.TimeoutExpired:
            self.error("Nuclei version check timed out")
            self._nuclei_available = False

        return self._nuclei_available

    def _update_templates(self, nuclei_path: str) -> None:
        """Update Nuclei templates."""
        self.info("Updating Nuclei templates...")
        try:
            subprocess.run(
                [nuclei_path, '-ut'],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.info("Nuclei templates updated")
        except Exception as e:
            self.debug(f"Template update failed (non-fatal): {e}")

    def _run_nuclei(self, targets: list[str]) -> list[dict]:
        """Run Nuclei against a list of targets.

        Args:
            targets: List of hostnames, IPs, or URLs.

        Returns:
            List of parsed finding dicts from Nuclei JSON output.
        """
        nuclei_path = self.opts.get('nuclei_path', 'nuclei')

        # Write targets to temp file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, prefix='sf_nuclei_'
        ) as tf:
            for t in targets:
                tf.write(t + '\n')
            targets_file = tf.name

        # Build command
        cmd = [
            nuclei_path,
            '-l', targets_file,
            '-jsonl',                   # JSON Lines output
            '-silent',                  # Suppress banner
            '-nc',                      # No color
            '-rl', str(self.opts.get('rate_limit', 50)),
            '-bs', str(self.opts.get('bulk_size', 25)),
            '-c', str(self.opts.get('concurrency', 10)),
            '-timeout', str(self.opts.get('timeout', 10)),
        ]

        # Severity filter
        severity = self.opts.get('severity_filter', 'info,low,medium,high,critical')
        if severity:
            cmd.extend(['-severity', severity])

        # Tag filters
        tags = self.opts.get('template_tags', '')
        if tags:
            cmd.extend(['-tags', tags])

        exclude_tags = self.opts.get('template_exclude_tags', 'dos,fuzz')
        if exclude_tags:
            cmd.extend(['-etags', exclude_tags])

        # Custom templates
        custom_dir = self.opts.get('custom_templates_dir', '')
        if custom_dir and os.path.isdir(custom_dir):
            cmd.extend(['-t', custom_dir])

        findings = []
        max_duration = self.opts.get('max_scan_duration', 600)

        try:
            self.info(f"Running Nuclei against {len(targets)} target(s)...")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max_duration,
            )

            # Parse JSON Lines output
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    finding = json.loads(line)
                    findings.append(finding)
                except json.JSONDecodeError:
                    self.debug(f"Skipping non-JSON line: {line[:100]}")

            if proc.returncode != 0 and not findings:
                stderr_snippet = (proc.stderr or "")[:500]
                self.debug(f"Nuclei stderr: {stderr_snippet}")

        except subprocess.TimeoutExpired:
            self.error(f"Nuclei scan timed out after {max_duration}s")
        except Exception as e:
            self.error(f"Nuclei execution failed: {e}")
        finally:
            try:
                os.unlink(targets_file)
            except OSError:
                pass

        self.info(f"Nuclei returned {len(findings)} finding(s)")
        return findings

    def _severity_to_event_type(self, severity: str) -> str:
        """Map Nuclei severity to SpiderFoot event type."""
        severity = (severity or "").lower()
        mapping = {
            "critical": "VULNERABILITY_CVE_CRITICAL",
            "high": "VULNERABILITY_CVE_HIGH",
            "medium": "VULNERABILITY_CVE_MEDIUM",
            "low": "VULNERABILITY_CVE_LOW",
            "info": "VULNERABILITY_GENERAL",
        }
        return mapping.get(severity, "VULNERABILITY_GENERAL")

    def _format_finding(self, finding: dict) -> str:
        """Format a Nuclei finding into a human-readable string."""
        info = finding.get("info", {})
        template_id = finding.get("template-id", finding.get("templateID", "unknown"))
        name = info.get("name", template_id)
        severity = info.get("severity", "unknown")
        matched_at = finding.get("matched-at", finding.get("host", ""))
        matcher_name = finding.get("matcher-name", finding.get("matcher_name", ""))
        extracted = finding.get("extracted-results", [])
        description = info.get("description", "")

        parts = [
            f"[Nuclei] {name}",
            f"  Severity: {severity.upper()}",
            f"  Template: {template_id}",
            f"  Matched:  {matched_at}",
        ]
        if matcher_name:
            parts.append(f"  Matcher:  {matcher_name}")
        if description:
            parts.append(f"  Details:  {description[:500]}")

        # CVE references
        cve_ids = info.get("classification", {}).get("cve-id") or []
        if cve_ids:
            parts.append(f"  CVEs:     {', '.join(cve_ids)}")

        # CWE
        cwe_ids = info.get("classification", {}).get("cwe-id") or []
        if cwe_ids:
            parts.append(f"  CWEs:     {', '.join(cwe_ids)}")

        # CVSS
        cvss_score = info.get("classification", {}).get("cvss-score")
        if cvss_score:
            parts.append(f"  CVSS:     {cvss_score}")

        # Tags
        tags = info.get("tags") or []
        if tags:
            tag_list = tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",")]
            parts.append(f"  Tags:     {', '.join(tag_list[:10])}")

        if extracted:
            parts.append(f"  Extracted: {', '.join(str(e) for e in extracted[:5])}")

        return "\n".join(parts)

    def _extract_technologies(self, finding: dict) -> list[str]:
        """Extract technology names from info-level Nuclei findings."""
        info = finding.get("info", {})
        tags = info.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        techs = []
        # Technology detection templates often have specific tags
        template_id = finding.get("template-id", finding.get("templateID", ""))
        if "tech-detect" in template_id or "technologies" in template_id:
            matcher = finding.get("matcher-name", finding.get("matcher_name", ""))
            if matcher:
                techs.append(matcher)

        return techs

    def handleEvent(self, event):
        """Handle an incoming event by running Nuclei scans."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        # Check Nuclei availability
        if not self._check_nuclei():
            self.errorState = True
            return

        # Dedup
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already scanned.")
            return
        self.results[eventData] = True

        # Skip info-only if not wanted
        if not self.opts.get('include_info_findings', False):
            pass  # Filtering happens in severity_filter

        # Determine target format
        target = eventData
        if eventName in ("INTERNET_NAME", "DOMAIN_NAME"):
            # Scan as hostname — Nuclei will probe HTTP/HTTPS
            target = eventData
        elif eventName == "IP_ADDRESS":
            if not self.opts.get('scan_ips', True):
                return
            target = eventData
        elif eventName == "LINKED_URL_INTERNAL":
            if not self.opts.get('scan_urls', True):
                return
            target = eventData

        if self.checkForStop():
            return

        # Run Nuclei
        findings = self._run_nuclei([target])

        for finding in findings:
            if self.checkForStop():
                return

            info = finding.get("info", {})
            severity = info.get("severity", "info")

            # Skip info if not wanted
            if severity == "info" and not self.opts.get("include_info_findings", False):
                # Still extract technologies from info findings
                for tech in self._extract_technologies(finding):
                    tech_event = SpiderFootEvent(
                        "WEBSERVER_TECHNOLOGY", tech, self.__name__, event
                    )
                    self.notifyListeners(tech_event)
                continue

            # Emit raw data
            raw_event = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(finding, indent=2), self.__name__, event
            )
            self.notifyListeners(raw_event)

            # Emit typed vulnerability event
            event_type = self._severity_to_event_type(severity)
            formatted = self._format_finding(finding)
            vuln_event = SpiderFootEvent(
                event_type, formatted, self.__name__, event
            )
            self.notifyListeners(vuln_event)

            # Extract technology detections
            for tech in self._extract_technologies(finding):
                tech_event = SpiderFootEvent(
                    "WEBSERVER_TECHNOLOGY", tech, self.__name__, event
                )
                self.notifyListeners(tech_event)
