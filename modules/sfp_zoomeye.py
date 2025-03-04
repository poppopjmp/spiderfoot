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

from spiderfoot import SpiderFootEvent, SpiderFootPlugin

try:
    from zoomeyeai.sdk import ZoomEye
except ImportError:
    ZoomEye = None


class sfp_zoomeye(SpiderFootPlugin):

    meta = {
        'name': "ZoomEye",
        'summary': "Look up domain, IP address, and other information from ZoomEye.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://www.zoomeye.org/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://www.zoomeye.org/api/doc",
            ],
            'apiKeyInstructions': [
                "Visit https://www.zoomeye.org/",
                "Register a free account",
                "Navigate to https://www.zoomeye.org/profile",
                "Your API key will be listed under 'API Key'",
            ],
            'favIcon': "https://www.zoomeye.org/favicon.ico",
            'logo': "https://www.zoomeye.org/logo.png",
            'description': "ZoomEye is a search engine for cyberspace that lets researchers find specific network components, such as routers, servers, and IoT devices."
        }
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
    zoomeye_api = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.errorState = False
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        if ZoomEye and self.opts['api_key']:
            self.zoomeye_api = ZoomEye(api_key=self.opts['api_key'])
        elif not ZoomEye:
            self.error("ZoomEye-python library not found. Install it using 'pip install zoomeye'.")
            self.errorState = True

    def watchedEvents(self):
        return ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self):
        return ["INTERNET_NAME", "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS", "RAW_RIR_DATA"]

    def query(self, qry, querytype, page=1):
        if self.errorState or not self.zoomeye_api:
            return None

        try:
            if querytype == "host":
                res = self.zoomeye_api.search(qry, page=page, pagesize=20, sub_type='all', fields='', facets='')
            elif querytype == "web":
                res = self.zoomeye_api.search(qry, page=page, pagesize=20, sub_type='all', fields='', facets='')
            else:
                self.error(f"Invalid query type: {querytype}")
                return None

            time.sleep(self.opts['delay'])

            if not res or not res.get('matches'):
                self.info(f"No ZoomEye info found for {qry}")
                return None

            if res.get('total') > res.get('size', 10) * page:
                page += 1
                if page > self.opts['max_pages']:
                    self.error("Maximum number of pages reached.")
                    return [res]
                return [res] + self.query(qry, querytype, page)
            return [res]

        except Exception as e:
            self.error(f"Error querying ZoomEye API: {e}")
            self.errorState = True
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
                matches = rec.get('matches')
                if not matches:
                    continue

                self.debug("Found web results in ZoomEye")
                for match in matches:
                    host = match.get('site')
                    if host:
                        e = SpiderFootEvent("INTERNET_NAME", host, self.__name__, event)
                        self.notifyListeners(e)

        elif eventName in ["IP_ADDRESS", "IPV6_ADDRESS"]:
            ret = self.query(eventData, "host")
            if ret is None:
                self.info(f"No host info for {eventData}")
                return

            for rec in ret:
                matches = rec.get('matches')
                if not matches:
                    continue

                self.debug("Found host results in ZoomEye")
                for match in matches:
                    ip = match.get('ip')
                    if ip:
                        e = SpiderFootEvent("IP_ADDRESS", ip, self.__name__, event)
                        self.notifyListeners(e)

                    domain = match.get('domain')
                    if domain:
                        e = SpiderFootEvent("DOMAIN_NAME", domain, self.__name__, event)
                        self.notifyListeners(e)

                    e = SpiderFootEvent("RAW_RIR_DATA", str(match), self.__name__, event)
                    self.notifyListeners(e)
