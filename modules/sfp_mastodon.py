from __future__ import annotations

"""SpiderFoot plug-in module: mastodon."""

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

class sfp_mastodon(SpiderFootAsyncPlugin):
    """Monitors Mastodon for posts and emits events."""

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

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("access_token"):
            self.error("[setup] Mastodon access token is required.")
            self.errorState = True

            return
        if not self.opts.get("username"):
            self.error("[setup] Mastodon username is required.")
            self.errorState = True

            return
        if not isinstance(self.opts.get("max_posts"), int) or self.opts["max_posts"] <= 0:
            self.error("[setup] max_posts must be a positive integer.")
            self.errorState = True

            return
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            self.errorState = True

            return

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["MASTODON_POST"]

    def handleEvent(self, event: SpiderFootEvent) -> None:
        if self.errorState:
            return

        """Handle an event received by this module."""
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"[handleEvent] Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        self.debug("[handleEvent] (stub) Would process and emit Mastodon events here.")
        return None

    def shutdown(self) -> None:
        """Shutdown."""
        self.debug("[shutdown] Shutting down Mastodon module.")
