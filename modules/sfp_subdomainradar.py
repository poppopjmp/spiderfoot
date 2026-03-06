from __future__ import annotations

"""SpiderFoot plug-in module: subdomainradar."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_subdomainradar
# Purpose:     Query SubDomainRadar API for comprehensive subdomain
#              enumeration and port scanning via an asynchronous task-based API.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_subdomainradar(SpiderFootAsyncPlugin):

    """Query SubDomainRadar for subdomain enumeration via async task-based API."""

    meta = {
        'name': "SubDomainRadar",
        'summary': "Query SubDomainRadar API for comprehensive subdomain enumeration aggregating multiple passive and active sources.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Passive DNS"],
        'dataSource': {
            'website': "https://subdomainradar.io/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://api.subdomainradar.io/docs",
            ],
            'apiKeyInstructions': [
                "Visit https://subdomainradar.io/",
                "Register a free account",
                "Navigate to your account dashboard for the API key",
                "Free tier provides 100 points",
            ],
            'favIcon': "https://subdomainradar.io/favicon.ico",
            'logo': "https://subdomainradar.io/logo.png",
            'description': (
                "SubDomainRadar provides comprehensive subdomain enumeration "
                "by aggregating results from multiple passive and active sources. "
                "The async task-based API supports bulk domain scanning with "
                "optional port scanning. Free tier provides 100 points."
            ),
        }
    }

    opts = {
        'api_key': "",
        'poll_interval': 5,
        'max_poll_time': 300,
        'enumerator_group': "Fast",
        'fetch_ports': False,
    }

    optdescs = {
        'api_key': "SubDomainRadar API key (Bearer token).",
        'poll_interval': "Seconds to wait between polling for task completion.",
        'max_poll_time': "Maximum seconds to wait for a task to complete before giving up.",
        'enumerator_group': "Enumerator group to use: 'Fast' (free tier) or 'Deep' (paid). Fast is recommended for passive enumeration.",
        'fetch_ports': "Fetch open ports for the task after enumeration completes? (uses the /tasks/{id}/ports endpoint)",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "DOMAIN_NAME",
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "TCP_PORT_OPEN",
            "RAW_RIR_DATA",
        ]

    # ---- API helpers ----

    def _apiRequest(self, method: str, path: str, json_data: dict | None = None) -> dict | None:
        """Make an authenticated request to the SubDomainRadar API."""
        url = f"https://api.subdomainradar.io{path}"

        headers = {
            "Authorization": f"Bearer {self.opts['api_key']}",
            "Content-Type": "application/json",
        }

        kwargs = {
            "timeout": self.opts.get('_fetchtimeout', 30),
            "useragent": "SpiderFoot",
            "headers": headers,
        }

        if method.upper() == "POST" and json_data is not None:
            kwargs["data"] = json.dumps(json_data)
            kwargs["postData"] = json.dumps(json_data)

        res = self.fetch_url(url, method=method, **kwargs)

        if not res:
            self.error(f"No response from SubDomainRadar API ({path})")
            return None

        if res['code'] in ["401", "403"]:
            self.error("SubDomainRadar API key is invalid or expired.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("SubDomainRadar API rate limit exceeded (5 req/sec).")
            return None

        if res['code'] == "402":
            self.error("SubDomainRadar: insufficient API points.")
            self.errorState = True
            return None

        if res['code'] not in ["200", "201", "202"]:
            self.error(f"Unexpected HTTP {res['code']} from SubDomainRadar API")
            return None

        if not res.get('content'):
            self.debug(f"Empty response from SubDomainRadar API ({path})")
            return None

        try:
            return json.loads(res['content'])
        except (ValueError, TypeError) as e:
            self.error(f"Error parsing SubDomainRadar response: {e}")
            return None

    def _getEnumeratorNames(self) -> list[str] | None:
        """Fetch enumerator names for the configured group.

        GET /enumerators/groups
        Returns a list of enumerator display_name strings.
        """
        data = self._apiRequest("GET", "/enumerators/groups")
        if not data or not isinstance(data, list):
            self.error("SubDomainRadar: could not fetch enumerator groups")
            return None

        target_group = self.opts.get('enumerator_group', 'Fast')
        for group in data:
            if group.get('name', '').lower() == target_group.lower():
                enumerators = group.get('enumerators', [])
                names = [e.get('display_name', '') for e in enumerators if e.get('display_name')]
                if names:
                    return names

        self.error(f"SubDomainRadar: enumerator group '{target_group}' not found")
        return None

    def _submitEnumeration(self, domain: str) -> str | None:
        """Submit a subdomain enumeration task.

        POST /enumerate
        Body: {"domains": ["domain"], "enumerators": ["Name1", ...]}
        Returns task_id on success.
        """
        enumerator_names = self._getEnumeratorNames()
        if not enumerator_names:
            return None

        payload = {
            "domains": [domain],
            "enumerators": enumerator_names,
        }

        data = self._apiRequest("POST", "/enumerate", json_data=payload)
        if not data:
            return None

        # Response: {"message": "Tasks initiated", "tasks": {"domain": "task-uuid"}}
        tasks = data.get('tasks', {})
        task_id = tasks.get(domain)
        if not task_id:
            # Try first available task_id if domain key doesn't match exactly
            if tasks:
                task_id = next(iter(tasks.values()))
            else:
                self.error(f"SubDomainRadar: no task_id in response: {data}")
                return None

        self.debug(f"SubDomainRadar: submitted enumeration task {task_id} for {domain}")
        return task_id

    def _pollTask(self, task_id: str) -> dict | None:
        """Poll a task until it completes or times out.

        GET /tasks/{task_id}
        """
        poll_interval = self.opts.get('poll_interval', 5)
        max_poll_time = self.opts.get('max_poll_time', 300)
        elapsed = 0

        while elapsed < max_poll_time:
            if self.checkForStop() or self.errorState:
                return None

            data = self._apiRequest("GET", f"/tasks/{task_id}")
            if not data:
                return None

            status = data.get('status', '').lower()

            if status == 'completed':
                self.debug(f"SubDomainRadar: task {task_id} completed")
                return data

            if status in ('failed', 'error'):
                self.error(f"SubDomainRadar: task {task_id} failed: {data.get('error', data.get('message', 'unknown'))}")
                return None

            self.debug(f"SubDomainRadar: task {task_id} status={status}, waiting {poll_interval}s")
            time.sleep(poll_interval)
            elapsed += poll_interval

        self.error(f"SubDomainRadar: task {task_id} timed out after {max_poll_time}s")
        return None

    # ---- Event handler ----

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if not self.opts.get('api_key'):
            self.error("You enabled sfp_subdomainradar but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventName == "DOMAIN_NAME":
            self._handleDomain(event, eventData)

    def _handleDomain(self, event: SpiderFootEvent, domain: str) -> None:
        """Submit enumeration task, poll for completion, emit results."""
        task_id = self._submitEnumeration(domain)
        if not task_id:
            return

        result = self._pollTask(task_id)
        if not result:
            return

        # Emit raw data
        evt = SpiderFootEvent(
            "RAW_RIR_DATA", json.dumps(result, indent=2),
            self.__name__, event)
        self.notifyListeners(evt)

        # Process subdomains from the task result
        # API returns subdomains as a list of objects within the task response
        subdomains = result.get('subdomains', result.get('results', []))

        if isinstance(subdomains, dict):
            # Handle { "subdomain": { "ips": [...] } } format
            self._processSubdomainDict(event, subdomains)
        elif isinstance(subdomains, list):
            # Handle [ { "subdomain": "x", "ips": [...] }, ... ] format
            self._processSubdomainList(event, subdomains)

        # Optionally fetch open ports from /tasks/{task_id}/ports
        if self.opts.get('fetch_ports') and not self.checkForStop() and not self.errorState:
            self._fetchPorts(event, task_id)

    def _processSubdomainDict(self, event: SpiderFootEvent, subdomains: dict) -> None:
        """Process subdomains in dict format: { subdomain: {ips, ports} }."""
        for hostname, info in subdomains.items():
            if self.checkForStop() or self.errorState:
                return

            if not hostname or not isinstance(hostname, str):
                continue

            hostname = hostname.strip().lower()
            if hostname in self.results:
                continue
            self.results[hostname] = True

            # Emit hostname
            if self.getTarget().matches(hostname):
                evt = SpiderFootEvent(
                    "INTERNET_NAME", hostname, self.__name__, event)
                self.notifyListeners(evt)
            else:
                evt = SpiderFootEvent(
                    "INTERNET_NAME_UNRESOLVED", hostname, self.__name__, event)
                self.notifyListeners(evt)

            if not isinstance(info, dict):
                continue

            # Emit IPs
            for ip in info.get('ips', []):
                if ip and isinstance(ip, str) and ip not in self.results:
                    self.results[ip] = True
                    if ':' in ip:
                        evt = SpiderFootEvent(
                            "IPV6_ADDRESS", ip, self.__name__, event)
                    else:
                        evt = SpiderFootEvent(
                            "IP_ADDRESS", ip, self.__name__, event)
                    self.notifyListeners(evt)

            # Emit open ports
            for port in info.get('ports', []):
                if port:
                    port_str = f"{hostname}:{port}"
                    if port_str not in self.results:
                        self.results[port_str] = True
                        evt = SpiderFootEvent(
                            "TCP_PORT_OPEN", port_str, self.__name__, event)
                        self.notifyListeners(evt)

    def _processSubdomainList(self, event: SpiderFootEvent, subdomains: list) -> None:
        """Process subdomains in list format: [ {subdomain, ips, ports}, ... ]."""
        for entry in subdomains:
            if self.checkForStop() or self.errorState:
                return

            if isinstance(entry, str):
                hostname = entry.strip().lower()
                info = {}
            elif isinstance(entry, dict):
                hostname = entry.get('subdomain', entry.get('hostname', '')).strip().lower()
                info = entry
            else:
                continue

            if not hostname or hostname in self.results:
                continue
            self.results[hostname] = True

            # Emit hostname
            if self.getTarget().matches(hostname):
                evt = SpiderFootEvent(
                    "INTERNET_NAME", hostname, self.__name__, event)
                self.notifyListeners(evt)
            else:
                evt = SpiderFootEvent(
                    "INTERNET_NAME_UNRESOLVED", hostname, self.__name__, event)
                self.notifyListeners(evt)

            # Emit IPs
            for ip in info.get('ips', info.get('ip_addresses', [])):
                if ip and isinstance(ip, str) and ip not in self.results:
                    self.results[ip] = True
                    if ':' in ip:
                        evt = SpiderFootEvent(
                            "IPV6_ADDRESS", ip, self.__name__, event)
                    else:
                        evt = SpiderFootEvent(
                            "IP_ADDRESS", ip, self.__name__, event)
                    self.notifyListeners(evt)

            # Emit open ports
            for port in info.get('ports', info.get('open_ports', [])):
                if port:
                    port_str = f"{hostname}:{port}"
                    if port_str not in self.results:
                        self.results[port_str] = True
                        evt = SpiderFootEvent(
                            "TCP_PORT_OPEN", port_str, self.__name__, event)
                        self.notifyListeners(evt)

    def _fetchPorts(self, event: SpiderFootEvent, task_id: str) -> None:
        """Fetch open ports from the /tasks/{task_id}/ports endpoint.

        Response: [{"host": "x", "port": 80, "protocol": "tcp", "service": "http", ...}]
        """
        data = self._apiRequest("GET", f"/tasks/{task_id}/ports")
        if not data or not isinstance(data, list):
            return

        for entry in data:
            if self.checkForStop() or self.errorState:
                return

            host = entry.get('host', '').strip().lower()
            port = entry.get('port')
            if not host or port is None:
                continue

            port_str = f"{host}:{port}"
            if port_str in self.results:
                continue
            self.results[port_str] = True

            evt = SpiderFootEvent(
                "TCP_PORT_OPEN", port_str, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_subdomainradar class
