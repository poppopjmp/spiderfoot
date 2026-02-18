"""SpiderFoot module: ffuf - Fast web fuzzer.

Integrates ffuf for discovering hidden directories, files, virtual hosts,
and parameters on web servers via dictionary-based fuzzing.

Requires: ffuf binary in PATH or configured via ffuf_path option.
Install: go install -v github.com/ffuf/ffuf/v2@latest
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_ffuf(SpiderFootModernPlugin):
    """Fast web fuzzing for hidden content discovery via ffuf."""

    meta = {
        "name": "Tool - ffuf",
        "summary": "Fast web fuzzer for directory, file, and parameter discovery.",
        "flags": ["tool", "slow", "invasive"],
        "useCases": ["Footprint", "Investigate"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "ffuf",
            "installUrl": "https://github.com/ffuf/ffuf",
        },
        "dataSource": {
            "website": "https://github.com/ffuf/ffuf",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/ffuf/ffuf"],
            "description": "Fast web fuzzer for directory, file, and parameter discovery.",
        },
    }

    opts = {
        "ffuf_path": "",
        "wordlist": "/tools/wordlists/common.txt",
        "threads": 40,
        "rate_limit": 0,
        "timeout": 10,
        "follow_redirects": False,
        "method": "GET",
        "match_codes": "200,204,301,302,307,401,403,405",
        "filter_codes": "",
        "filter_size": "",
        "extensions": "",
        "max_targets": 50,
        "run_timeout": 300,
    }

    optdescs = {
        "ffuf_path": "Path to ffuf binary. Leave blank to use PATH.",
        "wordlist": "Path to wordlist file.",
        "threads": "Number of concurrent threads.",
        "rate_limit": "Rate limit (requests per second, 0=unlimited).",
        "timeout": "HTTP request timeout in seconds.",
        "follow_redirects": "Follow HTTP redirects.",
        "method": "HTTP method.",
        "match_codes": "HTTP status codes to match (comma-separated).",
        "filter_codes": "HTTP status codes to filter out (comma-separated).",
        "filter_size": "Filter responses by size (comma-separated).",
        "extensions": "File extensions to fuzz (e.g. php,asp,html).",
        "max_targets": "Maximum number of targets to fuzz.",
        "run_timeout": "Total run timeout per target in seconds.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["DOMAIN_NAME", "LINKED_URL_INTERNAL"]

    def producedEvents(self):
        return [
            "LINKED_URL_INTERNAL",
            "URL_FORM",
            "HTTP_CODE",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("ffuf_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("ffuf", "ffuf.exe"):
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

        if sum(1 for v in self.results.values() if v) > self.opts["max_targets"]:
            return

        binary = self._find_binary()
        if not binary:
            self.error("ffuf binary not found.")
            self.errorState = True
            return

        wordlist = self.opts["wordlist"]
        if not os.path.isfile(wordlist):
            self.error(f"Wordlist not found: {wordlist}")
            self.errorState = True
            return

        if event.eventType == "DOMAIN_NAME":
            base_url = f"https://{data}/FUZZ"
        else:
            # For URLs, append FUZZ to the path
            base_url = data.rstrip("/") + "/FUZZ"

        output_path = tempfile.mktemp(suffix=".json")

        cmd = [
            binary,
            "-u", base_url,
            "-w", wordlist,
            "-t", str(self.opts["threads"]),
            "-timeout", str(self.opts["timeout"]),
            "-o", output_path,
            "-of", "json",
            "-s",  # silent
        ]

        if self.opts["match_codes"]:
            cmd.extend(["-mc", self.opts["match_codes"]])
        if self.opts["filter_codes"]:
            cmd.extend(["-fc", self.opts["filter_codes"]])
        if self.opts["filter_size"]:
            cmd.extend(["-fs", self.opts["filter_size"]])
        if self.opts["rate_limit"] > 0:
            cmd.extend(["-rate", str(self.opts["rate_limit"])])
        if self.opts["follow_redirects"]:
            cmd.append("-r")
        if self.opts["extensions"]:
            cmd.extend(["-e", self.opts["extensions"]])
        if self.opts["method"] != "GET":
            cmd.extend(["-X", self.opts["method"]])

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["run_timeout"],
            )

            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    try:
                        data_json = json.load(f)
                    except json.JSONDecodeError:
                        return

                results = data_json.get("results", [])
                for result in results:
                    url = result.get("url", "")
                    status = result.get("status", 0)
                    length = result.get("length", 0)

                    if not url or url in self.results:
                        continue
                    self.results[url] = True

                    evt = self.sf.SpiderFootEvent(
                        "LINKED_URL_INTERNAL", url, self.__name__, event
                    )
                    self.notifyListeners(evt)

                    code_info = f"{url} [{status}] [Size: {length}]"
                    evt = self.sf.SpiderFootEvent(
                        "HTTP_CODE", code_info, self.__name__, event
                    )
                    self.notifyListeners(evt)

                self.info(f"ffuf found {len(results)} paths on {base_url}")

        except subprocess.TimeoutExpired:
            self.error(f"ffuf timed out for {base_url}")
        except Exception as e:
            self.error(f"ffuf error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
