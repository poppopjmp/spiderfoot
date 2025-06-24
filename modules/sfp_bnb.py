from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_bnb(SpiderFootPlugin):
    meta = {
        'name': "BNB Chain Monitor",
        'summary': "Monitors Binance Smart Chain (BNB) for transactions and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'name': 'BscScan',
            'summary': 'BscScan API for BNB Chain monitoring',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://bscscan.com/',
                'Get your API key and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "api_key": "",
        "addresses": "",  # Comma-separated BNB addresses
        "max_transactions": 10,
        "start_block": 0,
        "end_block": 0,
        "min_value": 0.0,
        "event_types": "transfer,contract",  # Comma-separated event types
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "api_key": "BscScan API key.",
        "addresses": "Comma-separated list of BNB addresses.",
        "max_transactions": "Maximum number of transactions to fetch per address.",
        "start_block": "Start block number for filtering transactions (0 for earliest).",
        "end_block": "End block number for filtering transactions (0 for latest).",
        "min_value": "Minimum transaction value (BNB) to include.",
        "event_types": "Comma-separated list of event types to include (e.g., transfer,contract).",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        # Option validation
        if not self.opts.get("api_key"):
            self.error("BNB module requires a BscScan API key.")
        if not self.opts.get("addresses"):
            self.error("BNB module requires at least one address.")
        if not isinstance(self.opts.get("max_transactions"), int) or self.opts["max_transactions"] <= 0:
            self.error("max_transactions must be a positive integer.")
        if self.opts.get("min_value") and self.opts["min_value"] < 0:
            self.error("min_value must be non-negative.")
        self.debug(f"BNB module options: {self.opts}")

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["BNB_ADDRESS", "BNB_TX"]

    def handleEvent(self, event):
        self.debug(f"Received event: {event.eventType} from {event.module}")
        # Optionally filter by event_types (stub logic)
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        # Optionally filter by min_value (stub logic)
        try:
            value = float(getattr(event, 'value', 0))
            if value < self.opts.get("min_value", 0.0):
                self.debug(f"Event value {value} below min_value {self.opts['min_value']}, skipping.")
                return None
        except Exception:
            pass
        # Stub: would process and emit events here
        self.debug("Stub: would process and emit BNB events here.")
        return None

    def shutdown(self):
        self.debug("Shutting down BNB module.")
