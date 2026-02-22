from __future__ import annotations

"""SpiderFoot plug-in module: hunterhow."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_hunterhow
# Purpose:     Search Hunter.how for information about IP addresses and domains.
#
# Author:      Agostino Panico <van1sh@van1shland.io>
#
# Created:     18/02/2026
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import base64
import json
import time
import urllib.parse
from datetime import datetime, timedelta

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_hunterhow(SpiderFootAsyncPlugin):

    """Search Hunter.how for open ports, banners, domains and geolocation data."""

    meta = {
        'name': "Hunter.how",
        'summary': "Search Hunter.how for open ports, banners, domains and geolocation data.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://hunter.how/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://hunter.how/search-api",
            ],
            'apiKeyInstructions': [
                "Visit https://hunter.how/",
                "Register a free account",
                "Navigate to your account dashboard",
                "The API key is listed on the dashboard",
            ],
            'favIcon': "https://hunter.how/favicon.ico",
            'logo': "https://hunter.how/logo.png",
            'description': (
                "Hunter.how is an internet-wide search engine that scans and indexes "
                "every device connected to the internet. It provides information about "
                "open ports, banners, domains, protocols, geolocation and ASN data."
            ),
        }
    }

    opts = {
        'api_key': "",
        'age_limit_days': 90,
        'max_pages': 5,
    }

    optdescs = {
        'api_key': "Hunter.how API key.",
        'age_limit_days': "Number of days back to search for results (default: 90).",
        'max_pages': "Maximum number of result pages to request (default: 5, max 100 results per page).",
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
        return ["IP_ADDRESS", "IPV6_ADDRESS", "DOMAIN_NAME", "INTERNET_NAME"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "TCP_PORT_OPEN",
            "TCP_PORT_OPEN_BANNER",
            "UDP_PORT_OPEN",
            "GEOINFO",
            "BGP_AS_MEMBER",
            "OPERATING_SYSTEM",
            "SOFTWARE_USED",
            "RAW_RIR_DATA",
            "INTERNET_NAME",
            "IP_ADDRESS",
            "WEBSERVER_HTTPHEADERS",
        ]

    def queryHunter(self, qry: str, qryType: str, page: int = 1) -> dict | None:
        """Query the Hunter.how API.

        Args:
            qry: The value to search for.
            qryType: The type of query ('ip' or 'domain').
            page: Page number for pagination.

        Returns:
            dict or None: Parsed JSON response or None on error.
        """
        if qryType == "ip":
            query_str = f'ip="{qry}"'
        else:
            query_str = f'domain.suffix="{qry}"'

        encoded_query = base64.urlsafe_b64encode(query_str.encode()).decode()

        end_time = datetime.now().strftime("%Y-%m-%d")
        start_time = (datetime.now() - timedelta(days=self.opts['age_limit_days'])).strftime("%Y-%m-%d")

        params = {
            'api-key': self.opts['api_key'],
            'query': encoded_query,
            'page': page,
            'page_size': 100,
            'start_time': start_time,
            'end_time': end_time,
            'fields': 'ip,port,domain,protocol,transport_protocol,web_title,country,province,city,url,asn,as_org,as_name,status_code,os,header,header_server,banner,product,updated_at',
        }

        res = self.fetch_url(
            f"https://api.hunter.how/search?{urllib.parse.urlencode(params)}",
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
        )

        time.sleep(2)  # Rate limit: 1 request per 2 seconds

        if res['code'] in ["401", "403"]:
            self.error("Hunter.how API key rejected or usage limits exceeded.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("Hunter.how rate limit exceeded.")
            self.errorState = True
            return None

        if res['content'] is None:
            self.info(f"No Hunter.how info found for {qry}")
            return None

        try:
            data = json.loads(res['content'])
            if data.get('code') != 200:
                self.error(f"Hunter.how API error: {data.get('message', 'Unknown error')}")
                return None
            return data
        except Exception as e:
            self.error(f"Error parsing Hunter.how JSON: {e}")
            return None

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {event.module}")

        if self.opts['api_key'] == "":
            self.error("You enabled sfp_hunterhow but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        qryType = "ip" if eventName in ["IP_ADDRESS", "IPV6_ADDRESS"] else "domain"

        ports_seen = set()
        banners_seen = set()
        asns_seen = set()
        products_seen = set()
        oses_seen = set()
        hosts_seen = set()
        geoinfo_seen = set()
        headers_seen = set()

        max_pages = self.opts.get('max_pages', 5)

        for page in range(1, max_pages + 1):
            if self.checkForStop():
                return

            data = self.queryHunter(eventData, qryType, page)
            if data is None:
                break

            items = data.get('data', {}).get('list', [])
            if not items:
                break

            total = data.get('data', {}).get('total', 0)

            evt = SpiderFootEvent(
                "RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(evt)

            for item in items:
                ip = item.get('ip', '')
                port = str(item.get('port', ''))
                domain = item.get('domain', '')
                protocol = item.get('transport_protocol', 'tcp')
                banner = item.get('banner', '')
                asn = item.get('asn', '')
                os_name = item.get('os', '')
                product = item.get('product')
                country = item.get('country', '')
                city = item.get('city', '')
                province = item.get('province', '')
                header = item.get('header', '')

                # Open ports
                if ip and port:
                    cp = f"{ip}:{port}"
                    if cp not in ports_seen:
                        ports_seen.add(cp)
                        port_type = "UDP_PORT_OPEN" if protocol == "udp" else "TCP_PORT_OPEN"
                        evt = SpiderFootEvent(
                            port_type, cp, self.__name__, event)
                        self.notifyListeners(evt)

                # Banners
                if banner and banner not in banners_seen:
                    banners_seen.add(banner)
                    evt = SpiderFootEvent(
                        "TCP_PORT_OPEN_BANNER", banner, self.__name__, event)
                    self.notifyListeners(evt)

                # ASN
                if asn and asn not in asns_seen:
                    asns_seen.add(asn)
                    evt = SpiderFootEvent(
                        "BGP_AS_MEMBER", asn.replace("AS", ""), self.__name__, event)
                    self.notifyListeners(evt)

                # OS
                if os_name and os_name not in oses_seen:
                    oses_seen.add(os_name)
                    evt = SpiderFootEvent(
                        "OPERATING_SYSTEM", f"{os_name} ({ip})", self.__name__, event)
                    self.notifyListeners(evt)

                # Software / Product
                if product:
                    product_list = product if isinstance(product, list) else [product]
                    for p in product_list:
                        name = p.get('name', '') if isinstance(p, dict) else str(p)
                        version = p.get('version', '') if isinstance(p, dict) else ''
                        sw = f"{name} {version}".strip() if version else name
                        if sw and sw not in products_seen:
                            products_seen.add(sw)
                            evt = SpiderFootEvent(
                                "SOFTWARE_USED", sw, self.__name__, event)
                            self.notifyListeners(evt)

                # GeoInfo
                if country:
                    location = ', '.join([_f for _f in [city, province, country] if _f])
                    if location and location not in geoinfo_seen:
                        geoinfo_seen.add(location)
                        evt = SpiderFootEvent(
                            "GEOINFO", location, self.__name__, event)
                        self.notifyListeners(evt)

                # Hostnames / domains
                if domain and domain not in hosts_seen:
                    hosts_seen.add(domain)
                    if self.getTarget().matches(domain):
                        evt = SpiderFootEvent(
                            "INTERNET_NAME", domain, self.__name__, event)
                        self.notifyListeners(evt)

                # IP addresses (from domain queries)
                if ip and qryType == "domain" and ip not in self.results:
                    self.results[ip] = True
                    evt = SpiderFootEvent(
                        "IP_ADDRESS", ip, self.__name__, event)
                    self.notifyListeners(evt)

                # HTTP Headers
                if header and header not in headers_seen:
                    headers_seen.add(header)
                    evt = SpiderFootEvent(
                        "WEBSERVER_HTTPHEADERS", header, self.__name__, event)
                    self.notifyListeners(evt)

            # Check if we've fetched all results
            if page * 100 >= total:
                break

# End of sfp_hunterhow class
