# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_ethereum
# Purpose:      SpiderFoot plug-in for scanning retrieved content by other
#               modules (such as sfp_spider) and identifying ethereum addresses.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     03/09/2018
# Copyright:   (c) Steve Micallef 2018
# Licence:     MIT
# -------------------------------------------------------------------------------

import re

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_ethereum(SpiderFootPlugin):

    meta = {
        'name': "Ethereum Address Extractor",
        'summary': "Identify ethereum addresses in scraped webpages.",
        'flags': ['apikey'],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Content Analysis"],
        'dataSource': {
            'name': 'Etherscan',
            'summary': 'Etherscan API for Ethereum blockchain monitoring',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://etherscan.io/',
                'Get your API key and paste it into the module configuration.'
            ]
        }
    }

    # Default options
    opts = {
        "api_key": "",
        "addresses": "",  # Comma-separated Ethereum addresses
        "max_transactions": 10,
        "start_block": 0,
        "end_block": 0,
        "min_value": 0.0,
        "event_types": "transfer,contract",  # Comma-separated event types
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "api_key": "Etherscan API key.",
        "addresses": "Comma-separated list of Ethereum addresses.",
        "max_transactions": "Maximum number of transactions to fetch per address.",
        "start_block": "Start block number for filtering transactions (0 for earliest).",
        "end_block": "End block number for filtering transactions (0 for latest).",
        "min_value": "Minimum transaction value (ETH) to include.",
        "event_types": "Comma-separated list of event types to include (e.g., transfer,contract).",
        "output_format": "Output format: summary (default) or full."
    }

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.opts.update(userOpts)
        self.debug("[setup] Options: {}".format(self.opts))
        # Option validation
        if not self.opts.get("api_key"):
            self.error("[setup] API key is required.")
            raise ValueError("API key is required for Ethereum module.")
        if not self.opts.get("addresses") or not str(self.opts.get("addresses")).strip():
            self.error("[setup] addresses is required.")
            raise ValueError("addresses is required for Ethereum module.")
        if not isinstance(self.opts.get("max_transactions"), int) or self.opts["max_transactions"] <= 0:
            self.error("[setup] max_transactions must be a positive integer.")
            raise ValueError("max_transactions must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["ROOT"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["ETHEREUM_ADDRESS", "ETHEREUM_TX"]

    # Handle events sent to this module
    def handleEvent(self, event):
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        # Stub event filtering logic
        if event.eventType not in self.watchedEvents():
            self.debug(f"[handleEvent] Ignoring event type: {event.eventType}")
            return
        # Stub for Ethereum monitoring logic
        self.debug("[handleEvent] (stub) No real logic implemented.")

    def shutdown(self):
        self.debug("[shutdown] Shutting down Ethereum module.")

# End of sfp_ethereum class
