from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_bluesky(SpiderFootPlugin):
    meta = {
        'name': "Bluesky Monitor",
        'summary': "Monitors Bluesky for posts and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Bluesky',
            'summary': 'Bluesky decentralized social network',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://bsky.app/',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "username": "",
        "event_types": "post,reply,like",  # Comma-separated event types
        "since": "",  # Timestamp or token for incremental sync
        "max_posts": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "access_token": "Bluesky access token.",
        "username": "Bluesky username to monitor.",
        "event_types": "Comma-separated list of event types to include (e.g., post,reply,like).",
        "since": "Timestamp or token for incremental sync (empty for full history).",
        "max_posts": "Maximum number of posts to fetch per user.",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("access_token"):
            self.error("[setup] Bluesky access token is required.")
            raise ValueError("Bluesky access token is required.")
        if not self.opts.get("username"):
            self.error("[setup] Bluesky username is required.")
            raise ValueError("Bluesky username is required.")
        if not isinstance(self.opts.get("max_posts"), int) or self.opts["max_posts"] <= 0:
            self.error("[setup] max_posts must be a positive integer.")
            raise ValueError("max_posts must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["BLUESKY_POST"]

    def handleEvent(self, event):
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"[handleEvent] Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        self.debug("[handleEvent] (stub) Would process and emit Bluesky events here.")
        return None

    def shutdown(self):
        self.debug("[shutdown] Shutting down Bluesky module.")
