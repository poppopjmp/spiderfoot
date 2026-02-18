from __future__ import annotations

"""SpiderFoot plug-in module: psbdmp."""

# -------------------------------------------------------------------------------
# Name:         sfp_psbdmp
# Purpose:      Query psbdmp.cc for potentially hacked e-mail addresses.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     21/11/2016
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import re

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_psbdmp(SpiderFootModernPlugin):

    """Check psbdmp.cc (PasteBin Dump) for potentially hacked e-mails and domains."""

    meta = {
        'name': "Psbdmp",
        'summary': "Check psbdmp.cc (PasteBin Dump) for potentially hacked e-mails and domains.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "https://psbdmp.cc/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://psbdmp.cc/api"
            ],
            'favIcon': "",
            'logo': "https://psbdmp.cc/logo.png",
            'description': "Pastebin dump security monitor."
        }
    }

    opts = {
    }

    optdescs = {
    }

    results = None

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["EMAILADDR", "DOMAIN_NAME", "INTERNET_NAME"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["LEAKSITE_URL", "LEAKSITE_CONTENT"]

    def query(self, qry: str) -> list | None:
        """Query the data source."""
        ret = None

        if "@" in qry:
            url = "https://psbdmp.cc/api/search/email/" + qry
        else:
            url = "https://psbdmp.cc/api/search/domain/" + qry

        res = self.fetch_url(url, timeout=15, useragent="SpiderFoot")

        if res['code'] == "403" or res['content'] is None:
            self.info("Unable to fetch data from psbdmp.cc right now.")
            return None

        try:
            ret = json.loads(res['content'])
        except Exception as e:
            self.error(f"Error processing JSON response from psbdmp.cc: {e}")
            return None

        ids = list()
        if 'count' not in ret:
            return None

        if ret['count'] <= 0:
            return None

        for d in ret['data']:
            ids.append("https://pastebin.com/" + d['id'])

        return ids

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        data = self.query(eventData)
        if data is None:
            return

        for n in data:
            if self.checkForStop():
                return
            e = SpiderFootEvent("LEAKSITE_URL", n, self.__name__, event)
            self.notifyListeners(e)

            res = self.fetch_url(
                n,
                timeout=self.opts['_fetchtimeout'],
                useragent=self.opts['_useragent']
            )

            if res['content'] is None:
                self.debug(f"Ignoring {n} as no data returned")
                continue

            if re.search(
                r"[^a-zA-Z\-\_0-9]" +
                    re.escape(eventData) + r"[^a-zA-Z\-\_0-9]",
                res['content'],
                re.IGNORECASE
            ) is None:
                continue

            evt = SpiderFootEvent("LEAKSITE_CONTENT",
                                  res['content'], self.__name__, e)
            self.notifyListeners(evt)

# End of sfp_psbdmp class
