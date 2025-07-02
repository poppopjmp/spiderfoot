# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_arin
# Purpose:      Queries the ARIN internet registry to get netblocks and other
#               bits of info.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     23/02/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_arin(SpiderFootPlugin):
    """SpiderFoot plugin to query the ARIN internet registry for contact information."""
    meta = {
        "name": "ARIN",
        "summary": "Queries ARIN registry for contact information.",
        "flags": [],
        "useCases": ["Footprint", "Investigate", "Passive"],
        "categories": ["Public Registries"],
        "dataSource": {
            "website": "https://www.arin.net/",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": [
                "https://www.arin.net/resources/",
                "https://www.arin.net/reference/",
                "https://www.arin.net/participate/",
                "https://www.arin.net/resources/guide/request/",
                "https://www.arin.net/resources/registry/transfers/",
                "https://www.arin.net/resources/guide/ipv6/",
            ],
            "favIcon": "https://www.arin.net/img/favicon.ico",
            "logo": "https://www.arin.net/img/logo-stnd.svg",
            "description": "ARIN is a nonprofit, member-based organization that administers IP addresses & "
            "ASNs in support of the operation and growth of the Internet.\n"
            "Established in December 1997 as a Regional Internet Registry, "
            "the American Registry for Internet Numbers (ARIN) is responsible for the management "
            "and distribution of Internet number resources such as Internet Protocol (IP) addresses "
            "and Autonomous System Numbers (ASNs). ARIN manages these resources within its service region, "
            "which is comprised of Canada, the United States, and many Caribbean and North Atlantic islands.",
        },
    }

    # Default options
    opts = {}
    optdescs = {}

    results = None
    currentEventSrc = None
    keywords = None

    def setup(self, sfc, userOpts=dict()):
        """
        Set up the plugin with SpiderFoot context and user options.

        Args:
            sfc (SpiderFoot): The SpiderFoot context object.
            userOpts (dict): User-supplied options for the module.
        """
        self.sf = sfc
        self.results = self.tempStorage()
        self.currentEventSrc = None
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        """
        Return a list of event types this module is interested in.

        Returns:
            list: List of event type strings.
        """
        return ["DOMAIN_NAME", "HUMAN_NAME"]

    def producedEvents(self):
        """
        Return a list of event types this module produces.

        Returns:
            list: List of event type strings.
        """
        return ["RAW_RIR_DATA", "HUMAN_NAME"]

    def fetchRir(self, url):
        """
        Fetch content from ARIN and return the response if available.

        Args:
            url (str): The URL to fetch.

        Returns:
            dict or None: The response dict or None if not found.
        """
        head = {"Accept": "application/json"}
        res = self.sf.fetchUrl(
            url,
            timeout=self.opts["_fetchtimeout"],
            useragent=self.opts["_useragent"],
            headers=head,
        )
        if res["content"] is not None and res["code"] != "404":
            return res
        return None

    def query(self, qtype, value):
        """
        Query ARIN for information based on type and value.

        Args:
            qtype (str): Query type ('domain', 'name', or 'contact').
            value (str): Value to query.

        Returns:
            dict or None: The parsed JSON data or None if not found.
        """
        url = "https://whois.arin.net/rest/"
        if qtype == "domain":
            url += "pocs;domain=@" + value
        try:
            if qtype == "name":
                fname, lname = value.split(" ", 1)
                if fname.endswith(","):
                    t = fname
                    fname = lname
                    lname = t
                url += "pocs;first=" + fname + ";last=" + lname
        except Exception as e:
            self.debug("Couldn't process name: " + value + " (" + str(e) + ")")
            return None
        if qtype == "contact":
            url = value
        res = self.fetchRir(url)
        if not res:
            self.debug("No info found/available for " + value + " at ARIN.")
            return None
        try:
            data = json.loads(res["content"])
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")
            return None
        evt = SpiderFootEvent(
            "RAW_RIR_DATA", str(data), self.__class__.__name__, self.currentEventSrc
        )
        self.notifyListeners(evt)
        return data

    def handleEvent(self, event):
        """
        Handle incoming events, query ARIN for data, and emit events for found information.

        Args:
            event (SpiderFootEvent): The event to handle.
        """
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        self.currentEventSrc = event
        self.debug(f"Received event, {eventName}, from {srcModuleName}")
        # Don't look up stuff twice
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return
        self.results[eventData] = True
        if eventName == "DOMAIN_NAME":
            ret = self.query("domain", eventData)
            if not ret:
                return
            if "pocs" in ret:
                if "pocRef" in ret["pocs"]:
                    ref = list()
                    # Might be a list or a dictionary
                    if isinstance(ret["pocs"]["pocRef"], dict):
                        ref = [ret["pocs"]["pocRef"]]
                    else:
                        ref = ret["pocs"]["pocRef"]
                    for p in ref:
                        name = p["@name"]
                        if "," in name:
                            sname = name.split(", ", 1)
                            name = sname[1] + " " + sname[0]
                        evt = SpiderFootEvent(
                            "HUMAN_NAME", name, self.__class__.__name__, self.currentEventSrc
                        )
                        self.notifyListeners(evt)
                        # We just want the raw data so we can get potential
                        # e-mail addresses.
                        self.query("contact", p["$"])
        if eventName == "HUMAN_NAME":
            ret = self.query("name", eventData)
            if not ret:
                return
            if "pocs" in ret:
                if "pocRef" in ret["pocs"]:
                    ref = list()
                    # Might be a list or a dictionary
                    if isinstance(ret["pocs"]["pocRef"], dict):
                        ref = [ret["pocs"]["pocRef"]]
                    else:
                        ref = ret["pocs"]["pocRef"]
                    for p in ref:
                        # We just want the raw data so we can get potential
                        # e-mail addresses.
                        self.query("contact", p["$"])


# End of sfp_arin class
