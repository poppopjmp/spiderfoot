# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_h1
# Purpose:     Query the HackerOne API to find security vulnerabilities disclosed
#              for a target domain.
#
# Author:      <van1sh@van1shland.io>
#
# Created:     2025-03-08
# Copyright:   (c) Agostino Panico
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_h1(SpiderFootPlugin):
    meta = {
        'name': "HackerOne",
        'summary': "Query the HackerOne API to find security vulnerabilities disclosed for a target domain.",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'website': "https://www.hackerone.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://api.hackerone.com/",
                "https://docs.hackerone.com/",
                "https://hackerone.com/programs/search"
            ],
            'apiKeyInstructions': [
                "Visit https://hackerone.com/",
                "Register a free account",
                "Navigate to Settings > API Tokens",
                "Create a new API token",
                "The API key will be provided"
            ],
            'favIcon': "https://www.hackerone.com/sites/default/files/favicon_0.ico",
            'logo': "https://www.hackerone.com/sites/default/files/h1-logo.png",
            'description': "HackerOne is a vulnerability coordination and bug bounty platform that connects businesses "
                           "with penetration testers and cybersecurity researchers.",
        }
    }

    # Default options
    opts = {
        'api_key': '',
        'username': '',
        'delay': 1,
        'limit': 100
    }

    # Option descriptions
    optdescs = {
        'api_key': "HackerOne API key.",
        'username': "HackerOne API username.",
        'delay': "Delay between API requests in seconds.",
        'limit': "Maximum number of results to retrieve per API call."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "INTERNET_NAME", "COMPANY_NAME"]

    # What events this module produces
    def producedEvents(self):
        return [
            "VULNERABILITY_DISCLOSURE",
            "RAW_RIR_DATA"
        ]

    def queryApi(self, query):
        """Query the HackerOne API."""
        if not self.opts['api_key'] or not self.opts['username']:
            self.error("You enabled sfp_h1 but did not set an API key/username!")
            self.errorState = True
            return None

        headers = {
            'Authorization': f"Basic {self.opts['api_key']}",
            'User-Agent': 'SpiderFoot',
            'Accept': 'application/json'
        }

        # Build the API URL with query parameters
        params = {
            'query': query,
            'sort': 'latest_disclosable_activity_at',
            'page[size]': str(self.opts['limit'])
        }
        
        url = f"https://api.hackerone.com/v1/reports?{urllib.parse.urlencode(params)}"
        
        res = self.sf.fetchUrl(
            url,
            timeout=30,
            useragent="SpiderFoot",
            headers=headers
        )

        time.sleep(self.opts['delay'])

        if res['code'] == "401":
            self.error("Invalid HackerOne API key/username.")
            self.errorState = True
            return None

        if res['code'] == "429":
            self.error("You are being rate-limited by HackerOne.")
            self.errorState = True
            return None

        if res['code'] != "200":
            self.error(f"Unexpected HTTP response code {res['code']} from HackerOne.")
            self.errorState = True
            return None

        if res['content'] is None:
            self.debug("No results found on HackerOne")
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.error(f"Error processing JSON response from HackerOne: {e}")
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

        if eventName not in self.watchedEvents():
            return

        self.debug(f"Querying HackerOne for {eventData}")

        data = self.queryApi(eventData)
        
        if not data:
            self.debug(f"No results found for {eventData} from HackerOne")
            return
            
        # Process the results
        reports = data.get('data', [])
        
        if not reports:
            self.debug(f"No vulnerability reports found for {eventData}")
            return
            
        evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(data), self.__name__, event)
        self.notifyListeners(evt)
            
        for report in reports:
            try:
                report_id = report.get('id')
                report_type = report.get('type')
                
                if report_type != 'report':
                    continue
                    
                attrs = report.get('attributes', {})
                
                title = attrs.get('title', '')
                state = attrs.get('state', '')
                severity = attrs.get('severity', '')
                disclosed_at = attrs.get('disclosed_at', '')
                
                if not title:
                    continue
                    
                disclosure = f"HackerOne Report #{report_id}: {title} (Severity: {severity}, Status: {state}, Disclosed: {disclosed_at})\n"
                disclosure += f"URL: https://hackerone.com/reports/{report_id}\n"
                
                evt = SpiderFootEvent("VULNERABILITY_DISCLOSURE", disclosure, self.__name__, event)
                self.notifyListeners(evt)
                
            except Exception as e:
                self.error(f"Error processing HackerOne report: {e}")
                continue

# End of sfp_h1 class
