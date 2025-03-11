# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:     sfp_fofa
# Purpose:   Search Fofa for domain, IP address, and other information.
#
# Author:    Agostino Panico <van1sh@van1shland.io>
#
# Created:    01/02/2025
# Copyright: (c) poppopjmp
# Licence:    MIT
# -------------------------------------------------------------------------------

import json
import time
import urllib.parse
import base64

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_fofa(SpiderFootPlugin):
    meta = {
        "name": "Fofa",
        "summary": "Look up domain, IP address, and other information from Fofa.",
        "flags": ["apikey"],
        "useCases": ["Passive", "Footprint", "Investigate"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://fofa.info/",
            "model": "FREE_NOAUTH_LIMITED",
            "references": [
                "https://en.fofa.info/api",
            ],
            "apiKeyInstructions": [
                "Visit https://fofa.info/user/register",
                "Register a free account",
                "Visit https://en.fofa.info/api",
                "Your API Key will be listed under 'API Key'.",
            ],
            "favIcon": "https://en.fofa.info/favicon.ico",
            "logo": "https://en.fofa.info/static/img/logo.png",
            "description": "Fofa is a search engine for Internet-connected devices and assets.",
        },
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

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.errorState = False
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ["DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"]

    def producedEvents(self):
        return [
            "INTERNET_NAME",
            "DOMAIN_NAME",
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "RAW_RIR_DATA",
        ]

    def query(self, query):
        api_email = self.opts["api_email"]
        api_key = self.opts["api_key"]
        max_age_days = self.opts["max_age_days"]

        if not api_key or not api_email:
            self.error(
                "You enabled sfp_fofa but did not set an API key or email!")
            self.errorState = True
            return None

        query_encoded = base64.b64encode(query.encode("utf-8")).decode("utf-8")
        params = urllib.parse.urlencode(
            {
                "email": api_email,
                "key": api_key,
                "qbase64": query_encoded,
                "size": 100,  # Get a reasonable amount of data.
                # retrieve only the fields we care about.
                "fields": "host,ip,domain,ipv6",
                "time": f"-{max_age_days}d",  # limit to max_age_days
            }
        )

        url = f"https://fofa.info/api/v1/search/all?{params}"

        res = self.sf.fetchUrl(url, useragent=self.opts["_useragent"])

        time.sleep(1)

        if not res:
            self.debug("No response from Fofa API endpoint")
            return None

        return self.parseApiResponse(res)

    def parseApiResponse(self, res: dict):
        if not res:
            self.error("No response from Fofa API.")
            return None

        if res["code"] != "200":
            self.error(f"Fofa API HTTP error: {res['code']}")
            self.errorState = True
            return None

        if res["content"] is None:
            self.error("Empty response from Fofa API")
            return None

        try:
            content = json.loads(res["content"])
            if "error" in content:
                self.error(f"Fofa API error: {content['error']}")
                self.errorState = True
                return None
            return content
        except Exception as e:
            self.error(f"Error processing JSON response: {e}")
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

        if self.opts["api_key"] == "" or self.opts["api_email"] == "":
            self.error(
                f"You enabled {self.__class__.__name__} but did not set an API key or email!"
            )
            self.errorState = True
            return

        if eventName not in self.watchedEvents():
            return

        data = self.query(eventData)

        if not data or "results" not in data:
            return

        e = SpiderFootEvent("RAW_RIR_DATA", str(data), self.__name__, event)
        self.notifyListeners(e)

        for result in data["results"]:
            if "host" in result and result["host"]:
                host = result["host"].strip()
                if host:
                    e = SpiderFootEvent(
                        "INTERNET_NAME", host, self.__name__, event)
                    self.notifyListeners(e)
            if "domain" in result and result["domain"]:
                domain = result["domain"].strip()
                if domain:
                    e = SpiderFootEvent(
                        "DOMAIN_NAME", domain, self.__name__, event)
                    self.notifyListeners(e)
            if "ip" in result and result["ip"]:
                ip = result["ip"].strip()
                if ip and not self.sf.validIP(ip):
                    continue
                e = SpiderFootEvent("IP_ADDRESS", ip, self.__name__, event)
                self.notifyListeners(e)
            if "ipv6" in result and result["ipv6"]:
                ipv6 = result["ipv6"].strip()
                if ipv6 and not self.sf.validIP6(ipv6):
                    continue
                e = SpiderFootEvent("IPV6_ADDRESS", ipv6, self.__name__, event)
                self.notifyListeners(e)
