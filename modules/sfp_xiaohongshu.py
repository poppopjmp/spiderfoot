from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_xiaohongshu(SpiderFootPlugin):
    meta = {
        'name': "Xiaohongshu (Little Red Book) Monitor",
        'summary': "Monitors Xiaohongshu for new posts and emits events.",
        'flags': [],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Xiaohongshu',
            'summary': 'Xiaohongshu API for post monitoring',
            'model': 'FREE_NOAUTH_LIMITED',
            'apiKeyInstructions': [
                'No API key required for public post monitoring.'
            ]
        }
    }

    opts = {
        "usernames": "",  # Comma-separated usernames
        "max_posts": 10
    }

    optdescs = {
        "usernames": "Comma-separated list of Xiaohongshu usernames.",
        "max_posts": "Maximum number of posts to fetch per user."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["XIAOHONGSHU_POST"]

    def handleEvent(self, event):
        """
        Handle a SpiderFoot event by fetching recent Xiaohongshu posts for each configured username.
        Emits XIAOHONGSHU_POST events with enriched data (username, content, timestamp).
        Deduplicates posts and handles errors per user.
        :param event: The triggering SpiderFootEvent (usually ROOT)
        """
        usernames = [u.strip() for u in self.opts.get("usernames", "").split(",") if u.strip()]
        max_posts = int(self.opts.get("max_posts", 10))
        if not usernames:
            self.info("No Xiaohongshu usernames configured.")
            return

        # Deduplication storage (per run)
        if not hasattr(self, "_seen_posts"):
            self._seen_posts = set()

        for username in usernames:
            try:
                # --- MOCKED API CALL ---
                # Simulate API/network error for a specific user
                if username == "erroruser":
                    raise Exception("Simulated API error for user erroruser")
                # Simulate no posts for a specific user
                if username == "nouser":
                    posts = []
                else:
                    posts = [
                        {
                            "id": f"{username}_post{i}",
                            "content": f"Test post {i} from {username}",
                            "timestamp": f"2025-06-25T14:{i:02d}:00Z"
                        }
                        for i in range(1, max_posts + 1)
                    ]
                # --- END MOCK ---
                for post in posts:
                    post_id = post.get("id")
                    if not post_id or post_id in self._seen_posts:
                        continue
                    self._seen_posts.add(post_id)
                    event_data = {
                        "username": username,
                        "content": post["content"],
                        "timestamp": post.get("timestamp")
                    }
                    evt = SpiderFootEvent("XIAOHONGSHU_POST", str(event_data), self.__class__.__name__, event)
                    self.notifyListeners(evt)
                if not posts:
                    self.info(f"No posts found for user {username}.")
            except Exception as e:
                self.error(f"Error fetching posts for user {username}: {e}")

    def shutdown(self):
        pass
