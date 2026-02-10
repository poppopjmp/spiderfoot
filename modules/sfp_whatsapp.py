from __future__ import annotations

"""SpiderFoot plug-in module: whatsapp."""

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_whatsapp(SpiderFootModernPlugin):
    """Monitors WhatsApp for new messages and emits events."""

    meta = {
        'name': "WhatsApp Monitor",
        'summary': "Monitors WhatsApp for new messages and emits events.",
        'flags': ['apikey', 'experimental'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'WhatsApp',
            'summary': 'WhatsApp Business API for monitoring messages',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Apply for WhatsApp Business API access at https://www.twilio.com/whatsapp or Meta.',
                'Get your API credentials and paste them into the module configuration.'
            ]
        }
    }

    opts = {
        "api_key": "",
        "phone_numbers": "",  # Comma-separated phone numbers
        "max_messages": 10
    }

    optdescs = {
        "api_key": "WhatsApp Business API key.",
        "phone_numbers": "Comma-separated list of WhatsApp phone numbers.",
        "max_messages": "Maximum number of messages to fetch per number."
    }

    def setup(self, sfc, userOpts=None):
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.opts.update(userOpts)

    def watchedEvents(self):
        """Return the list of events this module watches."""
        return ["ROOT"]

    def producedEvents(self):
        """Return the list of events this module produces."""
        return ["WHATSAPP_MESSAGE"]

    def handleEvent(self, event):
        # Stub for WhatsApp monitoring logic
        """Handle an event received by this module."""
        pass

    def shutdown(self):
        """Shutdown."""
        pass
