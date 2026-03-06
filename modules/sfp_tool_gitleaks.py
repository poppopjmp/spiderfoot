"""SpiderFoot module: gitleaks - Secret detection in git repositories.

Integrates Gitleaks for detecting hardcoded secrets, API keys,
passwords, and tokens in git repositories and directories.

Requires: gitleaks in PATH (go install github.com/gitleaks/gitleaks/v8@latest).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_tool_gitleaks(SpiderFootAsyncPlugin):
    """Secret detection in git repositories via Gitleaks."""

    meta = {
        "name": "Tool - Gitleaks",
        "summary": "Detect hardcoded secrets, API keys, and credentials in git repos.",
        "flags": ["tool", "slow"],
        "useCases": ["Investigate", "Passive"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "binaryName": "gitleaks",
            "installUrl": "https://github.com/gitleaks/gitleaks",
        },
        "dataSource": {
            "website": "https://github.com/gitleaks/gitleaks",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": ["https://github.com/gitleaks/gitleaks"],
            "description": "Secret detection tool for git repositories.",
        },
    }

    opts = {
        "gitleaks_path": "",
        "timeout": 300,
        "max_targets": 10,
        "config": "",
        "depth": 0,
        "no_git": False,
    }

    optdescs = {
        "gitleaks_path": "Path to gitleaks. Leave blank to use PATH.",
        "timeout": "Scan timeout in seconds.",
        "max_targets": "Maximum number of repos to scan.",
        "config": "Path to custom gitleaks config TOML file.",
        "depth": "Git log depth (0 = full history).",
        "no_git": "Scan directory mode instead of git mode.",
    }

    results = None

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["PUBLIC_CODE_REPO"]

    def producedEvents(self):
        return [
            "PASSWORD_COMPROMISED",
            "VULNERABILITY_GENERAL",
            "RAW_RIR_DATA",
        ]

    def _find_binary(self):
        custom = self.opts.get("gitleaks_path", "")
        if custom and os.path.isfile(custom):
            return custom
        for p in os.environ.get("PATH", "").split(os.pathsep):
            candidate = os.path.join(p, "gitleaks")
            if os.path.isfile(candidate):
                return candidate
        for fallback in ("/usr/local/bin/gitleaks", "/usr/bin/gitleaks"):
            if os.path.isfile(fallback):
                return fallback
        return None

    def _extract_repo_url(self, data):
        """Extract the git clone URL from PUBLIC_CODE_REPO data."""
        if data.startswith("http") and ".git" in data:
            return data
        if "github.com" in data or "gitlab.com" in data or "bitbucket.org" in data:
            url = data.strip().rstrip("/")
            if not url.startswith("http"):
                url = f"https://{url}"
            if not url.endswith(".git"):
                url += ".git"
            return url
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
            self.error("gitleaks not found. Install: go install github.com/gitleaks/gitleaks/v8@latest")
            self.errorState = True
            return

        repo_url = self._extract_repo_url(data)
        if not repo_url:
            self.debug(f"Could not extract git URL from: {data}")
            return

        # Clone to temp directory
        clone_dir = tempfile.mkdtemp(prefix="gitleaks_")
        report_path = os.path.join(clone_dir, "report.json")

        try:
            # Clone the repo
            clone_cmd = ["git", "clone", "--depth", "50", repo_url, os.path.join(clone_dir, "repo")]
            clone_proc = subprocess.run(
                clone_cmd, capture_output=True, text=True, timeout=120,
            )
            if clone_proc.returncode != 0:
                self.debug(f"git clone failed for {repo_url}: {clone_proc.stderr}")
                return

            repo_path = os.path.join(clone_dir, "repo")

            # Run gitleaks
            cmd = [
                binary, "detect",
                "--source", repo_path,
                "--report-format", "json",
                "--report-path", report_path,
                "--exit-code", "0",
            ]

            if self.opts["config"]:
                cmd.extend(["--config", self.opts["config"]])
            if self.opts["depth"]:
                cmd.extend(["--log-opts", f"--max-count={self.opts['depth']}"])
            if self.opts["no_git"]:
                cmd.append("--no-git")

            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.opts["timeout"],
            )

            leak_count = 0
            if os.path.exists(report_path):
                with open(report_path, "r") as f:
                    try:
                        findings = json.load(f)
                    except json.JSONDecodeError:
                        findings = []

                if isinstance(findings, list):
                    for finding in findings:
                        if self.checkForStop():
                            return
                        rule_id = finding.get("RuleID", "unknown")
                        description = finding.get("Description", "Secret detected")
                        file_path = finding.get("File", "")
                        line_num = finding.get("StartLine", "")
                        commit = finding.get("Commit", "")[:12] if finding.get("Commit") else ""
                        match = finding.get("Match", "")
                        secret = finding.get("Secret", "")

                        # Mask the actual secret value
                        if secret and len(secret) > 4:
                            masked = secret[:2] + "***" + secret[-2:]
                        elif secret:
                            masked = "***"
                        else:
                            masked = match[:20] + "..." if match else ""

                        report = (
                            f"[{rule_id}] {description}\n"
                            f"Repo: {repo_url}\n"
                            f"File: {file_path}:{line_num}\n"
                        )
                        if commit:
                            report += f"Commit: {commit}\n"
                        report += f"Match: {masked}"

                        # API keys and passwords are high priority
                        if any(x in rule_id.lower() for x in ("password", "private-key", "secret")):
                            evt = self.sf.SpiderFootEvent(
                                "PASSWORD_COMPROMISED",
                                report,
                                self.__name__,
                                event,
                            )
                        else:
                            evt = self.sf.SpiderFootEvent(
                                "VULNERABILITY_GENERAL",
                                report,
                                self.__name__,
                                event,
                            )
                        self.notifyListeners(evt)
                        leak_count += 1

            self.info(f"gitleaks found {leak_count} secrets in {repo_url}")

        except subprocess.TimeoutExpired:
            self.error(f"gitleaks timed out for {repo_url}")
        except Exception as e:
            self.error(f"gitleaks error: {e}")
        finally:
            # Cleanup cloned repo
            import shutil
            try:
                shutil.rmtree(clone_dir, ignore_errors=True)
            except Exception:
                pass
