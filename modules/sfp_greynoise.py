from __future__ import annotations

"""SpiderFoot plug-in module: greynoise."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_greynoise
# Purpose:      Query GreyNoise's API
#
# Author:       Steve Micallef
# Updated By:   Brad Chiappetta, GreyNoise
#
# Created:      20/11/2018
# Updated:      31-Aug-2022
# Copyright:    (c) Steve Micallef
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import time
from datetime import datetime
from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_greynoise(SpiderFootAsyncPlugin):

    """Obtain IP enrichment data from GreyNoise"""

    meta = {
        "name": "GreyNoise",
        "summary": "Obtain IP enrichment data from GreyNoise",
        "flags": ["apikey"],
        "useCases": ["Investigate", "Passive"],
        "categories": ["Reputation Systems"],
        "dataSource": {
            "website": "https://greynoise.io/",
            "model": "FREE_AUTH_LIMITED",
            "references": ["https://docs.greynoise.io/", "https://viz.greynoise.io/signup"],
            "apiKeyInstructions": [
                "Visit https://viz.greynoise.io/signup",
                "Sign up for a free account",
                "Navigate to https://viz.greynoise.io/account",
                "The API key is listed under 'API Key'",
            ],
            "favIcon": "https://viz.greynoise.io/favicon.ico",
            "logo": "https://viz.greynoise.io/_nuxt/img/greynoise-logo.dccd59d.png",
            "description": "At GreyNoise, we collect and analyze untargeted, widespread, "
            "and opportunistic scan and attack activity that reaches every server directly connected to the Internet. "
            "Mass scanners (such as Shodan and Censys), search engines, bots, worms, "
            "and crawlers generate logs and events omnidirectionally on every IP address in the IPv4 space. "
            "GreyNoise gives you the ability to filter this useless noise out.",
        },
    }

    # Default options
    opts = {
        "api_key": "",
        "age_limit_days": 30,
        "netblocklookup": True,
        "maxnetblock": 24,
        "subnetlookup": True,
        "maxsubnet": 24
        # 'asnlookup': True
    }

    # Option descriptions
    optdescs = {
        "api_key": "GreyNoise API Key.",
        "age_limit_days": "Ignore any records older than this many days. 0 = unlimited.",
        "netblocklookup": "Look up netblocks deemed to be owned by your target for possible blacklisted hosts on the same target subdomain/domain?",
        "maxnetblock": "If looking up owned netblocks, the maximum netblock size to look up all IPs within (CIDR value, 24 = /24, 16 = /16, etc.)",
        "subnetlookup": "Look up subnets which your target is a part of for blacklisting?",
        "maxsubnet": "If looking up subnets, the maximum subnet size to look up all the IPs within (CIDR value, 24 = /24, 16 = /16, etc.)"
        # 'asnlookup': "Look up ASNs that your target is a member of?"
    }

    # Be sure to completely clear any class variables in setup()
    # or you run the risk of data persisting between scan runs.

    results = None
    errorState = False

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

        # Clear / reset any other class member variables here
        # or you risk them persisting between threads.
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["IP_ADDRESS", "AFFILIATE_IPADDR", "NETBLOCK_MEMBER", "NETBLOCK_OWNER"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "MALICIOUS_IPADDR",
            "MALICIOUS_ASN",
            "MALICIOUS_SUBNET",
            "MALICIOUS_AFFILIATE_IPADDR",
            "MALICIOUS_NETBLOCK",
            "COMPANY_NAME",
            "GEOINFO",
            "BGP_AS_MEMBER",
            "OPERATING_SYSTEM",
            "RAW_RIR_DATA",
        ]

    def queryIP(self, qry: str, qry_type: str) -> dict | None:
        """Query IP via GreyNoise API v3."""
        gn_ip_url = "https://api.greynoise.io/v3/ip/"
        gn_gnql_url = "https://api.greynoise.io/v3/gnql?query="

        headers = {"key": self.opts["api_key"], "accept": "application/json"}
        res = {}
        if qry_type == "ip":
            self.debug(f"Querying GreyNoise for IP: {qry}")
            ip_response = self.fetch_url(
                gn_ip_url + qry,
                timeout=self.opts["_fetchtimeout"],
                useragent="greynoise-spiderfoot-v2.0.0",
                headers=headers,
            )
            if ip_response and str(ip_response.get("code", "")) == "200":
                res = json.loads(ip_response["content"])
        else:
            self.debug(f"Querying GreyNoise for Netblock: {qry}")
            query_response = self.fetch_url(
                gn_gnql_url + qry,
                timeout=self.opts["_fetchtimeout"],
                useragent="greynoise-spiderfoot-v2.0.0",
                headers=headers,
            )
            if query_response and str(query_response.get("code", "")) == "200":
                res = json.loads(query_response["content"])

        if not res:
            self.error(
                "Greynoise API key seems to have been rejected or you have exceeded usage limits.")
            self.errorState = True
            return None

        return res

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.opts["api_key"] == "":
            self.error("You enabled sfp_greynoise but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName == "NETBLOCK_OWNER":
            if not self.opts["netblocklookup"]:
                return

            max_netblock = self.opts['maxnetblock']
            if IPNetwork(eventData).prefixlen < max_netblock:
                self.debug(
                    f"Network size bigger than permitted: {IPNetwork(eventData).prefixlen} > {max_netblock}")
                return

        if eventName == "NETBLOCK_MEMBER":
            if not self.opts["subnetlookup"]:
                return

            max_subnet = self.opts['maxsubnet']
            if IPNetwork(eventData).prefixlen < max_subnet:
                self.debug(
                    f"Network size bigger than permitted: {IPNetwork(eventData).prefixlen} > {max_subnet}")
                return

        if eventName == "IP_ADDRESS":
            evtType = "MALICIOUS_IPADDR"
            qryType = "ip"
        if eventName.startswith("NETBLOCK_"):
            evtType = "MALICIOUS_IPADDR"
            qryType = "netblock"
        if eventName == "AFFILIATE_IPADDR":
            evtType = "MALICIOUS_AFFILIATE_IPADDR"
            qryType = "ip"

        ret = self.queryIP(eventData, qryType)

        if not ret:
            return

        # v3: Normalize into a list of scan intelligence records.
        # Single IP responses nest data under "internet_scanner_intelligence".
        # GNQL responses return a "data" array, each item with "internet_scanner_intelligence".
        records = []
        if "data" in ret:
            for item in ret.get("data", []):
                intel = item.get("internet_scanner_intelligence", {})
                if intel and intel.get("seen"):
                    # Ensure top-level ip is accessible
                    intel.setdefault("ip", item.get("ip", ""))
                    records.append(intel)
        elif "internet_scanner_intelligence" in ret:
            intel = ret["internet_scanner_intelligence"]
            if intel and intel.get("seen"):
                intel.setdefault("ip", ret.get("ip", ""))
                records.append(intel)

        if not records:
            return

        for rec in records:
            if self.checkForStop():
                return

            ip_addr = rec.get("ip", eventData)
            self.debug(f"Found threat info in Greynoise: {ip_addr}")

            lastseen = rec.get("last_seen", "1970-01-01")
            lastseen_dt = datetime.strptime(lastseen, "%Y-%m-%d")
            lastseen_ts = int(time.mktime(lastseen_dt.timetuple()))
            age_limit_ts = int(time.time()) - (86400 * self.opts["age_limit_days"])
            if self.opts["age_limit_days"] > 0 and lastseen_ts < age_limit_ts:
                self.debug(f"Record [{ip_addr}] found but too old, skipping.")
                continue

            # Only report metadata about the target, not affiliates
            if rec.get("metadata") and eventName == "IP_ADDRESS":
                met = rec.get("metadata")
                if met.get("country", "unknown") != "unknown":
                    loc = ""
                    if met.get("city"):
                        loc = met.get("city") + ", "
                    loc += met.get("country")
                    e = SpiderFootEvent("GEOINFO", loc, self.__name__, event)
                    self.notifyListeners(e)
                if met.get("asn", "unknown") != "unknown":
                    asn = str(met.get("asn")).replace("AS", "")
                    e = SpiderFootEvent("BGP_AS_MEMBER", asn, self.__name__, event)
                    self.notifyListeners(e)
                if met.get("organization", "unknown") != "unknown":
                    e = SpiderFootEvent(
                        "COMPANY_NAME", met.get("organization"),
                        self.__name__, event)
                    self.notifyListeners(e)
                if met.get("os", "unknown") != "unknown":
                    e = SpiderFootEvent(
                        "OPERATING_SYSTEM", met.get("os"),
                        self.__name__, event)
                    self.notifyListeners(e)
                e = SpiderFootEvent(
                    "RAW_RIR_DATA", str(rec), self.__name__, event)
                self.notifyListeners(e)

            if rec.get("classification"):
                descr = (
                    "GreyNoise - Mass-Scanning IP Detected ["
                    + ip_addr
                    + "]\n - Classification: "
                    + rec.get("classification")
                )
                if rec.get("tags"):
                    descr += "\n - Scans For Tags: " + ", ".join(rec.get("tags"))
                # v3: "cve" renamed to "cves"
                cves = rec.get("cves") or rec.get("cve")
                if cves:
                    descr += "\n - Scans For CVEs: " + ", ".join(cves)
                if rec.get("raw_data") and not (rec.get("tags") or cves):
                    descr += "\n - Raw data: " + str(rec.get("raw_data"))
                descr += "\n<SFURL>https://viz.greynoise.io/ip/" + ip_addr + "</SFURL>"
                e = SpiderFootEvent(evtType, descr, self.__name__, event)
                self.notifyListeners(e)

# End of sfp_greynoise class
