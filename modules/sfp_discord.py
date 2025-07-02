from spiderfoot import SpiderFootPlugin, SpiderFootEvent
import json
import requests

class sfp_discord(SpiderFootPlugin):
    """Discord Channel Monitor"""
    meta = {
        'name': "Discord Channel Monitor",
        'summary': "Monitors specified Discord channels for new messages and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'group': ["Passive", "Investigate"],
        'categories': ["Social Media"],
        'dataSource': {
            'name': 'Discord',
            'summary': 'Discord API for channel monitoring',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Go to https://discord.com/developers/applications',
                'Create a new application and bot, add it to your server.',
                'Copy the bot token and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "bot_token": "",
        "channel_ids": "",  # Comma-separated channel IDs
        "max_messages": 10
    }

    optdescs = {
        "bot_token": "Discord bot token.",
        "channel_ids": "Comma-separated list of Discord channel IDs.",
        "max_messages": "Maximum number of messages to fetch per channel."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        # Option validation
        if not self.opts.get("bot_token"):
            self.error("Discord bot token is required.")
            raise ValueError("Discord bot token is required.")
        if not self.opts.get("channel_ids"):
            self.error("At least one Discord channel ID is required.")
            raise ValueError("At least one Discord channel ID is required.")
        if not isinstance(self.opts.get("max_messages"), int) or self.opts["max_messages"] <= 0:
            self.error("max_messages must be a positive integer.")
            raise ValueError("max_messages must be a positive integer.")

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["DISCORD_MESSAGE"]

    def handleEvent(self, event):
        """
        Handle event: fetch Discord messages for each channel and emit DISCORD_MESSAGE events.
        """
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        bot_token = self.opts.get("bot_token")
        channel_ids = [cid.strip() for cid in self.opts.get("channel_ids", "").split(",") if cid.strip()]
        max_messages = self.opts.get("max_messages", 10)
        headers = {
            "Authorization": f"Bot {bot_token}",
            "User-Agent": "DiscordBot (https://github.com/sm/sfp_discord, 1.0)",
        }
        for channel_id in channel_ids:
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={max_messages}"
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 401:
                    self.error(f"[handleEvent] Unauthorized: Invalid Discord bot token for channel {channel_id}.")
                    continue
                if resp.status_code == 403:
                    self.error(f"[handleEvent] Forbidden: Bot does not have access to channel {channel_id}.")
                    continue
                if resp.status_code != 200:
                    self.error(f"[handleEvent] Discord API error: {resp.status_code} {resp.text}")
                    continue
                messages = resp.json()
            except Exception as e:
                self.error(f"[handleEvent] Exception fetching Discord messages: {e}")
                continue
            if not messages:
                self.debug(f"[handleEvent] No messages found for channel {channel_id}.")
                continue
            for msg in messages:
                summary = {
                    "id": msg.get("id"),
                    "content": msg.get("content"),
                    "author": msg.get("author", {}).get("username"),
                    "timestamp": msg.get("timestamp"),
                    "channel_id": channel_id
                }
                event_data = json.dumps(summary)
                evt = SpiderFootEvent(
                    "DISCORD_MESSAGE",
                    event_data,
                    self.__class__.__name__,
                    event
                )
                self.notifyListeners(evt)

    def shutdown(self):
        self.debug("[shutdown] Shutting down Discord module.")
