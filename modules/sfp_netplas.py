# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:     sfp_netlas
# Purpose:   Search Netlas for domain, IP address, and other information.
#
# Author:    [Your Name]
#
# Created:   [Date]
# Copyright:  (c) [Your Name]
# Licence:   MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib.parse

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_netlas(SpiderFootPlugin):

    meta = {
        'name': "Netlas",
        'summary': "Look up domain, IP address, and other information from Netlas.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://netlas.io/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://docs.netlas.io/automation/",
            ],
            'apiKeyInstructions': [
                "Visit https://netlas.io/user/profile",
                "Create an account or login",
                "Your API key will be listed under 'API Key'.",
            ],
            'favIcon': "https://netlas.io/favicon.ico",
            'logo': "https://netlas.io/static/img/logo.png",
            'description': "Netlas is a search engine for Internet-connected devices and assets."
        }
    }

    opts = {
        "api_key": "",
        "result_limit": 100,
    }

    optdescs = {
        "api_key": "Netlas API key.",
        "result_limit": "Maximum number of results to retrieve.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.errorState = False
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self):
        return ["INTERNET_NAME", "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS", "RAW_RIR_DATA"]

    def query(self, query):
        api_key = self.opts['api_key']
        result_limit = self.opts['result_limit']

        if not api_key:
            self.error("You enabled sfp_netlas but did not set an API key!")
            self.errorState = True
            return None

        params = urllib.parse.urlencode({
            'q': query,
            'size': result_limit,
        })

        url = f"https://app.netlas.io/api/v2/search/combined/?{params}"

        res = self.sf.fetchUrl(
            url,
            headers={'X-API-Key': api_key},
            useragent=self.opts['_useragent']
        )

        time.sleep(1)

        if not res:
            self.debug("No response from Netlas API endpoint")
            return None

        return self.parseApiResponse(res)

    def parseApiResponse(self, res: dict):
        if not res:
            self.error("No response from Netlas API.")
            return None

        if res['code'] != '200':
            try:
                error_json = json.loads(res['content'])
                error_message = error_json.get("error", "Unknown error")
                self.error(f"Netlas API error: {error_message}")
            except:
                self.error(f"Netlas API error, code: {res['code']}")
            self.errorState = True
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")
            return None

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if self.opts["api_key"] == "":
            self.error(
                f"You enabled {self.__class__.__name__} but did not set an API key!"
            )
            self.errorState = True
            return

        if eventName not in self.watchedEvents():
            return

        data = self.query(eventData)

        if not data or 'items' not in data:
            return

        e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
        self.notifyListeners(e)

        for result in data['items']:
            if 'host' in result.get('data', {}):
                e = SpiderFootEvent("INTERNET_NAME", result['data']['host'], self.__name__, event)
                self.notifyListeners(e)
            if 'domain' in result.get('data', {}):
                e = SpiderFootEvent("DOMAIN_NAME", result['data']['domain'], self.__name__, event)
                self.notifyListeners(e)
            if 'ip' in result.get('data', {}):
                e = SpiderFootEvent("IP_ADDRESS", result['data']['ip'], self.__name__, event)
                self.notifyListeners(e)
            if 'ipv6' in result.get('data', {}):
                e = SpiderFootEvent("IPV6_ADDRESS", result['data']['ipv6'], self.__name__, event)
                self.notifyListeners(e)
