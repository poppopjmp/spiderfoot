from spiderfoot import SpiderFootEvent
from spiderfoot.plugin import SpiderFootPlugin
import time
import threading

try:
    from telethon import TelegramClient, events
except ImportError:
    TelegramClient = None

class sfp_telegram(SpiderFootPlugin):
    meta = {
        'name': "Telegram Channel Monitor",
        'summary': "Monitors specified Telegram channels for new messages and emits events.",
        'flags': ["security"],
        'useCases': [ "Passive", "Investigate"],
        'categories': ["Social Media", "Messaging"],
    }

    opts = {
        "api_id": "",
        "api_hash": "",
        "channels": "",
        "poll_interval": 60,
        "max_messages": 10,
        "filter_keywords": "",  # Comma-separated keywords
        "message_types": "text",  # Comma-separated types: text,media,link
        "severity_keywords": "phishing:high,malware:high,scam:medium"
    }

    optdescs = {
        "api_id": "Telegram API ID (get from https://my.telegram.org)",
        "api_hash": "Telegram API Hash (get from https://my.telegram.org)",
        "channels": "Comma-separated list of Telegram channel usernames (e.g. @channel1,@channel2)",
        "poll_interval": "Polling interval in seconds for checking new messages.",
        "max_messages": "Maximum number of messages to fetch per channel per poll.",
        "filter_keywords": "Only emit events for messages containing these keywords (comma-separated). Leave blank for all.",
        "message_types": "Comma-separated message types to emit: text,media,link.",
        "severity_keywords": "Comma-separated keyword:severity pairs (e.g. phishing:high,scam:medium) for tagging events."
    }

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._client = None
        self._last_message_ids = {}
        self._emitted_message_ids = set()  # For deduplication

    def setup(self, sfc, userOpts=dict()):
        super().setup(sfc, userOpts)
        if not TelegramClient:
            self.error("telethon library is not installed. Please add it to requirements.txt.")
            self.errorState = True
            return False
        # Check for required options
        api_id = self.opts.get("api_id")
        api_hash = self.opts.get("api_hash")
        channels = self.opts.get("channels")
        if not api_id or not api_hash or not channels:
            self.error("Telegram API credentials and channels must be set.")
            self.errorState = True
            return False
        return True

    def start(self):
        if self.errorState:
            return
        api_id = self.opts.get("api_id")
        api_hash = self.opts.get("api_hash")
        channels = [c.strip() for c in self.opts.get("channels", "").split(",") if c.strip()]
        poll_interval = int(self.opts.get("poll_interval", 60))
        max_messages = int(self.opts.get("max_messages", 10))
        if not api_id or not api_hash or not channels:
            self.error("Telegram API credentials and channels must be set.")
            self.errorState = True
            return
        self._client = TelegramClient("sfp_telegram", api_id, api_hash)
        self._thread = threading.Thread(target=self._poll_channels, args=(channels, poll_interval, max_messages))
        self._thread.daemon = True
        self._thread.start()

    def _parse_keywords(self, s):
        return [k.strip().lower() for k in s.split(",") if k.strip()]

    def _parse_severity_map(self, s):
        mapping = {}
        for pair in s.split(","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                mapping[k.strip().lower()] = v.strip().lower()
        return mapping

    def _poll_channels(self, channels, poll_interval, max_messages):
        filter_keywords = self._parse_keywords(self.opts.get("filter_keywords", ""))
        message_types = self._parse_keywords(self.opts.get("message_types", "text"))
        severity_map = self._parse_severity_map(self.opts.get("severity_keywords", ""))
        with self._client:
            self._client.start()
            while not self._stop_event.is_set():
                for channel in channels:
                    try:
                        entity = self._client.get_entity(channel)
                        messages = self._client.get_messages(entity, limit=max_messages)
                        for msg in reversed(list(messages)):
                            last_id = self._last_message_ids.get(channel)
                            if last_id is not None and msg.id <= last_id:
                                continue
                            if msg.id in self._emitted_message_ids:
                                continue  # Deduplication
                            self._last_message_ids[channel] = msg.id
                            self._emitted_message_ids.add(msg.id)
                            # Message type filtering (simple: only text supported in this example)
                            msg_type = "text" if hasattr(msg, "text") and msg.text else "media"
                            if msg_type not in message_types:
                                continue
                            # Keyword filtering
                            msg_text = msg.text or ""
                            if filter_keywords and not any(kw in msg_text.lower() for kw in filter_keywords):
                                continue
                            # Severity tagging
                            severity = "info"
                            for kw, sev in severity_map.items():
                                if kw in msg_text.lower():
                                    severity = sev
                                    break
                            # Sender info
                            sender_id = getattr(msg, "sender_id", "?")
                            sender = getattr(msg, "sender", None)
                            sender_name = getattr(sender, "username", None) or getattr(sender, "first_name", None) or str(sender_id)
                            evt_text = f"[{channel}] {sender_name} ({sender_id}): {msg_text}\nSeverity: {severity}"
                            evt = SpiderFootEvent(
                                "TELEGRAM_MESSAGE",
                                evt_text,
                                self.__class__.__name__,
                                None
                            )
                            self.notifyListeners(evt)
                    except Exception as e:
                        self.error(f"Error fetching messages from {channel}: {e}")
                time.sleep(poll_interval)

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["TELEGRAM_MESSAGE"]

    def handleEvent(self, event):
        # This module is passive and does not process incoming events
        pass

    def finish(self):
        self._stop_event.set()
        if hasattr(self, "_thread") and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self._client:
            self._client.disconnect()
