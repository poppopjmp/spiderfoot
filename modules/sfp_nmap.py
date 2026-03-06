from __future__ import annotations

"""SpiderFoot plug-in module: Nmap port scanner integration.

Runs Nmap against discovered IP addresses and hostnames to detect
open ports, service versions, and OS fingerprints.

Nmap must be installed on the system (or available in Docker).
Requires root/sudo for SYN scans and OS detection; falls back
to TCP connect scan for unprivileged users.

Event flow:
  IN:  IP_ADDRESS, INTERNET_NAME, DOMAIN_NAME, NETBLOCK_OWNER
  OUT: TCP_PORT_OPEN, TCP_PORT_OPEN_BANNER, UDP_PORT_OPEN,
       OPERATING_SYSTEM, RAW_RIR_DATA, WEBSERVER_BANNER
"""

import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_nmap(SpiderFootAsyncPlugin):
    """Nmap — network exploration and port scanning."""

    meta = {
        'name': "Nmap Port Scanner",
        'summary': "Run Nmap scans against discovered hosts to identify open ports, running services, and OS fingerprints.",
        'flags': ["slow", "invasive"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Crawling and Scanning"],
        'toolDetails': {
            'name': "Nmap",
            'description': "Network exploration tool and security/port scanner.",
            'website': 'https://nmap.org/',
            'repository': 'https://github.com/nmap/nmap',
        },
        'dataSource': {
            'website': "https://nmap.org/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://nmap.org/book/man.html",
                "https://nmap.org/nsedoc/",
            ],
            'favIcon': "https://nmap.org/favicon.ico",
            'logo': "https://nmap.org/images/sitelogo.png",
            'description': "Nmap is a free and open source utility for network "
            "discovery and security auditing, supporting port scanning, service "
            "detection, OS fingerprinting, and NSE script scanning.",
        },
    }

    opts = {
        'nmap_path': 'nmap',
        'scan_type': 'default',       # default, syn, connect, udp, comprehensive
        'port_range': '-F',           # -F (fast/top 100), or custom like 1-1000
        'service_detection': True,
        'os_detection': False,
        'script_scan': '',            # NSE scripts: 'default', 'vuln', 'safe', etc.
        'timing': 'T3',              # T0-T5
        'max_retries': 2,
        'host_timeout': 300,          # seconds per host
        'max_scan_duration': 600,     # total timeout
        'scan_netblocks': False,
        'max_netblock': 24,           # /24 minimum
    }

    optdescs = {
        'nmap_path': "Path to the nmap binary.",
        'scan_type': "Scan type: 'default' (auto-detect), 'syn' (requires root), 'connect', 'udp', 'comprehensive'.",
        'port_range': "Port range: '-F' (fast/top 100), '--top-ports 1000', or '1-65535'.",
        'service_detection': "Enable service/version detection (-sV).",
        'os_detection': "Enable OS detection (-O, requires root).",
        'script_scan': "NSE script categories to run (e.g. 'default', 'vuln', 'safe'). Empty = none.",
        'timing': "Timing template: T0 (paranoid) to T5 (insane). Default T3.",
        'max_retries': "Max probe retries per port.",
        'host_timeout': "Timeout per host in seconds.",
        'max_scan_duration': "Total Nmap invocation timeout in seconds.",
        'scan_netblocks': "Scan entire netblocks (careful!).",
        'max_netblock': "Minimum CIDR prefix to scan (24 = /24, 16 = /16).",
    }

    results = None
    errorState = False
    _nmap_checked = False
    _nmap_available = False
    _is_root = False

    def setup(self, sfc, userOpts=None):
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()
        self._nmap_checked = False
        self._nmap_available = False
        self._is_root = os.geteuid() == 0 if hasattr(os, 'geteuid') else False

    def watchedEvents(self):
        events = ["IP_ADDRESS", "INTERNET_NAME", "DOMAIN_NAME"]
        if self.opts.get('scan_netblocks', False):
            events.append("NETBLOCK_OWNER")
        return events

    def producedEvents(self):
        return [
            "TCP_PORT_OPEN",
            "TCP_PORT_OPEN_BANNER",
            "UDP_PORT_OPEN",
            "OPERATING_SYSTEM",
            "RAW_RIR_DATA",
            "WEBSERVER_BANNER",
        ]

    def _check_nmap(self) -> bool:
        """Verify nmap is installed."""
        if self._nmap_checked:
            return self._nmap_available

        self._nmap_checked = True
        nmap_path = self.opts.get('nmap_path', 'nmap')
        try:
            result = subprocess.run(
                [nmap_path, '--version'],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                self.info(f"Nmap available: {version_line}")
                self._nmap_available = True
            else:
                self.error("Nmap returned an error")
                self._nmap_available = False
        except FileNotFoundError:
            self.error(f"Nmap not found at '{nmap_path}'. Install from https://nmap.org/")
            self._nmap_available = False
        except subprocess.TimeoutExpired:
            self.error("Nmap version check timed out")
            self._nmap_available = False

        return self._nmap_available

    def _build_nmap_cmd(self, target: str) -> list[str]:
        """Build nmap command-line arguments."""
        nmap_path = self.opts.get('nmap_path', 'nmap')
        cmd = [nmap_path]

        # Scan type
        scan_type = self.opts.get('scan_type', 'default')
        if scan_type == 'syn' and self._is_root:
            cmd.append('-sS')
        elif scan_type == 'udp' and self._is_root:
            cmd.append('-sU')
        elif scan_type == 'comprehensive' and self._is_root:
            cmd.extend(['-sS', '-sU'])
        elif scan_type == 'connect' or not self._is_root:
            cmd.append('-sT')
        else:
            # Default: SYN if root, connect if not
            cmd.append('-sS' if self._is_root else '-sT')

        # Port range
        port_range = self.opts.get('port_range', '-F')
        if port_range.startswith('-'):
            cmd.append(port_range)
        elif port_range.startswith('--'):
            cmd.extend(port_range.split())
        else:
            cmd.extend(['-p', port_range])

        # Service detection
        if self.opts.get('service_detection', True):
            cmd.append('-sV')

        # OS detection
        if self.opts.get('os_detection', False) and self._is_root:
            cmd.append('-O')

        # NSE scripts
        scripts = self.opts.get('script_scan', '')
        if scripts:
            cmd.extend(['--script', scripts])

        # Timing
        timing = self.opts.get('timing', 'T3')
        cmd.append(f'-{timing}')

        # Retries
        max_retries = self.opts.get('max_retries', 2)
        cmd.extend(['--max-retries', str(max_retries)])

        # Host timeout
        host_timeout = self.opts.get('host_timeout', 300)
        cmd.extend(['--host-timeout', f'{host_timeout}s'])

        # XML output
        cmd.extend(['-oX', '-'])  # stdout XML

        # No ping (we already know host is up)
        cmd.append('-Pn')

        # Target
        cmd.append(target)

        return cmd

    def _parse_nmap_xml(self, xml_output: str) -> list[dict]:
        """Parse Nmap XML output into structured findings."""
        findings = []
        try:
            root = ET.fromstring(xml_output)
        except ET.ParseError as e:
            self.error(f"Failed to parse Nmap XML: {e}")
            return findings

        for host in root.findall('.//host'):
            host_status = host.find('status')
            if host_status is not None and host_status.get('state') != 'up':
                continue

            # Get host address
            addr_elem = host.find('address')
            host_addr = addr_elem.get('addr', '') if addr_elem is not None else ''

            # OS detection
            os_elem = host.find('.//osmatch')
            if os_elem is not None:
                os_name = os_elem.get('name', '')
                os_accuracy = os_elem.get('accuracy', '')
                if os_name:
                    findings.append({
                        'type': 'os',
                        'host': host_addr,
                        'os': os_name,
                        'accuracy': os_accuracy,
                    })

            # Ports
            for port in host.findall('.//port'):
                state_elem = port.find('state')
                if state_elem is None:
                    continue

                port_state = state_elem.get('state', '')
                if port_state != 'open':
                    continue

                protocol = port.get('protocol', 'tcp')
                portid = port.get('portid', '')

                service_elem = port.find('service')
                service_name = ''
                service_product = ''
                service_version = ''
                service_extra = ''

                if service_elem is not None:
                    service_name = service_elem.get('name', '')
                    service_product = service_elem.get('product', '')
                    service_version = service_elem.get('version', '')
                    service_extra = service_elem.get('extrainfo', '')

                service_banner = ' '.join(filter(None, [
                    service_product, service_version, service_extra
                ])).strip()

                findings.append({
                    'type': 'port',
                    'host': host_addr,
                    'protocol': protocol,
                    'port': portid,
                    'state': port_state,
                    'service': service_name,
                    'banner': service_banner,
                })

                # Script output
                for script in port.findall('script'):
                    script_id = script.get('id', '')
                    script_output = script.get('output', '')
                    if script_output:
                        findings.append({
                            'type': 'script',
                            'host': host_addr,
                            'port': portid,
                            'protocol': protocol,
                            'script': script_id,
                            'output': script_output[:2000],
                        })

        return findings

    def _run_nmap(self, target: str) -> list[dict]:
        """Run Nmap against a single target and return findings."""
        cmd = self._build_nmap_cmd(target)
        max_duration = self.opts.get('max_scan_duration', 600)

        try:
            self.info(f"Running Nmap scan against {target}")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=max_duration,
            )

            if proc.returncode != 0 and not proc.stdout:
                self.error(f"Nmap failed: {proc.stderr[:500]}")
                return []

            return self._parse_nmap_xml(proc.stdout)

        except subprocess.TimeoutExpired:
            self.error(f"Nmap scan timed out after {max_duration}s")
        except Exception as e:
            self.error(f"Nmap execution failed: {e}")

        return []

    def handleEvent(self, event):
        """Handle incoming events by running Nmap scans."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if not self._check_nmap():
            self.errorState = True
            return

        # Dedup
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already scanned.")
            return
        self.results[eventData] = True

        if eventName == 'NETBLOCK_OWNER':
            if not self.opts.get('scan_netblocks', False):
                return
            from netaddr import IPNetwork
            net_size = IPNetwork(eventData).prefixlen
            if net_size < self.opts.get('max_netblock', 24):
                self.debug(f"Network /{net_size} too large, skipping")
                return

        if self.checkForStop():
            return

        # Run scan
        findings = self._run_nmap(eventData)

        # Emit raw data
        if findings:
            raw_event = SpiderFootEvent(
                "RAW_RIR_DATA",
                json.dumps(findings, indent=2),
                self.__name__, event
            )
            self.notifyListeners(raw_event)

        for finding in findings:
            if self.checkForStop():
                return

            ftype = finding.get('type', '')

            if ftype == 'port':
                protocol = finding.get('protocol', 'tcp')
                port = finding.get('port', '')
                service = finding.get('service', '')
                banner = finding.get('banner', '')
                host = finding.get('host', eventData)

                port_info = f"{host}:{port}/{protocol}"
                if service:
                    port_info += f" ({service})"

                if protocol == 'tcp':
                    evt = SpiderFootEvent(
                        "TCP_PORT_OPEN", port_info, self.__name__, event
                    )
                    self.notifyListeners(evt)

                    if banner:
                        banner_info = f"{host}:{port} - {banner}"
                        evt = SpiderFootEvent(
                            "TCP_PORT_OPEN_BANNER", banner_info, self.__name__, event
                        )
                        self.notifyListeners(evt)

                        # Web server detection
                        if service in ('http', 'https', 'http-proxy', 'http-alt'):
                            evt = SpiderFootEvent(
                                "WEBSERVER_BANNER", banner, self.__name__, event
                            )
                            self.notifyListeners(evt)

                elif protocol == 'udp':
                    evt = SpiderFootEvent(
                        "UDP_PORT_OPEN", port_info, self.__name__, event
                    )
                    self.notifyListeners(evt)

            elif ftype == 'os':
                os_name = finding.get('os', '')
                accuracy = finding.get('accuracy', '')
                host = finding.get('host', eventData)
                os_info = f"{os_name} ({accuracy}% confidence) [{host}]"
                evt = SpiderFootEvent(
                    "OPERATING_SYSTEM", os_info, self.__name__, event
                )
                self.notifyListeners(evt)
