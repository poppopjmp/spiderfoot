from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_rocketchat(SpiderFootPlugin):
    meta = {
        'name': "Rocket.Chat Server Monitor",
        'summary': "Monitors Rocket.Chat servers for messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Rocket.Chat',
            'summary': 'Rocket.Chat open-source team communication platform',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at your Rocket.Chat server',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "server_url": "",
        "room_id": ""
    }

    optdescs = {
        "access_token": "Rocket.Chat access token.",
        "server_url": "Rocket.Chat server URL.",
        "room_id": "Rocket.Chat room ID to monitor."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["ROCKETCHAT_MESSAGE"]

    def handleEvent(self, event):
        # Stub for Rocket.Chat monitoring logic
        pass

    def shutdown(self):
        pass
