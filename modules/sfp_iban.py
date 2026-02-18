from __future__ import annotations

"""SpiderFoot plug-in module: iban."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_iban
# Purpose:      SpiderFoot plug-in for scanning retrieved content by other
#               modules (such as sfp_spider) and identifying IBANs.
#
# Author:      Krishnasis Mandal <krishnasis@hotmail.com>
#
# Created:     26/04/2020
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_iban(SpiderFootModernPlugin):

    """Identify International Bank Account Numbers (IBANs) in any data."""

    meta = {
        'name': "IBAN Number Extractor",
        'summary': "Identify International Bank Account Numbers (IBANs) in any data.",
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

        # Override datasource for sfp_iban module
        self.__dataSource__ = "Target Website"
    # What events is this module interested in for input
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["TARGET_WEB_CONTENT", "DARKNET_MENTION_CONTENT",
                "LEAKSITE_CONTENT"]

    # What events this module produces
    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["IBAN_NUMBER"]

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        ibans = SpiderFootHelpers.extractIbansFromText(eventData)
        for ibanNumber in set(ibans):
            if ibanNumber in self.results:
                continue
            self.results[ibanNumber] = True

            self.info(f"Found IBAN number: {ibanNumber}")
            evt = SpiderFootEvent(
                "IBAN_NUMBER", ibanNumber, getattr(self, '__name__', self.__class__.__name__), event)
            if event.moduleDataSource:
                evt.moduleDataSource = event.moduleDataSource
            else:
                evt.moduleDataSource = "Unknown"
            self.notifyListeners(evt)

# End of sfp_iban class
