from __future__ import annotations

"""SpiderFoot plug-in module: mattermost."""

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

class sfp_mattermost(SpiderFootAsyncPlugin):
    """Monitors Mattermost servers for messages and emits events."""

    meta = {
        'name': "Mattermost Server Monitor",
        'summary': "Monitors Mattermost servers for messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Mattermost',
            'summary': 'Mattermost open-source messaging platform',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at your Mattermost server',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "server_url": "",
        "channel_id": "",
        "event_types": "message,join,leave",  # Comma-separated event types
        "since": "",  # Timestamp or token for incremental sync
        "max_messages": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "access_token": "Mattermost access token.",
        "server_url": "Mattermost server URL.",
        "channel_id": "Mattermost channel ID to monitor.",
        "event_types": "Comma-separated list of event types to include (e.g., message,join,leave).",
        "since": "Timestamp or token for incremental sync (empty for full history).",
        "max_messages": "Maximum number of messages to fetch per channel.",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("access_token"):
            self.error("[setup] Mattermost access token is required.")
            self.errorState = True

            return
        if not self.opts.get("channel_id"):
            self.error("[setup] Mattermost channel_id is required.")
            self.errorState = True

            return
        if not isinstance(self.opts.get("max_messages"), int) or self.opts["max_messages"] <= 0:
            self.error("[setup] max_messages must be a positive integer.")
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
        return ["MATTERMOST_MESSAGE"]

    def handleEvent(self, event: SpiderFootEvent) -> None:
        if self.errorState:
            return

        """Handle an event received by this module."""
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"[handleEvent] Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        self.debug("[handleEvent] (stub) Would process and emit Mattermost events here.")
        return None

    def shutdown(self) -> None:
        """Shutdown."""
        self.debug("[shutdown] Shutting down Mattermost module.")
