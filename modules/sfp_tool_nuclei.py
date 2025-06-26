# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_tool_nuclei
# Purpose:      SpiderFoot plug-in for using the 'Nuclei' tool.
#               Tool: https://github.com/EnableSecurity/nuclei
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     2022-04-02
# Copyright:   (c) Steve Micallef 2022
# Licence:     MIT
# -------------------------------------------------------------------------------

import os
import re
import sys
import json
from netaddr import IPNetwork
from subprocess import Popen, PIPE, TimeoutExpired
import paramiko
import io

from spiderfoot import SpiderFootPlugin, SpiderFootEvent, SpiderFootHelpers


class sfp_tool_nuclei(SpiderFootPlugin):

    meta = {
        "name": "Tool - Nuclei",
        "summary": "Fast and customisable vulnerability scanner.",
        "flags": [
            "tool",
            "slow",
            "invasive"
        ],
        "useCases": ["Footprint", "Investigate"],
        "categories": ["Crawling and Scanning"],
        "toolDetails": {
            "name": "Nuclei",
            "description": "Fast and customisable vulnerability scanner based on simple YAML based DSL.",
            "website": "https://nuclei.projectdiscovery.io/",
            "repository": "https://github.com/projectdiscovery/nuclei"
        }
    }

    # Default options
    opts = {
        "nuclei_path": "",
        "template_path": "",
        'netblockscan': True,
        'netblockscanmax': 24,
        # Remote execution options
        'remote_enabled': False,
        'remote_host': '',
        'remote_user': '',
        'remote_password': '',
        'remote_ssh_key': '',  # (deprecated, for backward compatibility)
        'remote_ssh_key_data': '',  # New: paste private key directly
        'remote_tool_path': '',
        'remote_tool_args': '',
    }

    # Option descriptions
    optdescs = {
        'nuclei_path': "The path to your nuclei binary. Must be set.",
        'template_path': "The path to your nuclei templates. Must be set.",
        'netblockscan': "Check all IPs within identified owned netblocks?",
        'netblockscanmax': "Maximum netblock/subnet size to scan IPs within (CIDR value, 24 = /24, 16 = /16, etc.)",
        'remote_enabled': "Enable remote execution via SSH (true/false)",
        'remote_host': "Remote SSH host (IP or hostname)",
        'remote_user': "Remote SSH username",
        'remote_password': "Remote SSH password (optional if using key)",
        'remote_ssh_key': "(Deprecated) Path to SSH private key (use remote_ssh_key_data instead)",
        'remote_ssh_key_data': "Paste your SSH private key here (PEM format, multi-line)",
        'remote_tool_path': "Path to the tool on the remote machine",
        'remote_tool_args': "Extra arguments/config for the tool on the remote machine",
    }

    # Target
    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in userOpts.keys():
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["INTERNET_NAME", "IP_ADDRESS", "NETBLOCK_OWNER"]

    def producedEvents(self):
        return [
            "VULNERABILITY_CVE_CRITICAL",
            "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_MEDIUM",
            "VULNERABILITY_CVE_LOW",
            "IP_ADDRESS",
            "VULNERABILITY_GENERAL",
            "WEBSERVER_TECHNOLOGY"
        ]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        if srcModuleName == "sfp_tool_nuclei":
            return

        # Remote execution support (exclusive)
        if self.opts.get("remote_enabled"):
            if not self.opts['remote_tool_path'] or not self.opts['template_path']:
                self.error(
                    "You enabled sfp_tool_nuclei remote but did not set a path to the tool and/or templates!")
                self.errorState = True
                return
            target = eventData
            timeout = 240
            if eventName == "NETBLOCK_OWNER" and self.opts['netblockscan']:
                target = ""
                net = IPNetwork(eventData)
                if net.prefixlen < self.opts['netblockscanmax']:
                    self.debug(f"Skipping scanning of {eventData}, too big.")
                    return
                for addr in IPNetwork(eventData).iter_hosts():
                    target += str(addr) + "\n"
                    timeout += 240
            output = self.run_remote_tool(target, self.opts['template_path'])
            content = output if output else None
        else:
            if not self.opts['nuclei_path'] or not self.opts['template_path']:
                self.error(
                    "You enabled sfp_tool_nuclei but did not set a path to the tool and/or templates!")
                self.errorState = True
                return
            exe = self.opts['nuclei_path']
            if self.opts['nuclei_path'].endswith('/'):
                exe = f"{exe}nuclei"
            if not os.path.isfile(exe):
                self.error(f"File does not exist: {exe}")
                self.errorState = True
                return
            if not SpiderFootHelpers.sanitiseInput(eventData, extra=['/']):
                self.debug("Invalid input, skipping.")
                return
            # Don't look up stuff twice
            if eventData in self.results:
                self.debug(f"Skipping {eventData} as already scanned.")
                return
            if eventName != "INTERNET_NAME":
                for addr in self.results:
                    try:
                        if IPNetwork(eventData) in IPNetwork(addr):
                            self.debug(
                                f"Skipping {eventData} as already within a scanned range.")
                            return
                    except Exception:
                        continue
            self.results[eventData] = True
            timeout = 240
            target = eventData
            if eventName == "NETBLOCK_OWNER" and self.opts['netblockscan']:
                target = ""
                net = IPNetwork(eventData)
                if net.prefixlen < self.opts['netblockscanmax']:
                    self.debug(f"Skipping scanning of {eventData}, too big.")
                    return
                for addr in IPNetwork(eventData).iter_hosts():
                    target += str(addr) + "\n"
                    timeout += 240
            try:
                args = [
                    exe,
                    "-silent",
                    "-json",
                    "-concurrency",
                    "100",
                    "-retries",
                    "1",
                    "-t",
                    self.opts["template_path"],
                    "-no-interactsh",
                    "-etags",
                    "dos",
                    "fuzz",
                    "misc",
                ]
                p = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
                try:
                    stdout, stderr = p.communicate(
                        input=target.encode(sys.stdin.encoding), timeout=timeout)
                    if p.returncode == 0:
                        content = stdout.decode(sys.stdout.encoding)
                    else:
                        self.error("Unable to read Nuclei content.")
                        self.debug(f"Error running Nuclei: {stderr}, {stdout}")
                        return
                except TimeoutExpired:
                    p.kill()
                    stdout, stderr = p.communicate()
                    self.debug("Timed out waiting for Nuclei to finish")
                    return
            except Exception as e:
                self.error(f"Unable to run Nuclei: {e}")
                return

        if not content:
            return

        try:
            for line in content.split("\n"):
                if not line:
                    continue

                data = json.loads(line)
                srcevent = event
                host = data['matched-at'].split(":")[0]
                if host != eventData:
                    if self.sf.validIP(host):
                        srctype = "IP_ADDRESS"
                    else:
                        srctype = "INTERNET_NAME"
                    srcevent = SpiderFootEvent(
                        srctype, host, self.__class__.__name__, event)
                    self.notifyListeners(srcevent)

                matches = re.findall(r"CVE-\d{4}-\d{4,7}", line)
                if matches:
                    for cve in matches:
                        etype, cvetext = self.sf.cveInfo(cve)
                        e = SpiderFootEvent(
                            etype, cvetext, self.__class__.__name__, srcevent
                        )
                        self.notifyListeners(e)
                else:
                    if "matcher-name" in data:
                        etype = "VULNERABILITY_GENERAL"
                        if data['info']['severity'] == "info":
                            etype = "WEBSERVER_TECHNOLOGY"

                        datatext = f"Template: {data['info']['name']}({data['template-id']})\n"
                        datatext += f"Matcher: {data['matcher-name']}\n"
                        datatext += f"Matched at: {data['matched-at']}\n"
                        if data['info'].get('reference'):
                            datatext += f"Reference: <SFURL>{data['info']['reference'][0]}</SFURL>"

                        evt = SpiderFootEvent(
                            etype,
                            datatext,
                            self.__class__.__name__,
                            srcevent,
                        )
                        self.notifyListeners(evt)
        except (KeyError, ValueError) as e:
            self.error(f"Couldn't parse the JSON output of Nuclei: {e}")
            self.error(f"Nuclei content: {content}")
            return

    def run_remote_tool(self, target, template_path):
        """
        Execute the Nuclei tool remotely via SSH.

        Args:
            target (str): The target(s) to scan.
            template_path (str): Path to the Nuclei templates on the remote host.

        Returns:
            str or None: Output from the remote tool, or None on error.
        """
        host = self.opts.get("remote_host")
        user = self.opts.get("remote_user")
        password = self.opts.get("remote_password")
        ssh_key_data = self.opts.get("remote_ssh_key_data")
        ssh_key_path = self.opts.get("remote_ssh_key")
        tool_path = self.opts.get("remote_tool_path")
        tool_args = self.opts.get("remote_tool_args", "")
        if not (host and user and tool_path and template_path):
            self.error("Remote execution enabled but host/user/tool_path/template_path not set.")
            return None

        cmd = f'{tool_path} -silent -json -concurrency 100 -retries 1 -t {template_path} -no-interactsh -etags dos fuzz misc {tool_args}'
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            pkey = None
            parse_key_failed = False
            if ssh_key_data:
                try:
                    pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_key_data))
                except Exception as e:
                    self.error(f"Failed to parse pasted SSH key: {e}")
                    parse_key_failed = True
            # If both password and key file are set, prefer password-only auth
            if pkey:
                try:
                    ssh.connect(host, username=user, pkey=pkey, password=password or None, timeout=10)
                except Exception as e:
                    self.error(f"Failed to connect using pasted SSH key: {e}")
                    return None
            elif ssh_key_path and (not ssh_key_data or parse_key_failed) and not password:
                try:
                    ssh.connect(host, username=user, key_filename=ssh_key_path, password=None, timeout=10)
                except Exception as e:
                    self.error(f"Failed to connect using SSH key file: {e}")
                    return None
            else:
                try:
                    ssh.connect(host, username=user, password=password or None, timeout=10)
                except Exception as e:
                    self.error(f"Failed to connect using password: {e}")
                    return None
            try:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                try:
                    if target:
                        stdin.write(target)
                        stdin.flush()
                    stdin.channel.shutdown_write()
                except Exception as e:
                    self.error(f"Failed to send target to remote tool: {e}")
                    ssh.close()
                    return None
                output = stdout.read().decode(errors="replace")
                err = stderr.read().decode(errors="replace")
                ssh.close()
                if err.strip():
                    self.error(f"Remote tool error: {err}")
                    return None
                return output
            except Exception as e:
                self.error(f"SSH command execution failed: {e}")
                ssh.close()
                return None
        except Exception as e:
            self.error(f"SSH connection or execution failed: {e}")
            return None


# End of sfp_tool_nuclei class
