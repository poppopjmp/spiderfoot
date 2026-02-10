# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_comodo
# Purpose:     SpiderFoot plug-in for looking up whether hosts are blocked by
#              Comodo Secure DNS.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     30/05/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""SpiderFoot plug-in module: comodo."""

import dns.resolver

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_comodo(SpiderFootModernPlugin):
    """SpiderFoot plugin to check if a host would be blocked by Comodo Secure DNS."""
    meta = {
        'name': "Comodo Secure DNS",
        'summary': "Check if a host would be blocked by Comodo Secure DNS.",
        'flags': [],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://www.comodo.com/secure-dns/",
            'model': "FREE_NOAUTH_LIMITED",
            'references': [
                "https://cdome.comodo.com/pdf/Datasheet-Dome-Shield.pdf",
                "http://securedns.dnsbycomodo.com/",
                "https://www.comodo.com/secure-dns/secure-dns-assets/dowloads/ccs-dome-shield-whitepaper-threat-intelligence.pdf",
                "https://www.comodo.com/secure-dns/secure-dns-assets/dowloads/domeshield-all-use-cases.pdf",
            ],
            'favIcon': "https://www.comodo.com/favicon.ico",
            'logo': "https://www.comodo.com/new-assets/images/logo.png",
            'description': "Comodo Secure DNS is a domain name resolution service "
            "that resolves your DNS requests through our worldwide network of redundant DNS servers, "
            "bringing you the most reliable fully redundant DNS service anywhere, for a safer, "
            "smarter and faster Internet experience."
        }
    }

    opts = {
    }

    optdescs = {
    }

    results = None

    def __init__(self) -> None:
        """Initialize the sfp comodo."""
        super().__init__()
        self.__name__ = "sfp_comodo"

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
            "MALICIOUS_INTERNET_NAME",
            "MALICIOUS_AFFILIATE_INTERNET_NAME",
            "MALICIOUS_COHOST",
        ]

    def query(self, qaddr) -> bool:
        """Query the data source."""
        res = dns.resolver.Resolver()
        res.nameservers = ["8.26.56.26", "8.20.247.20"]

        try:
            addrs = res.resolve(qaddr)
            self.debug(f"Addresses returned: {addrs}")
        except Exception as e:
            self.debug(f"Unable to resolve {qaddr}")
            return False

        if addrs:
            return True
        return False

    def handleEvent(self, event) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventData in self.results:
            return

        self.results[eventData] = True

        if eventName == "INTERNET_NAME":
            malicious_type = "MALICIOUS_INTERNET_NAME"
            blacklist_type = "BLACKLISTED_INTERNET_NAME"
        elif eventName == "AFFILIATE_INTERNET_NAME":
            malicious_type = "MALICIOUS_AFFILIATE_INTERNET_NAME"
            blacklist_type = "BLACKLISTED_AFFILIATE_INTERNET_NAME"
        elif eventName == "CO_HOSTED_SITE":
            malicious_type = "MALICIOUS_COHOST"
            blacklist_type = "BLACKLISTED_COHOST"
        else:
            self.debug(f"Unexpected event type {eventName}, skipping")
            return

        # Check that it resolves first, as it becomes a valid
        # malicious host only if NOT resolved by Comodo Secure DNS.
        if not self.resolve_host(eventData) and not self.resolve_host6(eventData):
            return

        found = self.query(eventData)

        # Host was found, not blocked
        if found:
            return

        evt = SpiderFootEvent(
            blacklist_type, f"Comodo Secure DNS [{eventData}]", self.__name__, event)
        self.notifyListeners(evt)

        evt = SpiderFootEvent(
            malicious_type, f"Comodo Secure DNS [{eventData}]", self.__name__, event)
        self.notifyListeners(evt)

# End of sfp_comodo class
