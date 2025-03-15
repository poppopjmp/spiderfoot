# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_criminalip
# Purpose:     Search CriminalIP for domain, phone and IP address information.
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


class sfp_criminalip(SpiderFootPlugin):
    meta = {
        "name": "CriminalIP",
        "summary": "Look up domain, phone and IP address information from CriminalIP.",
        "flags": ["apikey"],
        "useCases": ["Passive", "Footprint", "Investigate"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://www.criminalip.io/",
            "model": "FREE_NOAUTH_LIMITED",
            "references": [
                "https://www.criminalip.io/",
            ],
            "apiKeyInstructions": [
                "Visit https://www.criminalip.io/users/signup",
                "Register a free account",
                "Visit https://www.criminalip.io/api/",
                "Your API Key will be listed under 'API Key'.",
            ],
            "favIcon": "https://www.criminalip.io/favicon.ico",
            "logo": "https://www.criminalip.io/logo192.png",
            "description": "CriminalIP provides powerful APIs to help you enrich any user experience or automate any workflow.",
        },
    }

    opts = {
        "api_key": "",
    }

    optdescs = {
        "api_key": "CriminalIP API key.",
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
        return ["DOMAIN_NAME", "PHONE_NUMBER", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self):
        return [
            "COMPANY_NAME",
            "SOCIAL_MEDIA",
            "GEOINFO",
            "PHYSICAL_COORDINATES",
            "PROVIDER_TELCO",
            "RAW_RIR_DATA",
        ]

    def parseApiResponse(self, res: dict):
        if not res:
            self.error("No response from CriminalIP API.")
            return None

        # Rate limited to one request per second
        if res["code"] == "429":
            self.error("You are being rate-limited by CriminalIP API.")
            return None

        if res["code"] == "401":
            self.error("Unauthorized. Invalid CriminalIP API key.")
            self.errorState = True
            return None

        if res["code"] == "422":
            self.error("Usage quota reached. Insufficient API credit.")
            self.errorState = True
            return None

        if res["code"] == "500" or res["code"] == "502" or res["code"] == "503":
            self.error("CriminalIP API service is unavailable")
            self.errorState = True
            return None

        if res["code"] == "204":
            self.debug("No response data for target")
            return None

        if res["code"] != "200":
            self.error(f"Unexpected reply from CriminalIP API: {res['code']}")
            return None

        if res["content"] is None:
            return None

        try:
            return json.loads(res["content"])
        except Exception as e:
            self.debug(f"Error processing JSON response: {e}")

        return None

    def queryCriminalIP(self, qry, endpoint):
        """Query CriminalIP API.

        Args:
            qry (str): query string
            endpoint (str): API endpoint

        Returns:
            dict: API response
        """

        api_key = self.opts["api_key"]
        if not api_key:
            return None

        params = urllib.parse.urlencode(
            {
                "api_key": api_key,
                "query": qry.encode("raw_unicode_escape").decode(
                    "ascii", errors="replace"
                ),
            }
        )

        res = self.sf.fetchUrl(
            f"https://api.criminalip.io/{endpoint}?{params}",
            useragent=self.opts["_useragent"],
        )

        time.sleep(1)

        if not res:
            self.debug(f"No response from CriminalIP API endpoint: {endpoint}")
            return None

        return self.parseApiResponse(res)

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
                f"You enabled {self.__class__.__name__} but did not set the API key!"
            )
            self.errorState = True
            return

        if eventName not in self.watchedEvents():
            return

        if eventName == "DOMAIN_NAME":
            data = self.queryCriminalIP(eventData, "domain")

            if not data:
                return

            name = data.get("name")
            if not name:
                return

            if name == "To Be Confirmed":
                return

            e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(e)

            e = SpiderFootEvent("COMPANY_NAME", name, self.__name__, event)
            self.notifyListeners(e)

            linkedin_url = data.get("linkedin_url")
            if linkedin_url:
                parsed_url = urllib.parse.urlparse(linkedin_url)
                if parsed_url.hostname and (parsed_url.hostname == "linkedin.com" or parsed_url.hostname.endswith(".linkedin.com")):
                    if not linkedin_url.startswith("http"):
                        linkedin_url = f"https://{linkedin_url}"
                e = SpiderFootEvent(
                    "SOCIAL_MEDIA",
                    f"LinkedIn (Company): <SFURL>{linkedin_url}</SFURL>",
                    self.__name__,
                    event,
                )
                self.notifyListeners(e)

            locality = data.get("locality")
            country = data.get("country")
            geoinfo = ", ".join(filter(None, [locality, country]))

            if geoinfo:
                e = SpiderFootEvent("GEOINFO", geoinfo, self.__name__, event)
                self.notifyListeners(e)

        elif eventName == "PHONE_NUMBER":
            data = self.queryCriminalIP(eventData, "phone")

            if not data:
                return

            valid = data.get("valid")
            if not valid:
                return

            e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(e)

            carrier = data.get("carrier")
            if carrier:
                e = SpiderFootEvent(
                    "PROVIDER_TELCO", carrier, self.__name__, event)
                self.notifyListeners(e)

            location = data.get("location")
            country = data.get("country")
            country_name = None
            if country:
                country_name = country.get("name")

            geoinfo = ", ".join(filter(None, [location, country_name]))

            if geoinfo:
                e = SpiderFootEvent("GEOINFO", geoinfo, self.__name__, event)
                self.notifyListeners(e)

        elif eventName in ["IP_ADDRESS", "IPV6_ADDRESS"]:
            data = self.queryCriminalIP(eventData, "ip")

            if not data:
                return

            e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(e)

            geoinfo = ", ".join(
                [
                    _f
                    for _f in [
                        data.get("city"),
                        data.get("region"),
                        data.get("postal_code"),
                        data.get("country"),
                        data.get("continent"),
                    ]
                    if _f
                ]
            )

            if geoinfo:
                e = SpiderFootEvent("GEOINFO", geoinfo, self.__name__, event)
                self.notifyListeners(e)

            latitude = data.get("latitude")
            longitude = data.get("longitude")
            if latitude and longitude:
                e = SpiderFootEvent(
                    "PHYSICAL_COORDINATES",
                    f"{latitude}, {longitude}",
                    self.__name__,
                    event,
                )
                self.notifyListeners(e)


# End of sfp_criminalip class
