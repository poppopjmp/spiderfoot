# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_netlas
# Purpose:     Search Netlas API for domain, IP address, and other information.
#
# Author:      Your Name <your.email@example.com>
# Copyright:   (c) Your Name
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_netlas(SpiderFootPlugin):
    """SpiderFoot plug-in for searching Netlas API for domain, IP address, and
    other information.

    This class is responsible for querying Netlas API to retrieve
    information about domains, IP addresses, and other related data.
    """

    meta = {
        "name": "Netlas",
        "summary": "Look up domain and IP address information from Netlas API.",
        "flags": ["apikey"],
        "useCases": ["Passive", "Footprint", "Investigate"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://netlas.io/",
            "model": "FREE_NOAUTH_LIMITED",
            "references": [
                "https://netlas.io/",
            ],
            "apiKeyInstructions": [
                "Visit https://netlas.io/signup",
                "Register a free account",
                "Visit https://netlas.io/api/",
                "Your API Key will be listed under 'API Key'.",
            ],
            "favIcon": "https://netlas.io/favicon.ico",
            "logo": "https://netlas.io/logo.png",
            "description": "Netlas provides powerful APIs to help you enrich any user experience or automate any workflow.",
        },
    }

    # Default options
    opts = {
        "api_key": "",
    }

    # Option descriptions
    optdescs = {
        "api_key": "Netlas API key.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        """Set up the module with user options.

        Args:
            sfc: SpiderFoot instance
            userOpts (dict): User options
        """
        self.sf = sfc
        self.errorState = False
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        """Define the events this module is interested in for input.

        Returns:
            list: List of event types
        """
        return ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self):
        """Define the events this module produces.

        Returns:
            list: List of event types
        """
        return ["RAW_RIR_DATA", "GEOINFO", "PHYSICAL_COORDINATES", "PROVIDER_TELCO"]

    def queryNetlas(self, qry, qryType):
        """Query Netlas API for information.

        Args:
            qry (str): Query string
            qryType (str): Query type (domain, ip, etc.)

        Returns:
            dict: Response data
        """
        api_key = self.opts["api_key"]
        if not api_key:
            return None

        params = urllib.parse.urlencode(
            {
                "api_key": api_key,
                "query": qry.encode("raw_unicode_escape").decode(
                    "ascii", errors="replace"
                ),
                "type": qryType,
            }
        )

        res = self.sf.fetchUrl(
            f"https://api.netlas.io/v1/search?{params}",
            useragent=self.opts["_useragent"],
        )

        time.sleep(1)

        if not res:
            self.debug("No response from Netlas API endpoint")
            return None

        return self.parseApiResponse(res)

    def parseApiResponse(self, res: dict):
        """Parse the API response from Netlas.

        Args:
            res (dict): API response

        Returns:
            dict or None: Parsed response data or None on error
        """
        if not res:
            self.error("No response from Netlas API.")
            self.errorState = True
            return None

        code = res.get("code")
        if code == "429":
            self.error("You are being rate-limited by Netlas API.")
            self.errorState = True
            return None
        elif code == "401":
            self.error("Unauthorized. Invalid Netlas API key.")
            self.errorState = True
            return None
        elif code == "422":
            self.error("Usage quota reached. Insufficient API credit.")
            self.errorState = True
            return None
        elif code in ("500", "502", "503"):
            self.error("Netlas API service is unavailable")
            self.errorState = True
            return None
        elif code == "204":
            self.debug("No response data for target")
            return None
        elif code != "200":
            self.error(f"Unexpected reply from Netlas API: {code}")
            self.errorState = True
            return None

        if res.get("content") is None:
            return None

        try:
            return json.loads(res["content"])
        except Exception as e:
            self.error(f"Error processing JSON response: {e}")
            self.errorState = True
        return None

    def handleEvent(self, event):
        """Handle events sent to this module.

        Args:
            event: SpiderFoot event
        """
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.opts["api_key"] == "":
            self.error(
                f"You enabled {self.__class__.__name__} but did not set any API keys!"
            )
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True
        emitted = set()
        def emit(evt_type, data):
            key = (evt_type, str(data))
            if key in emitted:
                return
            emitted.add(key)
            e = SpiderFootEvent(evt_type, data, self.__class__.__name__, event)
            self.notifyListeners(e)

        if eventName not in self.watchedEvents():
            return

        if eventName == "DOMAIN_NAME":
            data = self.queryNetlas(eventData, "domain")
            if not data:
                return
            emit("RAW_RIR_DATA", str(data))
            geoinfo = data.get("geoinfo")
            if geoinfo:
                emit("GEOINFO", geoinfo)

        elif eventName in ["IP_ADDRESS", "IPV6_ADDRESS"]:
            data = self.queryNetlas(eventData, "ip")
            if not data:
                return
            emit("RAW_RIR_DATA", str(data))
            geoinfo = data.get("geoinfo")
            if geoinfo:
                emit("GEOINFO", geoinfo)
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            if latitude and longitude:
                emit(
                    "PHYSICAL_COORDINATES",
                    f"{latitude}, {longitude}"
                )


# End of sfp_netlas class
