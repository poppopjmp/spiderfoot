from spiderfoot import SpiderFootPlugin, SpiderFootEvent
import json
import requests

class sfp_bluesky(SpiderFootPlugin):
    """SpiderFoot plugin to monitor Bluesky for posts and emit events."""
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
        "username": "",
        "event_types": "post,reply,like",  # Comma-separated event types
        "since": "",  # Timestamp or token for incremental sync
        "max_posts": 50,
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "access_token": "Bluesky access token.",
        "username": "Bluesky username to monitor.",
        "event_types": "Comma-separated list of event types to include (e.g., post,reply,like).",
        "since": "Timestamp or token for incremental sync (empty for full history).",
        "max_posts": "Maximum number of posts to fetch per user.",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.debug(f"[setup] Options: {self.opts}")
        # Option validation
        if not self.opts.get("access_token"):
            self.error("[setup] Bluesky access token is required.")
            raise ValueError("Bluesky access token is required.")
        if not self.opts.get("username"):
            self.error("[setup] Bluesky username is required.")
            raise ValueError("Bluesky username is required.")
        if not isinstance(self.opts.get("max_posts"), int) or self.opts["max_posts"] <= 0:
            self.error("[setup] max_posts must be a positive integer.")
            raise ValueError("max_posts must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["INTERNET_NAME", "ROOT"]

    def producedEvents(self):
        return ["BLUESKY_POST"]

    def handleEvent(self, event):
        """
        Handle event: fetch Bluesky posts for the configured username and emit BLUESKY_POST events.
        """
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        allowed_types = [t.strip() for t in self.opts.get("event_types", "").split(",") if t.strip()]
        if event.eventType.lower() not in [t.lower() for t in allowed_types]:
            self.debug(f"[handleEvent] Event type {event.eventType} not in allowed types {allowed_types}, skipping.")
            return None
        username = self.opts.get("username")
        access_token = self.opts.get("access_token")
        max_posts = self.opts.get("max_posts", 50)
        since = self.opts.get("since", "")
        output_format = self.opts.get("output_format", "summary")
        # Bluesky API: GET https://bsky.social/xrpc/app.bsky.feed.getAuthorFeed?actor={username}&limit={max_posts}
        url = f"https://bsky.social/xrpc/app.bsky.feed.getAuthorFeed?actor={username}&limit={max_posts}"
        if since:
            url += f"&since={since}"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 401:
                self.error("[handleEvent] Unauthorized: Invalid Bluesky access token.")
                return None
            if resp.status_code != 200:
                self.error(f"[handleEvent] Bluesky API error: {resp.status_code} {resp.text}")
                return None
            data = resp.json()
        except Exception as e:
            self.error(f"[handleEvent] Exception fetching Bluesky posts: {e}")
            return None
        posts = data.get("feed", [])
        if not posts:
            self.debug(f"[handleEvent] No posts found for user {username}.")
            return None
        for post in posts:
            if output_format == "summary":
                summary = {
                    "uri": post.get("post", {}).get("uri"),
                    "text": post.get("post", {}).get("text"),
                    "createdAt": post.get("post", {}).get("createdAt"),
                    "author": post.get("post", {}).get("author", {}).get("handle"),
                }
                event_data = json.dumps(summary)
            else:
                event_data = json.dumps(post)
            evt = SpiderFootEvent(
                "BLUESKY_POST",
                event_data,
                self.__class__.__name__,
                event
            )
            self.notifyListeners(evt)
        return None

    def shutdown(self):
        self.debug("[shutdown] Shutting down Bluesky module.")
