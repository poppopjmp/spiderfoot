from __future__ import annotations

"""SpiderFoot plug-in module: openbugbounty."""

# -------------------------------------------------------------------------------
# Name:         sfp_openbugbounty
# Purpose:      Query the Open Bug Bounty database to see if our target appears.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     04/10/2015
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

import re

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_openbugbounty(SpiderFootAsyncPlugin):

    """Check external vulnerability scanning/reporting service openbugbounty.org to see if the target is listed."""

    meta = {
        'name': "Open Bug Bounty",
        'summary': "Check external vulnerability scanning/reporting service openbugbounty.org to see if the target is listed.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "https://www.openbugbounty.org/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://www.openbugbounty.org/cert/"
            ],
            'favIcon': "https://www.openbugbounty.org/favicon.ico",
            'logo': "https://www.openbugbounty.org/images/design/logo-obbnew.svg",
            'description': "Open Bug Bounty is an open, disintermediated, cost-free, and community-driven bug bounty platform "
            "for coordinated, responsible and ISO 29147 compatible vulnerability disclosure.\n"
            "The role of Open Bug Bounty is limited to independent verification of the "
            "submitted vulnerabilities and proper notification of website owners by all available means. "
            "Once notified, the website owner and the researcher are in direct contact to "
            "remediate the vulnerability and coordinate its disclosure. "
            "At this and at any later stages, we never act as an intermediary between "
            "website owners and security researchers.",
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
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["INTERNET_NAME"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["VULNERABILITY_DISCLOSURE"]

    # Query XSSposed.org
    def queryOBB(self, qry: str):
        """Query OBB."""
        ret = list()
        base = "https://www.openbugbounty.org"
        url = "https://www.openbugbounty.org/search/?search=" + qry
        res = self.fetch_url(
            url, timeout=30, useragent=self.opts['_useragent'])

        if res['content'] is None:
            self.debug("No content returned from openbugbounty.org")
            return None

        try:
            rx = re.compile(".*<div class=.cell1.><a href=.(.*).>(.*" +
                            qry + ").*?</a></div>.*", re.IGNORECASE)
            for m in rx.findall(str(res['content'])):
                # Report it
                if m[1] == qry or m[1].endswith("." + qry):
                    ret.append("From openbugbounty.org: <SFURL>" +
                               base + m[0] + "</SFURL>")
        except Exception as e:
            self.error(
                "Error processing response from openbugbounty.org: " + str(e))
            return None
        return ret

    # Handle events sent to this module
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
            # Notify other modules of what you've found
            e = SpiderFootEvent("VULNERABILITY_DISCLOSURE",
                                n, self.__name__, event)
            self.notifyListeners(e)

# End of sfp_openbugbounty class
