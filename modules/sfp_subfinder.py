"""SpiderFoot module: subfinder - Passive subdomain discovery.

Integrates ProjectDiscovery's subfinder for fast passive subdomain
enumeration using multiple sources (APIs, certificate transparency,
search engines, etc.).

Requires: subfinder binary in PATH or configured via subfinder_path option.
Install: go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_subfinder(SpiderFootAsyncPlugin):
    """Passive subdomain discovery via ProjectDiscovery subfinder."""

    meta = {
        "name": "Tool - subfinder",
        "summary": "Passive subdomain enumeration using ProjectDiscovery subfinder.",
        "flags": ["tool"],
        "useCases": ["Investigate", "Footprint", "Passive"],
        "categories": ["Passive DNS"],
        "toolDetails": {
            "binaryName": "subfinder",
            "installUrl": "https://github.com/projectdiscovery/subfinder",
        },
        "dataSource": {
            "website": "https://github.com/projectdiscovery/subfinder",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/projectdiscovery/subfinder"],
            "description": "Passive subdomain enumeration tool by ProjectDiscovery.",
        },
    }

    opts = {
        "subfinder_path": "",
        "threads": 30,
        "timeout": 30,
        "max_enum_time": 10,
        "all_sources": False,
        "recursive": False,
        "exclude_sources": "",
        "use_sources": "",
        "rate_limit": 0,
        "max_results": 2000,
    }

    optdescs = {
        "subfinder_path": "Path to subfinder binary. Leave blank to use PATH.",
        "threads": "Number of concurrent goroutines for resolving.",
        "timeout": "Timeout in seconds for individual sources.",
        "max_enum_time": "Maximum time in minutes for enumeration.",
        "all_sources": "Use all available sources (includes slower ones).",
        "recursive": "Use recursion to find more subdomains.",
        "exclude_sources": "Comma-separated sources to exclude.",
        "use_sources": "Comma-separated specific sources to use (overrides default).",
        "rate_limit": "Maximum number of HTTP requests per second (0=unlimited).",
        "max_results": "Maximum number of subdomains to return.",
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
            "DOMAIN_NAME",
            "RAW_RIR_DATA",
        ]

    def _find_subfinder(self) -> str | None:
        """Find the subfinder binary."""
        custom = self.opts.get("subfinder_path", "")
        if custom and os.path.isfile(custom):
            return custom

        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "subfinder")
            if os.path.isfile(candidate):
                return candidate
            candidate_exe = candidate + ".exe"
            if os.path.isfile(candidate_exe):
                return candidate_exe

        return None

    def _build_cmd(self, subfinder_path: str, domain: str, output_file: str) -> list[str]:
        """Build subfinder command line."""
        cmd = [
            subfinder_path,
            "-d", domain,
            "-o", output_file,
            "-oJ",  # JSON output
            "-silent",
            "-t", str(self.opts["threads"]),
            "-timeout", str(self.opts["timeout"]),
            "-max-time", str(self.opts["max_enum_time"]),
        ]

        if self.opts["all_sources"]:
            cmd.append("-all")
        if self.opts["recursive"]:
            cmd.append("-recursive")
        if self.opts["exclude_sources"]:
            cmd.extend(["-es", self.opts["exclude_sources"]])
        if self.opts["use_sources"]:
            cmd.extend(["-s", self.opts["use_sources"]])
        if self.opts["rate_limit"] > 0:
            cmd.extend(["-rL", str(self.opts["rate_limit"])])

        return cmd

    def _parse_results(self, output_file: str, parent_event: Any) -> int:
        """Parse subfinder JSON output and emit events. Returns count."""
        if not os.path.exists(output_file):
            return 0

        count = 0
        with open(output_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if count >= self.opts["max_results"]:
                    self.info(f"Max results ({self.opts['max_results']}) reached")
                    break

                # Try JSON format
                subdomain = None
                source = ""
                try:
                    data = json.loads(line)
                    subdomain = data.get("host", "").strip().lower()
                    source = data.get("source", "")
                except json.JSONDecodeError:
                    # Plain text fallback
                    subdomain = line.strip().lower()

                if not subdomain or subdomain in self.results:
                    continue

                self.results[subdomain] = True
                count += 1

                # Emit INTERNET_NAME for subdomains
                evt = self.sf.SpiderFootEvent(
                    "INTERNET_NAME", subdomain, self.__name__, parent_event
                )
                self.notifyListeners(evt)

                # Log source for debugging
                if source:
                    self.debug(f"Found {subdomain} via {source}")

        return count

    def handleEvent(self, event):
        data = event.data

        if self.errorState:
            return

        # Only process domains, not other event types
        if event.eventType == "ROOT":
            # Extract domain from scan target
            target = self.sf.targetValue
            if not target:
                return
            data = target

        if data in self.results:
            self.debug(f"Skipping already-enumerated domain: {data}")
            return
        self.results[data] = True

        subfinder_path = self._find_subfinder()
        if not subfinder_path:
            self.error(
                "subfinder binary not found. Install from "
                "https://github.com/projectdiscovery/subfinder"
            )
            self.errorState = True
            return

        # Create output file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as outfile:
            output_path = outfile.name

        try:
            cmd = self._build_cmd(subfinder_path, data, output_path)
            self.debug(f"Running: {' '.join(cmd)}")

            timeout_secs = (self.opts["max_enum_time"] + 2) * 60
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_secs,
            )

            if proc.returncode != 0 and proc.stderr:
                self.debug(f"subfinder stderr: {proc.stderr[:500]}")

            count = self._parse_results(output_path, event)
            self.info(f"subfinder found {count} subdomains for {data}")

            # Emit raw output summary
            if count > 0:
                summary = {
                    "tool": "subfinder",
                    "domain": data,
                    "subdomains_found": count,
                }
                raw = json.dumps(summary, indent=2)
                evt = self.sf.SpiderFootEvent(
                    "RAW_RIR_DATA", raw, self.__name__, event
                )
                self.notifyListeners(evt)

        except subprocess.TimeoutExpired:
            self.error(f"subfinder timed out after {timeout_secs}s for {data}")
        except Exception as e:
            self.error(f"subfinder error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
