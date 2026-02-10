from __future__ import annotations

"""SpiderFoot plug-in module: matrix."""

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_matrix(SpiderFootModernPlugin):
    """Monitors Matrix servers for messages and emits events."""

    meta = {
        'name': "Matrix Server Monitor",
        'summary': "Monitors Matrix servers for messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Matrix.org',
            'summary': 'Matrix open network for secure, decentralized communication',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://matrix.org/',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "homeserver": "https://matrix.org",
        "room_id": "",
        "event_types": "message,join,leave",  # Comma-separated event types
        "since": "",  # Token for incremental sync
        "max_messages": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "access_token": "Matrix access token.",
        "homeserver": "Matrix homeserver URL.",
        "room_id": "Matrix room ID to monitor.",
        "event_types": "Comma-separated list of event types to include (e.g., message,join,leave).",
        "since": "Token for incremental sync (empty for full history).",
        "max_messages": "Maximum number of messages to fetch per room.",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.opts.update(userOpts)
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("access_token"):
            self.error("[setup] Matrix access token is required.")
            raise ValueError("Matrix access token is required.")
        if not self.opts.get("room_id"):
            self.error("[setup] Matrix room_id is required.")
            raise ValueError("Matrix room_id is required.")
        if not isinstance(self.opts.get("max_messages"), int) or self.opts["max_messages"] <= 0:
            self.error("[setup] max_messages must be a positive integer.")
            raise ValueError("max_messages must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["MATRIX_MESSAGE"]

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"[handleEvent] Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        self.debug("[handleEvent] (stub) Would process and emit Matrix events here.")
        return None

    def shutdown(self) -> None:
        """Shutdown."""
        self.debug("[shutdown] Shutting down Matrix module.")
