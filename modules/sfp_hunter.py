from __future__ import annotations

"""SpiderFoot plug-in module: hunter."""

# -------------------------------------------------------------------------------
# Name:         sfp_hunter
# Purpose:      Query hunter.io using their API.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     22/02/2017
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import urllib.error
import urllib.parse
import urllib.request

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_hunter(SpiderFootModernPlugin):

    """Check for e-mail addresses and names on hunter.io."""

    meta = {
        'name': "Hunter.io",
        'summary': "Check for e-mail addresses and names on hunter.io.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://hunter.io/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://hunter.io/api"
            ],
            'apiKeyInstructions': [
                "Visit https://hunter.io/",
                "Sign up for a free account",
                "Click on 'Account Settings'",
                "Click on 'API'",
                "The API key is listed under 'Your API Key'"
            ],
            'favIcon': "https://hunter.io/assets/head/favicon-d5796c45076e78aa5cf22dd53c5a4a54155062224bac758a412f3a849f38690b.ico",
            'logo': "https://hunter.io/assets/head/touch-icon-iphone-fd9330e31552eeaa12b177489943de997551bfd991c4c44e8c3d572e78aea5f3.png",
            'description': "Hunter lets you find email addresses in seconds and connect with the people that matter for your business.\n"
            "The Domain Search lists all the people working in a company with their name "
            "and email address found on the web. With 100+ million email addresses indexed, "
            "effective search filters and scoring, it's the most powerful email-finding tool ever created.",
        }
    }

    # Default options
    opts = {
        "api_key": ""
    }

    # Option descriptions
    optdescs = {
        "api_key": "Hunter.io API key."
    }

    # Be sure to completely clear any class variables in setup()
    # or you run the risk of data persisting between scan runs.

    results = None
    errorState = False

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False

        # Clear / reset any other class member variables here
        # or you risk them persisting between threads.
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["DOMAIN_NAME", "INTERNET_NAME"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["EMAILADDR", "EMAILADDR_GENERIC", "RAW_RIR_DATA"]

    def query(self, qry: str, offset: int = 0, limit: int = 10):
        """Query the data source."""
        params = {
            "domain": qry.encode('raw_unicode_escape').decode("ascii", errors='replace'),
            "api_key": self.opts['api_key'],
            "offset": str(offset),
            "limit": str(limit)
        }

        url = f"https://api.hunter.io/v2/domain-search?{urllib.parse.urlencode(params)}"

        res = self.fetch_url(
            url, timeout=self.opts['_fetchtimeout'], useragent="SpiderFoot")

        if res['code'] == "404":
            return None

        if not res['content']:
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.error(f"Error processing JSON response from hunter.io: {e}")

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

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if self.opts['api_key'] == "":
            self.error("You enabled sfp_hunter but did not set an API key!")
            self.errorState = True
            return

        data = self.query(eventData, 0, 10)
        if not data:
            return

        if "data" not in data:
            return

        # Check if we have more results on further pages
        if "meta" in data:
            maxgoal = data['meta'].get('results', 10)
        else:
            maxgoal = 10

        rescount = len(data['data'].get('emails', list()))

        while rescount <= maxgoal:
            for email in data['data'].get('emails', list()):
                # Notify other modules of what you've found
                em = email.get('value')
                if not em:
                    continue
                if em.split("@")[0] in self.opts['_genericusers'].split(","):
                    evttype = "EMAILADDR_GENERIC"
                else:
                    evttype = "EMAILADDR"

                e = SpiderFootEvent(evttype, em, self.__name__, event)
                self.notifyListeners(e)

                if 'first_name' in email and 'last_name' in email:
                    if email['first_name'] is not None and email['last_name'] is not None:
                        n = email['first_name'] + " " + email['last_name']
                        e = SpiderFootEvent("RAW_RIR_DATA", "Possible full name: " + n,
                                            self.__name__, event)
                        self.notifyListeners(e)

            if rescount >= maxgoal:
                return

            data = self.query(eventData, rescount, 10)
            if data is None:
                return
            if "data" not in data:
                return

            rescount += len(data['data'].get('emails', list()))

# End of sfp_hunter class
