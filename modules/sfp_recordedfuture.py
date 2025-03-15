# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_recordedfuture
# Purpose:     Query Recorded Future's Vulnerability Database API.
#
# Author:      <your-email@example.com>
#
# Created:     2023-04-01
# Copyright:   (c) Your Name 2023
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_recordedfuture(SpiderFootPlugin):

    meta = {
        'name': "Recorded Future",
        'summary': "Obtain vulnerability information from Recorded Future's Vulnerability Database API.",
        'flags': ["apikey"],
        'useCases': ["Investigate", "Footprint", "Passive"],
        'categories': ["Vulnerabilities"],
        'dataSource': {
            'website': "https://www.recordedfuture.com/",
            'model': "COMMERCIAL_ONLY",
            'references': [
                "https://support.recordedfuture.com/hc/en-us/articles/360035531473-API-Documentation",
            ],
            'apiKeyInstructions': [
                "Visit https://www.recordedfuture.com/",
                "Register for an account",
                "Navigate to the API section",
                "Generate an API key"
            ],
            'favIcon': "https://www.recordedfuture.com/favicon.ico",
            'logo': "https://www.recordedfuture.com/wp-content/uploads/2020/02/RF-Logo-Black-1.png",
            'description': "Recorded Future provides real-time threat intelligence powered by machine learning. "
            "Their Vulnerability Database API allows you to query and obtain information about vulnerabilities."
        }
    }

    opts = {
        'api_key': '',
        'verify': True
    }

    optdescs = {
        'api_key': 'Recorded Future API key.',
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
        return ['VULNERABILITY_DISCLOSURE']

    def query(self, qry):
        headers = {
            'X-RFToken': self.opts['api_key'],
            'Content-Type': 'application/json',
        }

        res = self.sf.fetchUrl(f'https://api.recordedfuture.com/v2/vulnerability/search?q={qry}',
                               headers=headers,
                               useragent=self.opts['_useragent'],
                               timeout=self.opts['_fetchtimeout'])

        if res['code'] in ["400", "401", "403", "500"]:
            self.error(f"Unexpected HTTP response code {res['code']} from Recorded Future")
            self.errorState = True
            return None

        if res['content'] is None:
            return None

        try:
            data = json.loads(res['content'])
        except Exception as e:
            self.debug(f"Error processing JSON response from Recorded Future: {e}")
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

        if srcModuleName == 'sfp_recordedfuture':
            self.debug(f"Ignoring {eventName}, from self.")
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        if self.opts['api_key'] == '':
            self.error('You enabled sfp_recordedfuture but did not set an API key!')
            self.errorState = True
            return

        self.results[eventData] = True

        data = self.query(eventData)

        if not data:
            self.info(f"No results found for {eventData}")
            return

        for result in data.get('data', []):
            vuln_info = f"Vulnerability: {result.get('id')}\nDescription: {result.get('description')}\n"
            e = SpiderFootEvent('VULNERABILITY_DISCLOSURE', vuln_info, self.__name__, event)
            self.notifyListeners(e)
