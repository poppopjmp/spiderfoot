from __future__ import annotations

"""SpiderFoot plug-in module: publicwww."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_publicwww
# Purpose:     Search PublicWWW source code search engine for websites
#              containing specific code snippets, analytics IDs, or
#              technology signatures.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import re
import time
import urllib.parse

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_publicwww(SpiderFootModernPlugin):

    """Search PublicWWW for websites sharing the same analytics IDs, code snippets or technology fingerprints."""

    meta = {
        'name': "PublicWWW",
        'summary': "Search PublicWWW source code search engine to find sites sharing analytics IDs, code snippets or similar technology.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://publicwww.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://publicwww.com/api-documentation.html",
            ],
            'apiKeyInstructions': [
                "Visit https://publicwww.com/",
                "Register a free account",
                "Navigate to https://publicwww.com/profile/api.html",
                "Your API key will be listed on that page",
            ],
            'favIcon': "https://publicwww.com/favicon.ico",
            'logo': "https://publicwww.com/img/publicwww-logo.png",
            'description': (
                "PublicWWW is a source code search engine that indexes the HTML, "
                "CSS and JavaScript of over 200 million websites. Use it to find "
                "sites sharing analytics IDs, ad network codes, technology "
                "fingerprints and code snippets."
            ),
        }
    }

    opts = {
        'api_key': "",
        'max_results': 500,
    }

    optdescs = {
        'api_key': "PublicWWW API key.",
        'max_results': "Maximum number of results to retrieve per query (default: 500).",
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
        return ["WEB_ANALYTICS_ID"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "AFFILIATE_INTERNET_NAME",
            "RAW_RIR_DATA",
        ]

    def queryPublicWWW(self, search_term: str) -> list | None:
        """Query PublicWWW for sites containing the given code snippet.

        Args:
            search_term: The code snippet or analytics ID to search for.

        Returns:
            List of domain strings or None on error.
        """
        encoded = urllib.parse.quote(f'"{search_term}"', safe='')
        url = (
            f"https://publicwww.com/websites/{encoded}/"
            f"?export=urls&key={self.opts['api_key']}"
        )

        res = self.fetch_url(
            url,
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
        )

        time.sleep(2)

        if res['code'] in ["401", "403"]:
            self.error("PublicWWW API key rejected or access denied.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("PublicWWW rate limit exceeded.")
            self.errorState = True
            return None

        if res['content'] is None:
            self.info(f"No PublicWWW data for: {search_term}")
            return None

        # Response is a newline-separated list of URLs
        domains = []
        for line in res['content'].strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            # Extract domain from URL
            match = re.match(r'https?://([^/]+)', line)
            if match:
                domain = match.group(1).lower()
                # Remove www. prefix for consistency
                if domain.startswith('www.'):
                    domain = domain[4:]
                if domain not in domains:
                    domains.append(domain)

            if len(domains) >= self.opts.get('max_results', 500):
                break

        return domains if domains else None

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {event.module}")

        if self.opts['api_key'] == "":
            self.error("You enabled sfp_publicwww but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Parse WEB_ANALYTICS_ID format: "Network: ID"
        try:
            network = eventData.split(": ")[0]
            analytics_id = eventData.split(": ")[1]
        except Exception:
            self.error(f"Unable to parse WEB_ANALYTICS_ID: {eventData}")
            return

        # Only process relevant analytics types
        supported_networks = [
            'Google AdSense',
            'Google Analytics',
            'Google Tag Manager',
            'Google Site Verification',
        ]

        if network not in supported_networks:
            self.debug(f"Skipping unsupported network: {network}")
            return

        domains = self.queryPublicWWW(analytics_id)
        if not domains:
            return

        evt = SpiderFootEvent(
            "RAW_RIR_DATA",
            f"PublicWWW results for {eventData}: {len(domains)} sites found",
            self.__name__,
            event,
        )
        self.notifyListeners(evt)

        for domain in domains:
            if self.checkForStop():
                return

            if domain in self.results:
                continue

            self.results[domain] = True

            if self.getTarget().matches(domain):
                continue  # Skip our own domain

            evt = SpiderFootEvent(
                "AFFILIATE_INTERNET_NAME", domain, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_publicwww class
