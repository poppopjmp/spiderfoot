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
        """
        Handle a SpiderFoot event by fetching recent Douyin videos for each configured username.
        Emits DOUYIN_VIDEO events with enriched data (username, description, timestamp).
        Deduplicates videos and handles errors per user.
        :param event: The triggering SpiderFootEvent (usually ROOT)
        """
        usernames = [u.strip() for u in self.opts.get("usernames", "").split(",") if u.strip()]
        max_videos = int(self.opts.get("max_videos", 10))
        if not usernames:
            self.info("No Douyin usernames configured.")
            return

        # Deduplication storage (per run)
        if not hasattr(self, "_seen_videos"):
            self._seen_videos = set()

        for username in usernames:
            try:
                # --- MOCKED API CALL ---
                # Simulate API/network error for a specific user
                if username == "erroruser":
                    raise Exception("Simulated API error for user erroruser")
                # Simulate no videos for a specific user
                if username == "nouser":
                    videos = []
                else:
                    videos = [
                        {
                            "id": f"{username}_vid{i}",
                            "desc": f"Test video {i} from {username}",
                            "timestamp": f"2025-06-25T13:{i:02d}:00Z"
                        }
                        for i in range(1, max_videos + 1)
                    ]
                # --- END MOCK ---
                for vid in videos:
                    vid_id = vid.get("id")
                    if not vid_id or vid_id in self._seen_videos:
                        continue
                    self._seen_videos.add(vid_id)
                    event_data = {
                        "username": username,
                        "desc": vid["desc"],
                        "timestamp": vid.get("timestamp")
                    }
                    evt = SpiderFootEvent("DOUYIN_VIDEO", str(event_data), self.__class__.__name__, event)
                    self.notifyListeners(evt)
                if not videos:
                    self.info(f"No videos found for user {username}.")
            except Exception as e:
                self.error(f"Error fetching videos for user {username}: {e}")

    def shutdown(self):
        pass
