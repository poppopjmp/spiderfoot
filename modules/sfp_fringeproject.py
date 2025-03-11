# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_fringeproject
# Purpose:  Query the Fringe Project API for information about domains and IPs.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib.parse

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_fringeproject(SpiderFootPlugin):
    meta = {
        "name": "Fringe Project",
        "summary": "Obtain information from Fringe Project about various online assets.",
        "flags": ["slow"],
        "useCases": ["Footprint", "Investigate", "Passive"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://fringeproject.com/",
            "model": "FREE_NOAUTH_LIMITED",
            "references": [
                "https://fringeproject.com/api",
                "https://fringeproject.com/docs",
            ],
            "favIcon": "https://fringeproject.com/favicon.ico",
            "logo": "https://fringeproject.com/static/images/logo.png",
            "description": "Fringe Project is an open database with information about "
            "various Internet assets like domains, IPs, and URLs.",
        },
    }

    # Default options
    opts = {"verify": True, "max_pages": 5, "delay": 1}

    # Option descriptions
    optdescs = {
        "verify": "Verify identified domains exist before reporting them.",
        "max_pages": "Maximum number of pages to fetch from search results.",
        "delay": "Delay between API requests in seconds.",
    }

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "INTERNET_NAME", "IP_ADDRESS", "USERNAME", "EMAILADDR"]

    # What events this module produces
    def producedEvents(self):
        return [
            "RAW_RIR_DATA",
            "INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "DOMAIN_NAME",
            "IP_ADDRESS",
            "WEBSERVER_BANNER",
            "TCP_PORT_OPEN",
            "SOFTWARE_USED",
            "WEBSERVER_HTTPHEADERS",
        ]

    def query(self, qry, endpoint="search"):
        """Query the Fringe Project API."""

        base_url = f"https://api.fringeproject.com/api/v1/{endpoint}"

        if endpoint == "search":
            url = f"{base_url}?q={urllib.parse.quote(qry)}"
        else:
            url = f"{base_url}/{urllib.parse.quote(qry)}"

        res = self.sf.fetchUrl(
            url,
            timeout=15,
            useragent=self.opts.get("_useragent", "SpiderFoot"),
            verify=True,
        )

        if not res or not res.get("content"):
            self.debug(
                f"No results found from Fringe Project for {qry} ({endpoint})")
            return None

        try:
            data = json.loads(res["content"])
            return data
        except Exception as e:
            self.error(f"Error processing Fringe Project response: {e}")
            return None

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Different search strategies depending on event type
        if eventName == "DOMAIN_NAME" or eventName == "INTERNET_NAME":
            # Search for domain/host information
            data = self.query(eventData, "domain")

            if not data:
                self.debug(f"No domain information found for {eventData}")
                return

            # Report the raw data
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(data), self.__name__, event
            )
            self.notifyListeners(evt)

            # Process subdomains if present
            subdomains = data.get("subdomains", [])
            for subdomain in subdomains:
                if self.opts["verify"]:
                    if self.sf.resolveHost(subdomain) or self.sf.resolveHost(
                        "www." + subdomain
                    ):
                        evt = SpiderFootEvent(
                            "INTERNET_NAME", subdomain, self.__name__, event
                        )
                        self.notifyListeners(evt)

                        if self.sf.isDomain(subdomain, self.opts["_internettlds"]):
                            evt = SpiderFootEvent(
                                "DOMAIN_NAME", subdomain, self.__name__, event
                            )
                            self.notifyListeners(evt)
                    else:
                        evt = SpiderFootEvent(
                            "INTERNET_NAME_UNRESOLVED", subdomain, self.__name__, event
                        )
                        self.notifyListeners(evt)
                else:
                    evt = SpiderFootEvent(
                        "INTERNET_NAME", subdomain, self.__name__, event
                    )
                    self.notifyListeners(evt)

                    if self.sf.isDomain(subdomain, self.opts["_internettlds"]):
                        evt = SpiderFootEvent(
                            "DOMAIN_NAME", subdomain, self.__name__, event
                        )
                        self.notifyListeners(evt)

            # Process IP addresses if present
            ip_addresses = data.get("ips", [])
            for ip in ip_addresses:
                if self.sf.validIP(ip):
                    evt = SpiderFootEvent(
                        "IP_ADDRESS", ip, self.__name__, event)
                    self.notifyListeners(evt)

            # Process web server details if present
            webserver = data.get("webserver")
            if webserver:
                if webserver.get("banner"):
                    evt = SpiderFootEvent(
                        "WEBSERVER_BANNER",
                        webserver.get("banner"),
                        self.__name__,
                        event,
                    )
                    self.notifyListeners(evt)

                # Process ports if present
                ports = webserver.get("ports", [])
                for port in ports:
                    if port:
                        evt = SpiderFootEvent(
                            "TCP_PORT_OPEN", f"{eventData}:{port}", self.__name__, event
                        )
                        self.notifyListeners(evt)

                # Process headers if present
                headers = webserver.get("headers")
                if headers:
                    evt = SpiderFootEvent(
                        "WEBSERVER_HTTPHEADERS",
                        json.dumps(headers),
                        self.__name__,
                        event,
                    )
                    self.notifyListeners(evt)

                    # Check for server software info in headers
                    if headers.get("Server"):
                        evt = SpiderFootEvent(
                            "SOFTWARE_USED",
                            f"Web Server: {headers.get('Server')}",
                            self.__name__,
                            event,
                        )
                        self.notifyListeners(evt)

        elif eventName == "IP_ADDRESS":
            # Search for IP information
            data = self.query(eventData, "ip")

            if not data:
                self.debug(f"No IP information found for {eventData}")
                return

            # Report the raw data
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(data), self.__name__, event
            )
            self.notifyListeners(evt)

            # Process domains associated with this IP
            domains = data.get("domains", [])
            for domain in domains:
                if self.opts["verify"]:
                    if self.sf.resolveHost(domain):
                        evt = SpiderFootEvent(
                            "INTERNET_NAME", domain, self.__name__, event
                        )
                        self.notifyListeners(evt)

                        if self.sf.isDomain(domain, self.opts["_internettlds"]):
                            evt = SpiderFootEvent(
                                "DOMAIN_NAME", domain, self.__name__, event
                            )
                            self.notifyListeners(evt)
                    else:
                        evt = SpiderFootEvent(
                            "INTERNET_NAME_UNRESOLVED", domain, self.__name__, event
                        )
                        self.notifyListeners(evt)
                else:
                    evt = SpiderFootEvent(
                        "INTERNET_NAME", domain, self.__name__, event)
                    self.notifyListeners(evt)

                    if self.sf.isDomain(domain, self.opts["_internettlds"]):
                        evt = SpiderFootEvent(
                            "DOMAIN_NAME", domain, self.__name__, event
                        )
                        self.notifyListeners(evt)

            # Process ports if present
            ports = data.get("ports", [])
            for port in ports:
                if port:
                    evt = SpiderFootEvent(
                        "TCP_PORT_OPEN", f"{eventData}:{port}", self.__name__, event
                    )
                    self.notifyListeners(evt)

        else:
            # For other types like USERNAME, EMAILADDR, use the search endpoint
            data = self.query(eventData, "search")

            if not data or not data.get("results"):
                self.debug(f"No search results found for {eventData}")
                return

            # Report the raw data
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(data), self.__name__, event
            )
            self.notifyListeners(evt)

            # Process the search results
            results = data.get("results", [])
            page = 1

            while results and page < self.opts["max_pages"]:
                for result in results:
                    result_type = result.get("type")
                    result_value = result.get("value")

                    if not result_value:
                        continue

                    if result_type == "domain":
                        if self.opts["verify"]:
                            if self.sf.resolveHost(result_value):
                                evt = SpiderFootEvent(
                                    "INTERNET_NAME", result_value, self.__name__, event
                                )
                                self.notifyListeners(evt)

                                if self.sf.isDomain(
                                    result_value, self.opts["_internettlds"]
                                ):
                                    evt = SpiderFootEvent(
                                        "DOMAIN_NAME",
                                        result_value,
                                        self.__name__,
                                        event,
                                    )
                                    self.notifyListeners(evt)
                            else:
                                evt = SpiderFootEvent(
                                    "INTERNET_NAME_UNRESOLVED",
                                    result_value,
                                    self.__name__,
                                    event,
                                )
                                self.notifyListeners(evt)
                        else:
                            evt = SpiderFootEvent(
                                "INTERNET_NAME", result_value, self.__name__, event
                            )
                            self.notifyListeners(evt)

                            if self.sf.isDomain(
                                result_value, self.opts["_internettlds"]
                            ):
                                evt = SpiderFootEvent(
                                    "DOMAIN_NAME", result_value, self.__name__, event
                                )
                                self.notifyListeners(evt)
                    elif result_type == "ip" and self.sf.validIP(result_value):
                        evt = SpiderFootEvent(
                            "IP_ADDRESS", result_value, self.__name__, event
                        )
                        self.notifyListeners(evt)

                # Check if there are more pages
                if data.get("next_page"):
                    page += 1
                    time.sleep(self.opts["delay"])  # Be nice to the API

                    next_url = data.get("next_page")
                    res = self.sf.fetchUrl(
                        next_url,
                        timeout=15,
                        useragent=self.opts.get("_useragent", "SpiderFoot"),
                        verify=True,
                    )

                    if not res or not res.get("content"):
                        break

                    try:
                        data = json.loads(res["content"])
                        results = data.get("results", [])
                    except Exception:
                        break
                else:
                    break
