from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_unwiredlabs(SpiderFootPlugin):
    meta = {
        'name': "UnwiredLabs Geolocation API",
        'summary': "Queries UnwiredLabs for geolocation data based on cell towers, WiFi, or IP.",
        'flags': ['apikey'],
        'useCases': ["Investigate", "Footprint"],
        'categories': ["Real World"],
        'dataSource': {
            'name': 'UnwiredLabs',
            'summary': 'UnwiredLabs Location API for geolocation lookups',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://unwiredlabs.com/',
                'Get your API key and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "api_key": "",
        "search_type": "ip",  # ip, wifi, cell
        "search_value": "",
        "country": "",
        "city": "",
        "max_results": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "api_key": "UnwiredLabs API key.",
        "search_type": "Type of search: ip, wifi, or cell.",
        "search_value": "Value to search for (IP address, WiFi MAC, or cell info).",
        "country": "Country to filter results.",
        "city": "City to filter results.",
        "max_results": "Maximum number of results to return.",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("api_key") or not str(self.opts.get("api_key")).strip():
            self.error("[setup] UnwiredLabs API key is required.")
            raise ValueError("UnwiredLabs API key is required.")
        if not self.opts.get("search_value") or not str(self.opts.get("search_value")).strip():
            self.error("[setup] search_value is required.")
            raise ValueError("search_value is required.")
        if self.opts.get("search_type") not in ["ip", "wifi", "cell"]:
            self.error("[setup] search_type must be one of: ip, wifi, cell.")
            raise ValueError("search_type must be one of: ip, wifi, cell.")
        if not isinstance(self.opts.get("max_results"), int) or self.opts["max_results"] <= 0:
            self.error("[setup] max_results must be a positive integer.")
            raise ValueError("max_results must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["IP_ADDRESS", "MAC_ADDRESS", "CELL_TOWER"]

    def producedEvents(self):
        return ["UNWIREDLABS_GEOINFO"]

    def handleEvent(self, event):
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        # Stub event filtering logic
        if event.eventType not in self.watchedEvents():
            self.debug(f"[handleEvent] Ignoring event type: {event.eventType}")
            return None
        self.debug("[handleEvent] (stub) Would process and emit UnwiredLabs events here.")
        return None

    def shutdown(self):
        self.debug("[shutdown] Shutting down UnwiredLabs module.")
