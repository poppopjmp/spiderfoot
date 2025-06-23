from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_bluesky(SpiderFootPlugin):
    meta = {
        'name': "Bluesky Monitor",
        'summary': "Monitors Bluesky for posts and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Bluesky',
            'summary': 'Bluesky decentralized social network',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://bsky.app/',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "username": ""
    }

    optdescs = {
        "access_token": "Bluesky access token.",
        "username": "Bluesky username to monitor."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["BLUESKY_POST"]

    def handleEvent(self, event):
        # Stub for Bluesky monitoring logic
        pass

    def shutdown(self):
        pass
