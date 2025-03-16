# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_mandiant_ti
# Purpose:     Query Mandiant Threat Intelligence API.
#
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# Created:      14/03/2025
# Copyright:    (c) poppopjmp
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_mandiant_ti(SpiderFootPlugin):

    meta = {
        'name': "Mandiant Threat Intelligence",
        'summary': "Obtain threat intelligence information from Mandiant Threat Intelligence API.",
        'flags': ["apikey"],
        'useCases': ["Investigate", "Footprint", "Passive"],
        'categories': ["Threat Intelligence"],
        'dataSource': {
            'website': "https://www.mandiant.com/",
            'model': "COMMERCIAL_ONLY",
            'references': [
                "https://www.mandiant.com/resources/threat-intelligence",
            ],
            'apiKeyInstructions': [
                "Visit https://www.mandiant.com/",
                "Register for an account",
                "Navigate to the API section",
                "Generate an API key"
            ],
            'favIcon': "https://www.mandiant.com/favicon.ico",
            'logo': "https://www.mandiant.com/sites/default/files/2021-06/mandiant-logo.png",
            'description': "Mandiant Threat Intelligence provides real-time threat intelligence powered by machine learning. "
            "Their API allows you to query and obtain information about threats."
        }
    }

    opts = {
        'api_key': '',
        'verify': True
    }

    optdescs = {
        'api_key': 'Mandiant Threat Intelligence API key.',
        'verify': 'Verify host names resolve'
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ['DOMAIN_NAME', 'INTERNET_NAME', 'IP_ADDRESS']

    def producedEvents(self):
        return ['THREAT_INTELLIGENCE']

    def query(self, qry):
        headers = {
            'Authorization': f'Bearer {self.opts["api_key"]}',
            'Content-Type': 'application/json',
        }

        res = self.sf.fetchUrl(f'https://api.mandiant.com/v4/threats?q={qry}',
                               headers=headers,
                               useragent=self.opts['_useragent'],
                               timeout=self.opts['_fetchtimeout'])

        if res['code'] in ["400", "401", "403", "500"]:
            self.error(f"Unexpected HTTP response code {res['code']} from Mandiant")
            self.errorState = True
            return None

        if res['content'] is None:
            return None

        try:
            data = json.loads(res['content'])
        except Exception as e:
            self.debug(f"Error processing JSON response from Mandiant: {e}")
            return None

        if not data:
            self.debug(f"No results found for {qry}")
            return None

        return data

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if srcModuleName == 'sfp_mandiant_ti':
            self.debug(f"Ignoring {eventName}, from self.")
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        if self.opts['api_key'] == '':
            self.error('You enabled sfp_mandiant_ti but did not set an API key!')
            self.errorState = True
            return

        self.results[eventData] = True

        data = self.query(eventData)

        if not data:
            self.info(f"No results found for {eventData}")
            return

        for result in data.get('data', []):
            threat_info = f"Threat: {result.get('id')}\nDescription: {result.get('description')}\n"
            e = SpiderFootEvent('THREAT_INTELLIGENCE', threat_info, self.__name__, event)
            self.notifyListeners(e)
