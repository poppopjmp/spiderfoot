from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_instagram(SpiderFootPlugin):
    meta = {
        'name': "Instagram Monitor",
        'summary': "Monitors Instagram for new posts or stories and emits events.",
        'flags': ['apikey'],
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

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["INSTAGRAM_POST"]

    def handleEvent(self, event):
        # Stub for Instagram monitoring logic
        pass

    def shutdown(self):
        pass
