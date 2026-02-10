# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_ipinfo_modern
# Purpose:     SpiderFoot plug-in to identify the Geo-location of IP addresses
#              using ipinfo.io — MIGRATED to SpiderFootModernPlugin.
#
#              Demonstrates migration with API key authentication and
#              error-state circuit-breaker patterns.
#
# Original:    sfp_ipinfo.py (Steve Micallef)
# Migrated:    2025-07-08
# Copyright:   (c) Steve Micallef 2017
# Licence:     MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
Migration notes (sfp_ipinfo → sfp_ipinfo_modern):

1. Base class: SpiderFootPlugin → SpiderFootModernPlugin
2. self.sf.fetchUrl() → self.fetch_url() (HttpService with fallback)
3. Auth header passed via headers= kwarg (unchanged pattern)
4. Added cache_get/cache_put for caching API responses (NEW)
5. Error state preserved — same circuit-breaker pattern
6. setup() calls super().setup() for automatic service wiring

New features enabled by ModernPlugin:
- HTTP request metrics (latency, status codes)
- Optional response caching via CacheService
- Connection pooling via HttpService
"""

import json
from typing import Any

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class sfp_ipinfo_modern(SpiderFootModernPlugin):

    """Identifies the physical location of IP addresses """

    meta = {
        'name': "IPInfo.io (Modern)",
        'summary': "Identifies the physical location of IP addresses "
                   "using ipinfo.io — modernized with service layer.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Real World"],
        'dataSource': {
            'website': "https://ipinfo.io",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://ipinfo.io/developers"
            ],
            'apiKeyInstructions': [
                "Visit https://ipinfo.io/",
                "Sign up for a free account",
                "Navigate to https://ipinfo.io/account",
                "The API key is listed above 'is your access token'",
            ],
            'favIcon': "https://ipinfo.io/static/favicon-96x96.png?v3",
            'logo': "https://ipinfo.io/static/deviceicons/android-icon-96x96.png",
            'description': "The Trusted Source for IP Address Data.\n"
                           "With IPinfo, you can pinpoint your users' locations, "
                           "customize their experiences, prevent fraud, ensure "
                           "compliance, and so much more.",
        }
    }

    opts: dict[str, Any] = {
        "api_key": "",
        "cache_ttl": 3600,  # NEW: cache responses for 1 hour
    }
    optdescs: dict[str, str] = {
        "api_key": "Ipinfo.io access token.",
        "cache_ttl": "Seconds to cache API responses (0 to disable).",
    }

    results = None
    errorState: bool = False

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        self.errorState = False

    def watchedEvents(self) -> list[str]:
        return ['IP_ADDRESS', 'IPV6_ADDRESS']

    def producedEvents(self) -> list[str]:
        return ["GEOINFO"]

    def queryIP(self, ip: str) -> dict | None:
        """Query ipinfo.io for IP geolocation.

        Uses CacheService for response caching (new feature) and
        HttpService for the HTTP request (with legacy fallback).
        """
        # Check cache first (NEW: uses CacheService when available)
        cache_key = f"ipinfo:{ip}"
        cache_ttl = int(self.opts.get("cache_ttl", 3600))

        if cache_ttl > 0:
            cached = self.cache_get(cache_key)
            if cached is not None:
                self.debug(f"Cache hit for {ip}")
                return cached

        # HTTP request with auth header
        headers = {
            'Authorization': f"Bearer {self.opts['api_key']}"
        }
        res = self.fetch_url(
            f"https://ipinfo.io/{ip}/json",
            timeout=self.opts.get('_fetchtimeout', 15),
            headers=headers,
        )

        if res is None:
            return None

        if res.get('code') == "429":
            self.error("You are being rate-limited by ipinfo.io.")
            self.errorState = True
            return None

        if res.get('content') is None:
            self.info(f"No GeoIP info found for {ip}")
            return None

        try:
            data = json.loads(res['content'])
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")
            return None

        # Store in cache (NEW)
        if cache_ttl > 0 and data:
            self.cache_put(cache_key, data, ttl=cache_ttl)

        return data

    def handleEvent(self, event) -> None:
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.opts['api_key'] == "":
            self.error(
                "You enabled sfp_ipinfo_modern but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        data = self.queryIP(eventData)

        if data is None:
            return

        if 'country' not in data:
            return

        location = ', '.join(
            [_f for _f in [
                data.get('city'),
                data.get('region'),
                data.get('country'),
            ] if _f]
        )
        self.info(f"Found GeoIP for {eventData}: {location}")

        evt = SpiderFootEvent("GEOINFO", location, self.__name__, event)
        self.notifyListeners(evt)
