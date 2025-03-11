# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_geoip
# Purpose:  SpiderFoot plug-in to identify the Geo-location of IP addresses.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import json
import ipaddress

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_geoip(SpiderFootPlugin):
    meta = {
        "name": "GeoIP",
        "summary": "Identifies the physical location of IP addresses.",
        "flags": ["apikey"],
        "useCases": ["Footprint", "Investigate", "Passive"],
        "categories": ["Real World"],
        "dataSource": {
            "website": "https://ipinfo.io/",
            "model": "FREE_AUTH_LIMITED",
            "references": [
                "https://ipinfo.io/developers",
                "https://ipinfo.io/products/ip-geolocation-api",
            ],
            "apiKeyInstructions": [
                "Visit https://ipinfo.io/",
                "Sign up for a free account",
                "Navigate to 'Dashboard'",
                "The API key is listed under 'API Key'",
            ],
            "favIcon": "https://ipinfo.io/static/favicon.png",
            "logo": "https://ipinfo.io/static/ipinfo-logo.svg",
            "description": "The trusted source for IP address data. "
            "Accurate IP address data that keeps pace with secure, specific, and forward-looking use cases.",
        },
    }

    # Default options
    opts = {
        "api_key": "",
        "local_cache_only": False,
        "max_netblocks": 1000,
        "max_subnets": 24,
        "skip_private_ips": True,
    }

    # Option descriptions
    optdescs = {
        "api_key": "IPInfo.io API Key.",
        "local_cache_only": "Only use local GeoIP database, don't query online service.",
        "max_netblocks": "Maximum number of netblocks to analyze for target.",
        "max_subnets": "Maximum number of subnets to process within netblocks.",
        "skip_private_ips": "Skip private IP addresses.",
    }

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["IP_ADDRESS", "AFFILIATE_IPADDR", "NETBLOCK_OWNER", "NETBLOCKV6_OWNER"]

    # What events this module produces
    def producedEvents(self):
        return [
            "GEOINFO",
            "PHYSICAL_COORDINATES",
            "PHYSICAL_ADDRESS",
            "RAW_RIR_DATA",
            "COMPANY_NAME",
            "PROVIDER_TELCO",
        ]

    def queryIPInfo(self, ip):
        """Query the IPInfo.io API for geo-location data."""
        if not self.opts["api_key"] and not self.opts["local_cache_only"]:
            self.error(
                "You enabled sfp_geoip but did not set an API key and local_cache_only is False!"
            )
            self.errorState = True
            return None

        if self.opts["local_cache_only"]:
            # Try to get geo data from local cache
            data = self.sf.cacheGet("geoip_" + ip, 86400)  # Cache for 24 hours
            if data:
                try:
                    return json.loads(data)
                except Exception:
                    self.debug(f"Couldn't load geo data from cache for {ip}")
            return None

        # Query the API
        url = f"https://ipinfo.io/{ip}?token={self.opts['api_key']}"

        res = self.sf.fetchUrl(
            url,
            timeout=self.opts["_fetchtimeout"],
            useragent=self.opts["_useragent"],
            verify=True,
        )

        if not res["content"]:
            self.debug(f"No geo data available for {ip}")
            return None

        try:
            data = json.loads(res["content"])
            # Cache for 24 hours
            self.sf.cachePut("geoip_" + ip, res["content"], 86400)
            return data
        except Exception as e:
            self.error(f"Error processing geo-location response for {ip}: {e}")
            return None

    def isPrivateIP(self, ip):
        """Check if an IP is in private IP space."""
        try:
            return ipaddress.ip_address(ip).is_private
        except Exception:
            return False

    def processNetblock(self, netblock):
        """Process a netblock by looking up GeoIP info for IPs within it."""
        if netblock in self.results:
            return

        self.results[netblock] = True

        try:
            # Get netblock in CIDR notation
            if "/" not in netblock:
                netblock += "/24"  # Assume /24 if no prefix specified

            net = ipaddress.ip_network(netblock, strict=False)

            # Limit the number of subnets processed
            if net.prefixlen < self.opts["max_subnets"]:
                self.debug(
                    f"Netblock {netblock} too large to process completely")

                # Break it down into smaller subnets
                subnets = list(net.subnets(
                    new_prefix=self.opts["max_subnets"]))

                # Limit the number of subnets to process
                if len(subnets) > self.opts["max_netblocks"]:
                    self.debug(
                        f"Limiting netblock analysis to {self.opts['max_netblocks']} subnets"
                    )
                    subnets = subnets[: self.opts["max_netblocks"]]

                # Process a few IPs from each subnet
                for subnet in subnets:
                    subnet_size = subnet.num_addresses
                    if subnet_size > 0:
                        # Check the first IP in the subnet
                        first_ip = str(subnet[0])
                        if not self.opts["skip_private_ips"] or not self.isPrivateIP(
                            first_ip
                        ):
                            self.processIP(first_ip)
            else:
                # Process a few IPs from the netblock
                ips = list(net.hosts())[: self.opts["max_netblocks"]]
                for ip in ips:
                    ip_str = str(ip)
                    if not self.opts["skip_private_ips"] or not self.isPrivateIP(
                        ip_str
                    ):
                        self.processIP(ip_str)

        except Exception as e:
            self.error(f"Error processing netblock {netblock}: {e}")

    def processIP(self, ip):
        """Process a single IP address."""
        if ip in self.results:
            return

        self.results[ip] = True

        if self.opts["skip_private_ips"] and self.isPrivateIP(ip):
            self.debug(f"Skipping private IP: {ip}")
            return

        # Look up the geo location of the IP
        data = self.queryIPInfo(ip)
        if not data:
            return

        return data

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        # Skip if we've already processed this data
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName in ["NETBLOCK_OWNER", "NETBLOCKV6_OWNER"]:
            self.processNetblock(eventData)
            return

        if eventName.startswith("AFFILIATE_"):
            # Skip affiliate IPs if configured to do so
            if not self.opts.get("checkaffiliates", False):
                return

        # Process the IP address
        data = self.processIP(eventData)
        if not data:
            return

        # Report the raw RIR data
        evt = SpiderFootEvent(
            "RAW_RIR_DATA", json.dumps(data), self.__name__, event)
        self.notifyListeners(evt)

        # Extract geo information
        location = []

        # Country
        if data.get("country"):
            location.append(f"Country: {data.get('country')}")

        # Region/State
        if data.get("region"):
            location.append(f"Region: {data.get('region')}")

        # City
        if data.get("city"):
            location.append(f"City: {data.get('city')}")

        # Postal/ZIP code
        if data.get("postal"):
            location.append(f"Postal Code: {data.get('postal')}")

        # Create GEOINFO event with formatted location
        if location:
            evt = SpiderFootEvent("GEOINFO", ", ".join(
                location), self.__name__, event)
            self.notifyListeners(evt)

        # Extract physical coordinates
        if data.get("loc") and "," in data.get("loc"):
            lat, lon = data.get("loc").split(",")
            coords = f"{lat},{lon}"
            evt = SpiderFootEvent("PHYSICAL_COORDINATES",
                                  coords, self.__name__, event)
            self.notifyListeners(evt)

        # Extract physical address
        address_parts = []
        if data.get("city"):
            address_parts.append(data.get("city"))
        if data.get("region"):
            address_parts.append(data.get("region"))
        if data.get("postal"):
            address_parts.append(data.get("postal"))
        if data.get("country"):
            address_parts.append(data.get("country"))

        if address_parts:
            address = ", ".join(address_parts)
            evt = SpiderFootEvent("PHYSICAL_ADDRESS",
                                  address, self.__name__, event)
            self.notifyListeners(evt)

        # Extract organization/company name
        if data.get("org"):
            org = data.get("org")

            # Try to separate ASN from company name if present
            if " " in org and org.split(" ")[0].startswith("AS"):
                asn, company = org.split(" ", 1)
                evt = SpiderFootEvent(
                    "COMPANY_NAME", company, self.__name__, event)
                self.notifyListeners(evt)

                # Also report as provider
                evt = SpiderFootEvent(
                    "PROVIDER_TELCO", company, self.__name__, event)
                self.notifyListeners(evt)
            else:
                evt = SpiderFootEvent(
                    "COMPANY_NAME", org, self.__name__, event)
                self.notifyListeners(evt)

                # Also report as provider
                evt = SpiderFootEvent(
                    "PROVIDER_TELCO", org, self.__name__, event)
                self.notifyListeners(evt)
