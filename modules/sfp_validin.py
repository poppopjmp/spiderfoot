from __future__ import annotations

"""SpiderFoot plug-in module: validin."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_validin
# Purpose:     Query Validin for passive DNS, subdomain, certificate and
#              reputation data for domains and IP addresses.
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


class sfp_validin(SpiderFootAsyncPlugin):

    """Query Validin for passive DNS, subdomains, certificates and reputation data."""

    meta = {
        'name': "Validin",
        'summary': "Query Validin for passive DNS history, subdomains, certificate transparency and reputation data.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Passive DNS"],
        'dataSource': {
            'website': "https://validin.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://docs.validin.com/reference",
                "https://docs.validin.com/docs/overview-3",
            ],
            'apiKeyInstructions': [
                "Visit https://app.validin.com/",
                "Register a free account",
                "Navigate to Account settings",
                "Your API key is listed under API Keys",
            ],
            'favIcon': "https://validin.com/favicon.ico",
            'logo': "https://validin.com/logo.png",
            'description': (
                "Validin is a domain and IP intelligence platform that provides "
                "historical passive DNS, WHOIS history, HTTP crawl fingerprinting, "
                "certificate transparency data, and reputation scoring for "
                "cyber threat intelligence and security analysis."
            ),
        }
    }

    opts = {
        'api_key': "",
        'fetch_subdomains': True,
        'fetch_certificates': True,
        'fetch_reputation': True,
    }

    optdescs = {
        'api_key': "Validin API key.",
        'fetch_subdomains': "Retrieve subdomains for domain targets?",
        'fetch_certificates': "Retrieve certificate transparency data for domain targets?",
        'fetch_reputation': "Retrieve reputation scores for targets?",
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
        return ["DOMAIN_NAME", "INTERNET_NAME", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "RAW_RIR_DATA",
            "SSL_CERTIFICATE_RAW",
            "MALICIOUS_INTERNET_NAME",
            "MALICIOUS_IPADDR",
            "DNS_TEXT",
        ]

    def _query(self, endpoint: str) -> dict | None:
        """Make an authenticated request to the Validin API.

        Args:
            endpoint: API endpoint path (e.g. '/api/axon/domain/dns/history/example.com').

        Returns:
            Parsed JSON dict or None on error.
        """
        headers = {
            'Authorization': f"Bearer {self.opts['api_key']}",
            'Accept': 'application/json',
        }

        res = self.fetch_url(
            f"https://app.validin.com{endpoint}",
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
            headers=headers,
        )

        time.sleep(1)

        if res['code'] in ["401", "403"]:
            self.error("Validin API key rejected or access denied.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("Validin rate limit exceeded.")
            self.errorState = True
            return None

        if res['code'] == "404":
            self.debug(f"No Validin data for endpoint: {endpoint}")
            return None

        if res['content'] is None:
            self.info(f"No Validin data for endpoint: {endpoint}")
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.error(f"Error parsing Validin JSON: {e}")
            return None

    def queryDomainDNS(self, domain: str) -> dict | None:
        """Query passive DNS history for a domain."""
        return self._query(f"/api/axon/domain/dns/history/{domain}")

    def queryDomainSubdomains(self, domain: str) -> dict | None:
        """Query subdomains for a domain."""
        return self._query(f"/api/axon/domain/subdomains/{domain}")

    def queryDomainCertificates(self, domain: str) -> dict | None:
        """Query certificate transparency data for a domain."""
        return self._query(f"/api/axon/domain/certificates/{domain}")

    def queryDomainReputation(self, domain: str) -> dict | None:
        """Query reputation data for a domain."""
        return self._query(f"/api/axon/domain/reputation/quick/{domain}")

    def queryIPDNS(self, ip: str) -> dict | None:
        """Query passive DNS history for an IP address."""
        return self._query(f"/api/axon/ip/dns/history/{ip}")

    def queryIPReputation(self, ip: str) -> dict | None:
        """Query reputation data for an IP address."""
        return self._query(f"/api/axon/ip/reputation/quick/{ip}")

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {event.module}")

        if self.opts['api_key'] == "":
            self.error("You enabled sfp_validin but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName in ["DOMAIN_NAME", "INTERNET_NAME"]:
            self._handleDomain(event, eventData)
        elif eventName in ["IP_ADDRESS", "IPV6_ADDRESS"]:
            self._handleIP(event, eventData)

    def _handleDomain(self, event: SpiderFootEvent, domain: str) -> None:
        """Process a domain event through Validin APIs."""
        # 1. Passive DNS history
        dns_data = self.queryDomainDNS(domain)
        if dns_data:
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", str(dns_data), self.__name__, event)
            self.notifyListeners(evt)

            # Extract IP addresses from DNS records
            for record_type in ['a', 'aaaa']:
                for record in dns_data.get('records', {}).get(record_type, []):
                    ip = record.get('value', '') if isinstance(record, dict) else str(record)
                    if ip and ip not in self.results:
                        self.results[ip] = True
                        etype = "IPV6_ADDRESS" if record_type == 'aaaa' else "IP_ADDRESS"
                        evt = SpiderFootEvent(etype, ip, self.__name__, event)
                        self.notifyListeners(evt)

            # Extract TXT records
            for record in dns_data.get('records', {}).get('txt', []):
                txt = record.get('value', '') if isinstance(record, dict) else str(record)
                if txt:
                    evt = SpiderFootEvent("DNS_TEXT", txt, self.__name__, event)
                    self.notifyListeners(evt)

        if self.checkForStop():
            return

        # 2. Subdomains
        if self.opts.get('fetch_subdomains', True):
            sub_data = self.queryDomainSubdomains(domain)
            if sub_data:
                subdomains = sub_data.get('subdomains', [])
                if isinstance(subdomains, list):
                    for sub in subdomains:
                        subdomain = sub.get('domain', sub) if isinstance(sub, dict) else str(sub)
                        if subdomain and subdomain not in self.results:
                            self.results[subdomain] = True
                            if self.getTarget().matches(subdomain):
                                evt = SpiderFootEvent(
                                    "INTERNET_NAME", subdomain, self.__name__, event)
                                self.notifyListeners(evt)
                            else:
                                evt = SpiderFootEvent(
                                    "INTERNET_NAME_UNRESOLVED", subdomain, self.__name__, event)
                                self.notifyListeners(evt)

        if self.checkForStop():
            return

        # 3. Certificates
        if self.opts.get('fetch_certificates', True):
            cert_data = self.queryDomainCertificates(domain)
            if cert_data:
                certs = cert_data.get('certificates', [])
                if isinstance(certs, list):
                    for cert in certs:
                        cert_raw = cert.get('raw', '') if isinstance(cert, dict) else ''
                        if cert_raw:
                            evt = SpiderFootEvent(
                                "SSL_CERTIFICATE_RAW", cert_raw, self.__name__, event)
                            self.notifyListeners(evt)

                        # Extract domains from certificate SANs
                        sans = cert.get('sans', []) if isinstance(cert, dict) else []
                        for san in sans:
                            if san and san not in self.results and not san.startswith('*'):
                                self.results[san] = True
                                if self.getTarget().matches(san):
                                    evt = SpiderFootEvent(
                                        "INTERNET_NAME", san, self.__name__, event)
                                    self.notifyListeners(evt)

        if self.checkForStop():
            return

        # 4. Reputation
        if self.opts.get('fetch_reputation', True):
            rep_data = self.queryDomainReputation(domain)
            if rep_data:
                score = rep_data.get('score', 0)
                verdict = rep_data.get('verdict', '')
                if verdict and verdict.lower() in ['malicious', 'suspicious', 'phishing']:
                    evt = SpiderFootEvent(
                        "MALICIOUS_INTERNET_NAME",
                        f"Validin [{domain}] - Verdict: {verdict} (Score: {score})",
                        self.__name__,
                        event,
                    )
                    self.notifyListeners(evt)

    def _handleIP(self, event: SpiderFootEvent, ip: str) -> None:
        """Process an IP address event through Validin APIs."""
        # 1. Passive DNS history for IP
        dns_data = self.queryIPDNS(ip)
        if dns_data:
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", str(dns_data), self.__name__, event)
            self.notifyListeners(evt)

            # Extract hostnames that resolved to this IP
            for record in dns_data.get('records', {}).get('a', []):
                hostname = record.get('domain', '') if isinstance(record, dict) else str(record)
                if hostname and hostname not in self.results:
                    self.results[hostname] = True
                    if self.getTarget().matches(hostname):
                        evt = SpiderFootEvent(
                            "INTERNET_NAME", hostname, self.__name__, event)
                        self.notifyListeners(evt)
                    else:
                        evt = SpiderFootEvent(
                            "INTERNET_NAME_UNRESOLVED", hostname, self.__name__, event)
                        self.notifyListeners(evt)

            for record in dns_data.get('records', {}).get('aaaa', []):
                hostname = record.get('domain', '') if isinstance(record, dict) else str(record)
                if hostname and hostname not in self.results:
                    self.results[hostname] = True
                    if self.getTarget().matches(hostname):
                        evt = SpiderFootEvent(
                            "INTERNET_NAME", hostname, self.__name__, event)
                        self.notifyListeners(evt)
                    else:
                        evt = SpiderFootEvent(
                            "INTERNET_NAME_UNRESOLVED", hostname, self.__name__, event)
                        self.notifyListeners(evt)

        if self.checkForStop():
            return

        # 2. Reputation for IP
        if self.opts.get('fetch_reputation', True):
            rep_data = self.queryIPReputation(ip)
            if rep_data:
                score = rep_data.get('score', 0)
                verdict = rep_data.get('verdict', '')
                if verdict and verdict.lower() in ['malicious', 'suspicious']:
                    evt = SpiderFootEvent(
                        "MALICIOUS_IPADDR",
                        f"Validin [{ip}] - Verdict: {verdict} (Score: {score})",
                        self.__name__,
                        event,
                    )
                    self.notifyListeners(evt)

# End of sfp_validin class
