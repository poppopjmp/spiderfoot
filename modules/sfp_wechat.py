from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_wechat(SpiderFootPlugin):
    meta = {
        'name': "WeChat Monitor",
        'summary': "Monitors WeChat for new messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'WeChat',
            'summary': 'WeChat API for message monitoring',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register for WeChat API access at https://open.weixin.qq.com/',
                'Get your API credentials and paste them into the module configuration.'
            ]
        }
    }

    opts = {
        "api_key": "",
        "user_ids": "",  # Comma-separated user IDs
        "max_messages": 10
    }

    optdescs = {
        "api_key": "WeChat API key.",
        "user_ids": "Comma-separated list of WeChat user IDs.",
        "max_messages": "Maximum number of messages to fetch per user."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["WECHAT_MESSAGE"]

    def handleEvent(self, event):
        # Stub for WeChat monitoring logic
        pass

    def shutdown(self):
        pass
