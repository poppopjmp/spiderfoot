# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_rocketreach
# Purpose:      Search RocketReach for contact information.
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# Created:      01/02/2025
# Copyright: (c) poppopjmp
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_rocketreach(SpiderFootPlugin):

    meta = {
        'name': "RocketReach",
        'summary': "Look up contact information from RocketReach.",
        'flags': ["apikey"],
        'useCases': ["Passive", "Footprint", "Investigate"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://rocketreach.co/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://rocketreach.co/api",
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
        "max_pages": 10,
    }

    optdescs = {
        "api_key": "RocketReach API key.",
        "delay": "Delay between API requests (in seconds).",
        "max_pages": "Maximum number of pages to iterate through, to avoid exceeding RocketReach API usage limits.",
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

    def query(self, qry, querytype, page=1):
        if self.errorState:
            return None

        headers = {
            'API-KEY': self.opts['api_key']
        }

        if querytype == "email":
            queryurl = f"https://api.rocketreach.co/v1/api/lookupEmail?email={qry}&page={page}"
        elif querytype == "domain":
            queryurl = f"https://api.rocketreach.co/v1/api/lookupDomain?domain={qry}&page={page}"
        else:
            self.error(f"Invalid query type: {querytype}")
            return None

        res = self.sf.fetchUrl(
            queryurl,
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot",
            headers=headers
        )

        time.sleep(self.opts['delay'])

        if res['code'] in ["429", "500"]:
            self.error("RocketReach API key seems to have been rejected or you have exceeded usage limits.")
            self.errorState = True
            return None
        if res['code'] == 401:
            self.error("RocketReach API key is invalid.")
            self.errorState = True
            return None
        if res['code'] == 400:
            self.error("Invalid request to RocketReach API (bad query syntax or missing parameters).")
            self.errorState = True
            return None

        if not res['content']:
            self.info(f"No RocketReach info found for {qry}")
            return None

        try:
            info = json.loads(res['content'])
        except json.JSONDecodeError as e:
            self.error(f"Error processing JSON response from RocketReach: {e}")
            return None

        if info.get('total', 0) > info.get('size', 10) * page:
            page += 1
            if page > self.opts['max_pages']:
                self.error("Maximum number of pages reached.")
                return [info]
            return [info] + self.query(qry, querytype, page)
        return [info]

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

        if eventName == "EMAILADDR":
            ret = self.query(eventData, "email")
            if ret is None:
                self.info(f"No email info for {eventData}")
                return

            for rec in ret:
                matches = rec.get('matches')
                if not matches:
                    continue

                self.debug("Found email results in RocketReach")
                for match in matches:
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

                    social = match.get('social')
                    if social:
                        e = SpiderFootEvent("SOCIAL_MEDIA", social, self.__name__, event)
                        self.notifyListeners(e)

                    e = SpiderFootEvent("RAW_RIR_DATA", str(match), self.__name__, event)
                    self.notifyListeners(e)

        elif eventName == "DOMAIN_NAME":
            ret = self.query(eventData, "domain")
            if ret is None:
                self.info(f"No domain info for {eventData}")
                return

            for rec in ret:
                matches = rec.get('matches')
                if not matches:
                    continue

                self.debug("Found domain results in RocketReach")
                for match in matches:
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

                    social = match.get('social')
                    if social:
                        e = SpiderFootEvent("SOCIAL_MEDIA", social, self.__name__, event)
                        self.notifyListeners(e)

                    e = SpiderFootEvent("RAW_RIR_DATA", str(match), self.__name__, event)
                    self.notifyListeners(e)
