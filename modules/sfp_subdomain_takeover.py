from __future__ import annotations

"""SpiderFoot plug-in module: subdomain_takeover."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_subdomain_takeover
# Purpose:     Check if affiliated subdomains are vulnerable to takeover
#              using the fingerprints.json list from subjack by haccer:
#              - https://github.com/haccer/subjack/master/fingerprints.json
#
# Author:      <bcoles@gmail.com>
#
# Created:     2020-06-21
# Copyright:   (c) bcoles 2020
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_subdomain_takeover(SpiderFootModernPlugin):

    """Check if affiliated subdomains are vulnerable to takeover."""

    meta = {
        'name': "Subdomain Takeover Checker",
        'summary': "Check if affiliated subdomains are vulnerable to takeover.",
        'flags': [],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Crawling and Scanning"]
    }

    # Default options
    opts = {
    }

    # Option descriptions
    optdescs = {
    }

    results = None
    errorState = False
    fingerprints = dict()

    # Initialize module and module options
    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
        content = self.cache_get("subjack-fingerprints", 48)
        if content is None:
            url = "https://raw.githubusercontent.com/haccer/subjack/master/fingerprints.json"
            res = self.fetch_url(url, useragent="SpiderFoot")

            if res['content'] is None:
                self.error(f"Unable to fetch {url}")
                self.errorState = True
                return

            self.cache_put("subjack-fingerprints", res['content'])
            content = res['content']

        try:
            self.fingerprints = json.loads(content)
        except Exception as e:
            self.error(
                f"Unable to parse subdomain takeover fingerprints list: {e}")
            self.errorState = True
            return

    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["AFFILIATE_INTERNET_NAME", "AFFILIATE_INTERNET_NAME_UNRESOLVED"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["AFFILIATE_INTERNET_NAME_HIJACKABLE"]

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventName == "AFFILIATE_INTERNET_NAME":
            for data in self.fingerprints:
                service = data.get("service")
                cnames = data.get("cname")
                fingerprints = data.get("fingerprint")
                nxdomain = data.get("nxdomain")

                if nxdomain:
                    continue

                for cname in cnames:
                    if cname.lower() not in eventData.lower():
                        continue

                    for proto in ["https", "http"]:
                        res = self.fetch_url(
                            f"{proto}://{eventData}/",
                            timeout=15,
                            useragent=self.opts['_useragent'],
                            verify=False
                        )
                        if not res:
                            continue
                        if not res['content']:
                            continue
                        for fingerprint in fingerprints:
                            if fingerprint in res['content']:
                                self.info(
                                    f"{eventData} appears to be vulnerable to takeover on {service}")
                                evt = SpiderFootEvent(
                                    "AFFILIATE_INTERNET_NAME_HIJACKABLE", eventData, self.__name__, event)
                                self.notifyListeners(evt)
                                break

        if eventName == "AFFILIATE_INTERNET_NAME_UNRESOLVED":
            for data in self.fingerprints:
                service = data.get("service")
                cnames = data.get("cname")
                nxdomain = data.get("nxdomain")

                if not nxdomain:
                    continue

                for cname in cnames:
                    if cname.lower() not in eventData.lower():
                        continue
                    self.info(
                        f"{eventData} appears to be vulnerable to takeover on {service}")
                    evt = SpiderFootEvent(
                        "AFFILIATE_INTERNET_NAME_HIJACKABLE", eventData, self.__name__, event)
                    self.notifyListeners(evt)

# End of sfp_subdomain_takeover class
