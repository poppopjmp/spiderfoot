from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_matrix(SpiderFootPlugin):
    meta = {
        'name': "Matrix Server Monitor",
        'summary': "Monitors Matrix servers for messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Matrix.org',
            'summary': 'Matrix open network for secure, decentralized communication',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://matrix.org/',
                'Get your access token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "access_token": "",
        "homeserver": "https://matrix.org",
        "room_id": ""
    }

    optdescs = {
        "access_token": "Matrix access token.",
        "homeserver": "Matrix homeserver URL.",
        "room_id": "Matrix room ID to monitor."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["MATRIX_MESSAGE"]

    def handleEvent(self, event):
        # Stub for Matrix monitoring logic
        pass

    def shutdown(self):
        pass
