from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_mattermost(SpiderFootPlugin):
    meta = {
        'name': "Mattermost Server Monitor",
        'summary': "Monitors Mattermost servers for messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Mattermost',
            'summary': 'Mattermost open-source messaging platform',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at your Mattermost server',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "server_url": "",
        "channel_id": ""
    }

    optdescs = {
        "access_token": "Mattermost access token.",
        "server_url": "Mattermost server URL.",
        "channel_id": "Mattermost channel ID to monitor."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["MATTERMOST_MESSAGE"]

    def handleEvent(self, event):
        # Stub for Mattermost monitoring logic
        pass

    def shutdown(self):
        pass
