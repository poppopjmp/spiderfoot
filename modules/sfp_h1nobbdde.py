from __future__ import annotations

"""SpiderFoot plug-in module: h1nobbdde."""

# -------------------------------------------------------------------------------
# Name:         sfp_h1.nobbd.de
# Purpose:      Query the the unofficial HackerOne disclosure timeline database
#               to see if our target appears.
#
# Author:      Dhiraj Mishra <dhiraj@notsosecure.com>
# Created:     28/10/2018
# Copyright:   (c) Dhiraj Mishra
# Licence:     MIT
# -------------------------------------------------------------------------------

import re

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_h1nobbdde(SpiderFootModernPlugin):

    """Check external vulnerability scanning/reporting service h1.nobbd.de to see if the target is listed."""

    meta = {
        'name': "HackerOne (Unofficial)",
        'summary': "Check external vulnerability scanning/reporting service h1.nobbd.de to see if the target is listed.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "http://www.nobbd.de/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "http://www.nobbd.de/index.php#projekte",
                "https://twitter.com/disclosedh1"
            ],
            'favIcon': "http://www.nobbd.de/favicon.ico",
            'logo': "http://www.nobbd.de/favicon.ico",
            'description': "Unofficial Bug Monitoring platform for HackerOne.",
        }
    }

    # Default options
    opts = {
    }

    # Option descriptions
    optdescs = {
    }

    # Be sure to completely clear any class variables in setup()
    # or you run the risk of data persisting between scan runs.

    results = None

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()

        # Clear / reset any other class member variables here
        # or you risk them persisting between threads.
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["DOMAIN_NAME"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["VULNERABILITY_DISCLOSURE"]

    # Query h1.nobbd.de
    def queryOBB(self, qry: str):
        """Query OBB."""
        ret = list()
        url = "http://h1.nobbd.de/search.php?q=" + qry
        res = self.fetch_url(
            url, timeout=30, useragent=self.opts['_useragent'])

        if res['content'] is None:
            self.debug("No content returned from h1.nobbd.de")
            return None

        try:
            rx = re.compile(
                "<a class=\"title\" href=.(.[^\"]+).*?title=.(.[^\"\']+)", re.IGNORECASE | re.DOTALL)
            for m in rx.findall(str(res['content'])):
                # Report it
                if qry in m[1]:
                    ret.append(m[1] + "\n<SFURL>" + m[0] + "</SFURL>")
        except Exception as e:
            self.error(f"Error processing response from h1.nobbd.de: {e}")
            return None

        return ret

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        data = list()

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        obb = self.queryOBB(eventData)
        if obb:
            data.extend(obb)

        for n in data:
            e = SpiderFootEvent("VULNERABILITY_DISCLOSURE",
                                n, self.__name__, event)
            self.notifyListeners(e)

# End of sfp_h1nobbdde class
