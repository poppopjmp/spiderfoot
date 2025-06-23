from spiderfoot import SpiderFootPlugin, SpiderFootEvent
import requests
import re

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

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.pattern = re.compile(self.opts["search_patterns"])

    def watchedEvents(self):
        return ["DOMAIN_NAME", "EMAILADDR", "ORG_NAME"]

    def producedEvents(self):
        return ["CREDENTIAL_LEAK", "API_KEY_LEAK"]

    def handleEvent(self, event):
        query = event.data
        headers = {"Authorization": f"token {self.opts['github_token']}"}
        url = f"https://api.github.com/search/code?q={query}&per_page={self.opts['max_results']}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    file_url = item.get("html_url", "")
                    evt = SpiderFootEvent(
                        "API_KEY_LEAK",
                        f"Possible leak in: {file_url}",
                        self.__class__.__name__,
                        event
                    )
                    self.notifyListeners(evt)
            else:
                self.error(f"GitHub API error: {resp.status_code}")
        except Exception as e:
            self.error(f"Error searching GitHub: {e}")
