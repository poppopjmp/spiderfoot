from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_aparat(SpiderFootPlugin):
    meta = {
        'name': "Aparat Monitor",
        'summary': "Monitors Aparat for new videos and emits events.",
        'flags': [],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Aparat',
            'summary': 'Aparat API for video monitoring',
            'model': 'FREE_NOAUTH_LIMITED',
            'apiKeyInstructions': [
                'No API key required for public video monitoring.'
            ]
        }
    }

    opts = {
        "usernames": "",  # Comma-separated usernames
        "max_videos": 10
    }

    optdescs = {
        "usernames": "Comma-separated list of Aparat usernames.",
        "max_videos": "Maximum number of videos to fetch per user."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["APARAT_VIDEO"]

    def handleEvent(self, event):
        # Stub for Aparat monitoring logic
        pass

    def shutdown(self):
        pass
