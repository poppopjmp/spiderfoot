from __future__ import annotations

"""SpiderFoot plug-in module: ipinfo."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_ipinfo
# Purpose:     SpiderFoot plug-in to identify the Geo-location of IP addresses
#              identified by other modules using ipinfo.io.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     17/06/2017
# Copyright:   (c) Steve Micallef 2017
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_ipinfo(SpiderFootModernPlugin):

    """Identifies the physical location of IP addresses identified using ipinfo.io."""

    meta = {
        'name': "IPInfo.io",
        'summary': "Identifies the physical location of IP addresses identified using ipinfo.io.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Real World"],
        'dataSource': {
            'website': "https://ipinfo.io",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://ipinfo.io/developers"
            ],
            'apiKeyInstructions': [
                "Visit https://ipinfo.io/",
                "Sign up for a free account",
                "Navigate to https://ipinfo.io/account",
                "The API key is listed above 'is your access token'"
            ],
            'favIcon': "https://ipinfo.io/static/favicon-96x96.png?v3",
            'logo': "https://ipinfo.io/static/deviceicons/android-icon-96x96.png",
            'description': "The Trusted Source for IP Address Data.\n"
            "With IPinfo, you can pinpoint your users’ locations, customize their experiences, "
            "prevent fraud, ensure compliance, and so much more.",
        }
    }

    # Default options
    opts = {
        "api_key": ""
    }
    optdescs = {
        "api_key": "Ipinfo.io access token."
    }

    results = None
    errorState = False

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['IP_ADDRESS', 'IPV6_ADDRESS']

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["GEOINFO"]

    # https://ipinfo.io/developers
    def queryIP(self, ip: str) -> dict | None:
        """Query IP."""
        headers = {
            'Authorization': "Bearer " + self.opts['api_key']
        }
        res = self.fetch_url("https://ipinfo.io/" + ip + "/json",
                               timeout=self.opts['_fetchtimeout'],
                               useragent=self.opts['_useragent'],
                               headers=headers)

        if res['code'] == "429":
            self.error("You are being rate-limited by ipinfo.io.")
            self.errorState = True
            return None

        if res['content'] is None:
            self.info("No GeoIP info found for " + ip)
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")

        return None

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.opts['api_key'] == "":
            self.error("You enabled sfp_ipinfo but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        data = self.queryIP(eventData)

        if data is None:
            return

        if 'country' not in data:
            return

        location = ', '.join(
            [_f for _f in [data.get('city'), data.get('region'), data.get('country')] if _f])
        self.info("Found GeoIP for " + eventData + ": " + location)

        evt = SpiderFootEvent("GEOINFO", location, self.__name__, event)
        self.notifyListeners(evt)

# End of sfp_ipinfo class
