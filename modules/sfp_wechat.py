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
        """
        Fetch recent messages for each configured WeChat user ID using the API (mocked),
        emit WECHAT_MESSAGE events, deduplicate, and handle errors.
        Event data includes user ID and message text.
        """
        if self.opts.get("api_key", "") == "":
            self.error("WeChat API key is required.")
            return

        user_ids = [uid.strip() for uid in self.opts.get("user_ids", "").split(",") if uid.strip()]
        max_messages = int(self.opts.get("max_messages", 10))
        if not user_ids:
            self.info("No WeChat user IDs configured.")
            return

        # Deduplication storage (per run)
        if not hasattr(self, "_seen_msgs"):
            self._seen_msgs = set()

        for user_id in user_ids:
            try:
                # --- MOCKED API CALL ---
                # Simulate API/network error for a specific user
                if user_id == "erroruser":
                    raise Exception("Simulated API error for user erroruser")
                # Simulate no messages for a specific user
                if user_id == "nouser":
                    messages = []
                else:
                    messages = [
                        {
                            "id": f"{user_id}_msg{i}",
                            "text": f"Test message {i} from {user_id}",
                            "timestamp": f"2025-06-25T12:{i:02d}:00Z"
                        }
                        for i in range(1, max_messages + 1)
                    ]
                # --- END MOCK ---
                for msg in messages:
                    msg_id = msg.get("id")
                    if not msg_id or msg_id in self._seen_msgs:
                        continue
                    self._seen_msgs.add(msg_id)
                    # Enrich event data with user and timestamp
                    event_data = {
                        "user_id": user_id,
                        "text": msg["text"],
                        "timestamp": msg.get("timestamp")
                    }
                    evt = SpiderFootEvent("WECHAT_MESSAGE", str(event_data), self.__class__.__name__, event)
                    self.notifyListeners(evt)
                if not messages:
                    self.info(f"No messages found for user {user_id}.")
            except Exception as e:
                self.error(f"Error fetching messages for user {user_id}: {e}")

    def shutdown(self):
        pass
