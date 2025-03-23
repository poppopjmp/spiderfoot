# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_zoomeye
# Purpose:  Search ZoomEye for domain, IP address, and other information.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import time
import json
import requests

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_zoomeye(SpiderFootPlugin):
    meta = {
        "name": "ZoomEye",
        "summary": "Look up domain, IP address, and other information from ZoomEye.",
        "flags": ["apikey"],
        "useCases": ["Passive", "Footprint", "Investigate"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://www.zoomeye.org/",
            "model": "FREE_AUTH_LIMITED",
            "references": [
                "https://www.zoomeye.org/api/doc",
            ],
            "apiKeyInstructions": [
                "Visit https://www.zoomeye.org/",
                "Register a free account",
                "Navigate to https://www.zoomeye.org/profile",
                "Your API key will be listed under 'API Key'",
            ],
            "favIcon": "https://www.zoomeye.org/favicon.ico",
            "logo": "https://www.zoomeye.org/logo.png",
            "description": "ZoomEye is a search engine for cyberspace that lets researchers find specific network components, such as routers, servers, and IoT devices.",
        },
    }

    opts = {
        "api_key": "",
        "delay": 1,
        "max_pages": 10,
    }

    optdescs = {
        "api_key": "ZoomEye API key.",
        "delay": "Delay between API requests (in seconds).",
        "max_pages": "Maximum number of pages to iterate through, to avoid exceeding ZoomEye API usage limits.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.errorState = False
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        if not self.opts["api_key"]:
            self.error("ZoomEye API key is required.")
            self.errorState = True

    def watchedEvents(self):
        return ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self):
        return [
            "INTERNET_NAME",
            "DOMAIN_NAME",
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "RAW_RIR_DATA",
        ]

    def query(self, qry, querytype, page=1):
        if self.errorState:
            return None

        api_endpoint = (
            "https://api.zoomeye.org/host/search"
            if querytype == "host"
            else "https://api.zoomeye.org/web/search"
        )
        headers = {
            "API-KEY": self.opts["api_key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        params = {"query": qry, "page": page, "pageSize": 20}

        try:
            self.debug(
                f"Querying ZoomEye API: {api_endpoint} for {qry} (page {page})")
            response = requests.get(
                api_endpoint, headers=headers, params=params)
            time.sleep(self.opts["delay"])

            if response.status_code != 200:
                self.error(
                    f"ZoomEye API returned HTTP status {response.status_code}: {response.text}"
                )
                self.errorState = True
                return None

            data = response.json()

            if not data or not data.get("matches"):
                self.info(f"No ZoomEye info found for {qry}")
                return None

            results = [data]

            # Check if we should fetch more pages
            if data.get("total", 0) > data.get("pageSize", 20) * page:
                page += 1
                if page <= self.opts["max_pages"]:
                    next_page_results = self.query(qry, querytype, page)
                    if next_page_results:
                        results.extend(next_page_results)
                else:
                    self.debug("Maximum number of pages reached.")

            return results

        except requests.exceptions.RequestException as e:
            self.error(f"Error querying ZoomEye API: {e}")
            self.errorState = True
            return None
        except json.JSONDecodeError as e:
            self.error(f"Error decoding JSON response from ZoomEye: {e}")
            self.errorState = True
            return None
        except Exception as e:
            self.error(f"Unexpected error querying ZoomEye API: {e}")
            self.errorState = True
            return None

    def queryHost(self, qry, page=1, pageSize=20):
        """Query ZoomEye for host information."""
        headers = {
            'API-KEY': self.opts['api_key'],
        }
        
        try:
            res = self.sf.fetchUrl(
                f"https://api.zoomeye.org/host/search?query={qry}&page={page}&pageSize={pageSize}",
                timeout=self.opts['_fetchtimeout'],
                useragent="SpiderFoot",
                headers=headers
            )

            if res['code'] == "404":
                self.error("Invalid ZoomEye API key or credits expired.")
                return None
            
            if res['code'] == "429":
                self.error("You are being rate-limited by ZoomEye")
                return None
                
            if res['code'] != "200":
                self.error(f"Unexpected HTTP response code {res['code']} from ZoomEye.")
                return None
                
            try:
                return json.loads(res['content'])
            except Exception as e:
                self.error(f"Error processing JSON response from ZoomEye: {e}")
                return None
                
        except urllib.error.HTTPError as e:
            self.error(f"HTTP error when connecting to ZoomEye API: {e}")
            return None
        except urllib.error.URLError as e:
            self.error(f"URL error when connecting to ZoomEye API: {e}")
            return None
        except ConnectionError as e:
            self.error(f"Connection error when querying ZoomEye API: {e}")
            return None
        except Exception as e:
            self.error(f"Error querying ZoomEye API: {e}")
            return None

    def handleEvent(self, event):
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

        if eventName == "DOMAIN_NAME":
            ret = self.query(eventData, "web")
            if ret is None:
                self.info(f"No web info for {eventData}")
                return

            for rec in ret:
                matches = rec.get("matches")
                if not matches:
                    continue

                self.debug("Found web results in ZoomEye")
                for match in matches:
                    host = match.get("site")
                    if host:
                        e = SpiderFootEvent(
                            "INTERNET_NAME", host, self.__name__, event)
                        self.notifyListeners(e)

        elif eventName in ["IP_ADDRESS", "IPV6_ADDRESS"]:
            ret = self.query(eventData, "host")
            if ret is None:
                self.info(f"No host info for {eventData}")
                return

            for rec in ret:
                matches = rec.get("matches")
                if not matches:
                    continue

                self.debug("Found host results in ZoomEye")
                for match in matches:
                    ip = match.get("ip")
                    if ip:
                        e = SpiderFootEvent(
                            "IP_ADDRESS", ip, self.__name__, event)
                        self.notifyListeners(e)

                    domain = match.get("domain")
                    if domain:
                        e = SpiderFootEvent(
                            "DOMAIN_NAME", domain, self.__name__, event)
                        self.notifyListeners(e)

                    e = SpiderFootEvent(
                        "RAW_RIR_DATA", str(match), self.__name__, event
                    )
                    self.notifyListeners(e)
