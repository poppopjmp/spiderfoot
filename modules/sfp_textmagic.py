from __future__ import annotations

"""SpiderFoot plug-in module: textmagic."""

# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_textmagic
# Purpose:      Spiderfoot module to retrieve phone number type
#               using TextMagic API
#
# Author:      Krishnasis Mandal <krishnasis@hotmail.com>
#
# Created:     2020-10-05
# Copyright:   (c) Steve Micallef
# Licence:     MIT
# -------------------------------------------------------------------------------
import json

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin


class sfp_textmagic(SpiderFootModernPlugin):

    """Obtain phone number type from TextMagic API"""

    meta = {
        "name": "TextMagic",
        "summary": "Obtain phone number type from TextMagic API",
        'flags': ["apikey"],
        "useCases": ["Passive"],
        "categories": ["Search Engines"],
        "dataSource": {
            "website": "https://www.textmagic.com/",
            "model": "FREE_AUTH_LIMITED",
            "references": [
                "https://docs.textmagic.com/"
            ],
            "apiKeyInstructions": [
                "Visit https://textmagic.com",
                "Register a free trial account",
                "Visit https://my.textmagic.com/online/api/rest-api/keys",
                "Click on 'Add new API Key'",
                "Your API key will be listed beside 'The new API Key is'"
            ],
            "favIcon": "https://www.textmagic.com/wp-content/themes/textmagic-genesis/assets/app/images/favicon.png",
            "logo": "https://www.textmagic.com/wp-content/uploads/2015/04/logo.png",
            "description": "TextMagic is a business text-messaging service for sending "
            "notifications, alerts, reminders, confirmations and SMS marketing campaigns.",
        },
    }

    opts = {
        "api_key_username": "",
        "api_key": "",
    }

    optdescs = {
        "api_key_username": "TextMagic API Username",
        "api_key": "TextMagic API Key",
    }

    errorState = False

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.errorState = False
        self.results = self.tempStorage()

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return [
            "PHONE_NUMBER"
        ]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return [
            "PHONE_NUMBER_TYPE",
            "RAW_RIR_DATA"
        ]

    def handle_error_response(self, qry: str, res: dict) -> None:
        """Handle error response."""
        try:
            error_info = json.loads(res["content"])
        except Exception as e:
            error_info = None
        if error_info:
            error_message = error_info.get("message")
        else:
            error_message = None
        if error_message:
            error_str = f", message {error_message}"
        else:
            error_str = ""
        self.error(
            f"Failed to get results for {qry}, code {res['code']}{error_str}")

    def queryPhoneNumber(self, qry: str) -> dict | None:
        """Query PhoneNumber."""
        headers = {
            'X-TM-Username': self.opts['api_key_username'],
            'X-TM-Key': self.opts['api_key']
        }

        res = self.fetch_url(
            f"https://rest.textmagic.com/api/v2/lookups/{qry}",
            headers=headers,
            timeout=self.opts["_fetchtimeout"],
            useragent="SpiderFoot",
        )

        if res["code"] != "200":
            self.handle_error_response(qry, res)
            return None

        if res['content'] is None:
            self.info(f"No TextMagic info found for {qry}")
            return None

        try:
            return json.loads(res['content'])
        except Exception as e:
            self.error(f"Error processing JSON response from TextMagic: {e}")

        return None

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.opts["api_key"] == "" or self.opts["api_key_username"] == "":
            self.error(
                f"You enabled {self.__class__.__name__} but did not set an API Username/Key!"
            )
            self.errorState = True
            return

        if eventData in self.results:
            return
        self.results[eventData] = True

        data = self.queryPhoneNumber(event.data)

        if data is None:
            return

        phoneNumberType = data.get("type")
        if phoneNumberType is not None:
            evt = SpiderFootEvent(
                "RAW_RIR_DATA", str(data), self.__name__, event)
            self.notifyListeners(evt)

            evt = SpiderFootEvent("PHONE_NUMBER_TYPE",
                                  phoneNumberType, self.__name__, event)
            self.notifyListeners(evt)

# End of sfp_textmagic class
