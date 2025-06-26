# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_tool_wappalyzer
# Purpose:      SpiderFoot plug-in for using the Wappalyzer API directly.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     2022-04-02
# Copyright:   (c) Steve Micallef 2022
# Licence:     MIT
# -------------------------------------------------------------------------------

import sys
import json
import requests
from spiderfoot import SpiderFootPlugin, SpiderFootEvent, SpiderFootHelpers


class sfp_tool_wappalyzer(SpiderFootPlugin):
    meta = {
        "name": "Tool - Wappalyzer (API)",
        "summary": "Wappalyzer identifies technologies on websites using the official API.",
        "flags": ["tool"],
        "useCases": ["Footprint", "Investigate"],
        "categories": ["Content Analysis"],
        "toolDetails": {
            "name": "Wappalyzer API",
            "description": "Wappalyzer identifies technologies on websites, including content management systems, ecommerce platforms, JavaScript frameworks, analytics tools and much more, using the official API.",
            "website": "https://www.wappalyzer.com/",
            "repository": "https://github.com/AliasIO/wappalyzer"
        }
    }

    opts = {
        "wappalyzer_api_key": "",
        "wappalyzer_api_url": "https://api.wappalyzer.com/v2/lookup/"
    }

    optdescs = {
        "wappalyzer_api_key": "Your Wappalyzer API key (required). Get one at https://www.wappalyzer.com/api/.",
        "wappalyzer_api_url": "Wappalyzer API endpoint (default should be fine)."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        for opt in userOpts.keys():
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["INTERNET_NAME"]

    def producedEvents(self):
        return ["OPERATING_SYSTEM", "SOFTWARE_USED", "WEBSERVER_TECHNOLOGY"]

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        if not self.opts["wappalyzer_api_key"]:
            self.error("You must set your Wappalyzer API key in the module options!")
            self.errorState = True
            return

        if not SpiderFootHelpers.sanitiseInput(eventData):
            self.debug("Invalid input, skipping.")
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData} as already scanned.")
            return
        self.results[eventData] = True

        url = self.opts["wappalyzer_api_url"].rstrip("/")
        headers = {"x-api-key": self.opts["wappalyzer_api_key"]}
        params = {"urls": f"https://{eventData}"}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code != 200:
                self.error(f"Wappalyzer API error: {resp.status_code} {resp.text}")
                self.errorState = True
                return
            data = resp.json()
        except Exception as e:
            self.error(f"Unable to query Wappalyzer API: {e}")
            self.errorState = True
            return

        if not data or not isinstance(data, list) or not data[0].get("technologies"):
            self.debug(f"No technologies found for {eventData}")
            return

        try:
            for item in data[0]["technologies"]:
                for cat in item.get("categories", []):
                    if cat["name"] == "Operating systems":
                        evt = SpiderFootEvent(
                            "OPERATING_SYSTEM",
                            item["name"],
                            self.__class__.__name__,
                            event,
                        )
                    elif cat["name"] == "Web servers":
                        evt = SpiderFootEvent(
                            "WEBSERVER_TECHNOLOGY",
                            item["name"],
                            self.__class__.__name__,
                            event,
                        )
                    else:
                        evt = SpiderFootEvent(
                            "SOFTWARE_USED",
                            item["name"],
                            self.__class__.__name__,
                            event,
                        )
                    self.notifyListeners(evt)
        except (KeyError, ValueError) as e:
            self.error(f"Couldn't parse the JSON output of Wappalyzer API: {e}")
            self.error(f"Wappalyzer API content: {data}")
            return


# End of sfp_tool_wappalyzer class
