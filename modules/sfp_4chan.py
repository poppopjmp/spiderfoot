from spiderfoot import SpiderFootPlugin, SpiderFootEvent
import requests
import time
from typing import Optional, List, Dict

class sfp_4chan(SpiderFootPlugin):
    """
    SpiderFoot plugin to monitor 4chan boards for new posts and emit events.
    """

    meta = {
        'name': "4chan Monitor",
        'summary': "Monitors 4chan boards for new posts and emits events.",
        'flags': [],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': '4chan',
            'summary': '4chan JSON API for board monitoring',
            'model': 'FREE_NOAUTH_LIMITED',
            'apiKeyInstructions': [
                'No API key required for public board monitoring.'
            ]
        }
    }

    opts = {
        "boards": "",  # Comma-separated board names (e.g. pol,b)
        "max_threads": 10
    }

    optdescs = {
        "boards": "Comma-separated list of 4chan board names.",
        "max_threads": "Maximum number of threads to fetch per board."
    }

    def setup(self, sfc, userOpts=dict()):
        """
        Setup plugin with SpiderFoot context and user options.
        :param sfc: SpiderFoot context
        :param userOpts: User options
        """
        self.sf = sfc
        self.opts.update(userOpts)
        self._seen_posts = set()

    def watchedEvents(self) -> List[str]:
        """Return a list of event types this module watches."""
        return ["ROOT"]

    def producedEvents(self) -> List[str]:
        """Return a list of event types this module produces."""
        return ["FOURCHAN_POST"]

    def _fetch_catalog(self, board: str) -> Optional[List[Dict]]:
        url = f"https://a.4cdn.org/{board}/catalog.json"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            self.sf.error(f"Failed to fetch catalog for board {board}: {resp.status_code}")
        except Exception as e:
            self.sf.error(f"Exception fetching catalog for board {board}: {e}")
        return None

    def _fetch_thread(self, board: str, thread_id: int) -> Optional[Dict]:
        url = f"https://a.4cdn.org/{board}/thread/{thread_id}.json"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            self.sf.error(f"Failed to fetch thread {thread_id} on board {board}: {resp.status_code}")
        except Exception as e:
            self.sf.error(f"Exception fetching thread {thread_id} on board {board}: {e}")
        return None

    def handleEvent(self, event):
        """
        Handle the incoming event and monitor 4chan boards for new posts.
        :param event: SpiderFootEvent
        """
        boards = [b.strip() for b in self.opts.get("boards", "").split(",") if b.strip()]
        max_threads = int(self.opts.get("max_threads", 10))
        if not boards:
            self.sf.error("No 4chan boards specified in options.")
            return
        self.sf.info(f"Monitoring 4chan boards: {', '.join(boards)} (max_threads={max_threads})")
        for board in boards:
            catalog = self._fetch_catalog(board)
            if not catalog:
                continue
            threads = []
            for page in catalog:
                threads.extend(page.get("threads", []))
            for thread in threads[:max_threads]:
                thread_id = thread.get("no")
                if not thread_id:
                    continue
                thread_data = self._fetch_thread(board, thread_id)
                if not thread_data:
                    continue
                for post in thread_data.get("posts", []):
                    post_key = f"{board}-{thread_id}-{post.get('no')}"
                    if post_key in self._seen_posts:
                        continue
                    self._seen_posts.add(post_key)
                    # Emit structured event data
                    post_info = {
                        "board": board,
                        "thread_id": thread_id,
                        "post_id": post.get("no"),
                        "subject": post.get("sub"),
                        "comment": post.get("com"),
                        "name": post.get("name"),
                        "time": post.get("time"),
                        "trip": post.get("trip"),
                        "filename": post.get("filename"),
                        "ext": post.get("ext"),
                        "rest": post
                    }
                    self.sf.debug(f"Emitting FOURCHAN_POST event: {post_info}")
                    post_event = SpiderFootEvent(
                        "FOURCHAN_POST",
                        str(post_info),
                        self.__class__.__name__,
                        event
                    )
                    self.notifyListeners(post_event)
                time.sleep(1)  # Respect API rate limit

    def shutdown(self):
        """Clean up resources if needed."""
        pass
