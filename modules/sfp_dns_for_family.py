from __future__ import annotations

"""SpiderFoot plug-in module: dns_for_family."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_dns_for_family
# Purpose:     Check if a host would be blocked by DNS for Family.
#
# Author:      <bcoles@gmail.com>
#
# Created:     2021-10-11
# Copyright:   (c) bcoles 2021
# Licence:     MIT
# -------------------------------------------------------------------------------

import dns.resolver

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_dns_for_family(SpiderFootModernPlugin):
    """DNS for Family"""

    meta = {
        'name': "DNS for Family",
        'summary': "Check if a host would be blocked by DNS for Family.",
        'flags': [],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://dnsforfamily.com/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://dnsforfamily.com/",
            ],
            'favIcon': "https://dnsforfamily.com/Icons/favicon-32x32.png",
            'logo': "https://dnsforfamily.com/Templates/assets/images/logo.svg",
            'description': "DNS for Family aims to block websites which are considered as porn. "
            "So that you and your children can safely surf internet to their heart's desire, "
            "without worrying to be followed to harmful websites."
        }
    }

    opts = {
    }

    optdescs = {
    }

    results = None

    def setup(self, sfc, userOpts=None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "INTERNET_NAME",
            "AFFILIATE_INTERNET_NAME",
            "CO_HOSTED_SITE"
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "BLACKLISTED_INTERNET_NAME",
            "BLACKLISTED_AFFILIATE_INTERNET_NAME",
            "BLACKLISTED_COHOST",
        ]

    def queryAddr(self, qaddr):
        """Query Addr."""
        if not qaddr:
            return None

        res = dns.resolver.Resolver()
        res.nameservers = ["94.130.180.225", "78.47.64.161"]

        try:
            return res.resolve(qaddr)
        except Exception as e:
            self.debug(f"Unable to resolve {qaddr}")

        return None

    def handleEvent(self, event) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventData in self.results:
            return

        self.results[eventData] = True

        if eventName == "INTERNET_NAME":
            blacklist_type = "BLACKLISTED_INTERNET_NAME"
        elif eventName == "AFFILIATE_INTERNET_NAME":
            blacklist_type = "BLACKLISTED_AFFILIATE_INTERNET_NAME"
        elif eventName == "CO_HOSTED_SITE":
            blacklist_type = "BLACKLISTED_COHOST"
        else:
            self.debug(f"Unexpected event type {eventName}, skipping")
            return

        res = self.queryAddr(eventData)

        if not res:
            return

        for result in res:
            k = str(result)
            if k != '159.69.10.249':
                continue

            self.debug(f"{eventData} blocked by DNS for Family")
            evt = SpiderFootEvent(
                blacklist_type, f"DNS for Family [{eventData}]", self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_dns_for_family class
