# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:     sfp_fofa
# Purpose:   Search Fofa for domain, IP address, and other information.
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
import base64
from typing import Optional, Dict, Any
from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_fofa(SpiderFootPlugin):
    """SpiderFoot plugin for querying Fofa API to look up domain, IP address, and other information."""
    meta = {
        'name': "Fofa",
        'summary': "Look up domain, IP address, and other information from Fofa.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://fofa.info/",
            'model': "FREE_NOAUTH_LIMITED",
            'references': [
                "https://en.fofa.info/api",
            ],
            'apiKeyInstructions': [
                "Visit https://fofa.info/user/register",
                "Register a free account",
                "Visit https://en.fofa.info/api",
                "Your API Key will be listed under 'API Key'.",
            ],
            'favIcon': "https://en.fofa.info/favicon.ico",
            'logo': "https://en.fofa.info/static/img/logo.png",
            'description': "Fofa is a search engine for Internet-connected devices and assets."
        }
    }

    opts = {
        "api_email": "",
        "api_key": "",
        "max_age_days": 30,  # limit results to the past X days.
    }

    optdescs = {
        "api_email": "Fofa API email.",
        "api_key": "Fofa API key.",
        "max_age_days": "Limit results to assets discovered within this many days.",
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=None):
        """
        Setup plugin with SpiderFoot context and user options.
        :param sfc: SpiderFoot context
        :param userOpts: User-supplied options (dict)
        """
        if userOpts is None:
            userOpts = {}
        self.sf = sfc
        self.errorState = False
        self.results = self.tempStorage()
        for opt in userOpts:
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        """Return a list of event types this module watches."""
        return ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self):
        """Return a list of event types this module produces."""
        return ["INTERNET_NAME", "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS", "RAW_RIR_DATA"]

    def query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Query the Fofa API for the given search string.
        :param query: The search string (domain, IP, etc.)
        :return: Parsed JSON response or None
        """
        api_email = self.opts.get('api_email', '')
        api_key = self.opts.get('api_key', '')
        max_age_days = self.opts.get('max_age_days', 30)
        if not api_key or not api_email:
            self.error("You enabled sfp_fofa but did not set an API key or email!")
            self.errorState = True
            return None
        try:
            query_encoded = base64.b64encode(query.encode('utf-8')).decode('utf-8')
            params = urllib.parse.urlencode({
                'email': api_email,
                'key': api_key,
                'qbase64': query_encoded,
                'size': 100,
                'fields': 'host,ip,domain,ipv6',
                'time': f'-{max_age_days}d',
            })
            url = f"https://fofa.info/api/v1/search/all?{params}"
            res = self.sf.fetchUrl(
                url,
                useragent=self.opts.get('_useragent', 'SpiderFoot')
            )
            time.sleep(1)
            if not res:
                self.debug("No response from Fofa API endpoint")
                return None
            return self.parseApiResponse(res)
        except Exception as e:
            self.error(f"Exception during Fofa API query: {e}")
            return None

    def parseApiResponse(self, res: dict) -> Optional[Dict[str, Any]]:
        """
        Parse the Fofa API response.
        :param res: Response dict from fetchUrl
        :return: Parsed JSON or None
        """
        if not res:
            self.error("No response from Fofa API.")
            return None
        if res.get('code') != 200:
            errmsg = res.get('errmsg', 'Unknown error')
            self.error(f"Fofa API error: {errmsg}")
            self.errorState = True
            return None
        try:
            return json.loads(res.get('content', '{}'))
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")
            return None

    def handleEvent(self, event):
        """
        Handle incoming events, query Fofa, and emit results as SpiderFootEvents.
        :param event: SpiderFootEvent
        """
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        self.debug(f"Received event, {eventName}, from {srcModuleName}")
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return
        self.results[eventData] = True
        if self.opts.get("api_key", "") == "" or self.opts.get("api_email", "") == "":
            self.error(f"You enabled {self.__class__.__name__} but did not set an API key or email!")
            self.errorState = True
            return
        if eventName not in self.watchedEvents():
            self.debug(f"Event {eventName} not in watched events, skipping.")
            return
        data = self.query(eventData)
        if not data or 'results' not in data:
            self.debug(f"No results from Fofa for {eventData}")
            return
        # Emit the raw data event
        self._emit_event("RAW_RIR_DATA", str(data), event)
        # Deduplicate emitted values
        emitted = set()
        results = data['results'] if isinstance(data['results'], list) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            for key, event_type in [
                ('host', 'INTERNET_NAME'),
                ('domain', 'DOMAIN_NAME'),
                ('ip', 'IP_ADDRESS'),
                ('ipv6', 'IPV6_ADDRESS')
            ]:
                value = result.get(key)
                if value and (event_type, value) not in emitted:
                    self._emit_event(event_type, value, event)
                    emitted.add((event_type, value))

    def _emit_event(self, event_type: str, data: str, parent_event: SpiderFootEvent):
        """
        Helper to emit a SpiderFootEvent with debug logging.
        :param event_type: The event type to emit
        :param data: The event data
        :param parent_event: The parent SpiderFootEvent
        """
        self.debug(f"Emitting event {event_type}: {data}")
        evt = SpiderFootEvent(event_type, data, self.__class__.__name__, parent_event)
        self.notifyListeners(evt)
