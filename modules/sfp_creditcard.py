from __future__ import annotations

"""SpiderFoot plug-in module: creditcard."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_creditcard
# Purpose:      SpiderFoot plug-in for scanning retrieved content by other
#               modules (such as sfp_spider) and identifying credit card numbers.
#
# Author:      Krishnasis Mandal <krishnasis@hotmail.com>
#
# Created:     21/04/2020
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_creditcard(SpiderFootModernPlugin):
    """SpiderFoot plugin to identify credit card numbers in scraped webpages."""
    meta = {
        'name': "Credit Card Number Extractor",
        'summary': "Identify Credit Card Numbers in any data",
        'flags': ["errorprone"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Content Analysis"]
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

        # Override datasource for sfp_creditcard module
        self.__dataSource__ = "Target Website"
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["DARKNET_MENTION_CONTENT", "LEAKSITE_CONTENT"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["CREDIT_CARD_NUMBER"]

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        creditCards = SpiderFootHelpers.extractCreditCardsFromText(eventData)

        for creditCard in set(creditCards):
            self.info(f"Found credit card number: {creditCard}")
            evt = SpiderFootEvent("CREDIT_CARD_NUMBER",
                                  creditCard, getattr(self, '__name__', self.__class__.__name__), event)
            if event.moduleDataSource:
                evt.moduleDataSource = event.moduleDataSource
            else:
                evt.moduleDataSource = "Unknown"
            self.notifyListeners(evt)

# End of sfp_creditcard class
