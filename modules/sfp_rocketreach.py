# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:     sfp_rocketreach
# Purpose:    Search RocketReach for contact information using the official API.
#
# Author:    Agostino Panico <van1sh@van1shland.io>
#
# Created:    01/02/2025
# Copyright: (c) poppopjmp
# Licence:    MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin
import requests


class sfp_rocketreach(SpiderFootPlugin):

    meta = {
        'name': "RocketReach (Official API)",
        'summary': "Look up contact information from RocketReach using the official API.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://rocketreach.co/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://rocketreach.co/api",
                "https://github.com/rocketreach/rocketreach_python"
            ],
            'apiKeyInstructions': [
                "Visit https://rocketreach.co/",
                "Register a free account",
                "Navigate to https://rocketreach.co/api",
                "Your API key will be listed under 'API Key'",
            ],
            'favIcon': "https://rocketreach.co/favicon.ico",
            'logo': "https://rocketreach.co/logo.png",
            'description': "RocketReach is a search engine for finding contact information of professionals."
        }
    }

    opts = {
        "api_key": "",
        "delay": 1,
        "max_results": 100,  # Adapting to official API limit/pagination.
    }

    optdescs = {
        "api_key": "RocketReach API key.",
        "delay": "Delay between API requests (in seconds).",
        "max_results": "Maximum number of results to retrieve (respecting RocketReach API limits).",
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
        return ["DOMAIN_NAME", "EMAILADDR"]

    def producedEvents(self):
        return ["EMAILADDR", "PERSON_NAME", "PHONE_NUMBER", "SOCIAL_MEDIA", "RAW_RIR_DATA"]

    def query(self, query_value, query_type):
        if self.errorState:
            return None

        headers = {
            'X-Api-Key': self.opts['api_key']
        }

        params = {
            'query': query_value,
            'type': query_type,
            'limit': self.opts['max_results']
        }

        url = "https://api.rocketreach.co/v2/person/search"

        try:
            res = requests.get(url, headers=headers, params=params, timeout=self.opts['_fetchtimeout'])
            res.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            time.sleep(self.opts['delay'])
            return res.json()
        except requests.exceptions.RequestException as e:
            self.error(f"RocketReach API request failed: {e}")
            self.errorState = True
            return None
        except json.JSONDecodeError as e:
            self.error(f"Error processing JSON response from RocketReach: {e}")
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

        query_type = "email" if eventName == "EMAILADDR" else "domain" if eventName == "DOMAIN_NAME" else None

        if query_type:
            ret = self.query(eventData, query_type)
            if ret and 'results' in ret:
                for match in ret['results']:
                    email = match.get('email')
                    if email:
                        e = SpiderFootEvent("EMAILADDR", email, self.__name__, event)
                        self.notifyListeners(e)

                    name = match.get('name')
                    if name:
                        e = SpiderFootEvent("PERSON_NAME", name, self.__name__, event)
                        self.notifyListeners(e)

                    phone = match.get('phone')
                    if phone:
                        e = SpiderFootEvent("PHONE_NUMBER", phone, self.__name__, event)
                        self.notifyListeners(e)

                    social = match.get('linkedin')
                    if social:
                        e = SpiderFootEvent("SOCIAL_MEDIA", social, self.__name__, event)
                        self.notifyListeners(e)

                    e = SpiderFootEvent("RAW_RIR_DATA", str(match), self.__name__, event)
                    self.notifyListeners(e)
            elif ret is None:
                self.info(f"No RocketReach info found for {eventData}")
