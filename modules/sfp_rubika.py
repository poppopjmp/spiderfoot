from __future__ import annotations

"""SpiderFoot plug-in module: rubika."""

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin

class sfp_rubika(SpiderFootModernPlugin):
    """Monitors Rubika for new messages and emits events."""

    meta = {
        'name': "Rubika Monitor",
        'summary': "Monitors Rubika for new messages and emits events.",
        'flags': ['experimental'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Rubika',
            'summary': 'Rubika API for message monitoring',
            'model': 'FREE_NOAUTH_LIMITED',
            'apiKeyInstructions': [
                'No API key required for public channel monitoring.'
            ]
        }
    }

    opts = {
        "channel_ids": "",  # Comma-separated channel IDs
        "max_messages": 10
    }

    optdescs = {
        "channel_ids": "Comma-separated list of Rubika channel IDs.",
        "max_messages": "Maximum number of messages to fetch per channel."
    }

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.opts.update(userOpts)

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["ROOT"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["RUBIKA_MESSAGE"]

    def handleEvent(self, event: SpiderFootEvent) -> None:
        # Stub for Rubika monitoring logic
        """Handle an event received by this module."""
        pass

    def shutdown(self) -> None:
        """Shutdown."""
        pass
