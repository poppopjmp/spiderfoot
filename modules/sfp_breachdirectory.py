# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_breachdirectory
# Purpose:  Check BreachDirectory for leaked credentials.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_breachdirectory(SpiderFootPlugin):

    meta = {
        "name": "BreachDirectory",
        "summary": "Check BreachDirectory for leaked credentials.",
        "flags": ["apikey"],
        "useCases": ["Investigate", "Passive"],
        "categories": ["Leaks, Dumps and Breaches"],
        "dataSource": {
            "website": "https://breachdirectory.org/",
            "model": "FREE_AUTH_LIMITED",
            "references": ["https://breachdirectory.org/api"],
            "apiKeyInstructions": [
                "Visit https://rapidapi.com/rohan-patra/api/breachdirectory",
                "Sign up for a RapidAPI account",
                "Subscribe to the BreachDirectory API",
                "Navigate to Security -> API Keys",
                "The API key is listed under 'X-RapidAPI-Key'",
            ],
            "favIcon": "https://breachdirectory.org/favicon.png",
            "logo": "https://breachdirectory.org/img/icons/apple-touch-icon.png",
            "description": "BreachDirectory allows you to search for breached accounts and "
            "credentials leaked in data breaches to protect your accounts.",
        },
    }

    # Default options
    opts = {
        "api_key": "",
        "check_leaks": True,
        "check_domain_breach": True,
        "max_entries": 100,
    }

    # Option descriptions
    optdescs = {
        "api_key": "BreachDirectory API key (X-RapidAPI-Key).",
        "check_leaks": "Check for leaked credentials (email, username, phone).",
        "check_domain_breach": "Check for breached domains.",
        "max_entries": "Maximum number of breaches to return (0 = unlimited).",
    }

    # Be sure to completely clear any class variables in setup()
    # or you risk data persisting between scan runs.
    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["EMAILADDR", "USERNAME", "PHONE_NUMBER", "INTERNET_NAME"]

    # What events this module produces
    def producedEvents(self):
        return [
            "EMAILADDR_COMPROMISED",
            "PASSWORD_COMPROMISED",
            "HASH_COMPROMISED",
            "RAW_RIR_DATA",
            "DOMAIN_BREACHED",
        ]

    def query(self, qry, query_type="email"):
        """Query the BreachDirectory API."""
        if not self.opts["api_key"]:
            self.error(
                "You enabled sfp_breachdirectory but did not set an API key!")
            return None

        headers = {
            "X-RapidAPI-Host": "breachdirectory.p.rapidapi.com",
            "X-RapidAPI-Key": self.opts["api_key"],
        }

        url = f"https://breachdirectory.p.rapidapi.com/?func=auto&term={qry}"

        res = self.sf.fetchUrl(
            url, timeout=15, useragent="SpiderFoot", headers=headers)

        if res["code"] == "401":
            self.error("Invalid BreachDirectory API key.")
            return None

        if res["code"] == "429":
            self.error("API rate limit exceeded.")
            return None

        if res["code"] != "200":
            self.error(
                f"Unexpected HTTP response code {res['code']} from BreachDirectory API."
            )
            return None

        if res["content"] is None:
            self.debug(f"No results found for {qry} in BreachDirectory")
            return None

        try:
            data = json.loads(res["content"])
            return data
        except Exception as e:
            self.error(
                f"Error processing JSON response from BreachDirectory: {e}")
            return None

    def queryDomain(self, domain):
        """Query the BreachDirectory API for domain breaches."""
        if not self.opts["api_key"]:
            self.error(
                "You enabled sfp_breachdirectory but did not set an API key!")
            return None

        headers = {
            "X-RapidAPI-Host": "breachdirectory.p.rapidapi.com",
            "X-RapidAPI-Key": self.opts["api_key"],
        }

        url = f"https://breachdirectory.p.rapidapi.com/domain?func=breaches&domain={domain}"

        res = self.sf.fetchUrl(
            url, timeout=15, useragent="SpiderFoot", headers=headers)

        if res["code"] != "200":
            self.error(
                f"Unexpected HTTP response code {res['code']} from BreachDirectory API."
            )
            return None

        if res["content"] is None:
            self.debug(f"No breach results found for domain {domain}")
            return None

        try:
            data = json.loads(res["content"])
            return data
        except Exception as e:
            self.error(
                f"Error processing JSON response from BreachDirectory: {e}")
            return None

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if not self.opts["api_key"]:
            self.error(
                "You enabled sfp_breachdirectory but did not set an API key!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if eventName == "EMAILADDR":
            if not self.opts["check_leaks"]:
                return

            data = self.query(eventData, "email")

            if not data:
                return

            if data.get("result") == "null":
                self.debug(f"No breach data found for email: {eventData}")
                return

            # Generate raw RIR data event
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(data), self.__name__, event
            )
            self.notifyListeners(evt)

            # Process breach data
            breaches = data.get("result", [])

            if not breaches:
                self.debug(f"No breach details found for email: {eventData}")
                return

            count = 0
            for breach in breaches:
                if self.opts["max_entries"] > 0 and count >= self.opts["max_entries"]:
                    break

                sources = breach.get("sources", [])
                if sources:
                    source_str = ", ".join(sources)
                else:
                    source_str = "Unknown"

                if breach.get("password"):
                    evt = SpiderFootEvent(
                        "PASSWORD_COMPROMISED",
                        f"Password: {breach.get('password')} (Breach source(s): {source_str})",
                        self.__name__,
                        event,
                    )
                    self.notifyListeners(evt)

                if breach.get("hash"):
                    evt = SpiderFootEvent(
                        "HASH_COMPROMISED",
                        f"Hash: {breach.get('hash')} (Breach source(s): {source_str})",
                        self.__name__,
                        event,
                    )
                    self.notifyListeners(evt)

                # Compromised email
                desc = f"BreachDirectory: {eventData} found in {source_str}"
                evt = SpiderFootEvent(
                    "EMAILADDR_COMPROMISED", desc, self.__name__, event
                )
                self.notifyListeners(evt)

                count += 1

        elif eventName == "USERNAME" or eventName == "PHONE_NUMBER":
            if not self.opts["check_leaks"]:
                return

            data = self.query(
                eventData, "username" if eventName == "USERNAME" else "phone"
            )

            if not data:
                return

            if data.get("result") == "null":
                self.debug(
                    f"No breach data found for {eventName}: {eventData}")
                return

            # Generate raw RIR data event
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(data), self.__name__, event
            )
            self.notifyListeners(evt)

            # We don't have an event type for compromised usernames/phones,
            # so we'll just output the raw data

        elif eventName == "INTERNET_NAME":
            if not self.opts["check_domain_breach"]:
                return

            data = self.queryDomain(eventData)

            if not data:
                return

            if data.get("result") == "null" or not data.get("result"):
                self.debug(f"No breach data found for domain: {eventData}")
                return

            # Generate raw RIR data event
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", json.dumps(data), self.__name__, event
            )
            self.notifyListeners(evt)

            breaches = data.get("result", [])
            if not breaches:
                return

            breach_count = len(breaches)
            desc = f"BreachDirectory found {breach_count} breach(es) for domain: {eventData}"
            evt = SpiderFootEvent("DOMAIN_BREACHED", desc,
                                  self.__name__, event)
            self.notifyListeners(evt)
