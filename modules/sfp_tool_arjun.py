"""SpiderFoot module: arjun - HTTP parameter discovery.

Integrates Arjun for finding hidden HTTP parameters in web applications
by fuzzing GET/POST parameters.

Requires: arjun (pip install arjun).
"""

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_arjun(SpiderFootModernPlugin):
    """HTTP parameter discovery via Arjun."""

    meta = {
        "name": "Tool - Arjun",
        "summary": "Discover hidden HTTP parameters in web applications.",
        "flags": ["tool", "slow", "invasive"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "arjun",
            "installUrl": "https://github.com/s0md3v/Arjun",
        },
    }

    opts = {
        "arjun_path": "",
        "threads": 5,
        "timeout": 15,
        "method": "GET",
        "wordlist": "",
        "stable": True,
        "max_targets": 50,
        "run_timeout": 180,
    }

    optdescs = {
        "arjun_path": "Path to arjun binary. Leave blank to use PATH.",
        "threads": "Number of concurrent threads.",
        "timeout": "Request timeout in seconds.",
        "method": "HTTP method (GET, POST, JSON, XML).",
        "wordlist": "Custom wordlist path (blank=built-in).",
        "stable": "Use stable mode (slower but more reliable).",
        "max_targets": "Maximum number of URLs to test.",
        "run_timeout": "Total run timeout per URL in seconds.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        self.sf = sfc
        self.results = self.tempStorage()
        if userOpts:
            for opt in list(self.opts.keys()):
                self.opts[opt] = userOpts.get(opt, self.opts[opt])

    def watchedEvents(self):
        return ["LINKED_URL_INTERNAL", "URL_FORM"]

    def producedEvents(self):
        return ["URL_FORM", "RAW_RIR_DATA"]

    def _find_binary(self):
        custom = self.opts.get("arjun_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("arjun", "arjun.exe"):
                candidate = os.path.join(p, name)
                if os.path.isfile(candidate):
                    return candidate
        # Check pip venv
        venv_path = "/opt/venv/bin/arjun"
        if os.path.isfile(venv_path):
            return venv_path
        return None

    def handleEvent(self, event):
        data = event.data
        if self.errorState:
            return
        if data in self.results:
            return
        self.results[data] = True

        if not data.startswith("http"):
            return

        if sum(1 for v in self.results.values() if v) > self.opts["max_targets"]:
            return

        binary = self._find_binary()
        if not binary:
            self.error("arjun binary not found. Install with: pip install arjun")
            self.errorState = True
            return

        output_path = tempfile.mktemp(suffix=".json")

        cmd = [
            binary,
            "-u", data,
            "-t", str(self.opts["threads"]),
            "--timeout", str(self.opts["timeout"]),
            "-m", self.opts["method"],
            "-oJ", output_path,
        ]

        if self.opts["wordlist"] and os.path.isfile(self.opts["wordlist"]):
            cmd.extend(["-w", self.opts["wordlist"]])
        if self.opts["stable"]:
            cmd.append("--stable")

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["run_timeout"],
            )

            if os.path.exists(output_path):
                with open(output_path, "r") as f:
                    try:
                        results = json.load(f)
                    except json.JSONDecodeError:
                        return

                # arjun outputs {url: [params]}
                for url, params in results.items():
                    if isinstance(params, list) and params:
                        param_str = "&".join(f"{p}=FUZZ" for p in params)
                        separator = "&" if "?" in url else "?"
                        fuzzed_url = f"{url}{separator}{param_str}"

                        evt = self.sf.SpiderFootEvent(
                            "URL_FORM", fuzzed_url, self.__name__, event
                        )
                        self.notifyListeners(evt)

                        summary = {
                            "tool": "arjun",
                            "url": url,
                            "method": self.opts["method"],
                            "parameters": params,
                        }
                        raw = json.dumps(summary, indent=2)
                        evt = self.sf.SpiderFootEvent(
                            "RAW_RIR_DATA", raw, self.__name__, event
                        )
                        self.notifyListeners(evt)

                        self.info(f"arjun found {len(params)} params on {url}: {', '.join(params)}")

        except subprocess.TimeoutExpired:
            self.error(f"arjun timed out for {data}")
        except Exception as e:
            self.error(f"arjun error: {e}")
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass
