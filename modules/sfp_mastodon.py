from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_mastodon(SpiderFootPlugin):
    meta = {
        'name': "Mastodon Monitor",
        'summary': "Monitors Mastodon for posts and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Mastodon',
            'summary': 'Mastodon decentralized social network',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at your Mastodon instance',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "instance_url": "",
        "username": "",
        "event_types": "post,reply,boost",  # Comma-separated event types
        "since": "",  # Timestamp or token for incremental sync
        "max_posts": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "access_token": "Mastodon access token.",
        "instance_url": "Mastodon instance URL.",
        "username": "Mastodon username to monitor.",
        "event_types": "Comma-separated list of event types to include (e.g., post,reply,boost).",
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
            self.error("[setup] Mastodon access token is required.")
            raise ValueError("Mastodon access token is required.")
        if not self.opts.get("username"):
            self.error("[setup] Mastodon username is required.")
            raise ValueError("Mastodon username is required.")
        if not isinstance(self.opts.get("max_posts"), int) or self.opts["max_posts"] <= 0:
            self.error("[setup] max_posts must be a positive integer.")
            raise ValueError("max_posts must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["MASTODON_POST"]

    def handleEvent(self, event):
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"[handleEvent] Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        self.debug("[handleEvent] (stub) Would process and emit Mastodon events here.")
        return None

    def shutdown(self):
        self.debug("[shutdown] Shutting down Mastodon module.")
