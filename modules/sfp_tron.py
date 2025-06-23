from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_tron(SpiderFootPlugin):
    meta = {
        'name': "Tron Blockchain Monitor",
        'summary': "Monitors Tron blockchain for transactions and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'name': 'TronGrid',
            'summary': 'TronGrid API for Tron blockchain monitoring',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://www.trongrid.io/',
                'Get your API key and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "api_key": "",
        "addresses": "",  # Comma-separated Tron addresses
        "max_transactions": 10,
        "start_block": 0,
        "end_block": 0,
        "min_value": 0.0,
        "event_types": "transfer,contract",  # Comma-separated event types
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "api_key": "TronGrid API key.",
        "addresses": "Comma-separated list of Tron addresses.",
        "max_transactions": "Maximum number of transactions to fetch per address.",
        "start_block": "Start block number for filtering transactions (0 for earliest).",
        "end_block": "End block number for filtering transactions (0 for latest).",
        "min_value": "Minimum transaction value (TRX) to include.",
        "event_types": "Comma-separated list of event types to include (e.g., transfer,contract).",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.debug("[setup] Options: {}".format(self.opts))
        # Option validation
        if not self.opts.get("api_key"):
            self.error("[setup] API key is required.")
            raise ValueError("API key is required for Tron module.")
        if not self.opts.get("addresses") or not str(self.opts.get("addresses")).strip():
            self.error("[setup] addresses is required.")
            raise ValueError("addresses is required for Tron module.")
        if not isinstance(self.opts.get("max_transactions"), int) or self.opts["max_transactions"] <= 0:
            self.error("[setup] max_transactions must be a positive integer.")
            raise ValueError("max_transactions must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["TRON_ADDRESS", "TRON_TX"]

    def handleEvent(self, event):
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        # Stub event filtering logic
        if event.eventType not in self.watchedEvents():
            self.debug(f"[handleEvent] Ignoring event type: {event.eventType}")
            return
        # Stub for Tron monitoring logic
        self.debug("[handleEvent] (stub) No real logic implemented.")

    def shutdown(self):
        self.debug("[shutdown] Shutting down Tron module.")
