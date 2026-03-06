from __future__ import annotations

"""SpiderFoot plug-in module: bevigil."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_bevigil
# Purpose:     Query BeVigil OSINT API for subdomains, URLs and associated
#              mobile app packages discovered from mobile app analysis.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_bevigil(SpiderFootAsyncPlugin):

    """Query BeVigil OSINT API for subdomains, URLs, and mobile app packages associated with domains."""

    meta = {
        'name': "BeVigil",
        'summary': "Query BeVigil OSINT API for subdomains, URLs, S3 buckets and mobile app packages discovered from mobile app analysis.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Passive DNS"],
        'dataSource': {
            'website': "https://bevigil.com/osint-api",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://bevigil.com/osint-api",
                "https://github.com/Bevigil/BeVigil-OSINT-CLI",
            ],
            'apiKeyInstructions': [
                "Visit https://bevigil.com/osint-api",
                "Register a free account",
                "Free tier provides 50 queries per month",
                "Your API key is available in your account dashboard",
            ],
            'favIcon': "https://bevigil.com/favicon.ico",
            'logo': "https://bevigil.com/assets/images/logo.png",
            'description': (
                "BeVigil is an OSINT platform that discovers subdomains, URLs, "
                "S3 buckets, and associated mobile app packages by analysing "
                "mobile applications. Free tier offers 50 queries per month."
            ),
        }
    }

    opts = {
        'api_key': "",
        'fetch_subdomains': True,
        'fetch_urls': True,
        'fetch_s3buckets': True,
    }

    optdescs = {
        'api_key': "BeVigil OSINT API key.",
        'fetch_subdomains': "Discover subdomains for a domain?",
        'fetch_urls': "Discover URLs for a domain?",
        'fetch_s3buckets': "Discover S3 buckets related to the domain?",
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
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "LINKED_URL_EXTERNAL",
            "CLOUD_STORAGE_OPEN",
            "RAW_RIR_DATA",
        ]

    # ---- API helpers ----

    def _apiGet(self, endpoint: str) -> dict | None:
        """Make a GET request to the BeVigil OSINT API."""
        url = f"https://osint.bevigil.com/api/{endpoint}"

        res = self.fetch_url(
            url,
            timeout=self.opts.get('_fetchtimeout', 30),
            useragent="SpiderFoot",
            headers={"X-Access-Token": self.opts['api_key']},
        )

        if not res:
            self.error(f"No response from BeVigil API ({endpoint})")
            return None

        if res['code'] in ["401", "403"]:
            self.error("BeVigil API key is invalid or expired.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("BeVigil API rate limit exceeded (50 queries/month on free tier).")
            self.errorState = True
            return None

        if res['code'] not in ["200"]:
            self.error(f"Unexpected HTTP {res['code']} from BeVigil API")
            return None

        if not res.get('content'):
            self.debug(f"Empty response from BeVigil API ({endpoint})")
            return None

        try:
            return json.loads(res['content'])
        except (ValueError, TypeError) as e:
            self.error(f"Error parsing BeVigil response: {e}")
            return None

    def querySubdomains(self, domain: str) -> dict | None:
        """Query subdomains for a domain."""
        return self._apiGet(f"{domain}/subdomains/")

    def queryUrls(self, domain: str) -> dict | None:
        """Query URLs found in mobile apps for a domain."""
        return self._apiGet(f"{domain}/urls/")

    def queryS3Buckets(self, domain: str) -> dict | None:
        """Query S3 buckets associated with a domain/keyword."""
        return self._apiGet(f"{domain}/s3-buckets/")

    # ---- Event handler ----

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if not self.opts.get('api_key'):
            self.error("You enabled sfp_bevigil but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {event.module}")

        # Subdomains
        if self.opts.get('fetch_subdomains'):
            self._processSubdomains(event, eventData)
            time.sleep(1)

        if self.checkForStop() or self.errorState:
            return

        # URLs
        if self.opts.get('fetch_urls'):
            self._processUrls(event, eventData)
            time.sleep(1)

        if self.checkForStop() or self.errorState:
            return

        # S3 Buckets
        if self.opts.get('fetch_s3buckets'):
            self._processS3Buckets(event, eventData)

    def _processSubdomains(self, event: SpiderFootEvent, domain: str) -> None:
        """Fetch and emit subdomain events."""
        data = self.querySubdomains(domain)
        if not data:
            return

        subdomains = data.get('subdomains', [])
        if not subdomains:
            self.debug(f"No subdomains found for {domain} via BeVigil")
            return

        evt = SpiderFootEvent(
            "RAW_RIR_DATA", json.dumps(data, indent=2), self.__name__, event)
        self.notifyListeners(evt)

        for sub in subdomains:
            if not sub or not isinstance(sub, str):
                continue

            if self.checkForStop():
                return

            sub = sub.strip().lower()
            if not sub:
                continue

            if sub in self.results:
                continue
            self.results[sub] = True

            if self.getTarget().matches(sub):
                evt = SpiderFootEvent(
                    "INTERNET_NAME", sub, self.__name__, event)
                self.notifyListeners(evt)
            else:
                evt = SpiderFootEvent(
                    "INTERNET_NAME_UNRESOLVED", sub, self.__name__, event)
                self.notifyListeners(evt)

    def _processUrls(self, event: SpiderFootEvent, domain: str) -> None:
        """Fetch and emit URL events."""
        data = self.queryUrls(domain)
        if not data:
            return

        urls = data.get('urls', [])
        if not urls:
            self.debug(f"No URLs found for {domain} via BeVigil")
            return

        for url in urls:
            if not url or not isinstance(url, str):
                continue

            if self.checkForStop():
                return

            url = url.strip()
            if not url:
                continue

            if url in self.results:
                continue
            self.results[url] = True

            evt = SpiderFootEvent(
                "LINKED_URL_EXTERNAL", url, self.__name__, event)
            self.notifyListeners(evt)

    def _processS3Buckets(self, event: SpiderFootEvent, domain: str) -> None:
        """Fetch and emit S3 bucket events."""
        data = self.queryS3Buckets(domain)
        if not data:
            return

        buckets = data.get('s3_buckets', [])
        if not buckets:
            self.debug(f"No S3 buckets found for {domain} via BeVigil")
            return

        for bucket in buckets:
            if not bucket or not isinstance(bucket, str):
                continue

            if self.checkForStop():
                return

            bucket = bucket.strip()
            if not bucket:
                continue

            if bucket in self.results:
                continue
            self.results[bucket] = True

            evt = SpiderFootEvent(
                "CLOUD_STORAGE_OPEN", bucket, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_bevigil class
