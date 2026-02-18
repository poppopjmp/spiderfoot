from __future__ import annotations

"""SpiderFoot plug-in module: rapiddns."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_rapiddns
# Purpose:     Query RapidDNS.io for subdomains and reverse IP (same-site)
#              information.  No API key required.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import re
import time
from collections.abc import Generator

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_rapiddns(SpiderFootModernPlugin):

    """Query RapidDNS.io for subdomains (forward DNS) and reverse IP lookups. Free, no API key required."""

    meta = {
        'name': "RapidDNS",
        'summary': "Query RapidDNS.io for subdomain enumeration and reverse IP lookups, backed by 8.5 billion DNS records.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Passive DNS"],
        'dataSource': {
            'website': "https://rapiddns.io/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://rapiddns.io/",
            ],
            'favIcon': "https://rapiddns.io/favicon.ico",
            'logo': "https://rapiddns.io/static/logo.png",
            'description': (
                "RapidDNS is a DNS query tool that has a database of over "
                "8.5 billion DNS records. It provides free subdomain enumeration "
                "and reverse IP lookups without requiring an API key."
            ),
        }
    }

    opts = {
        'fetch_subdomains': True,
        'fetch_sameip': True,
        'max_pages': 5,
    }

    optdescs = {
        'fetch_subdomains': "Look up subdomains for target domains?",
        'fetch_sameip': "Look up domains sharing the same IP (reverse IP)?",
        'max_pages': "Maximum number of result pages to fetch per query.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "DOMAIN_NAME",
            "IP_ADDRESS",
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "CO_HOSTED_SITE",
            "IP_ADDRESS",
            "RAW_RIR_DATA",
        ]

    # ---- HTML scraping helpers ----

    def _fetchPage(self, url: str) -> str | None:
        """Fetch a page from RapidDNS and return the HTML content."""
        res = self.fetch_url(
            url,
            timeout=self.opts.get('_fetchtimeout', 30),
            useragent=self.opts.get('_useragent', 'SpiderFoot'),
        )

        if not res:
            self.error(f"No response from RapidDNS: {url}")
            return None

        if res['code'] == "429":
            self.error("RapidDNS rate limit exceeded.")
            self.errorState = True
            return None

        if res['code'] not in ["200"]:
            self.error(f"Unexpected HTTP {res['code']} from RapidDNS")
            return None

        return res.get('content', '')

    def _extractDomains(self, html: str) -> list[str]:
        """Extract domain names from RapidDNS HTML table rows.

        The site renders results in <td> tags. We extract anything that
        looks like a hostname.
        """
        if not html:
            return []

        # RapidDNS renders results inside <td> tags.
        # Pattern matches hostnames in table cells.
        pattern = r'<td>([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,})</td>'
        matches = re.findall(pattern, html)
        return list(set(m.lower().strip() for m in matches if m))

    def _extractIPs(self, html: str) -> list[str]:
        """Extract IP addresses from RapidDNS HTML table rows."""
        if not html:
            return []

        pattern = r'<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td>'
        return list(set(re.findall(pattern, html)))

    def _hasNextPage(self, html: str, current_page: int) -> bool:
        """Check if there is a next page link."""
        next_page = current_page + 1
        return f"page={next_page}" in html

    # ---- Query methods ----

    def querySubdomains(self, domain: str) -> Generator[str, None, None]:
        """Query RapidDNS for subdomains of a domain and emit events."""
        max_pages = self.opts.get('max_pages', 5)

        for page in range(1, max_pages + 1):
            if self.checkForStop() or self.errorState:
                return

            url = f"https://rapiddns.io/subdomain/{domain}?full=1&page={page}"
            html = self._fetchPage(url)
            if not html:
                break

            domains = self._extractDomains(html)
            if not domains:
                break

            yield from domains

            if not self._hasNextPage(html, page):
                break

            time.sleep(1)

    def querySameIP(self, ip: str) -> Generator[str, None, None]:
        """Query RapidDNS for domains sharing the same IP and emit events."""
        max_pages = self.opts.get('max_pages', 5)

        for page in range(1, max_pages + 1):
            if self.checkForStop() or self.errorState:
                return

            url = f"https://rapiddns.io/sameip/{ip}?full=1&page={page}"
            html = self._fetchPage(url)
            if not html:
                break

            domains = self._extractDomains(html)
            if not domains:
                break

            yield from domains

            if not self._hasNextPage(html, page):
                break

            time.sleep(1)

    # ---- Event handler ----

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventName == "DOMAIN_NAME" and self.opts.get('fetch_subdomains'):
            self._handleSubdomains(event, eventData)

        if eventName == "IP_ADDRESS" and self.opts.get('fetch_sameip'):
            self._handleSameIP(event, eventData)

    def _handleSubdomains(self, event: SpiderFootEvent, domain: str) -> None:
        """Process subdomain enumeration for a domain."""
        found = False

        for hostname in self.querySubdomains(domain):
            if self.checkForStop() or self.errorState:
                return

            if not hostname or hostname in self.results:
                continue

            self.results[hostname] = True
            found = True

            if self.getTarget().matches(hostname):
                evt = SpiderFootEvent(
                    "INTERNET_NAME", hostname, self.__name__, event)
                self.notifyListeners(evt)
            else:
                evt = SpiderFootEvent(
                    "INTERNET_NAME_UNRESOLVED", hostname, self.__name__, event)
                self.notifyListeners(evt)

        if found:
            evt = SpiderFootEvent(
                "RAW_RIR_DATA",
                f"RapidDNS subdomain enumeration results for {domain}",
                self.__name__,
                event,
            )
            self.notifyListeners(evt)

    def _handleSameIP(self, event: SpiderFootEvent, ip: str) -> None:
        """Process reverse IP / same-site lookup."""
        found = False

        for hostname in self.querySameIP(ip):
            if self.checkForStop() or self.errorState:
                return

            if not hostname or hostname in self.results:
                continue

            self.results[hostname] = True
            found = True

            if self.getTarget().matches(hostname):
                evt = SpiderFootEvent(
                    "INTERNET_NAME", hostname, self.__name__, event)
                self.notifyListeners(evt)
            else:
                evt = SpiderFootEvent(
                    "CO_HOSTED_SITE", hostname, self.__name__, event)
                self.notifyListeners(evt)

        if found:
            evt = SpiderFootEvent(
                "RAW_RIR_DATA",
                f"RapidDNS reverse IP results for {ip}",
                self.__name__,
                event,
            )
            self.notifyListeners(evt)

# End of sfp_rapiddns class
