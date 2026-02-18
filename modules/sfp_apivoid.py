from __future__ import annotations

"""SpiderFoot plug-in module: apivoid."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_apivoid
# Purpose:     Query APIVoid for IP reputation, domain reputation and
#              threat intelligence data.
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
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_apivoid(SpiderFootModernPlugin):

    """Query APIVoid for IP and domain reputation, blacklist checks and threat intelligence."""

    meta = {
        'name': "APIVoid",
        'summary': "Query APIVoid for IP and domain reputation, blacklist detections, geolocation and anonymity data.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://www.apivoid.com/",
            'model': "COMMERCIAL_ONLY",
            'references': [
                "https://docs.apivoid.com/",
                "https://www.apivoid.com/api/ip-reputation/",
                "https://www.apivoid.com/api/domain-reputation/",
            ],
            'apiKeyInstructions': [
                "Visit https://www.apivoid.com/",
                "Register for an account",
                "Subscribe to a plan (30-day free trial available)",
                "Navigate to your Dashboard to find your API key",
            ],
            'favIcon': "https://www.apivoid.com/favicon.ico",
            'logo': "https://www.apivoid.com/images/apivoid-logo.png",
            'description': (
                "APIVoid provides IP and domain reputation APIs that check "
                "against 70+ blacklist engines. It offers threat intelligence "
                "including anonymity detection (proxy, VPN, Tor), geolocation, "
                "risk scoring and blacklist analysis."
            ),
        }
    }

    opts = {
        'api_key': "",
        'risk_threshold': 50,
        'check_ip': True,
        'check_domain': True,
    }

    optdescs = {
        'api_key': "APIVoid API key.",
        'risk_threshold': "Risk score threshold (0-100). IPs/domains scoring above this are flagged as malicious.",
        'check_ip': "Check IP address reputation?",
        'check_domain': "Check domain reputation?",
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
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "DOMAIN_NAME",
            "INTERNET_NAME",
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "MALICIOUS_IPADDR",
            "MALICIOUS_INTERNET_NAME",
            "GEOINFO",
            "RAW_RIR_DATA",
        ]

    # ---- API helpers ----

    def _apiGet(self, endpoint: str, params: dict) -> dict | None:
        """Make a GET request to the APIVoid v1 REST API.

        APIVoid v1 uses GET with key as a query parameter.
        """
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://endpoint.apivoid.com/{endpoint}/v1/pay-as-you-go/?key={self.opts['api_key']}&{param_str}"

        res = self.fetch_url(
            url,
            timeout=self.opts.get('_fetchtimeout', 30),
            useragent="SpiderFoot",
        )

        if not res:
            self.error(f"No response from APIVoid ({endpoint})")
            return None

        if res['code'] in ["401", "403"]:
            self.error("APIVoid API key is invalid or account issue.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("APIVoid rate limit exceeded.")
            return None

        if res['code'] not in ["200"]:
            self.error(f"Unexpected HTTP {res['code']} from APIVoid ({endpoint})")
            return None

        if not res.get('content'):
            self.debug(f"Empty response from APIVoid ({endpoint})")
            return None

        try:
            data = json.loads(res['content'])
            if data.get('error'):
                self.error(f"APIVoid error: {data.get('error')}")
                return None
            return data
        except (ValueError, TypeError) as e:
            self.error(f"Error parsing APIVoid response: {e}")
            return None

    def queryIPReputation(self, ip: str) -> dict | None:
        """Query the IP Reputation API."""
        return self._apiGet("iprep", {"ip": ip})

    def queryDomainReputation(self, domain: str) -> dict | None:
        """Query the Domain Reputation API."""
        return self._apiGet("domainbl", {"host": domain})

    # ---- Event handler ----

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if not self.opts.get('api_key'):
            self.error("You enabled sfp_apivoid but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventName in ("IP_ADDRESS", "IPV6_ADDRESS"):
            if self.opts.get('check_ip'):
                self._handleIP(event, eventData)
        elif eventName in ("DOMAIN_NAME", "INTERNET_NAME"):
            if self.opts.get('check_domain'):
                self._handleDomain(event, eventData)

    def _handleIP(self, event: SpiderFootEvent, ip: str) -> None:
        """Process IP reputation lookup."""
        data = self.queryIPReputation(ip)
        if not data:
            return

        report = data.get('data', {}).get('report', {})
        if not report:
            return

        # Emit raw data
        evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(report, indent=2), self.__name__, event)
        self.notifyListeners(evt)

        # Geolocation
        info = report.get('information', {})
        geo_parts = []
        if info.get('city_name'):
            geo_parts.append(info['city_name'])
        if info.get('region_name'):
            geo_parts.append(info['region_name'])
        if info.get('country_name'):
            geo_parts.append(info['country_name'])
        if geo_parts:
            geo_str = ", ".join(geo_parts)
            evt = SpiderFootEvent("GEOINFO", geo_str, self.__name__, event)
            self.notifyListeners(evt)

        # Blacklist / Risk assessment
        blacklists = report.get('blacklists', {})
        risk_score = report.get('risk_score', {}).get('result', 0)
        detections = blacklists.get('detections', 0)
        detection_rate = blacklists.get('detection_rate', '0%')

        threshold = self.opts.get('risk_threshold', 50)
        if risk_score >= threshold or detections > 0:
            description = (
                f"APIVoid IP Reputation: risk_score={risk_score}/100, "
                f"blacklist_detections={detections} ({detection_rate})"
            )

            # Add anonymity flags if present
            anon = report.get('anonymity', {})
            anon_flags = []
            if anon.get('is_proxy'):
                anon_flags.append("proxy")
            if anon.get('is_vpn'):
                anon_flags.append("VPN")
            if anon.get('is_tor'):
                anon_flags.append("Tor")
            if anon.get('is_webproxy'):
                anon_flags.append("web-proxy")
            if anon.get('is_hosting'):
                anon_flags.append("hosting")
            if anon_flags:
                description += f", anonymity=[{', '.join(anon_flags)}]"

            evt = SpiderFootEvent(
                "MALICIOUS_IPADDR",
                f"{description} [{ip}]",
                self.__name__,
                event,
            )
            self.notifyListeners(evt)

    def _handleDomain(self, event: SpiderFootEvent, domain: str) -> None:
        """Process domain reputation lookup."""
        time.sleep(1)  # Rate limiting

        data = self.queryDomainReputation(domain)
        if not data:
            return

        report = data.get('data', {}).get('report', {})
        if not report:
            return

        # Emit raw data
        evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(report, indent=2), self.__name__, event)
        self.notifyListeners(evt)

        # Blacklist detections
        blacklists = report.get('blacklists', {})
        detections = blacklists.get('detections', 0)
        detection_rate = blacklists.get('detection_rate', '0%')
        risk_score = report.get('risk_score', {}).get('result', 0)

        threshold = self.opts.get('risk_threshold', 50)
        if risk_score >= threshold or detections > 0:
            description = (
                f"APIVoid Domain Reputation: risk_score={risk_score}/100, "
                f"blacklist_detections={detections} ({detection_rate})"
            )

            evt = SpiderFootEvent(
                "MALICIOUS_INTERNET_NAME",
                f"{description} [{domain}]",
                self.__name__,
                event,
            )
            self.notifyListeners(evt)

# End of sfp_apivoid class
