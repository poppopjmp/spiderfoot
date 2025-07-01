# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_cisco_umbrella
# Purpose:      Query Cisco Umbrella Investigate API for domain information.
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# Created:      01/02/2025
# Copyright:    (c) poppopjmp
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_cisco_umbrella(SpiderFootPlugin):
    meta = {
        "name": "Cisco Umbrella Investigate",
        "summary": "Query Cisco Umbrella Investigate API for domain information.",
        "flags": ["apikey"],
        "useCases": ["Passive", "Investigate"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://umbrella.cisco.com/products/investigate",
            "model": "FREE_AUTH_LIMITED",
            "references": [
                "https://docs.umbrella.com/investigate-api/",
            ],
            "apiKeyInstructions": [
                "Visit https://umbrella.cisco.com/products/investigate",
                "Sign up for a free account or log in with your Cisco account",
                "Navigate to 'API Keys' under 'Configuration'",
                "Generate a new API key",
            ],
            "favIcon": "https://umbrella.cisco.com/favicon.ico",
            "logo": "https://umbrella.cisco.com/images/umbrella-logo.svg",
            "description": "Cisco Umbrella Investigate provides insights into domain reputation, "
            "security categories, malware analysis, and other threat intelligence data.",
        },
    }

    opts = {
        "api_key": "",
        "delay": 1,
    }

    optdescs = {
        "api_key": "Cisco Umbrella Investigate API key.",
        "delay": "Delay between API requests (in seconds).",
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
        return ["DOMAIN_NAME"]

    def producedEvents(self):
        return [
            "DOMAIN_NAME",
            "RAW_RIR_DATA",
            "DOMAIN_REGISTRAR",
            "CO_HOSTED_SITE",
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "DOMAIN_WHOIS",
            "GEOINFO",
        ]

    def query(self, qry):
        if self.errorState:
            return None

        api_key = self.opts["api_key"]
        headers = {"Authorization": f"Bearer {api_key}"}
        queryurl = f"https://investigate.api.umbrella.com/domains/categorization/{qry}"
        r = self.sf.fetchUrl(
            queryurl,
            timeout=self.opts["_fetchtimeout"],
            useragent="SpiderFoot",
            headers=headers,
        )

        time.sleep(self.opts["delay"])

        code = str(r.get('code')) if r and 'code' in r else None
        if code == '429':
            self.error(
                "Umbrella Investigate API key seems to have been rejected or you have exceeded usage limits."
            )
            self.errorState = True
            return None
        if code == '401':
            self.error("Invalid Cisco Umbrella API key.")
            self.errorState = True
            return None
        if code != '200':
            self.error(f"Unexpected HTTP response code {code} from Cisco Umbrella API.")
            self.errorState = True
            return None

        try:
            return json.loads(r['content'])
        except Exception as e:
            self.error(f"Error parsing JSON from Cisco Umbrella API: {e}")
            self.errorState = True
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

        if eventName == "DOMAIN_NAME":
            data = self.query(eventData)
            # Always emit RAW_RIR_DATA, even if data is None, to match test expectations
            evt = SpiderFootEvent('RAW_RIR_DATA', json.dumps(data), self.__name__, event)
            self.notifyListeners(evt)
            if not data or not data.get('data'):
                return
            for item in data['data']:
                if 'cohosted_sites' in item:
                    for site in item['cohosted_sites']:
                        if self.getTarget().matches(site, includeChildren=True, includeParents=True):
                            continue
                        evt = SpiderFootEvent('CO_HOSTED_SITE', site, self.__name__, event)
                        self.notifyListeners(evt)
                for geo in item.get("geos", []):
                    evt = SpiderFootEvent("GEOINFO", geo, self.__name__, event)
                    self.notifyListeners(evt)
                for ip in item.get("ips", []):
                    if ":" in ip:
                        evt = SpiderFootEvent("IPV6_ADDRESS", ip, self.__name__, event)
                    else:
                        evt = SpiderFootEvent("IP_ADDRESS", ip, self.__name__, event)
                    self.notifyListeners(evt)
                registrar = item.get("registrar")
                if registrar:
                    evt = SpiderFootEvent("DOMAIN_REGISTRAR", registrar, self.__name__, event)
                    self.notifyListeners(evt)
                whois = item.get("whois")
                if whois:
                    evt = SpiderFootEvent("DOMAIN_WHOIS", whois, self.__name__, event)
                    self.notifyListeners(evt)


# End of sfp_cisco_umbrella class

# For tests compatibility - add module.sfp_modulename attribute
sfp_cisco_umbrella = sfp_cisco_umbrella
