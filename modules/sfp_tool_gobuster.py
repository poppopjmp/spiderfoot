# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_tool_gobuster
# Purpose:     SpiderFoot plug-in for using the 'gobuster' tool.
#              Tool: https://github.com/OJ/gobuster
#
# Author:      <van1sh@van1shland.io>
#
# Created:     2025-03-08
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import os.path
import tempfile
import paramiko
import io

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_tool_gobuster(SpiderFootPlugin):
    meta = {
        "name": "Tools - Gobuster",
        "summary": "Identify web paths on target websites using the Gobuster tool.",
        "flags": ["tool", "slow", "invasive"],
        "useCases": ["Footprint", "Investigate"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "name": "Gobuster",
            "description": "Gobuster is a tool used to brute-force URIs (directories and files) "
            "in web sites, DNS subdomains, Virtual Host names, Open Amazon S3 "
            "buckets, and TFTP servers.",
            "website": "https://github.com/OJ/gobuster",
            "repository": "https://github.com/OJ/gobuster",
        },
    }

    # Default options
    opts = {
        "gobuster_path": "",
        "wordlist": "",
        "threads": 10,
        "timeout": 30,
        "status_codes": "200,204,301,302,307,401,403",
        "follow_redirects": True,
        "extensions": "php,asp,aspx,jsp,html,htm,js",
        "use_proxy": False,
        # Remote execution options
        "remote_enabled": False,
        "remote_host": "",
        "remote_user": "",
        "remote_password": "",
        "remote_ssh_key": "",  # (deprecated, for backward compatibility)
        "remote_ssh_key_data": "",  # New: paste private key directly
        "remote_tool_path": "",
        "remote_tool_args": "",
    }

    # Option descriptions
    optdescs = {
        "gobuster_path": "Path to the gobuster binary. If just 'gobuster' then assume it's in the system path.",
        "wordlist": "Path to the wordlist used for brute-forcing.",
        "threads": "Number of concurrent threads (gobuster -t).",
        "timeout": "Timeout in seconds for gobuster requests (gobuster -to).",
        "status_codes": "Comma-separated list of status codes to consider valid (gobuster -s).",
        "follow_redirects": "Follow redirects (gobuster -r)",
        "extensions": "Comma-separated list of file extensions to look for (gobuster -x).",
        "use_proxy": "Use the configured SpiderFoot proxy for scanning.",
        "remote_enabled": "Enable remote execution via SSH (true/false)",
        "remote_host": "Remote SSH host (IP or hostname)",
        "remote_user": "Remote SSH username",
        "remote_password": "Remote SSH password (optional if using key)",
        "remote_ssh_key": "(Deprecated) Path to SSH private key (use remote_ssh_key_data instead)",
        "remote_ssh_key_data": "Paste your SSH private key here (PEM format, multi-line)",
        "remote_tool_path": "Path to the tool on the remote machine",
        "remote_tool_args": "Extra arguments/config for the tool on the remote machine",
    }

    # Target
    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["URL"]

    # What events this module produces
    def producedEvents(self):
        return ["URL_DIRECTORY", "URL_FILE"]

    def execute_command(self, cmd):
        """Execute an external command and return the output."""
        self.debug(f"Executing command: {' '.join(cmd)}")
        output_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        output_file.close()

        try:
            if not self.sf.outputProgress(f"Running Gobuster against {cmd[-1]}"):
                return None

            cmd = " ".join(cmd) + f" -o {output_file.name}"
            ret_val = self.sf.execute(cmd, useShell=True)

            if ret_val:
                self.error(f"Failed to execute gobuster: {ret_val}")
                return None

            return output_file.name
        except Exception as e:
            self.error(f"Failed to execute gobuster: {e}")
            return None
        finally:
            try:
                if not os.path.isfile(output_file.name):
                    os.unlink(output_file.name)
            except Exception:
                pass

    def run_remote_tool(self, target_url):
        host = self.opts.get("remote_host")
        user = self.opts.get("remote_user")
        password = self.opts.get("remote_password")
        ssh_key_data = self.opts.get("remote_ssh_key_data")
        ssh_key_path = self.opts.get("remote_ssh_key")
        tool_path = self.opts.get("remote_tool_path")
        tool_args = self.opts.get("remote_tool_args", "")
        wordlist = self.opts.get("wordlist")
        threads = self.opts.get("threads", 10)
        status_codes = self.opts.get("status_codes", "200,204,301,302,307,401,403")
        timeout = self.opts.get("timeout", 30)
        extensions = self.opts.get("extensions", "")
        follow_redirects = self.opts.get("follow_redirects", True)
        if not (host and user and tool_path and wordlist):
            self.error("Remote execution enabled but host/user/tool_path/wordlist not set.")
            return None
        cmd = f'{tool_path} dir -q -u "{target_url}" -w "{wordlist}" -t {threads} -s {status_codes} -to {timeout}s -j'
        if follow_redirects:
            cmd += ' -r'
        if extensions:
            cmd += f' -x {extensions}'
        if tool_args:
            cmd += f' {tool_args}'
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            pkey = None
            if ssh_key_data:
                try:
                    pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_key_data))
                except Exception as e:
                    self.error(f"Failed to parse pasted SSH key: {e}")
                    return None
            if pkey:
                ssh.connect(host, username=user, pkey=pkey, password=password or None, timeout=10)
            elif ssh_key_path:
                ssh.connect(host, username=user, key_filename=ssh_key_path, password=password or None, timeout=10)
            else:
                ssh.connect(host, username=user, password=password or None, timeout=10)
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode()
            err = stderr.read().decode()
            ssh.close()
            if err:
                self.error(f"Remote tool error: {err}")
                return None
            try:
                return json.loads(output)
            except Exception as e:
                self.error(f"Error parsing remote tool output: {e}")
                return None
        except Exception as e:
            self.error(f"SSH connection or execution failed: {e}")
            return None

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        # Remote execution support (exclusive)
        if self.opts.get("remote_enabled"):
            results = self.run_remote_tool(eventData)
            if not results:
                return
            # Process the results (same as local)
            for result in results.get("results", []):
                path = result.get("path")
                status = result.get("status")
                if not path:
                    continue
                base_url = eventData.rstrip("/")
                full_url = f"{base_url}{path}"
                event_type = "URL_DIRECTORY" if path.endswith("/") else "URL_FILE"
                evt = SpiderFootEvent(event_type, full_url, self.__name__, event)
                self.notifyListeners(evt)
            return

        gobuster_path = self.opts["gobuster_path"]
        wordlist = self.opts["wordlist"]

        if not gobuster_path:
            self.error(
                "You enabled sfp_tool_gobuster but did not set a path to the tool!"
            )
            self.errorState = True
            return

        if not wordlist:
            self.error(
                "You enabled sfp_tool_gobuster but did not set a wordlist!")
            self.errorState = True
            return

        if (
            not os.path.isfile(gobuster_path) and
            "/" not in gobuster_path and
            "\\" not in gobuster_path
        ):
            cmd = ["which", gobuster_path]
            path = self.sf.execute(cmd, useShell=True)
            if not path:
                self.error(f"Gobuster tool '{gobuster_path}' not found")
                self.errorState = True
                return
            gobuster_path = path

        if not os.path.isfile(wordlist):
            self.error(f"Wordlist '{wordlist}' not found")
            self.errorState = True
            return

        # Build the gobuster command
        cmd = [
            gobuster_path,
            "dir",
            "-q",
            "-u",
            eventData,
            "-w",
            wordlist,
            "-t",
            str(self.opts["threads"]),
            "-s",
            self.opts["status_codes"],
            "-to",
            str(self.opts["timeout"]) + "s",
            "-j",  # JSON output format
        ]

        if self.opts["follow_redirects"]:
            cmd.append("-r")

        if self.opts["extensions"]:
            cmd.extend(["-x", self.opts["extensions"]])

        if self.opts["use_proxy"] and self.sf.opts.get("_socks1type"):
            proxy = f"{self.sf.opts.get('_socks1type')}://{self.sf.opts.get('_socks2addr')}:{self.sf.opts.get('_socks3port')}"
            cmd.extend(["--proxy", proxy])

        output_file = self.execute_command(cmd)
        if not output_file:
            return

        try:
            with open(output_file, "r") as file:
                output = file.read()

            try:
                results = json.loads(output)
            except json.JSONDecodeError:
                self.error(
                    f"Could not parse gobuster output as JSON: {output}")
                return

            # Process the results
            for result in results.get("results", []):
                path = result.get("path")
                status = result.get("status")

                if not path:
                    continue

                # Construct the full URL
                base_url = eventData.rstrip("/")
                full_url = f"{base_url}{path}"

                # Determine if it's a directory or a file
                event_type = "URL_DIRECTORY" if path.endswith(
                    "/") else "URL_FILE"

                # Create and notify the event
                evt = SpiderFootEvent(
                    event_type, full_url, self.__name__, event)
                self.notifyListeners(evt)

        except Exception as e:
            self.error(f"Error processing gobuster results: {e}")
        finally:
            # Clean up the temporary file
            try:
                os.unlink(output_file)
            except Exception:
                pass
