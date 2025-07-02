from spiderfoot import SpiderFootPlugin, SpiderFootEvent
import re
import json


class sfp_dideo(SpiderFootPlugin):
    
    meta = {
        'name': "Dideo.ir Monitor",
        'summary': "Monitors Dideo.ir for new videos and emits events.",
        'flags': [],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Dideo.ir',
            'summary': 'Dideo.ir API for video monitoring',
            'model': 'FREE_NOAUTH_LIMITED',
            'apiKeyInstructions': [
                'No API key required for public video monitoring.'
            ]
        }
    }

    opts = {
        "keywords": "",  # Comma-separated keywords
        "max_videos": 10
    }

    optdescs = {
        "keywords": "Comma-separated list of keywords to search for.",
        "max_videos": "Maximum number of videos to fetch per search."
    }

    def __init__(self):
        super().__init__()
        self.sf = None

    def setup(self, sfc, userOpts=None):
        """
        Setup plugin with SpiderFoot context and user options.

        :param sfc: SpiderFoot context
        :param userOpts: User-supplied options (dict)
        """
        if userOpts is None:
            userOpts = {}
        self.sf = sfc
        self.opts.update(userOpts)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["DIDEO_VIDEO"]

    def handleEvent(self, event):
        """
        Handle ROOT event, search Dideo.ir for each keyword, emit DIDEO_VIDEO events for found videos.

        :param event: SpiderFootEvent
        :return: None
        """
        if self.errorState:
            return
        keywords = self.opts.get("keywords", "").strip()
        if not keywords:
            self.info("No keywords provided for Dideo.ir search.")
            return
        try:
            max_videos = int(self.opts.get("max_videos", 10))
        except Exception:
            max_videos = 10
        for keyword in [k.strip() for k in keywords.split(",") if k.strip()]:
            url = f"https://www.dideo.ir/search/{self.sf.urlFuzz(keyword)}"
            self.debug(f"Searching Dideo.ir for keyword: {keyword} (URL: {url})")
            res = self.sf.fetchUrl(url, timeout=15, useragent=self.opts.get('_useragent', 'SpiderFoot'))
            if not res or not res.get('content'):
                self.error(f"No response from Dideo.ir for keyword: {keyword}")
                continue
            videos = self._parse_videos_from_html(res['content'], max_videos)
            if not videos:
                self.debug(f"No videos found for keyword: {keyword}")
                continue
            for video in videos:
                evt = SpiderFootEvent(
                    "DIDEO_VIDEO",
                    json.dumps(video),
                    self.__class__.__name__,
                    event
                )
                self.notifyListeners(evt)

    def _parse_videos_from_html(self, html, max_videos):
        """
        Parse Dideo.ir search HTML and extract video info (title, url, thumbnail, date, etc).

        :param html: HTML content from Dideo.ir search results
        :param max_videos: Maximum number of videos to extract
        :return: List of video dicts
        """
        video_pattern = re.compile(r'<a[^>]+class="video-item"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        title_pattern = re.compile(r'<div[^>]+class="title"[^>]*>(.*?)</div>', re.DOTALL)
        thumb_pattern = re.compile(r'<img[^>]+src="([^"]+)"', re.DOTALL)
        date_pattern = re.compile(r'<div[^>]+class="date"[^>]*>(.*?)</div>', re.DOTALL)
        videos = []
        for match in video_pattern.finditer(html):
            href, inner = match.groups()
            title_match = title_pattern.search(inner)
            thumb_match = thumb_pattern.search(inner)
            date_match = date_pattern.search(inner)
            video = {
                'url': f'https://www.dideo.ir{href}',
                'title': title_match.group(1).strip() if title_match else None,
                'thumbnail': thumb_match.group(1) if thumb_match else None,
                'date': date_match.group(1).strip() if date_match else None
            }
            videos.append(video)
            if len(videos) >= max_videos:
                break
        return videos

    def shutdown(self):
        """
        Shutdown plugin (no-op).
        """
        return
