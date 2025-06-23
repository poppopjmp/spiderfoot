from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_douyin(SpiderFootPlugin):
    meta = {
        'name': "Douyin Monitor",
        'summary': "Monitors Douyin for new videos and emits events.",
        'flags': [],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Douyin',
            'summary': 'Douyin API for video monitoring',
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
        "usernames": "Comma-separated list of Douyin usernames.",
        "max_videos": "Maximum number of videos to fetch per user."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["DOUYIN_VIDEO"]

    def handleEvent(self, event):
        # Stub for Douyin monitoring logic
        pass

    def shutdown(self):
        pass
