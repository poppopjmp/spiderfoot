from __future__ import annotations

"""SpiderFoot plug-in module: reddit."""

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_reddit(SpiderFootModernPlugin):
    """Monitors specified subreddits for new posts and emits events."""

    meta = {
        'name': "Reddit Monitor",
        'summary': "Monitors specified subreddits for new posts and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Reddit',
            'summary': 'Reddit API for subreddit monitoring',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Go to https://www.reddit.com/prefs/apps',
                'Create a new application to get client ID and secret.',
                'Paste the client ID and secret into the module configuration.'
            ]
        }
    }

    opts = {
        "client_id": "",
        "client_secret": "",
        "subreddits": "",  # Comma-separated subreddit names
        "max_posts": 10
    }

    optdescs = {
        "client_id": "Reddit API client ID.",
        "client_secret": "Reddit API client secret.",
        "subreddits": "Comma-separated list of subreddit names.",
        "max_posts": "Maximum number of posts to fetch per subreddit."
    }

    def setup(self, sfc, userOpts=None):
        super().setup(sfc, userOpts or {})
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["REDDIT_POST"]

    def handleEvent(self, event):
        # This is a stub. Actual implementation would use praw or similar.
        pass

    def shutdown(self):
        pass
