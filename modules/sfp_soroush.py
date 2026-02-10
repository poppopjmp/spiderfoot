from __future__ import annotations

"""SpiderFoot plug-in module: soroush."""

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_soroush(SpiderFootModernPlugin):
    meta = {
        'name': "Soroush Monitor",
        'summary': "Monitors Soroush for new messages and emits events.",
        'flags': ['experimental'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Soroush',
            'summary': 'Soroush API for message monitoring',
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
        "channel_ids": "Comma-separated list of Soroush channel IDs.",
        "max_messages": "Maximum number of messages to fetch per channel."
    }

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["SOROUSH_MESSAGE"]

    def handleEvent(self, event):
        # Stub for Soroush monitoring logic
        pass

    def shutdown(self):
        pass
