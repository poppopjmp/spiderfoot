"""Tests for spiderfoot.module_comms module."""
from __future__ import annotations

import threading
import time
import unittest

from spiderfoot.module_comms import (
    ChannelStats,
    Message,
    MessageBus,
    MessagePriority,
    get_message_bus,
)


class TestMessagePriority(unittest.TestCase):
    def test_ordering(self):
        self.assertLess(MessagePriority.HIGH.value, MessagePriority.NORMAL.value)
        self.assertLess(MessagePriority.NORMAL.value, MessagePriority.LOW.value)


class TestMessage(unittest.TestCase):
    def test_creation(self):
        msg = Message(channel="test", payload={"key": "val"}, sender="sfp_dns")
        self.assertEqual(msg.channel, "test")
        self.assertEqual(msg.sender, "sfp_dns")
        self.assertIsNotNone(msg.timestamp)

    def test_to_dict(self):
        msg = Message(channel="test", payload="data", sender="mod1")
        d = msg.to_dict()
        self.assertEqual(d["channel"], "test")
        self.assertEqual(d["sender"], "mod1")
        self.assertEqual(d["payload_type"], "str")


class TestChannelStats(unittest.TestCase):
    def test_to_dict(self):
        s = ChannelStats(messages_sent=10, messages_delivered=8, errors=2)
        d = s.to_dict()
        self.assertEqual(d["messages_sent"], 10)
        self.assertEqual(d["errors"], 2)


class TestMessageBus(unittest.TestCase):
    def test_subscribe_and_publish(self):
        bus = MessageBus()
        received = []
        bus.subscribe("test", lambda msg: received.append(msg.payload))
        bus.publish("test", "hello", sender="mod1")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], "hello")

    def test_multiple_subscribers(self):
        bus = MessageBus()
        r1, r2 = [], []
        bus.subscribe("ch", lambda m: r1.append(m.payload))
        bus.subscribe("ch", lambda m: r2.append(m.payload))
        count = bus.publish("ch", "data")
        self.assertEqual(count, 2)
        self.assertEqual(r1, ["data"])
        self.assertEqual(r2, ["data"])

    def test_unsubscribe(self):
        bus = MessageBus()
        received = []
        handler = lambda m: received.append(m.payload)
        bus.subscribe("ch", handler)
        bus.publish("ch", "msg1")
        bus.unsubscribe("ch", handler)
        bus.publish("ch", "msg2")
        self.assertEqual(len(received), 1)

    def test_unsubscribe_nonexistent(self):
        bus = MessageBus()
        self.assertFalse(bus.unsubscribe("ch", lambda m: None))

    def test_publish_no_subscribers(self):
        bus = MessageBus()
        count = bus.publish("empty_ch", "data")
        self.assertEqual(count, 0)

    def test_broadcast(self):
        bus = MessageBus()
        r1, r2 = [], []
        bus.subscribe("ch1", lambda m: r1.append(True))
        bus.subscribe("ch2", lambda m: r2.append(True))
        total = bus.broadcast("alert", sender="system")
        self.assertEqual(total, 2)

    def test_handler_error_continues(self):
        bus = MessageBus()
        received = []

        def bad_handler(m):
            raise ValueError("oops")

        def good_handler(m):
            received.append(m.payload)

        bus.subscribe("ch", bad_handler)
        bus.subscribe("ch", good_handler)
        bus.publish("ch", "data")
        self.assertEqual(len(received), 1)

    def test_disabled(self):
        bus = MessageBus()
        received = []
        bus.subscribe("ch", lambda m: received.append(True))
        bus.disable()
        bus.publish("ch", "data")
        self.assertEqual(len(received), 0)
        bus.enable()
        bus.publish("ch", "data")
        self.assertEqual(len(received), 1)

    def test_channels(self):
        bus = MessageBus()
        bus.subscribe("alpha", lambda m: None)
        bus.subscribe("beta", lambda m: None)
        channels = bus.get_channels()
        self.assertEqual(channels, ["alpha", "beta"])

    def test_channel_stats(self):
        bus = MessageBus()
        bus.subscribe("ch", lambda m: None)
        bus.publish("ch", "data")
        bus.publish("ch", "more")

        stats = bus.get_channel_stats("ch")
        self.assertEqual(stats.messages_sent, 2)
        self.assertEqual(stats.messages_delivered, 2)
        self.assertEqual(stats.subscriber_count, 1)

    def test_all_stats(self):
        bus = MessageBus()
        bus.subscribe("a", lambda m: None)
        bus.subscribe("b", lambda m: None)
        bus.publish("a", "x")

        all_stats = bus.get_all_stats()
        self.assertIn("a", all_stats)
        self.assertIn("b", all_stats)

    def test_message_log(self):
        bus = MessageBus()
        bus.subscribe("ch", lambda m: None)
        bus.publish("ch", "msg1", sender="mod1")
        bus.publish("ch", "msg2", sender="mod2")

        log_entries = bus.get_message_log()
        self.assertEqual(len(log_entries), 2)

        filtered = bus.get_message_log(channel="ch")
        self.assertEqual(len(filtered), 2)

    def test_clear_channel(self):
        bus = MessageBus()
        bus.subscribe("ch", lambda m: None)
        bus.clear_channel("ch")
        self.assertIsNone(bus.get_channel_stats("ch"))

    def test_reset(self):
        bus = MessageBus()
        bus.subscribe("ch", lambda m: None)
        bus.publish("ch", "data")
        bus.reset()
        self.assertEqual(bus.channel_count, 0)
        self.assertEqual(bus.total_subscribers, 0)

    def test_filter(self):
        bus = MessageBus()
        received = []
        bus.subscribe("ch", lambda m: received.append(m.payload))

        # Only allow messages from "mod1"
        bus.add_filter("ch", lambda m: m.sender == "mod1")

        bus.publish("ch", "allowed", sender="mod1")
        bus.publish("ch", "blocked", sender="mod2")

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], "allowed")

    def test_request_reply(self):
        bus = MessageBus()

        def handler(msg):
            if msg.reply_to:
                bus.publish(msg.reply_to, f"reply:{msg.payload}")

        bus.subscribe("lookup", handler)
        result = bus.request("lookup", "example.com", timeout=2.0)
        self.assertEqual(result, "reply:example.com")

    def test_request_timeout(self):
        bus = MessageBus()
        # No handler → times out
        result = bus.request("empty", "data", timeout=0.1)
        self.assertIsNone(result)

    def test_counts(self):
        bus = MessageBus()
        bus.subscribe("a", lambda m: None)
        bus.subscribe("a", lambda m: None)
        bus.subscribe("b", lambda m: None)
        self.assertEqual(bus.channel_count, 2)
        self.assertEqual(bus.total_subscribers, 3)

    def test_to_dict(self):
        bus = MessageBus()
        bus.subscribe("ch", lambda m: None)
        d = bus.to_dict()
        self.assertIn("enabled", d)
        self.assertIn("channel_count", d)
        self.assertIn("channels", d)

    def test_thread_safety(self):
        bus = MessageBus()
        counter = {"count": 0}
        lock = threading.Lock()

        def handler(m):
            with lock:
                counter["count"] += 1

        bus.subscribe("ch", handler)
        errors = []

        def publish_many():
            try:
                for _ in range(100):
                    bus.publish("ch", "data")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publish_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(counter["count"], 400)


class TestSingleton(unittest.TestCase):
    def test_get_message_bus(self):
        b1 = get_message_bus()
        b2 = get_message_bus()
        self.assertIs(b1, b2)


if __name__ == "__main__":
    unittest.main()
