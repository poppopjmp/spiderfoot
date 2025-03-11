# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_dnssublist
# Purpose:  Enumerate subdomains using DNS techniques (brute force, zone transfer, etc).
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import dns.resolver
import dns.query
import dns.zone
import random
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_dnssublist(SpiderFootPlugin):

    meta = {
        "name": "DNS Subdomain Enumerator",
        "summary": "Enumerate subdomains using various DNS techniques.",
        "flags": ["slow"],
        "useCases": ["Footprint", "Investigate"],
        "categories": ["DNS"],
        "dataSource": {
            "website": "https://tools.ietf.org/html/rfc1035",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": [
                "https://tools.ietf.org/html/rfc1035",
                "https://en.wikipedia.org/wiki/Domain_Name_System",
            ],
            "favIcon": "",
            "logo": "",
            "description": "This module uses various DNS techniques including zone transfers, "
            "common subdomain brute-forcing, and reverse DNS lookups to identify subdomains.",
        },
    }

    # Default options
    opts = {
        "zonecheck": True,
        "bruteforce": True,
        "resolveall": True,
        "validate": True,
        "subnetlookup": False,
        "maxthreads": 20,
        "wordlist": "default",
        "commons": True,
        "top_ports": "80,443,8080,8443",
    }

    # Option descriptions
    optdescs = {
        "zonecheck": "Check for DNS zone transfers.",
        "bruteforce": "Perform brute-forcing of common subdomain names.",
        "resolveall": "Resolve all identified domain names.",
        "validate": "Validate discovered domain names are actually valid.",
        "subnetlookup": "If IPs are found, look up subnets they belong to for more hosts.",
        "maxthreads": "Maximum number of DNS resolving threads.",
        "wordlist": "Wordlist to use for brute-forcing (default or path to file).",
        "commons": "Add common prefixes/suffixes to the domain name.",
        "top_ports": "Top ports to check for web servers when validating domains.",
    }

    # Common subdomains to check
    COMMON_SUBDOMAINS = [
        "www",
        "mail",
        "ftp",
        "webmail",
        "login",
        "admin",
        "shop",
        "blog",
        "dev",
        "test",
        "portal",
        "ns1",
        "ns2",
        "smtp",
        "secure",
        "vpn",
        "m",
        "cloud",
        "api",
        "cdn",
        "app",
        "exchange",
        "owa",
        "intranet",
        "remote",
        "server",
        "cpanel",
        "webdisk",
        "ssh",
        "mx",
    ]

    results = None
    errorState = False
    threaded = True
    subdomains = set()

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.subdomains = set()
        self.errorState = False

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        # Load custom wordlist if specified
        if self.opts["wordlist"] != "default" and self.opts["bruteforce"]:
            try:
                with open(self.opts["wordlist"], "r") as f:
                    self.COMMON_SUBDOMAINS = [
                        line.strip() for line in f if line.strip()
                    ]
                self.debug(
                    f"Loaded {len(self.COMMON_SUBDOMAINS)} subdomains from wordlist"
                )
            except Exception as e:
                self.error(f"Failed to load wordlist: {e}")
                self.errorState = True

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "INTERNET_NAME"]

    # What events this module produces
    def producedEvents(self):
        return [
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "DOMAIN_NAME",
            "RAW_DNS_RECORDS",
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "DNS_ZONE_TRANSFER",
        ]

    def tryZoneTransfer(self, domain):
        """Attempt DNS zone transfer."""
        target = domain
        nameservers = []

        # Find nameservers for domain
        try:
            answers = dns.resolver.resolve(target, "NS")
            nameservers = [str(answer).rstrip(".") for answer in answers]
        except Exception as e:
            self.debug(f"Error getting nameservers for {domain}: {e}")
            return False

        if not nameservers:
            self.debug(f"No nameservers found for {domain}")
            return False

        # Try zone transfer with each nameserver
        transferred = False
        zone_info = ""

        for ns in nameservers:
            try:
                self.debug(f"Attempting zone transfer from {ns} for {domain}")
                axfr = dns.query.xfr(ns, domain, timeout=10)
                zone = dns.zone.from_xfr(axfr)

                # Process zone data
                if zone:
                    transferred = True
                    zone_str = str(zone)
                    zone_info += f"Zone transfer successful from {ns}:\n{zone_str}\n"

                    # Extract records from zone
                    for name, node in zone.nodes.items():
                        name_str = str(name)
                        if name_str == "@":
                            record_name = domain
                        elif name_str.endswith("."):
                            record_name = name_str
                        else:
                            record_name = name_str + "." + domain

                        # Only process if it's a subdomain
                        if record_name.endswith(f".{domain}") or record_name == domain:
                            self.subdomains.add(
                                record_name.rstrip(".").lower())

            except Exception as e:
                self.debug(f"Zone transfer failed from {ns}: {e}")

        if transferred:
            evt = SpiderFootEvent(
                "DNS_ZONE_TRANSFER",
                zone_info.strip(),
                self.__name__,
                None,  # This is a new top-level event
            )
            self.notifyListeners(evt)

            evt = SpiderFootEvent(
                "RAW_DNS_RECORDS", zone_info.strip(), self.__name__, None
            )
            self.notifyListeners(evt)

            return True

        return False

    def bruteForceSubdomains(self, domain):
        """Brute force common subdomains."""
        found = False

        for prefix in self.COMMON_SUBDOMAINS:
            if self.checkForStop():
                return

            subdomain = f"{prefix}.{domain}"

            try:
                # Try resolving the subdomain
                answers = dns.resolver.resolve(subdomain, "A")
                if answers:
                    self.subdomains.add(subdomain.lower())
                    found = True
            except:
                # If A record fails, try for AAAA (IPv6)
                try:
                    answers = dns.resolver.resolve(subdomain, "AAAA")
                    if answers:
                        self.subdomains.add(subdomain.lower())
                        found = True
                except:
                    continue

            # Don't hammer the DNS server
            time.sleep(random.uniform(0.1, 0.3))

        return found

    def validateSubdomain(self, subdomain):
        """Validate a subdomain is resolvable and potentially active."""
        try:
            # Try for A record
            answers = dns.resolver.resolve(subdomain, "A")
            ips = [str(answer) for answer in answers]
            return True, ips, []
        except:
            try:
                # Try for AAAA record
                answers = dns.resolver.resolve(subdomain, "AAAA")
                ipv6s = [str(answer) for answer in answers]
                return True, [], ipv6s
            except:
                return False, [], []

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        parentEvent = event

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Extract the domain name if it's an internet name
        if eventName == "INTERNET_NAME":
            domain_parts = eventData.split(".")
            if len(domain_parts) > 2:
                domain = ".".join(domain_parts[-2:])
            else:
                domain = eventData
        else:
            domain = eventData

        self.debug(f"Processing domain: {domain}")

        # Try zone transfer if enabled
        if self.opts["zonecheck"]:
            self.debug(f"Attempting zone transfer for {domain}")
            self.tryZoneTransfer(domain)

        # Try brute forcing if enabled
        if self.opts["bruteforce"]:
            self.debug(f"Brute forcing subdomains for {domain}")
            self.bruteForceSubdomains(domain)

        # Process all discovered subdomains
        for subdomain in self.subdomains:
            if self.checkForStop():
                return

            if subdomain in self.results:
                continue

            self.results[subdomain] = True

            # If validation is enabled, check if subdomain resolves
            if self.opts["validate"]:
                is_valid, ips, ipv6s = self.validateSubdomain(subdomain)

                if is_valid:
                    # Create internet name event
                    evt = SpiderFootEvent(
                        "INTERNET_NAME", subdomain, self.__name__, parentEvent
                    )
                    self.notifyListeners(evt)

                    # Check if it's a domain name
                    if self.sf.isDomain(subdomain, self.opts["_internettlds"]):
                        evt = SpiderFootEvent(
                            "DOMAIN_NAME", subdomain, self.__name__, parentEvent
                        )
                        self.notifyListeners(evt)

                    # Create IP address events
                    for ip in ips:
                        evt = SpiderFootEvent(
                            "IP_ADDRESS", ip, self.__name__, evt)
                        self.notifyListeners(evt)

                    for ipv6 in ipv6s:
                        evt = SpiderFootEvent(
                            "IPV6_ADDRESS", ipv6, self.__name__, evt)
                        self.notifyListeners(evt)
                else:
                    # Create unresolved event
                    evt = SpiderFootEvent(
                        "INTERNET_NAME_UNRESOLVED",
                        subdomain,
                        self.__name__,
                        parentEvent,
                    )
                    self.notifyListeners(evt)
            else:
                # No validation, just report the discovered name
                evt = SpiderFootEvent(
                    "INTERNET_NAME_UNRESOLVED", subdomain, self.__name__, parentEvent
                )
                self.notifyListeners(evt)
