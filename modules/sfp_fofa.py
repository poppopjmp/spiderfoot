# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_fofa
# Purpose:     Search Fofa for domain, IP address, and other information.
#
# Author:      Your Name <your.email@example.com>
#
# Created:     01/01/2023
# Copyright:   (c) Your Name
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_fofa(SpiderFootPlugin):

    meta = {
        'name': "Fofa",
        'summary': "Look up domain, IP address, and other information from Fofa.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://fofa.so/",
            'model': "FREE_NOAUTH_LIMITED",
            'references': [
                "https://fofa.so/",
            ],
            'apiKeyInstructions': [
                "Visit https://fofa.so/user/register",
                "Register a free account",
                "Visit https://fofa.so/api",
                "Your API Key will be listed under 'API Key'.",
            ],
            'favIcon': "https://fofa.so/favicon.ico",
            'logo': "https://fofa.so/logo.png",
            'description': "Fofa is a search engine for Internet-connected devices and assets."
        }
    }

    opts = {
        "api_key": "",
    }

    optdescs = {
        "api_key": "Fofa API key.",
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
        if not api_key:
            self.error("You enabled sfp_fofa but did not set an API key!")
            self.errorState = True
            return None

        params = urllib.parse.urlencode({
            'key': api_key,
            'qbase64': query.encode('raw_unicode_escape').decode("ascii", errors='replace'),
        })

        res = self.sf.fetchUrl(
            f"https://fofa.so/api/v1/search/all?{params}",
            useragent=self.opts['_useragent']
        )

        time.sleep(1)

        if not res:
            self.debug("No response from Fofa API endpoint")
            return None

        return self.parseApiResponse(res)

    def parseApiResponse(self, res: dict):
        if not res:
            self.error("No response from Fofa API.")
            return None

        if res['code'] == '429':
            self.error("You are being rate-limited by Fofa.")
            return None

        if res['code'] == '401':
            self.error("Unauthorized. Invalid Fofa API key.")
            self.errorState = True
            return None

        if res['code'] == '422':
            self.error("Usage quota reached. Insufficient API credit.")
            self.errorState = True
            return None

        if res['code'] == '500' or res['code'] == '502' or res['code'] == '503':
            self.error("Fofa service is unavailable")
            self.errorState = True
            return None

        if res['code'] == '204':
            self.debug("No response data for target")
            return None

        if res['code'] != '200':
            self.error(f"Unexpected reply from Fofa: {res['code']}")
            return None

        if res['content'] is None:
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

        if not data:
            return

        e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
        self.notifyListeners(e)

        for result in data.get('results', []):
            if 'host' in result:
                e = SpiderFootEvent("INTERNET_NAME", result['host'], self.__name__, event)
                self.notifyListeners(e)
            if 'domain' in result:
                e = SpiderFootEvent("DOMAIN_NAME", result['domain'], self.__name__, event)
                self.notifyListeners(e)
            if 'ip' in result:
                e = SpiderFootEvent("IP_ADDRESS", result['ip'], self.__name__, event)
                self.notifyListeners(e)
            if 'ipv6' in result:
                e = SpiderFootEvent("IPV6_ADDRESS", result['ipv6'], self.__name__, event)
                self.notifyListeners(e)

# End of sfp_fofa class
