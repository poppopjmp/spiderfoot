from __future__ import annotations

"""SpiderFoot plug-in module: phone."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_phone
# Purpose:      SpiderFoot plug-in for scanning retrieved content by other
#               modules (such as sfp_spider) to identify phone numbers, and
#               lookup carrier information in Google's libphonenumber DB.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     19/06/2016
# Copyright:   (c) Steve Micallef 2016
# Licence:     MIT
# -------------------------------------------------------------------------------

import phonenumbers
from phonenumbers import carrier

# from phonenumbers import geocoder
from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_phone(SpiderFootModernPlugin):

    """Identify phone numbers in scraped webpages."""

    meta = {
        'name': "Phone Number Extractor",
        'summary': "Identify phone numbers in scraped webpages.",
        'flags': [],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Content Analysis"],
        "dataSource": {
            "website": None,
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": [],
            "description": "Local data processing and extraction (no external API).",
        },
    }

    opts = {}

    results = None
    optdescs = {}

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ['TARGET_WEB_CONTENT', 'DOMAIN_WHOIS', 'NETBLOCK_WHOIS', 'PHONE_NUMBER']

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ['PHONE_NUMBER', 'PROVIDER_TELCO']

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        sourceData = self.sf.hashstring(eventData)

        if sourceData in self.results:
            return

        self.results[sourceData] = True

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventName in ['TARGET_WEB_CONTENT', 'DOMAIN_WHOIS', 'NETBLOCK_WHOIS']:
            # Make potential phone numbers more friendly to parse
            content = eventData.replace('.', '-')

            for match in phonenumbers.PhoneNumberMatcher(content, region=None):
                n = phonenumbers.format_number(
                    match.number, phonenumbers.PhoneNumberFormat.E164)
                evt = SpiderFootEvent("PHONE_NUMBER", n, self.__name__, event)
                if event.moduleDataSource:
                    evt.moduleDataSource = event.moduleDataSource
                else:
                    evt.moduleDataSource = "Unknown"
                self.notifyListeners(evt)

        if eventName == 'PHONE_NUMBER':
            try:
                number = phonenumbers.parse(eventData)
            except Exception as e:
                self.debug(f"Error parsing phone number: {e}")
                return

            try:
                number_carrier = carrier.name_for_number(number, 'en')
            except Exception as e:
                self.debug(f"Error retrieving phone number carrier: {e}")
                return

            if not number_carrier:
                self.debug(f"No carrier information found for {eventData}")
                return

            evt = SpiderFootEvent(
                "PROVIDER_TELCO", number_carrier, self.__name__, event)

            if event.moduleDataSource:
                evt.moduleDataSource = event.moduleDataSource
            else:
                evt.moduleDataSource = "Unknown"

            self.notifyListeners(evt)

            # try:
            #     location = geocoder.description_for_number(number, 'en')
            # except Exception as e:
            #     self.debug('Error retrieving phone number location: ' + str(e))
            #     return

            # if location:
            #     evt = SpiderFootEvent("GEOINFO", location, self.__name__, event)
            #     self.notifyListeners(evt)
            # else:
            #     self.debug("No location information found for " + eventData)

    def registerEventEmitter(self, emitter: str) -> None:
        """Register event emitter"""
        self.eventEmitter = emitter

# End of sfp_phone class
