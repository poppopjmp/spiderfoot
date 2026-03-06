from __future__ import annotations

"""SpiderFoot plug-in module: nameapi."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_nameapi
# Purpose:      Spiderfoot plugin to check if an email is
#               disposable using nameapi.org API.
#
# Author:      Krishnasis Mandal <krishnasis@hotmail.com>
#
# Created:     2020-10-02
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------

import json

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin


class sfp_nameapi(SpiderFootAsyncPlugin):

    """Check whether an email is disposable"""

    meta = {
        'name': "NameAPI",
        'summary': "Check whether an email is disposable",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://www.nameapi.org/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://www.nameapi.org/en/developer/manuals/rest-web-services/53/web-services/disposable-email-address-detector/"
            ],
            'apiKeyInstructions': [
                "Visit https://nameapi.org",
                "Click on 'Get API Key'",
                "Register a free account",
                "The API key will be sent to your email"
            ],
            'favIcon': "https://www.nameapi.org/fileadmin/favicon.ico",
            'logo': "https://www.nameapi.org/fileadmin/templates/nameprofiler/images/name-api-logo.png",
            'description': "The NameAPI DEA-Detector checks email addresses "
            "against a list of known trash domains such as mailinator.com.\n"
            "It classifies those as disposable which operate as a time-limited, "
            "web based way of receiving emails, for example, sign up confirmations.",
        }
    }

    opts = {
        'api_key': ''
    }

    optdescs = {
        'api_key': "API Key for NameAPI"
    }

    results = None
    errorState = False

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()
    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "EMAILADDR"
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "EMAILADDR_DISPOSABLE",
            "RAW_RIR_DATA"
        ]

    def queryEmailAddr(self, qry: str) -> dict | None:
        """Query EmailAddr."""
        res = self.fetch_url(
            f"https://api.nameapi.org/rest/v5.3/email/disposableemailaddressdetector?apiKey={self.opts['api_key']}&emailAddress={qry}",
            timeout=self.opts['_fetchtimeout'],
            useragent="SpiderFoot"
        )

        if res['content'] is None:
            self.info(f"No NameAPI info found for {qry}")
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.error(f"Error processing JSON response from NameAPI: {e}")

        return None

    # Handle events sent to this module
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
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
            return
        self.results[eventData] = True

        data = self.queryEmailAddr(eventData)

        if data is None:
            return

        isDisposable = data.get('disposable')

        if isDisposable == "YES":
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(evt)

            evt = SpiderFootEvent("EMAILADDR_DISPOSABLE",
                                  eventData, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_nameapi class
