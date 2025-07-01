# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_tool_nmap
# Purpose:      SpiderFoot plug-in for using nmap to perform OS fingerprinting.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     03/05/2020
# Copyright:   (c) Steve Micallef 2020
# Licence:     MIT
# -------------------------------------------------------------------------------

import os.path
from subprocess import PIPE, Popen
import paramiko
import io

from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_tool_nmap(SpiderFootPlugin):

    meta = {
        'name': "Tool - Nmap",
        'summary': "Identify what Operating System might be used.",
        'flags': ["tool", "slow", "invasive"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Crawling and Scanning"],
        'toolDetails': {
            'name': "Nmap",
            'description': "Nmap (\"Network Mapper\") is a free and open source utility for network discovery and security auditing.\n"
            "Nmap uses raw IP packets in novel ways to determine what hosts are available on the network, "
            "what services (application name and version) those hosts are offering, "
            "what operating systems (and OS versions) they are running, "
            "what type of packet filters/firewalls are in use, and dozens of other characteristics.\n",
            'website': "https://nmap.org/",
            'repository': "https://svn.nmap.org/nmap"
        },
    }

    # Default options
    opts = {
        'nmappath': "",
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
        'nmappath': "Path to the where the nmap binary lives. Must be set.",
        'netblockscan': "Port scan all IPs within identified owned netblocks?",
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

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Target Network"

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ['IP_ADDRESS', 'NETBLOCK_OWNER']

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["OPERATING_SYSTEM", "IP_ADDRESS"]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if srcModuleName == "sfp_tool_nmap":
            self.debug("Skipping event from myself.")
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        try:
            if eventName == "NETBLOCK_OWNER" and self.opts['netblockscan']:
                net = IPNetwork(eventData)
                if net.prefixlen < self.opts['netblockscanmax']:
                    self.debug("Skipping port scanning of " +
                               eventData + ", too big.")
                    return

        except Exception as e:
            self.error("Strange netblock identified, unable to parse: " +
                       eventData + " (" + str(e) + ")")
            return

        # Don't look up stuff twice, check IP == IP here
        if eventData in self.results:
            self.debug("Skipping " + eventData + " as already scanned.")
            return

        # Might be a subnet within a subnet or IP within a subnet
        for addr in self.results:
            if IPNetwork(eventData) in IPNetwork(addr):
                self.debug(
                    f"Skipping {eventData} as already within a scanned range.")
                return

        self.results[eventData] = True

        # Remote execution support (exclusive)
        if self.opts.get("remote_enabled"):
            output = self.run_remote_tool(eventData)
            if not output:
                return
            content = output
        else:
            if not self.opts['nmappath']:
                self.error(
                    "You enabled sfp_tool_nmap but did not set a path to the tool!")
                self.errorState = True
                return

            # Normalize path
            if self.opts['nmappath'].endswith('nmap') or self.opts['nmappath'].endswith('nmap.exe'):
                exe = self.opts['nmappath']
            elif self.opts['nmappath'].endswith('/'):
                exe = self.opts['nmappath'] + "nmap"
            else:
                self.error("Could not recognize your nmap path configuration.")
                self.errorState = True
                return

            # If tool is not found, abort
            if not os.path.isfile(exe):
                self.error("File does not exist: " + exe)
                self.errorState = True
                return

            # Sanitize domain name.
            if not self.sf.validIP(eventData) and not self.sf.validIpNetwork(eventData):
                self.error("Invalid input, refusing to run.")
                return

            try:
                p = Popen([exe, "-O", "--osscan-limit", eventData],
                          stdout=PIPE, stderr=PIPE)
                stdout, stderr = p.communicate(input=None)
                if p.returncode == 0:
                    content = stdout.decode('utf-8', errors='replace')
                else:
                    self.error("Unable to read Nmap content.")
                    self.debug(f"Error running Nmap: {stderr}, {stdout}")
                    return

                if "No exact OS matches for host" in content or "OSScan results may be unreliable" in content:
                    self.debug(f"Couldn't reliably detect the OS for {eventData}")
                    return
            except Exception as e:
                self.error(f"Unable to run Nmap: {e}")
                return

        if not content:
            self.debug("No content from Nmap to parse.")
            return

        if eventName == "IP_ADDRESS":
            try:
                opsys = None
                for line in content.split('\n'):
                    if "OS details:" in line:
                        junk, opsys = line.split(": ")
                if not opsys:
                    opsys = "Unknown"
                evt = SpiderFootEvent(
                    "OPERATING_SYSTEM", opsys, self.__name__, event)
                self.notifyListeners(evt)
            except Exception as e:
                self.error("Couldn't parse the output of Nmap: " + str(e))
                return

        if eventName == "NETBLOCK_OWNER":
            try:
                currentIp = None
                for line in content.split('\n'):
                    opsys = None
                    if "scan report for" in line:
                        currentIp = line.split("(")[1].replace(")", "")
                    if "OS details:" in line:
                        junk, opsys = line.split(": ")

                    if opsys and currentIp:
                        ipevent = SpiderFootEvent(
                            "IP_ADDRESS", currentIp, self.__name__, event)
                        self.notifyListeners(ipevent)

                        evt = SpiderFootEvent(
                            "OPERATING_SYSTEM", opsys, self.__name__, ipevent)
                        self.notifyListeners(evt)
                        currentIp = None
            except Exception as e:
                self.error(f"Couldn't parse the output of Nmap: {e}")
                return

    def run_remote_tool(self, target):
        host = self.opts.get("remote_host")
        user = self.opts.get("remote_user")
        password = self.opts.get("remote_password")
        ssh_key_data = self.opts.get("remote_ssh_key_data")
        ssh_key_path = self.opts.get("remote_ssh_key")
        tool_path = self.opts.get("remote_tool_path")
        tool_args = self.opts.get("remote_tool_args", "")
        if not (host and user and tool_path):
            self.error("Remote execution enabled but host/user/tool_path not set.")
            return None
        cmd = f'{tool_path} -O --osscan-limit {target}'
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
            return output
        except Exception as e:
            self.error(f"SSH connection or execution failed: {e}")
            return None

# End of sfp_tool_nmap class
