"""Module Communication Channels for SpiderFoot.

Provides an inter-module messaging system that allows modules
to communicate without direct dependencies. Supports pub/sub
channels, request/reply patterns, and broadcast messaging.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.module_comms")


class MessagePriority(Enum):
    """Message delivery priority."""
    HIGH = 0
    NORMAL = 1
    LOW = 2


@dataclass
class Message:
    """A message sent between modules."""
    channel: str
    payload: Any
    sender: str = ""
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    reply_to: str = ""  # Channel to send reply to
    correlation_id: str = ""  # For request/reply matching

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "channel": self.channel,
            "sender": self.sender,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to,
            "correlation_id": self.correlation_id,
            "payload_type": type(self.payload).__name__,
        }


@dataclass
class ChannelStats:
    """Statistics for a communication channel."""
    messages_sent: int = 0
    messages_delivered: int = 0
    subscriber_count: int = 0
    errors: int = 0
    last_message_at: float | None = None

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "messages_sent": self.messages_sent,
            "messages_delivered": self.messages_delivered,
            "subscriber_count": self.subscriber_count,
            "errors": self.errors,
            "last_message_at": self.last_message_at,
        }


class MessageBus:
    """Pub/sub message bus for inter-module communication.

    Usage:
        bus = MessageBus()

        # Subscribe to a channel
        bus.subscribe("dns_results", handler_func)

        # Publish a message
        bus.publish("dns_results", {"ip": "1.2.3.4"}, sender="sfp_dns")

        # Request/reply pattern
        bus.subscribe("dns_lookup", lookup_handler)
        reply = bus.request("dns_lookup", "example.com", sender="sfp_ssl")
    """

    def __init__(self) -> None:
        """Initialize the MessageBus."""
        self._subscribers: dict[str, list[Callable]] = {}
        self._channel_stats: dict[str, ChannelStats] = {}
        self._lock = threading.Lock()
        self._message_log: list[Message] = []
        self._max_log = 10000
        self._enabled = True
        self._filters: dict[str, list[Callable]] = {}

    def subscribe(
        self,
        channel: str,
        handler: Callable[[Message], None],
    ) -> None:
        """Subscribe to a channel."""
        with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = []
                self._channel_stats[channel] = ChannelStats()
            self._subscribers[channel].append(handler)
            self._channel_stats[channel].subscriber_count += 1

    def unsubscribe(
        self,
        channel: str,
        handler: Callable[[Message], None],
    ) -> bool:
        """Unsubscribe from a channel."""
        with self._lock:
            subs = self._subscribers.get(channel, [])
            if handler in subs:
                subs.remove(handler)
                self._channel_stats[channel].subscriber_count -= 1
                return True
            return False

    def publish(
        self,
        channel: str,
        payload: Any,
        sender: str = "",
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: str = "",
    ) -> int:
        """Publish a message to a channel.

        Returns the number of subscribers that received the message.
        """
        if not self._enabled:
            return 0

        msg = Message(
            channel=channel,
            payload=payload,
            sender=sender,
            priority=priority,
            correlation_id=correlation_id,
        )

        with self._lock:
            handlers = list(self._subscribers.get(channel, []))
            stats = self._channel_stats.get(channel)
            if stats is None:
                stats = ChannelStats()
                self._channel_stats[channel] = stats
            stats.messages_sent += 1
            stats.last_message_at = msg.timestamp

            # Apply filters
            for f in self._filters.get(channel, []):
                try:
                    if not f(msg):
                        return 0
                except Exception as e:
                    log.error("Message filter error on '%s': %s", channel, e)

            if len(self._message_log) < self._max_log:
                self._message_log.append(msg)

        delivered = 0
        for handler in handlers:
            try:
                handler(msg)
                delivered += 1
            except Exception as e:
                log.error(
                    "Message handler error on '%s' from '%s': %s",
                    channel, sender, e,
                )
                with self._lock:
                    stats.errors += 1

        with self._lock:
            stats.messages_delivered += delivered

        return delivered

    def broadcast(
        self,
        payload: Any,
        sender: str = "",
    ) -> int:
        """Broadcast a message to all channels."""
        total = 0
        with self._lock:
            channels = list(self._subscribers.keys())
        for ch in channels:
            total += self.publish(ch, payload, sender=sender)
        return total

    def request(
        self,
        channel: str,
        payload: Any,
        sender: str = "",
        timeout: float = 5.0,
    ) -> Any | None:
        """Send a request and wait for a reply.

        The handler should call msg.reply_to channel with the response.
        """
        reply_channel = f"_reply_{channel}_{id(payload)}_{time.time()}"
        result_queue: queue.Queue = queue.Queue()

        def reply_handler(msg: Message) -> None:
            result_queue.put(msg.payload)

        self.subscribe(reply_channel, reply_handler)

        try:
            msg = Message(
                channel=channel,
                payload=payload,
                sender=sender,
                reply_to=reply_channel,
            )

            with self._lock:
                handlers = list(self._subscribers.get(channel, []))

            for handler in handlers:
                try:
                    handler(msg)
                except Exception as e:
                    log.error("Request handler error: %s", e)

            try:
                return result_queue.get(timeout=timeout)
            except queue.Empty:
                return None
        finally:
            self.unsubscribe(reply_channel, reply_handler)

    def add_filter(
        self,
        channel: str,
        filter_fn: Callable[[Message], bool],
    ) -> None:
        """Add a message filter. Return False to drop the message."""
        with self._lock:
            if channel not in self._filters:
                self._filters[channel] = []
            self._filters[channel].append(filter_fn)

    def get_channels(self) -> list[str]:
        """Get all registered channels."""
        with self._lock:
            return sorted(self._subscribers.keys())

    def get_channel_stats(self, channel: str) -> ChannelStats | None:
        """Get stats for a specific channel."""
        with self._lock:
            return self._channel_stats.get(channel)

    def get_all_stats(self) -> dict[str, dict]:
        """Get stats for all channels."""
        with self._lock:
            return {
                ch: stats.to_dict()
                for ch, stats in self._channel_stats.items()
            }

    def get_message_log(self, channel: str | None = None, limit: int = 100) -> list[dict]:
        """Get recent message log, optionally filtered by channel."""
        with self._lock:
            msgs = self._message_log
            if channel:
                msgs = [m for m in msgs if m.channel == channel]
            return [m.to_dict() for m in msgs[-limit:]]

    def clear_channel(self, channel: str) -> None:
        """Remove all subscribers and stats for a channel."""
        with self._lock:
            self._subscribers.pop(channel, None)
            self._channel_stats.pop(channel, None)
            self._filters.pop(channel, None)

    def reset(self) -> None:
        """Clear all channels, subscribers, and stats."""
        with self._lock:
            self._subscribers.clear()
            self._channel_stats.clear()
            self._message_log.clear()
            self._filters.clear()

    def enable(self) -> None:
        """Enable message delivery."""
        self._enabled = True

    def disable(self) -> None:
        """Disable message delivery."""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Check whether the message bus is enabled."""
        return self._enabled

    @property
    def channel_count(self) -> int:
        """Return the number of registered channels."""
        with self._lock:
            return len(self._subscribers)

    @property
    def total_subscribers(self) -> int:
        """Return the total number of subscribers across all channels."""
        with self._lock:
            return sum(len(subs) for subs in self._subscribers.values())

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "channel_count": len(self._subscribers),
                "total_subscribers": sum(
                    len(s) for s in self._subscribers.values()
                ),
                "channels": {
                    ch: stats.to_dict()
                    for ch, stats in self._channel_stats.items()
                },
            }


# Singleton
_global_bus: MessageBus | None = None
_bus_lock = threading.Lock()


def get_message_bus() -> MessageBus:
    """Get the global message bus singleton."""
    global _global_bus
    if _global_bus is None:
        with _bus_lock:
            if _global_bus is None:
                _global_bus = MessageBus()
    return _global_bus
