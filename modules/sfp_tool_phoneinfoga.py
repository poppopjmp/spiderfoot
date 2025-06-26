# -*- coding: utf-8 -*-
"""
SpiderFoot plug-in for using the PhoneInfoga tool (https://github.com/sundowndev/phoneinfoga).
"""
import json
import time
from spiderfoot import SpiderFootEvent, SpiderFootPlugin

class sfp_tool_phoneinfoga(SpiderFootPlugin):
    meta = {
        "name": "Tools - PhoneInfoga",
        "summary": "Gather phone number intelligence using PhoneInfoga.",
        "flags": ["tool", "invasive", "apikey"],
        "useCases": ["Investigate"],
        "categories": ["Content Analysis"],
        "labels": ["tool", "invasive", "apikey"],
        "toolDetails": {
            "name": "PhoneInfoga",
            "description": "PhoneInfoga is one of the most advanced tools to scan international phone numbers.",
            "website": "https://github.com/sundowndev/phoneinfoga",
            "repository": "https://github.com/sundowndev/phoneinfoga",
        },
        "dataSource": {
            "type": "api",
            "model": "FREE_NOAUTH_UNLIMITED",
            "apiKeyInstructions": [
                "See https://github.com/sundowndev/phoneinfoga for API key setup instructions.",
                "Enter your API key in the module options."
            ]
        },
    }

    opts = {
        "api_endpoint": "http://localhost:5000/api/v2/scan",
        "timeout": 15,
        "api_key": "",
        "retries": 2,
        "retry_delay": 2,
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

    optdescs = {
        "api_endpoint": "PhoneInfoga API endpoint (default: http://localhost:5000/api/v2/scan)",
        "timeout": "Timeout in seconds for API requests.",
        "api_key": "API key for PhoneInfoga (if required, sent as X-Api-Key header)",
        "retries": "Number of times to retry the API call on failure.",
        "retry_delay": "Seconds to wait between retries.",
        "remote_enabled": "Enable remote execution via SSH (true/false)",
        "remote_host": "Remote SSH host (IP or hostname)",
        "remote_user": "Remote SSH username",
        "remote_password": "Remote SSH password (optional if using key)",
        "remote_ssh_key": "(Deprecated) Path to SSH private key (use remote_ssh_key_data instead)",
        "remote_ssh_key_data": "Paste your SSH private key here (PEM format, multi-line)",
        "remote_tool_path": "Path to the tool on the remote machine",
        "remote_tool_args": "Extra arguments/config for the tool on the remote machine",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["PHONE_NUMBER"]

    def producedEvents(self):
        return [
            "PHONE_NUMBER",
            "COUNTRY_NAME",
            "CARRIER_NAME",
            "LINE_TYPE",
            "REGION_NAME",
            "RAW_RIR_DATA",
            "INTERNATIONAL_FORMAT",
            "LOCAL_FORMAT",
            "NUMBER_TYPE",
            "IS_POSSIBLE",
            "IS_VALID",
            "LOCATION",
            "CARRIER_TYPE",
        ]

    def run_remote_tool(self, phone_number):
        """Run the tool remotely via SSH and return parsed JSON output."""
        import paramiko
        import io
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
        cmd = f'{tool_path} {tool_args} --format json --number "{phone_number}"'
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

    def query_api(self, phone_number):
        if self.opts.get("remote_enabled"):
            return self.run_remote_tool(phone_number)
        """Query the PhoneInfoga API for information about a phone number."""
        url = self.opts["api_endpoint"]
        headers = {"Content-Type": "application/json"}
        if self.opts.get("api_key"):
            headers["X-Api-Key"] = self.opts["api_key"]
        data = json.dumps({"number": phone_number})
        retries = int(self.opts.get("retries", 2))
        delay = int(self.opts.get("retry_delay", 2))
        for attempt in range(retries + 1):
            try:
                res = self.sf.fetchUrl(
                    url,
                    postData=data,
                    headers=headers,
                    timeout=self.opts["timeout"],
                    useragent=self.opts.get("_useragent", "SpiderFoot"),
                    verify=False,
                )
                if not res or not res.get("content"):
                    self.error(f"No response from PhoneInfoga API (attempt {attempt+1})")
                    if attempt < retries:
                        time.sleep(delay)
                        continue
                    return None
                if res.get("code") and str(res["code"]) not in ("200", 200):
                    self.error(f"PhoneInfoga API returned HTTP {res['code']}")
                    return None
                return json.loads(res["content"])
            except Exception as e:
                self.error(f"Error querying PhoneInfoga API (attempt {attempt+1}): {e}")
                if attempt < retries:
                    time.sleep(delay)
                    continue
                return None

    def handleEvent(self, event):
        """Handle PHONE_NUMBER events and query PhoneInfoga API."""
        eventData = event.data
        if eventData in self.results:
            return
        self.results[eventData] = True
        self.debug(f"Received event, {event.eventType}, from {event.module}")
        data = self.query_api(eventData)
        if not data:
            return
        # Emit events based on API response
        if data.get("valid"):
            evt = SpiderFootEvent("PHONE_NUMBER", eventData, self.__name__, event)
            self.notifyListeners(evt)
        if data.get("country"):
            evt = SpiderFootEvent("COUNTRY_NAME", data["country"], self.__name__, event)
            self.notifyListeners(evt)
        if data.get("carrier"):
            evt = SpiderFootEvent("CARRIER_NAME", data["carrier"], self.__name__, event)
            self.notifyListeners(evt)
        if data.get("line_type"):
            evt = SpiderFootEvent("LINE_TYPE", data["line_type"], self.__name__, event)
            self.notifyListeners(evt)
        if data.get("region"):
            evt = SpiderFootEvent("REGION_NAME", data["region"], self.__name__, event)
            self.notifyListeners(evt)
        if data.get("international_format"):
            evt = SpiderFootEvent("INTERNATIONAL_FORMAT", data["international_format"], self.__name__, event)
            self.notifyListeners(evt)
        if data.get("local_format"):
            evt = SpiderFootEvent("LOCAL_FORMAT", data["local_format"], self.__name__, event)
            self.notifyListeners(evt)
        if data.get("number_type"):
            evt = SpiderFootEvent("NUMBER_TYPE", data["number_type"], self.__name__, event)
            self.notifyListeners(evt)
        if "is_possible" in data:
            evt = SpiderFootEvent("IS_POSSIBLE", str(data["is_possible"]), self.__name__, event)
            self.notifyListeners(evt)
        if "is_valid" in data:
            evt = SpiderFootEvent("IS_VALID", str(data["is_valid"]), self.__name__, event)
            self.notifyListeners(evt)
        if data.get("location"):
            evt = SpiderFootEvent("LOCATION", data["location"], self.__name__, event)
            self.notifyListeners(evt)
        if data.get("carrier_type"):
            evt = SpiderFootEvent("CARRIER_TYPE", data["carrier_type"], self.__name__, event)
            self.notifyListeners(evt)
        # Always emit raw data
        evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(data), self.__name__, event)
        self.notifyListeners(evt)
