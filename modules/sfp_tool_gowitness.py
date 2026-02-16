"""SpiderFoot module: gowitness - Web page screenshotting.

Integrates gowitness for capturing screenshots of discovered web pages,
providing visual confirmation of web application state.

Requires: gowitness binary in PATH or configured via gowitness_path option.
Install: go install -v github.com/sensepost/gowitness@latest
Note: Requires chromium/chrome for headless screenshotting.
"""

import json
import os
import subprocess
import tempfile

from spiderfoot import SpiderFootModernPlugin


class sfp_tool_gowitness(SpiderFootModernPlugin):
    """Web page screenshotting via gowitness."""

    meta = {
        "name": "Tool - gowitness",
        "summary": "Capture web page screenshots for visual analysis.",
        "flags": ["tool", "slow"],
        "useCases": ["Investigate", "Footprint"],
        "categories": ["Content Analysis"],
        "toolDetails": {
            "binaryName": "gowitness",
            "installUrl": "https://github.com/sensepost/gowitness",
        },
    }

    opts = {
        "gowitness_path": "",
        "chrome_path": "",
        "timeout": 15,
        "resolution": "1440,900",
        "delay": 2,
        "max_targets": 100,
        "run_timeout": 60,
    }

    optdescs = {
        "gowitness_path": "Path to gowitness binary. Leave blank to use PATH.",
        "chrome_path": "Path to chromium/chrome binary. Leave blank to auto-detect.",
        "timeout": "Page load timeout in seconds.",
        "resolution": "Screenshot resolution (width,height).",
        "delay": "Delay in seconds after page load before screenshot.",
        "max_targets": "Maximum pages to screenshot.",
        "run_timeout": "Timeout per screenshot in seconds.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        self.sf = sfc
        self.results = self.tempStorage()
        if userOpts:
            for opt in list(self.opts.keys()):
                self.opts[opt] = userOpts.get(opt, self.opts[opt])

    def watchedEvents(self):
        return ["LINKED_URL_INTERNAL", "DOMAIN_NAME"]

    def producedEvents(self):
        return ["RAW_RIR_DATA"]

    def _find_binary(self):
        custom = self.opts.get("gowitness_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for name in ("gowitness", "gowitness.exe"):
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
            self.error("gowitness binary not found.")
            self.errorState = True
            return

        target = data if data.startswith("http") else f"https://{data}"
        output_dir = tempfile.mkdtemp(prefix="gowitness_")

        res = self.opts["resolution"].split(",")
        width = res[0] if len(res) > 0 else "1440"
        height = res[1] if len(res) > 1 else "900"

        cmd = [
            binary,
            "single",
            target,
            "--screenshot-path", output_dir,
            "--timeout", str(self.opts["timeout"]),
            "--delay", str(self.opts["delay"]),
            "--resolution-x", width,
            "--resolution-y", height,
            "--disable-logging",
        ]

        if self.opts["chrome_path"]:
            cmd.extend(["--chrome-path", self.opts["chrome_path"]])

        try:
            env = os.environ.copy()
            env["CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu --disable-dev-shm-usage"

            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["run_timeout"],
                env=env,
            )

            # Report screenshot capture result
            screenshot_files = []
            if os.path.isdir(output_dir):
                for fname in os.listdir(output_dir):
                    if fname.endswith(".png"):
                        screenshot_files.append(os.path.join(output_dir, fname))

            summary = {
                "tool": "gowitness",
                "url": target,
                "screenshots": len(screenshot_files),
                "output_dir": output_dir,
            }

            if proc.returncode == 0:
                summary["status"] = "success"
            else:
                summary["status"] = "partial"
                summary["stderr"] = proc.stderr[:300] if proc.stderr else ""

            raw = json.dumps(summary, indent=2)
            evt = self.sf.SpiderFootEvent(
                "RAW_RIR_DATA", raw, self.__name__, event
            )
            self.notifyListeners(evt)

            self.info(f"gowitness captured {len(screenshot_files)} screenshot(s) for {target}")

        except subprocess.TimeoutExpired:
            self.error(f"gowitness timed out for {target}")
        except Exception as e:
            self.error(f"gowitness error: {e}")
        finally:
            import shutil
            try:
                shutil.rmtree(output_dir, ignore_errors=True)
            except OSError:
                pass
