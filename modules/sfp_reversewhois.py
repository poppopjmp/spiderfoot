from __future__ import annotations

"""SpiderFoot plug-in module: reversewhois."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_reversewhois
# Purpose:      Scrape reversewhois.io
#
# Author:      TheTechromancer
#
# Created:     05/20/2021
# Copyright:   (c) Steve Micallef 2021
# Licence:     MIT
# -------------------------------------------------------------------------------

import re

from bs4 import BeautifulSoup

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_reversewhois(SpiderFootModernPlugin):

    """Reverse Whois lookups using reversewhois.io."""

    meta = {
        "name": "ReverseWhois",
        "summary": "Reverse Whois lookups using reversewhois.io.",
        "useCases": ["Investigate", "Passive"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://www.reversewhois.io/",
            "model": "FREE_NOAUTH_UNLIMITED",
            "favIcon": "https://www.reversewhois.io/dist/img/favicon-32x32.png",
            "description": "ReverseWhois is a free search engine to find domain names owned by an individual or company.\n"
            "Search based on names or email addresses.",
        }
    }

    # Default options
    opts = {}

    # Option descriptions
    optdescs = {}

    # Be sure to completely clear any class variables in setup()
    # or you run the risk of data persisting between scan runs.

    results = None
    errorState = False

    def setup(self, sfc, userOpts=None):
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False

        # Clear / reset any other class member variables here
        # or you risk them persisting between threads.
    # What events is this module interested in for input
    def watchedEvents(self):
        """Return the list of events this module watches."""
        return ["DOMAIN_NAME"]

    # What events this module produces
    def producedEvents(self):
        """Return the list of events this module produces."""
        return ["AFFILIATE_INTERNET_NAME", "AFFILIATE_DOMAIN_NAME", "DOMAIN_REGISTRAR"]

    # Search ReverseWhois
    def query(self, qry):
        """Query the data source."""
        url = f"https://reversewhois.io?searchterm={qry}"

        res = self.fetch_url(url, timeout=self.opts.get("_fetchtimeout", 30))

        if res["code"] not in ["200"]:
            self.error("You may have exceeded ReverseWhois usage limits.")
            self.errorState = True
            return ([], [])

        html = BeautifulSoup(res["content"], features="lxml")
        date_regex = re.compile(r'\d{4}-\d{2}-\d{2}')
        registrars = set()
        domains = set()
        for table_row in html.findAll("tr"):
            table_cells = table_row.findAll("td")
            # make double-sure we're in the right table by checking the date field
            try:
                if date_regex.match(table_cells[2].text.strip()):
                    domain = table_cells[1].text.strip().lower()
                    registrar = table_cells[-1].text.strip()
                    if domain:
                        domains.add(domain)
                    if registrar:
                        registrars.add(registrar)
            except IndexError:
                self.debug(f"Invalid row {table_row}")
                continue

        if not registrars and not domains:
            self.info(f"No ReverseWhois info found for {qry}")

        return (list(domains), list(registrars))

    # Handle events sent to this module
    def handleEvent(self, event):
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

        domains, registrars = self.query(eventData)

        for domain in set(domains):
            # if this domain isn't the main target
            if not self.getTarget().matches(domain, includeChildren=False):
                e = SpiderFootEvent("AFFILIATE_INTERNET_NAME",
                                    domain, self.__name__, event)
                self.notifyListeners(e)
                if self.sf.isDomain(domain, self.opts["_internettlds"]):
                    evt = SpiderFootEvent(
                        "AFFILIATE_DOMAIN_NAME", domain, self.__name__, event)
                    self.notifyListeners(evt)

        for registrar in set(registrars):
            e = SpiderFootEvent("DOMAIN_REGISTRAR",
                                registrar, self.__name__, event)
            self.notifyListeners(e)

# End of sfp_reversewhois class
