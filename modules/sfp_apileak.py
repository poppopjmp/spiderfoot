from spiderfoot import SpiderFootPlugin, SpiderFootEvent
import requests
import re
import base64

class sfp_apileak(SpiderFootPlugin):
    meta = {
        'name': "API Key/Secret Leak Detector",
        'summary': "Searches for leaked API keys and secrets on GitHub and paste sites.",
        'flags': ['apikey'],
        'useCases': ['Passive', 'Investigate'],
        'group': ['Passive', 'Investigate'],
        'categories': ["Leaks, Dumps and Breaches"],
        'dataSource': {
            'name': 'GitHub',
            'summary': 'Searches GitHub and paste sites for API key leaks.',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Sign up at https://github.com/',
                'Go to Settings > Developer settings > Personal access tokens.',
                'Generate a new token with code search permissions.',
                'Paste the token into the module configuration.'
            ]
        }
    }

    opts = {
        "github_token": "",
        "search_patterns": r"(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z-_]{35})",  # Example: AWS, Google
        "max_results": 10
    }

    optdescs = {
        "github_token": "GitHub API token.",
        "search_patterns": "Regex patterns for API keys/secrets.",
        "max_results": "Max search results per query."
    }

    def setup(self, sfc, userOpts: dict = dict()) -> None:
        self.sf = sfc
        self.opts.update(userOpts)
        # Support multiple patterns (comma-separated or list)
        patterns = self.opts["search_patterns"]
        if isinstance(patterns, str) and "," in patterns:
            self.patterns = [re.compile(p.strip()) for p in patterns.split(",") if p.strip()]
        elif isinstance(patterns, str):
            self.patterns = [re.compile(patterns)]
        elif isinstance(patterns, list):
            self.patterns = [re.compile(p) for p in patterns]
        else:
            self.patterns = []

    def watchedEvents(self):
        return ["DOMAIN_NAME", "EMAILADDR", "ORG_NAME"]

    def producedEvents(self):
        return ["CREDENTIAL_LEAK", "API_KEY_LEAK"]

    def handleEvent(self, event: 'SpiderFootEvent') -> None:
        """
        Search for leaked API keys and secrets on GitHub for the given event data.
        Emits API_KEY_LEAK and CREDENTIAL_LEAK events if matches are found.

        Args:
            event (SpiderFootEvent): The event object containing event data.
        """
        query = event.data
        token = self.opts.get('github_token', '').strip()
        if not token:
            self.error("GitHub API token is not set. Please configure the github_token option.")
            return
        headers = {"Authorization": f"token {token}"}
        url = f"https://api.github.com/search/code?q={query}&per_page={self.opts['max_results']}"
        self.debug(f"Searching GitHub for leaks with query: {query} (URL: {url})")
        leaks_found = 0
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 401:
                self.error("GitHub API token is invalid or expired.")
                return
            if resp.status_code == 403:
                self.error("GitHub API rate limit exceeded or access forbidden.")
                return
            if resp.status_code != 200:
                self.error(f"GitHub API error: {resp.status_code}")
                return
            items = resp.json().get("items", [])
            self.debug(f"GitHub search returned {len(items)} results for query: {query}")
            seen = set()
            for item in items:
                file_url = item.get("html_url", "")
                if not file_url or file_url in seen:
                    continue
                seen.add(file_url)
                evt = SpiderFootEvent(
                    "API_KEY_LEAK",
                    f"Possible leak in: {file_url}",
                    self.__class__.__name__,
                    event
                )
                self.notifyListeners(evt)
                leaks_found += 1
                # Optionally, fetch file content and match regex
                if self.opts.get('fetch_file_content', True):
                    raw_url = item.get("url")
                    if raw_url:
                        try:
                            file_resp = requests.get(raw_url, headers=headers, timeout=10)
                            if file_resp.status_code == 200:
                                content = file_resp.json().get("content", "")
                                try:
                                    decoded = base64.b64decode(content).decode(errors='ignore')
                                except Exception:
                                    decoded = content
                                for pattern in self.patterns:
                                    for match in pattern.findall(decoded):
                                        self.debug(f"Credential leak match found: {match} in {file_url}")
                                        evt2 = SpiderFootEvent(
                                            "CREDENTIAL_LEAK",
                                            f"Credential leak: {match} in {file_url}",
                                            self.__class__.__name__,
                                            event
                                        )
                                        self.notifyListeners(evt2)
                        except Exception as e:
                            self.error(f"Error fetching file content from GitHub: {e}")
            if leaks_found == 0:
                self.info(f"No API key or credential leaks found for query: {query}")
        except Exception as e:
            self.error(f"Error searching GitHub: {e}")
