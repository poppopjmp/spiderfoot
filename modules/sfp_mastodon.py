from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_mastodon(SpiderFootPlugin):
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
        "username": ""
    }

    optdescs = {
        "access_token": "Mastodon access token.",
        "instance_url": "Mastodon instance URL.",
        "username": "Mastodon username to monitor."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["MASTODON_POST"]

    def handleEvent(self, event):
        # Stub for Mastodon monitoring logic
        pass

    def shutdown(self):
        pass
