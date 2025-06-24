from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_wificafespots(SpiderFootPlugin):
    meta = {
        'name': "WiFiCafeSpots.com Lookup",
        'summary': "Queries WiFiCafeSpots.com for public WiFi hotspots and related info.",
        'flags': [],
        'useCases': ["Investigate", "Footprint"],
        'categories': ["Public Registries"],
        'dataSource': {
            'name': 'WiFiCafeSpots.com',
            'summary': 'Directory of public WiFi hotspots worldwide',
            'model': 'FREE_NOAUTH_UNLIMITED',
            'apiKeyInstructions': []
        }
    }

    opts = {
        "search_term": "",
        "country": "",
        "city": "",
        "max_results": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "search_term": "Term to search for (SSID, city, country, etc.)",
        "country": "Country to filter results.",
        "city": "City to filter results.",
        "max_results": "Maximum number of hotspots to return.",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("search_term") or not str(self.opts.get("search_term")).strip():
            self.error("[setup] search_term is required.")
            raise ValueError("search_term is required.")
        if not isinstance(self.opts.get("max_results"), int) or self.opts["max_results"] <= 0:
            self.error("[setup] max_results must be a positive integer.")
            raise ValueError("max_results must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["INTERNET_NAME", "GEOINFO"]

    def producedEvents(self):
        return ["WIFICAFESPOTS_HOTSPOT"]

    def handleEvent(self, event):
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        # Stub event filtering logic
        if event.eventType not in self.watchedEvents():
            self.debug(f"[handleEvent] Ignoring event type: {event.eventType}")
            return None
        self.debug("[handleEvent] (stub) Would process and emit WiFiCafeSpots events here.")
        return None

    def shutdown(self):
        self.debug("[shutdown] Shutting down WiFiCafeSpots module.")
