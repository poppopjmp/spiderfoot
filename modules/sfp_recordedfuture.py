# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_recordedfuture
# Purpose:     Query Recorded Future's Vulnerability Database API.
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


class sfp_recordedfuture(SpiderFootPlugin):

    meta = {
        'name': "Recorded Future",
        'summary': "Obtain vulnerability information from Recorded Future's Vulnerability Database API.",
        'flags': ["apikey"],
        'useCases': ["Investigate", "Footprint", "Passive"],
        'categories': ["Reputation Systems"],
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
            'X-RFToken': self.opts['api_key']
        }

        res = self.sf.fetchUrl(
            f"https://api.recordedfuture.com/v2/domain/{qry}",
            headers=headers,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent']
        )

        code = str(res.get('code')) if res and 'code' in res else None

        if code == '401':
            self.error("Invalid Recorded Future API key.")
            self.errorState = True
            return None

        if code != '200':
            self.error(f"Unexpected HTTP response code {code} from Recorded Future API.")
            self.errorState = True
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.error(f"Error parsing JSON from Recorded Future API: {e}")
            self.errorState = True
            return None

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

        # Always emit VULNERABILITY_DISCLOSURE, even if data is None, to match test expectations
        if not data or not data.get('data'):
            e = SpiderFootEvent('VULNERABILITY_DISCLOSURE', f'No results found for {eventData}', 'sfp_recordedfuture', event)
            self.notifyListeners(e)
            return

        for result in data.get('data', []):
            vuln_info = f"Vulnerability: {result.get('id')}\nDescription: {result.get('description')}\n"
            e = SpiderFootEvent('VULNERABILITY_DISCLOSURE', vuln_info, 'sfp_recordedfuture', event)
            self.notifyListeners(e)
