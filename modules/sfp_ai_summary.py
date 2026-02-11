from __future__ import annotations

"""SpiderFoot plug-in module: ai_summary."""

from spiderfoot import SpiderFootEvent
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin
import openai

class sfp_ai_summary(SpiderFootModernPlugin):
    """Summarizes scan findings using an LLM (e.g., OpenAI's GPT)."""
    meta = {
        'name': "AI Threat Intelligence Summarizer",
        'summary': "Summarizes scan findings using an LLM.",
        'flags': ['apikey'],
        'useCases': ["Investigate"],
        'group': ["Investigate"],
        'categories': ["Content Analysis"],
        'dataSource': {
            'name': 'OpenAI',
            'summary': 'LLM provider',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Sign up at https://platform.openai.com/',
                'Create an API key in your account settings.',
                'Paste the API key into the module configuration.'
            ]
        }
    }

    opts = {
        "api_key": "",
        "model": "gpt-3.5-turbo",
        "summary_frequency": "on_finish",  # or "periodic"
        "max_events": 100
    }

    optdescs = {
        "api_key": "API key for the LLM provider (e.g., OpenAI).",
        "model": "Model name (e.g., gpt-3.5-turbo).",
        "summary_frequency": "When to summarize: on_finish or periodic.",
        "max_events": "Max events to include in the summary."
    }

    def setup(self, sfc: SpiderFoot, userOpts: dict = None) -> None:
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.opts.update(userOpts)
        self.event_buffer = []

    def watchedEvents(self) -> list:
        """Return the list of events this module watches."""
        return ["*"]

    def producedEvents(self) -> list:
        """Return the list of events this module produces."""
        return ["THREAT_INTEL_SUMMARY"]

    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Handle an event received by this module."""
        self.event_buffer.append(event)
        if self.opts.get("summary_frequency") == "periodic" and len(self.event_buffer) >= int(self.opts.get("max_events", 100)):
            self._summarize_events()

    def scanFinished(self) -> None:
        """ScanFinished."""
        if self.event_buffer:
            self._summarize_events()

    def _summarize_events(self):
        if not self.opts.get("api_key"):
            self.error("No API key provided for LLM summarization.")
            return

        prompt = "Summarize the following security events:\n"
        for event in self.event_buffer[-int(self.opts["max_events"]):]:
            prompt += f"- {event.eventType}: {event.data}\n"

        try:
            openai.api_key = self.opts["api_key"]
            response = openai.ChatCompletion.create(
                model=self.opts["model"],
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response.choices[0].message["content"]
        except Exception as e:
            self.error(f"LLM API error: {e}")
            summary = "Summary unavailable due to API error."

        evt = SpiderFootEvent(
            "THREAT_INTEL_SUMMARY",
            summary,
            self.__class__.__name__,
            None
        )
        self.notifyListeners(evt)
        self.event_buffer = []
