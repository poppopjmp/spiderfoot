from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_rocketchat(SpiderFootPlugin):
    meta = {
        'name': "Rocket.Chat Server Monitor",
        'summary': "Monitors Rocket.Chat servers for messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Rocket.Chat',
            'summary': 'Rocket.Chat open-source team communication platform',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at your Rocket.Chat server',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "server_url": "",
        "room_id": "",
        "event_types": "message,join,leave",  # Comma-separated event types
        "since": "",  # Timestamp or token for incremental sync
        "max_messages": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "access_token": "Rocket.Chat access token.",
        "server_url": "Rocket.Chat server URL.",
        "room_id": "Rocket.Chat room ID to monitor.",
        "event_types": "Comma-separated list of event types to include (e.g., message,join,leave).",
        "since": "Timestamp or token for incremental sync (empty for full history).",
        "max_messages": "Maximum number of messages to fetch per room.",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("access_token"):
            self.error("[setup] Rocket.Chat access token is required.")
            raise ValueError("Rocket.Chat access token is required.")
        if not self.opts.get("room_id"):
            self.error("[setup] Rocket.Chat room_id is required.")
            raise ValueError("Rocket.Chat room_id is required.")
        if not isinstance(self.opts.get("max_messages"), int) or self.opts["max_messages"] <= 0:
            self.error("[setup] max_messages must be a positive integer.")
            raise ValueError("max_messages must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["ROCKETCHAT_MESSAGE"]

    def handleEvent(self, event):
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"[handleEvent] Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        self.debug("[handleEvent] (stub) Would process and emit Rocket.Chat events here.")
        return None

    def shutdown(self):
        self.debug("[shutdown] Shutting down Rocket.Chat module.")
