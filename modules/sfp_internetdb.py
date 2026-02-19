from __future__ import annotations

"""SpiderFoot plug-in module: internetdb."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_internetdb
# Purpose:     Query Shodan InternetDB for open ports, vulnerabilities,
#              hostnames, CPEs and tags for an IP address.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_internetdb(SpiderFootModernPlugin):

    """Query Shodan InternetDB for open ports, vulnerabilities, hostnames and CPEs."""

    meta = {
        'name': "Shodan InternetDB",
        'summary': "Query Shodan InternetDB for open ports, vulnerabilities, hostnames and CPEs for IP addresses.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://internetdb.shodan.io/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://internetdb.shodan.io/docs",
            ],
            'favIcon': "https://static.shodan.io/shodan/img/favicon.png",
            'logo': "https://static.shodan.io/developer/img/logo.png",
            'description': (
                "The InternetDB API provides a fast way to see the open ports, "
                "vulnerabilities, hostnames, CPEs and tags for any IP address. "
                "Free, no API key required. Updated weekly."
            ),
        }
    }

    opts = {
        'netblocklookup': True,
        'maxnetblock': 24,
    }

    optdescs = {
        'netblocklookup': "Look up all IPs on netblocks deemed to be owned by your target for possible hosts on the same target subdomain/domain?",
        'maxnetblock': "If looking up owned netblocks, the maximum netblock size to look up all IPs within (CIDR value, 24 = /24, 16 = /16, etc.)",
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
        return ["IP_ADDRESS", "IPV6_ADDRESS", "NETBLOCK_OWNER"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "TCP_PORT_OPEN",
            "VULNERABILITY_CVE_CRITICAL",
            "VULNERABILITY_CVE_HIGH",
            "VULNERABILITY_CVE_MEDIUM",
            "VULNERABILITY_CVE_LOW",
            "VULNERABILITY_GENERAL",
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "RAW_RIR_DATA",
            "WEBSERVER_TECHNOLOGY",
        ]

    def queryInternetDB(self, ip: str) -> dict | None:
        """Query the InternetDB API for a single IP address."""
        res = self.fetch_url(
            f"https://internetdb.shodan.io/{ip}",
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
        )

        if res['code'] == "404":
            self.debug(f"No InternetDB data for {ip}")
            return None

        if res['code'] in ["429"]:
            self.error("InternetDB rate limit exceeded.")
            self.errorState = True
            return None

        if res['content'] is None:
            self.info(f"No InternetDB info for {ip}")
            return None

        try:
            data = json.loads(res['content'])
            if "detail" in data:
                self.debug(f"InternetDB returned error for {ip}: {data['detail']}")
                return None
            return data
        except Exception as e:
            self.error(f"Error parsing InternetDB JSON for {ip}: {e}")
            return None

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName == 'NETBLOCK_OWNER':
            if not self.opts['netblocklookup']:
                return
            max_netblock = self.opts['maxnetblock']
            if IPNetwork(eventData).prefixlen < max_netblock:
                self.debug(
                    f"Network size bigger than permitted: "
                    f"{IPNetwork(eventData).prefixlen} > {max_netblock}"
                )
                return

        qrylist = []
        if eventName.startswith("NETBLOCK_"):
            for ipaddr in IPNetwork(eventData):
                qrylist.append(str(ipaddr))
                self.results[str(ipaddr)] = True
        else:
            qrylist.append(eventData)

        for addr in qrylist:
            if self.checkForStop():
                return

            rec = self.queryInternetDB(addr)
            if rec is None:
                continue

            # For netblocks, create the IP address event first
            if eventName == 'NETBLOCK_OWNER':
                pevent = SpiderFootEvent(
                    "IP_ADDRESS", addr, self.__name__, event)
                self.notifyListeners(pevent)
            else:
                pevent = event

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", str(rec), self.__name__, pevent)
            self.notifyListeners(evt)

            # Open ports
            for port in rec.get('ports', []):
                cp = f"{addr}:{port}"
                evt = SpiderFootEvent(
                    "TCP_PORT_OPEN", cp, self.__name__, pevent)
                self.notifyListeners(evt)

            # Vulnerabilities
            for vuln in rec.get('vulns', []):
                etype, cvetext = self.sf.cveInfo(vuln)
                evt = SpiderFootEvent(etype, cvetext, self.__name__, pevent)
                self.notifyListeners(evt)

            # Hostnames
            for hostname in rec.get('hostnames', []):
                if self.getTarget().matches(hostname):
                    evt = SpiderFootEvent(
                        "INTERNET_NAME", hostname, self.__name__, pevent)
                    self.notifyListeners(evt)
                else:
                    evt = SpiderFootEvent(
                        "INTERNET_NAME_UNRESOLVED", hostname, self.__name__, pevent)
                    self.notifyListeners(evt)

            # CPEs as technology indicators
            for cpe in rec.get('cpes', []):
                evt = SpiderFootEvent(
                    "WEBSERVER_TECHNOLOGY", cpe, self.__name__, pevent)
                self.notifyListeners(evt)

# End of sfp_internetdb class
