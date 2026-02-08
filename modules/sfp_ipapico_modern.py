# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_ipapico_modern
# Purpose:     SpiderFoot plug-in to identify the Geo-location of IP addresses
#              using ipapi.co — MIGRATED to SpiderFootModernPlugin.
#
#              This module demonstrates the migration path from the legacy
#              SpiderFootPlugin to SpiderFootModernPlugin, using the extracted
#              HttpService instead of self.sf.fetchUrl().
#
# Original:    sfp_ipapico.py (Krishnasis Mandal)
# Migrated:    2025-07-08
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

"""
Migration notes (sfp_ipapico → sfp_ipapico_modern):

1. Base class changed: SpiderFootPlugin → SpiderFootModernPlugin
2. self.sf.fetchUrl() → self.fetch_url() (uses HttpService with fallback)
3. self.tempStorage() → self.tempStorage() (unchanged, inherited)
4. Added type hints for clarity
5. setup() calls super().setup() which wires services automatically
6. No other changes needed — the module is API-identical

Behavioral differences:
- HTTP requests are now instrumented with Prometheus metrics
- Requests go through HttpService which supports connection pooling
- If HttpService is not available, falls back to self.sf.fetchUrl()
"""

import json
import time
from typing import Any, Dict, List, Optional

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_ipapico_modern(SpiderFootModernPlugin):

    meta = {
        'name': "ipapi.co (Modern)",
        'summary': "Queries ipapi.co to identify geolocation of IP Addresses "
                   "using ipapi.co API — modernized with service layer.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Real World"],
        'dataSource': {
            'website': "https://ipapi.co/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://ipapi.co/api/"
            ],
            'favIcon': "https://ipapi.co/static/images/favicon.b64f1de785e1.ico",
            'logo': "https://ipapi.co/static/images/favicon.34f0ec468301.png",
            'description': "Powerful & Simple REST API for IP Address Geolocation. "
                           "ipapi.co provides a REST API to find the location "
                           "of an IP address.",
        }
    }

    opts: Dict[str, Any] = {}
    optdescs: Dict[str, str] = {}
    results = None

    def setup(self, sfc, userOpts=None):
        # Modern setup — wires HttpService, DnsService, etc. automatically
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()

    def watchedEvents(self) -> List[str]:
        return [
            "IP_ADDRESS",
            "IPV6_ADDRESS",
        ]

    def producedEvents(self) -> List[str]:
        return [
            "GEOINFO",
            "RAW_RIR_DATA",
        ]

    def query(self, ip: str) -> Optional[dict]:
        """Query ipapi.co for IP geolocation.

        Uses self.fetch_url() which delegates to HttpService when available,
        falling back to self.sf.fetchUrl() otherwise.
        """
        url = f"https://ipapi.co/{ip}/json/"

        # Modern API: self.fetch_url() — auto-instrumented with metrics
        res = self.fetch_url(
            url,
            timeout=self.opts.get('_fetchtimeout', 15),
        )

        # Rate-limit courtesy delay
        time.sleep(1.5)

        if res is None or res.get('content') is None:
            self.info(f"No ipapi.co data found for {ip}")
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")
            return None

    def handleEvent(self, event) -> None:
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        data = self.query(eventData)

        if data is None:
            self.info("No results returned from ipapi.co")
            return

        if data.get('country'):
            location = ', '.join(filter(None, [
                data.get('city'),
                data.get('region'),
                data.get('region_code'),
                data.get('country_name'),
                data.get('country'),
            ]))

            evt = SpiderFootEvent('GEOINFO', location, self.__name__, event)
            self.notifyListeners(evt)

            evt = SpiderFootEvent(
                'RAW_RIR_DATA', str(data), self.__name__, event)
            self.notifyListeners(evt)
