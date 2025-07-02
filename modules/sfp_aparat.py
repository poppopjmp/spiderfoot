from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_aparat(SpiderFootPlugin):
    """Monitors Aparat for new videos and emits events."""
    meta = {
        'name': "Aparat Monitor",
        'summary': "Monitors Aparat for new videos and emits events.",
        'flags': [],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Aparat',
            'summary': 'Aparat API for video monitoring',
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
        "usernames": "Comma-separated list of Aparat usernames.",
        "max_videos": "Maximum number of videos to fetch per user."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["APARAT_VIDEO"]

    def handleEvent(self, event: 'SpiderFootEvent') -> None:
        """
        Handle ROOT event and monitor Aparat for new videos for configured usernames.
        Emits APARAT_VIDEO events for each video found.

        Args:
            event (SpiderFootEvent): The event object containing event data.
        """
        if event.eventType != "ROOT":
            return

        usernames = [u.strip() for u in self.opts.get("usernames", "").split(",") if u.strip()]
        max_videos = int(self.opts.get("max_videos", 10))

        if not usernames:
            self.info("No Aparat usernames configured.")
            return

        seen_global = set()
        total_found = 0
        for username in usernames:
            url = f"https://www.aparat.com/{username}/videos"
            self.debug(f"Fetching Aparat videos for user: {username} from {url}")
            try:
                res = self.sf.fetchUrl(url, timeout=15)
                if not res or res.get('code') != '200' or not res.get('content'):
                    self.error(f"Failed to fetch Aparat videos for user {username}. HTTP code: {res.get('code') if res else 'None'}")
                    continue
                import re
                # Improved regex: match both single/double quotes, tolerate whitespace, robust title extraction
                video_pattern = re.compile(r'<a[^>]+href=["\'](/v/[a-zA-Z0-9]+)[^"\']*["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
                videos = video_pattern.findall(res['content'])
                seen_user = set()
                count = 0
                for vurl, vtitle in videos:
                    vurl = vurl.strip()
                    vtitle = re.sub('<.*?>', '', vtitle).strip()  # Remove any HTML tags in title
                    if not vurl or vurl in seen_user or vurl in seen_global:
                        continue
                    seen_user.add(vurl)
                    seen_global.add(vurl)
                    video_link = f"https://www.aparat.com{vurl}"
                    evt = SpiderFootEvent(
                        "APARAT_VIDEO",
                        f"User: {username}\nTitle: {vtitle}\n<SFURL>{video_link}</SFURL>",
                        self.__class__.__name__,
                        event
                    )
                    self.notifyListeners(evt)
                    count += 1
                    total_found += 1
                    if count >= max_videos:
                        break
                if count == 0:
                    self.info(f"No videos found for Aparat user {username}.")
                else:
                    self.debug(f"Emitted {count} videos for user {username}.")
            except Exception as e:
                self.error(f"Error fetching or parsing Aparat videos for user {username}: {e}")
        if total_found == 0:
            self.info("No Aparat videos found for any configured user.")

    def shutdown(self):
        pass
