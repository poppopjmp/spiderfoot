from __future__ import annotations

"""SpiderFoot plug-in module: instagram."""

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_instagram(SpiderFootModernPlugin):
    """Monitors Instagram for new posts or stories and emits events."""

    meta = {
        'name': "Instagram Monitor",
        'summary': "Monitors Instagram for new posts or stories and emits events.",
        'flags': ['apikey', 'experimental'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Instagram',
            'summary': 'Instagram API for monitoring posts and stories',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register an application at https://www.instagram.com/developer/',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "usernames": "",  # Comma-separated usernames
        "max_items": 10
    }

    optdescs = {
        "access_token": "Instagram API access token.",
        "usernames": "Comma-separated list of Instagram usernames.",
        "max_items": "Maximum number of posts/stories to fetch per user."
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
        return ["INSTAGRAM_POST"]

    def handleEvent(self, event: SpiderFootEvent) -> None:
        # Stub for Instagram monitoring logic
        """Handle an event received by this module."""
        pass

    def shutdown(self) -> None:
        """Shutdown."""
        pass
