from __future__ import annotations

"""SpiderFoot plug-in module: whoisxmlapi."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_whoisxmlapi
# Purpose:     Query WhoisXML API for WHOIS records, subdomain discovery,
#              IP geolocation and domain reputation.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib.parse

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_whoisxmlapi(SpiderFootAsyncPlugin):

    """Query WhoisXML API for WHOIS records, subdomain discovery, IP geolocation and domain reputation."""

    meta = {
        'name': "WhoisXML API",
        'summary': "Query WhoisXML API for WHOIS records, subdomain discovery, IP geolocation and domain reputation.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://www.whoisxmlapi.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://whois.whoisxmlapi.com/documentation/making-requests",
                "https://subdomains.whoisxmlapi.com/api/documentation/making-requests",
                "https://ip-geolocation.whoisxmlapi.com/api/documentation/making-requests",
                "https://domain-reputation.whoisxmlapi.com/api/documentation/making-requests",
            ],
            'apiKeyInstructions': [
                "Visit https://www.whoisxmlapi.com/",
                "Sign up for a free account",
                "Navigate to https://user.whoisxmlapi.com/products",
                "Your API key is listed on the products page",
            ],
            'favIcon': "https://main.whoisxmlapi.com/favicon.ico",
            'logo': "https://main.whoisxmlapi.com/themes/flavor/modules/template/assets/img/base/wxalogo.svg",
            'description': (
                "WhoisXML API provides comprehensive domain and IP intelligence "
                "including WHOIS records, subdomain discovery, IP geolocation, "
                "and domain reputation scoring. Free tier offers 500 API credits."
            ),
        }
    }

    opts = {
        'api_key': "",
        'fetch_whois': True,
        'fetch_subdomains': True,
        'fetch_geolocation': True,
        'fetch_reputation': True,
        'reputation_threshold': 70,
        'max_subdomains': 500,
    }

    optdescs = {
        'api_key': "WhoisXML API key.",
        'fetch_whois': "Fetch WHOIS records for domains?",
        'fetch_subdomains': "Discover subdomains via the Subdomains Lookup API?",
        'fetch_geolocation': "Fetch IP geolocation data?",
        'fetch_reputation': "Fetch domain reputation scores?",
        'reputation_threshold': "Domain reputation score threshold (0-100). Domains scoring below this are flagged as potentially malicious.",
        'max_subdomains': "Maximum number of subdomains to return per domain.",
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
            "IPV6_ADDRESS",
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "DOMAIN_WHOIS",
            "DOMAIN_REGISTRAR",
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "GEOINFO",
            "RAW_RIR_DATA",
            "MALICIOUS_INTERNET_NAME",
        ]

    # ---- API query helpers ----

    def _apiCall(self, url: str) -> dict | None:
        """Make an API call and return parsed JSON response.

        Returns None on error, sets errorState on auth failures.
        """
        res = self.fetch_url(
            url,
            timeout=self.opts.get('_fetchtimeout', 30),
            useragent="SpiderFoot",
        )

        if not res:
            self.error(f"No response from WhoisXML API: {url}")
            return None

        if res['code'] in ["401", "403"]:
            self.error("WhoisXML API key is invalid or rate limit exceeded.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("WhoisXML API rate limit exceeded.")
            return None

        if res['code'] not in ["200"]:
            self.error(f"Unexpected HTTP status {res['code']} from WhoisXML API")
            return None

        if not res.get('content'):
            self.debug("Empty response from WhoisXML API")
            return None

        try:
            return json.loads(res['content'])
        except (ValueError, TypeError) as e:
            self.error(f"Error parsing WhoisXML API response: {e}")
            return None

    def queryWhois(self, domain: str) -> dict | None:
        """Query the WHOIS API for a domain.

        GET https://www.whoisxmlapi.com/whoisserver/WhoisService?apiKey=KEY&domainName=DOMAIN&outputFormat=JSON
        """
        params = urllib.parse.urlencode({
            'apiKey': self.opts['api_key'],
            'domainName': domain,
            'outputFormat': 'JSON',
        })
        url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService?{params}"
        return self._apiCall(url)

    def querySubdomains(self, domain: str) -> dict | None:
        """Query the Subdomains Lookup API.

        GET https://subdomains.whoisxmlapi.com/api/v1?apiKey=KEY&domainName=DOMAIN&outputFormat=JSON
        """
        params = urllib.parse.urlencode({
            'apiKey': self.opts['api_key'],
            'domainName': domain,
            'outputFormat': 'JSON',
        })
        url = f"https://subdomains.whoisxmlapi.com/api/v1?{params}"
        return self._apiCall(url)

    def queryGeolocation(self, ip: str) -> dict | None:
        """Query the IP Geolocation API.

        GET https://ip-geolocation.whoisxmlapi.com/api/v1?apiKey=KEY&ipAddress=IP
        """
        params = urllib.parse.urlencode({
            'apiKey': self.opts['api_key'],
            'ipAddress': ip,
            'outputFormat': 'JSON',
        })
        url = f"https://ip-geolocation.whoisxmlapi.com/api/v1?{params}"
        return self._apiCall(url)

    def queryReputation(self, domain: str) -> dict | None:
        """Query the Domain Reputation API.

        GET https://domain-reputation.whoisxmlapi.com/api/v2?apiKey=KEY&domainName=DOMAIN&mode=fast
        """
        params = urllib.parse.urlencode({
            'apiKey': self.opts['api_key'],
            'domainName': domain,
            'mode': 'fast',
            'outputFormat': 'JSON',
        })
        url = f"https://domain-reputation.whoisxmlapi.com/api/v2?{params}"
        return self._apiCall(url)

    # ---- Event handlers ----

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        if not self.opts.get('api_key'):
            self.error("You enabled sfp_whoisxmlapi but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventName == "DOMAIN_NAME":
            self._handleDomain(event, eventData)
        elif eventName in ("IP_ADDRESS", "IPV6_ADDRESS"):
            self._handleIP(event, eventData)

    def _handleDomain(self, event: SpiderFootEvent, domain: str) -> None:
        """Process domain-related lookups: WHOIS, subdomains, reputation."""

        # 1. WHOIS Lookup
        if self.opts.get('fetch_whois'):
            self._processWhois(event, domain)
            time.sleep(1)

        if self.checkForStop():
            return

        # 2. Subdomains Lookup
        if self.opts.get('fetch_subdomains'):
            self._processSubdomains(event, domain)
            time.sleep(1)

        if self.checkForStop():
            return

        # 3. Domain Reputation
        if self.opts.get('fetch_reputation'):
            self._processReputation(event, domain)
            time.sleep(1)

    def _handleIP(self, event: SpiderFootEvent, ip: str) -> None:
        """Process IP-related lookups: geolocation."""
        if self.opts.get('fetch_geolocation'):
            self._processGeolocation(event, ip)

    # ---- Processing methods ----

    def _processWhois(self, event: SpiderFootEvent, domain: str) -> None:
        """Fetch and emit WHOIS data for a domain."""
        data = self.queryWhois(domain)
        if not data:
            return

        whois_record = data.get('WhoisRecord')
        if not whois_record:
            self.debug(f"No WhoisRecord in response for {domain}")
            return

        # Check for data errors
        data_error = whois_record.get('dataError')
        if data_error:
            self.debug(f"WhoisXML API data error for {domain}: {data_error}")
            return

        # Emit raw WHOIS text
        raw_text = whois_record.get('rawText')
        if raw_text and len(raw_text) > 50:
            evt = SpiderFootEvent("DOMAIN_WHOIS", raw_text, self.__name__, event)
            self.notifyListeners(evt)
        else:
            # Fall back to full JSON as RAW_RIR_DATA
            evt = SpiderFootEvent(
                "RAW_RIR_DATA",
                json.dumps(whois_record, ensure_ascii=False),
                self.__name__,
                event,
            )
            self.notifyListeners(evt)

        # Extract registrar
        registrar = whois_record.get('registrarName')
        if registrar:
            evt = SpiderFootEvent("DOMAIN_REGISTRAR", registrar, self.__name__, event)
            self.notifyListeners(evt)

        # Extract name servers as potential hostnames
        name_servers = whois_record.get('nameServers', {})
        hostnames = name_servers.get('hostNames', [])
        for ns in hostnames:
            if not ns:
                continue
            ns = ns.lower().strip().rstrip('.')
            if not ns:
                continue
            # Only emit if it belongs to the target domain
            if self.getTarget().matches(ns, includeChildren=True, includeParents=False):
                if ns not in self.results:
                    self.results[ns] = True
                    if self.sf.resolveHost(ns) or self.sf.resolveHost6(ns):
                        evt = SpiderFootEvent("INTERNET_NAME", ns, self.__name__, event)
                    else:
                        evt = SpiderFootEvent("INTERNET_NAME_UNRESOLVED", ns, self.__name__, event)
                    self.notifyListeners(evt)

    def _processSubdomains(self, event: SpiderFootEvent, domain: str) -> None:
        """Fetch and emit subdomains for a domain."""
        data = self.querySubdomains(domain)
        if not data:
            return

        result = data.get('result', {})
        records = result.get('records', [])

        if not records:
            self.debug(f"No subdomains found for {domain}")
            return

        count = 0
        max_results = self.opts.get('max_subdomains', 500)

        for record in records:
            if self.checkForStop():
                return

            subdomain = record.get('domain', '').lower().strip().rstrip('.')
            if not subdomain:
                continue

            if subdomain in self.results:
                continue

            if not self.getTarget().matches(subdomain, includeChildren=True, includeParents=False):
                continue

            self.results[subdomain] = True

            if self.sf.resolveHost(subdomain) or self.sf.resolveHost6(subdomain):
                evt = SpiderFootEvent("INTERNET_NAME", subdomain, self.__name__, event)
            else:
                evt = SpiderFootEvent("INTERNET_NAME_UNRESOLVED", subdomain, self.__name__, event)
            self.notifyListeners(evt)

            count += 1
            if count >= max_results:
                self.debug(f"Reached max_subdomains limit ({max_results}) for {domain}")
                break

    def _processGeolocation(self, event: SpiderFootEvent, ip: str) -> None:
        """Fetch and emit geolocation data for an IP address."""
        data = self.queryGeolocation(ip)
        if not data:
            return

        location = data.get('location', {})
        if not location:
            self.debug(f"No geolocation data for {ip}")
            return

        # Emit raw data
        evt = SpiderFootEvent(
            "RAW_RIR_DATA",
            json.dumps(data, ensure_ascii=False),
            self.__name__,
            event,
        )
        self.notifyListeners(evt)

        # Build GEOINFO string
        parts = []
        country = location.get('country')
        region = location.get('region')
        city = location.get('city')
        lat = location.get('lat')
        lng = location.get('lng')

        if city:
            parts.append(city)
        if region:
            parts.append(region)
        if country:
            parts.append(country)
        if lat is not None and lng is not None:
            parts.append(f"({lat}, {lng})")

        if parts:
            geo_key = f"{ip}-geo"
            if geo_key not in self.results:
                self.results[geo_key] = True
                geoinfo = ", ".join(parts)
                evt = SpiderFootEvent("GEOINFO", geoinfo, self.__name__, event)
                self.notifyListeners(evt)

    def _processReputation(self, event: SpiderFootEvent, domain: str) -> None:
        """Fetch and emit domain reputation data."""
        data = self.queryReputation(domain)
        if not data:
            return

        reputation_score = data.get('reputationScore')
        if reputation_score is None:
            self.debug(f"No reputation score for {domain}")
            return

        # Emit raw reputation data
        evt = SpiderFootEvent(
            "RAW_RIR_DATA",
            json.dumps(data, ensure_ascii=False),
            self.__name__,
            event,
        )
        self.notifyListeners(evt)

        threshold = self.opts.get('reputation_threshold', 70)

        # Lower score = worse reputation in WhoisXML API
        # reputationScore is 0-100; domains below threshold are suspicious
        if isinstance(reputation_score, (int, float)) and reputation_score < threshold:
            description = (
                f"WhoisXML API Domain Reputation: score {reputation_score}/100 "
                f"(threshold: {threshold}) - [{domain}]"
            )
            mal_key = f"{domain}-mal"
            if mal_key not in self.results:
                self.results[mal_key] = True
                evt = SpiderFootEvent(
                    "MALICIOUS_INTERNET_NAME",
                    description,
                    self.__name__,
                    event,
                )
                self.notifyListeners(evt)

# End of sfp_whoisxmlapi class
