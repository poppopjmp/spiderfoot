# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_virustotal
# Purpose:      Query VirusTotal for identified IP addresses.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     21/03/2014
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""SpiderFoot plug-in module: virustotal."""

import json
import time

from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_virustotal(SpiderFootModernPlugin):

    """Obtain information from VirusTotal about identified IP addresses."""

    meta = {
        'name': "VirusTotal",
        'summary': "Obtain information from VirusTotal about identified IP addresses.",
        'flags': ["apikey"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://www.virustotal.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://docs.virustotal.com/reference/overview"
            ],
            'apiKeyInstructions': [
                "Visit https://www.virustotal.com/",
                "Register a free account",
                "Click on your profile",
                "Click on API Key",
                "The API key is listed under 'API Key'"
            ],
            'favIcon': "https://www.virustotal.com/gui/images/favicon.png",
            'logo': "https://www.virustotal.com/gui/images/logo.svg",
            'description': "Analyze suspicious files and URLs to detect types of malware, "
            "automatically share them with the security community.",
        }
    }

    opts = {
        'api_key': '',
        'verify': True,
        'publicapi': True,
        'checkcohosts': True,
        'checkaffiliates': True,
        'netblocklookup': True,
        'maxnetblock': 24,
        'subnetlookup': True,
        'maxsubnet': 24,
        '_fetchtimeout': 5
    }

    optdescs = {
        'api_key': 'VirusTotal API Key.',
        'publicapi': 'Are you using a public key? If so SpiderFoot will pause for 15 seconds after each query to avoid VirusTotal dropping requests.',
        'checkcohosts': 'Check co-hosted sites?',
        'checkaffiliates': 'Check affiliates?',
        'netblocklookup': 'Look up all IPs on netblocks deemed to be owned by your target for possible hosts on the same target subdomain/domain?',
        'maxnetblock': 'If looking up owned netblocks, the maximum netblock size to look up all IPs within (CIDR value, 24 = /24, 16 = /16, etc.)',
        'subnetlookup': 'Look up all IPs on subnets which your target is a part of?',
        'maxsubnet': 'If looking up subnets, the maximum subnet size to look up all the IPs within (CIDR value, 24 = /24, 16 = /16, etc.)',
        'verify': 'Verify that any hostnames found on the target domain still resolve?',
        '_fetchtimeout': 'Number of seconds to wait for a response from VirusTotal.'
    }

    results = None
    errorState = False

    def __init__(self) -> None:
        """Initialize the sfp virustotal."""
        super().__init__()

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "IP_ADDRESS",
            "AFFILIATE_IPADDR",
            "INTERNET_NAME",
            "CO_HOSTED_SITE",
            "NETBLOCK_OWNER",
            "NETBLOCK_MEMBER"
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "MALICIOUS_IPADDR",
            "MALICIOUS_INTERNET_NAME",
            "MALICIOUS_COHOST",
            "MALICIOUS_AFFILIATE_INTERNET_NAME",
            "MALICIOUS_AFFILIATE_IPADDR",
            "MALICIOUS_NETBLOCK",
            "MALICIOUS_SUBNET",
            "INTERNET_NAME",
            "AFFILIATE_INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "DOMAIN_NAME",
            "AFFILIATE_DOMAIN_NAME",
        ]

    def _vtHeaders(self) -> dict:
        """Return authentication headers for VirusTotal API v3."""
        return {
            'x-apikey': self.opts['api_key'],
            'accept': 'application/json'
        }

    def queryIp(self, qry: str) -> dict | None:
        """Query IP address via VirusTotal API v3."""
        res = self.fetch_url(
            f"https://www.virustotal.com/api/v3/ip_addresses/{qry}",
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
            headers=self._vtHeaders()
        )

        # Public API is limited to 4 queries per minute
        if self.opts['publicapi']:
            time.sleep(15)

        if res is None or res['content'] is None:
            self.info(f"No VirusTotal info found for {qry}")
            return None

        if str(res.get('code', '')) in ("204", "429"):
            self.error("Your request to VirusTotal was throttled.")
            self.errorState = True
            return None

        if str(res.get('code', '')) == "404":
            self.info(f"No VirusTotal info found for {qry}")
            return None

        try:
            data = json.loads(res['content'])
            return data.get('data', {})
        except Exception as e:
            self.error(f"Error processing JSON response from VirusTotal: {e}")
            self.errorState = True

        return None

    def queryDomain(self, qry: str) -> dict | None:
        """Query Domain via VirusTotal API v3."""
        res = self.fetch_url(
            f"https://www.virustotal.com/api/v3/domains/{qry}",
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
            headers=self._vtHeaders()
        )

        if res is None or str(res.get('code', '')) in ("204", "429"):
            self.error("Your request to VirusTotal was throttled.")
            self.errorState = True
            return None

        # Public API is limited to 4 queries per minute
        if self.opts['publicapi']:
            time.sleep(15)

        if str(res.get('code', '')) == "404":
            self.info(f"No VirusTotal info found for {qry}")
            return None

        if res['content'] is None:
            self.info(f"No VirusTotal info found for {qry}")
            return None

        try:
            data = json.loads(res['content'])
            return data.get('data', {})
        except Exception as e:
            self.error(f"Error processing JSON response from VirusTotal: {e}")
            self.errorState = True

        return None

    def queryRelationship(self, domain: str, relationship: str) -> list:
        """Query domain relationship (siblings/subdomains) via v3 API."""
        domains = []
        res = self.fetch_url(
            f"https://www.virustotal.com/api/v3/domains/{domain}/{relationship}?limit=40",
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
            headers=self._vtHeaders()
        )

        if self.opts['publicapi']:
            time.sleep(15)

        if res is None or res['content'] is None:
            return domains

        try:
            data = json.loads(res['content'])
            for item in data.get('data', []):
                domain_id = item.get('id')
                if domain_id:
                    domains.append(domain_id)
        except Exception as e:
            self.error(f"Error processing relationship response: {e}")

        return domains

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.opts["api_key"] == "":
            self.error(
                f"You enabled {self.__class__.__name__} but did not set an API key!"
            )
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName.startswith("AFFILIATE") and not self.opts['checkaffiliates']:
            return

        if eventName == 'CO_HOSTED_SITE' and not self.opts['checkcohosts']:
            return

        if eventName == 'NETBLOCK_OWNER':
            if not self.opts['netblocklookup']:
                return

            net_size = IPNetwork(eventData).prefixlen
            max_netblock = self.opts['maxnetblock']
            if net_size < max_netblock:
                self.debug(
                    f"Network size {net_size} bigger than permitted: {max_netblock}")
                return

        if eventName == 'NETBLOCK_MEMBER':
            if not self.opts['subnetlookup']:
                return

            net_size = IPNetwork(eventData).prefixlen
            max_subnet = self.opts['maxsubnet']
            if net_size < max_subnet:
                self.debug(
                    f"Network size {net_size} bigger than permitted: {max_subnet}")
                return

        qrylist = list()
        if eventName.startswith("NETBLOCK_"):
            for ipaddr in IPNetwork(eventData):
                qrylist.append(str(ipaddr))
                self.results[str(ipaddr)] = True
        else:
            qrylist.append(eventData)

        for addr in qrylist:
            if self.checkForStop():
                return

            if self.sf.validIP(addr):
                info = self.queryIp(addr)
            else:
                info = self.queryDomain(addr)

            if info is None:
                continue

            # v3: Check last_analysis_stats for malicious/suspicious detections
            attrs = info.get('attributes', {})
            stats = attrs.get('last_analysis_stats', {})
            malicious_count = stats.get('malicious', 0)
            suspicious_count = stats.get('suspicious', 0)

            if malicious_count > 0 or suspicious_count > 0:
                self.info(f"Found VirusTotal detections for {addr}")

                if eventName in ["IP_ADDRESS"] or eventName.startswith("NETBLOCK_"):
                    evt = "MALICIOUS_IPADDR"
                    infotype = "ip-address"

                if eventName == "AFFILIATE_IPADDR":
                    evt = "MALICIOUS_AFFILIATE_IPADDR"
                    infotype = "ip-address"

                if eventName == "INTERNET_NAME":
                    evt = "MALICIOUS_INTERNET_NAME"
                    infotype = "domain"

                if eventName == "AFFILIATE_INTERNET_NAME":
                    evt = "MALICIOUS_AFFILIATE_INTERNET_NAME"
                    infotype = "domain"

                if eventName == "CO_HOSTED_SITE":
                    evt = "MALICIOUS_COHOST"
                    infotype = "domain"

                infourl = f"<SFURL>https://www.virustotal.com/gui/{infotype}/{addr}</SFURL>"

                e = SpiderFootEvent(
                    evt, f"VirusTotal [{addr}]\n{infourl}",
                    self.__class__.__name__,
                    event
                )
                self.notifyListeners(e)

            domains = list()

            # v3: Siblings and subdomains are fetched via relationships API
            if eventName in ["IP_ADDRESS", "INTERNET_NAME"] and not self.sf.validIP(addr):
                for domain in self.queryRelationship(addr, 'siblings'):
                    domains.append(domain)

            if eventName == "INTERNET_NAME" and not self.sf.validIP(addr):
                for domain in self.queryRelationship(addr, 'subdomains'):
                    domains.append(domain)

            for domain in set(domains):
                if domain in self.results:
                    continue

                if self.getTarget().matches(domain):
                    evt_type = 'INTERNET_NAME'
                else:
                    evt_type = 'AFFILIATE_INTERNET_NAME'

                if self.opts['verify'] and not self.resolve_host(domain) and not self.resolve_host6(domain):
                    self.debug(f"Host {domain} could not be resolved")
                    evt_type += '_UNRESOLVED'

                evt = SpiderFootEvent(evt_type, domain, self.__class__.__name__, event)
                self.notifyListeners(evt)

                if self.sf.isDomain(domain, self.opts['_internettlds']):
                    if evt_type.startswith('AFFILIATE'):
                        evt = SpiderFootEvent(
                            'AFFILIATE_DOMAIN_NAME', domain, self.__class__.__name__, event)
                        self.notifyListeners(evt)
                    else:
                        evt = SpiderFootEvent(
                            'DOMAIN_NAME', domain, self.__class__.__name__, event)
                        self.notifyListeners(evt)

# End of sfp_virustotal class
