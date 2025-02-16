# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_rocketreach
# Purpose:     Search RocketReach for email addresses, phone numbers, and social media profiles.
#
# Author:      Your Name <your.email@example.com>
#
# Created:     2023-04-01
# Copyright:   (c) Your Name
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_rocketreach(SpiderFootPlugin):

    meta = {
        'name': "RocketReach",
        'summary': "Look up email addresses, phone numbers, and social media profiles from RocketReach.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://rocketreach.co/",
            'model': "FREE_NOAUTH_LIMITED",
            'references': [
                "https://rocketreach.co/",
            ],
            'apiKeyInstructions': [
                "Visit https://rocketreach.co/",
                "Register a free account",
                "Navigate to https://rocketreach.co/api",
                "Your API Key will be listed under 'API Key'",
            ],
            'favIcon': "https://rocketreach.co/favicon.ico",
            'logo': "https://rocketreach.co/logo.png",
            'description': "RocketReach provides powerful APIs to help you enrich any user experience or automate any workflow."
        }
    }

    opts = {
        "api_key": "",
    }

    optdescs = {
        "api_key": "RocketReach API key.",
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
        return ["EMAILADDR", "PHONE_NUMBER", "SOCIAL_MEDIA"]

    def producedEvents(self):
        return ["EMAILADDR", "PHONE_NUMBER", "SOCIAL_MEDIA", "RAW_RIR_DATA"]

    def queryRocketReach(self, qry, qry_type):
        """Query RocketReach API.

        Args:
            qry (str): query string (email, phone number, or social media profile)
            qry_type (str): type of query (email, phone, social)

        Returns:
            dict: response data
        """

        api_key = self.opts['api_key']
        if not api_key:
            return None

        params = urllib.parse.urlencode({
            'api_key': api_key,
            qry_type: qry.encode('raw_unicode_escape').decode("ascii", errors='replace'),
        })

        res = self.sf.fetchUrl(
            f"https://api.rocketreach.co/v1/?{params}",
            useragent=self.opts['_useragent']
        )

        time.sleep(1)

        if not res:
            self.debug("No response from RocketReach API endpoint")
            return None

        return self.parseApiResponse(res)

    def parseApiResponse(self, res: dict):
        if not res:
            self.error("No response from RocketReach API.")
            return None

        if res['code'] == '429':
            self.error("You are being rate-limited by RocketReach.")
            return None

        if res['code'] == '401':
            self.error("Unauthorized. Invalid RocketReach API key.")
            self.errorState = True
            return None

        if res['code'] == '422':
            self.error("Usage quota reached. Insufficient API credit.")
            self.errorState = True
            return None

        if res['code'] == '500' or res['code'] == '502' or res['code'] == '503':
            self.error("RocketReach API service is unavailable")
            self.errorState = True
            return None

        if res['code'] == '204':
            self.debug("No response data for target")
            return None

        if res['code'] != '200':
            self.error(f"Unexpected reply from RocketReach API: {res['code']}")
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

        if eventName == "EMAILADDR":
            data = self.queryRocketReach(eventData, 'email')

            if not data:
                return

            e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(e)

            e = SpiderFootEvent("EMAILADDR", eventData, self.__name__, event)
            self.notifyListeners(e)

        elif eventName == "PHONE_NUMBER":
            data = self.queryRocketReach(eventData, 'phone')

            if not data:
                return

            e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(e)

            e = SpiderFootEvent("PHONE_NUMBER", eventData, self.__name__, event)
            self.notifyListeners(e)

        elif eventName == "SOCIAL_MEDIA":
            data = self.queryRocketReach(eventData, 'social')

            if not data:
                return

            e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(e)

            e = SpiderFootEvent("SOCIAL_MEDIA", eventData, self.__name__, event)
            self.notifyListeners(e)

# End of sfp_rocketreach class
