#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for spiderfoot.websocket_service."""
from __future__ import annotations

import asyncio
import json
import unittest

from spiderfoot.websocket_service import (
    ChannelType,
    WebSocketClient,
    WebSocketHub,
    WebSocketMessage,
)


class TestWebSocketMessage(unittest.TestCase):
    """Test WebSocketMessage serialization."""

    def test_to_json(self):
        msg = WebSocketMessage(
            channel="broadcast",
            event_type="test",
            data={"key": "value"},
            timestamp=1234567890.0,
        )
        parsed = json.loads(msg.to_json())
        self.assertEqual(parsed["channel"], "broadcast")
        self.assertEqual(parsed["event"], "test")
        self.assertEqual(parsed["data"]["key"], "value")
        self.assertEqual(parsed["timestamp"], 1234567890.0)

    def test_scan_id(self):
        msg = WebSocketMessage(
            channel="scan:abc123",
            event_type="scan.event",
            data="test",
            scan_id="abc123",
        )
        parsed = json.loads(msg.to_json())
        self.assertEqual(parsed["scan_id"], "abc123")


class TestWebSocketClient(unittest.TestCase):
    """Test WebSocketClient."""

    def test_subscriptions(self):
        client = WebSocketClient("test1", lambda x: None)
        self.assertTrue(client.is_subscribed(ChannelType.BROADCAST.value))

        client.subscribe("scan:abc")
        self.assertTrue(client.is_subscribed("scan:abc"))

        client.unsubscribe("scan:abc")
        self.assertFalse(client.is_subscribed("scan:abc"))

    def test_stats(self):
        client = WebSocketClient("test1", lambda x: None)
        stats = client.stats
        self.assertEqual(stats["client_id"], "test1")
        self.assertEqual(stats["sent"], 0)
        self.assertEqual(stats["dropped"], 0)


class TestWebSocketHub(unittest.TestCase):
    """Test WebSocketHub."""

    def setUp(self):
        WebSocketHub.reset()
        self.hub = WebSocketHub.get_instance()

    def tearDown(self):
        WebSocketHub.reset()

    def test_singleton(self):
        hub2 = WebSocketHub.get_instance()
        self.assertIs(self.hub, hub2)

    def test_connect_disconnect(self):
        loop = asyncio.new_event_loop()

        async def run():
            sent = []
            async def send(data):
                sent.append(data)

            client = await self.hub.connect(send, client_id="c1")
            self.assertEqual(self.hub.client_count, 1)

            await self.hub.disconnect("c1")
            self.assertEqual(self.hub.client_count, 0)

        loop.run_until_complete(run())
        loop.close()

    def test_broadcast(self):
        loop = asyncio.new_event_loop()

        async def run():
            sent = []
            async def send(data):
                sent.append(data)

            client = await self.hub.connect(send, client_id="c1")

            count = await self.hub.broadcast(
                {"msg": "hello"}, event_type="test")
            self.assertEqual(count, 1)

            # Give writer task time to process
            await asyncio.sleep(0.05)

            self.assertTrue(len(sent) > 0)
            parsed = json.loads(sent[0])
            self.assertEqual(parsed["event"], "test")
            self.assertEqual(parsed["data"]["msg"], "hello")

            await self.hub.disconnect("c1")

        loop.run_until_complete(run())
        loop.close()

    def test_scan_subscription(self):
        loop = asyncio.new_event_loop()

        async def run():
            sent_c1 = []
            sent_c2 = []

            async def send_c1(data): sent_c1.append(data)
            async def send_c2(data): sent_c2.append(data)

            await self.hub.connect(send_c1, client_id="c1")
            await self.hub.connect(send_c2, client_id="c2")

            # Only c1 subscribes to scan:abc
            self.hub.subscribe_scan("c1", "abc")

            count = await self.hub.send_scan_event(
                "abc", {"event": "data"}, event_type="scan.event")
            self.assertEqual(count, 1)

            await asyncio.sleep(0.05)

            self.assertTrue(len(sent_c1) > 0)
            self.assertEqual(len(sent_c2), 0)

            await self.hub.disconnect("c1")
            await self.hub.disconnect("c2")

        loop.run_until_complete(run())
        loop.close()

    def test_handle_subscribe(self):
        loop = asyncio.new_event_loop()

        async def run():
            async def send(data): pass

            await self.hub.connect(send, client_id="c1")

            resp = await self.hub.handle_client_message(
                "c1", '{"action": "subscribe", "scan_id": "xyz"}')
            parsed = json.loads(resp)
            self.assertEqual(parsed["action"], "subscribed")
            self.assertEqual(parsed["scan_id"], "xyz")

            await self.hub.disconnect("c1")

        loop.run_until_complete(run())
        loop.close()

    def test_handle_ping(self):
        loop = asyncio.new_event_loop()

        async def run():
            async def send(data): pass

            await self.hub.connect(send, client_id="c1")
            resp = await self.hub.handle_client_message(
                "c1", '{"action": "ping"}')
            parsed = json.loads(resp)
            self.assertEqual(parsed["action"], "pong")
            self.assertIn("timestamp", parsed)

            await self.hub.disconnect("c1")

        loop.run_until_complete(run())
        loop.close()

    def test_handle_invalid_json(self):
        loop = asyncio.new_event_loop()

        async def run():
            async def send(data): pass

            await self.hub.connect(send, client_id="c1")
            resp = await self.hub.handle_client_message("c1", "not json")
            parsed = json.loads(resp)
            self.assertIn("error", parsed)

            await self.hub.disconnect("c1")

        loop.run_until_complete(run())
        loop.close()

    def test_handle_stats(self):
        loop = asyncio.new_event_loop()

        async def run():
            async def send(data): pass

            await self.hub.connect(send, client_id="c1")
            resp = await self.hub.handle_client_message(
                "c1", '{"action": "stats"}')
            parsed = json.loads(resp)
            self.assertEqual(parsed["action"], "stats")
            self.assertIn("client", parsed)

            await self.hub.disconnect("c1")

        loop.run_until_complete(run())
        loop.close()

    def test_hub_stats(self):
        self.assertEqual(self.hub.stats["connected_clients"], 0)
        self.assertEqual(self.hub.stats["total_messages"], 0)

    def test_max_clients(self):
        loop = asyncio.new_event_loop()
        hub = WebSocketHub(max_clients=2)

        async def run():
            async def send(data): pass

            await hub.connect(send, client_id="c1")
            await hub.connect(send, client_id="c2")

            with self.assertRaises(ConnectionError):
                await hub.connect(send, client_id="c3")

            await hub.disconnect("c1")
            await hub.disconnect("c2")

        loop.run_until_complete(run())
        loop.close()

    def test_unsubscribe_scan(self):
        loop = asyncio.new_event_loop()

        async def run():
            async def send(data): pass

            await self.hub.connect(send, client_id="c1")
            self.hub.subscribe_scan("c1", "scan1")
            self.hub.unsubscribe_scan("c1", "scan1")

            client = self.hub._clients.get("c1")
            self.assertFalse(
                client.is_subscribed("scan:scan1"))

            await self.hub.disconnect("c1")

        loop.run_until_complete(run())
        loop.close()


if __name__ == "__main__":
    unittest.main()
