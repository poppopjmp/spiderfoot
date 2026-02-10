"""Tests for the SpiderFoot EventBus abstraction layer."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from spiderfoot.eventbus.base import EventBus, EventBusConfig, EventBusBackend, EventEnvelope
from spiderfoot.eventbus.memory import InMemoryEventBus
from spiderfoot.eventbus.factory import create_event_bus, create_event_bus_from_config, EventBusBridge


class TestEventBusConfig:
    """Tests for EventBusConfig."""

    def test_default_config(self):
        config = EventBusConfig()
        assert config.backend == EventBusBackend.MEMORY
        assert config.channel_prefix == "sf"
        assert config.max_retry == 3

    def test_redis_config(self):
        config = EventBusConfig(
            backend=EventBusBackend.REDIS,
            redis_url="redis://myhost:6380/1"
        )
        assert config.backend == EventBusBackend.REDIS
        assert config.redis_url == "redis://myhost:6380/1"


class TestEventEnvelope:
    """Tests for EventEnvelope."""

    def test_create_envelope(self):
        env = EventEnvelope(
            topic="sf.scan1.IP_ADDRESS",
            scan_id="scan1",
            event_type="IP_ADDRESS",
            module="sfp_dnsresolve",
            data="1.2.3.4",
        )
        assert env.topic == "sf.scan1.IP_ADDRESS"
        assert env.confidence == 100
        assert env.risk == 0
        assert env.source_event_hash == "ROOT"


class TestInMemoryEventBus:
    """Tests for InMemoryEventBus."""

    @pytest.fixture
    def bus(self):
        return InMemoryEventBus()

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, bus):
        await bus.connect()
        assert bus.is_connected
        await bus.disconnect()
        assert not bus.is_connected

    @pytest.mark.asyncio
    async def test_publish_subscribe(self, bus):
        await bus.connect()
        received = []

        async def handler(envelope):
            received.append(envelope)

        sub_id = await bus.subscribe("sf.scan1.IP_ADDRESS", handler)
        
        env = EventEnvelope(
            topic="sf.scan1.IP_ADDRESS",
            scan_id="scan1",
            event_type="IP_ADDRESS",
            module="sfp_test",
            data="1.2.3.4",
        )
        
        result = await bus.publish(env)
        assert result is True
        
        # Give dispatch loop time
        await asyncio.sleep(0.1)
        
        assert len(received) == 1
        assert received[0].data == "1.2.3.4"
        
        await bus.unsubscribe(sub_id)
        await bus.disconnect()

    @pytest.mark.asyncio
    async def test_wildcard_subscribe(self, bus):
        await bus.connect()
        received = []

        async def handler(envelope):
            received.append(envelope)

        sub_id = await bus.subscribe("sf.scan1.*", handler)
        
        for evt_type in ["IP_ADDRESS", "DOMAIN_NAME", "URL_FORM"]:
            env = EventEnvelope(
                topic=f"sf.scan1.{evt_type}",
                scan_id="scan1",
                event_type=evt_type,
                module="sfp_test",
                data=f"test-{evt_type}",
            )
            await bus.publish(env)
        
        await asyncio.sleep(0.2)
        
        assert len(received) == 3
        
        await bus.unsubscribe(sub_id)
        await bus.disconnect()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, bus):
        await bus.connect()
        received = []

        async def handler(envelope):
            received.append(envelope)

        sub_id = await bus.subscribe("sf.scan1.IP_ADDRESS", handler)
        await bus.unsubscribe(sub_id)
        
        env = EventEnvelope(
            topic="sf.scan1.IP_ADDRESS",
            scan_id="scan1",
            event_type="IP_ADDRESS",
            module="sfp_test",
            data="1.2.3.4",
        )
        await bus.publish(env)
        await asyncio.sleep(0.1)
        
        assert len(received) == 0
        await bus.disconnect()

    @pytest.mark.asyncio
    async def test_no_publish_when_disconnected(self, bus):
        env = EventEnvelope(
            topic="sf.scan1.IP_ADDRESS",
            scan_id="scan1",
            event_type="IP_ADDRESS",
            module="sfp_test",
            data="1.2.3.4",
        )
        result = await bus.publish(env)
        assert result is False

    def test_topic_matches_exact(self):
        assert InMemoryEventBus._topic_matches("a.b.c", "a.b.c") is True
        assert InMemoryEventBus._topic_matches("a.b.c", "a.b.d") is False

    def test_topic_matches_wildcard(self):
        assert InMemoryEventBus._topic_matches("a.*.c", "a.b.c") is True
        assert InMemoryEventBus._topic_matches("a.*.c", "a.x.c") is True
        assert InMemoryEventBus._topic_matches("a.*.c", "a.b.d") is False

    def test_topic_matches_multi_wildcard(self):
        assert InMemoryEventBus._topic_matches("a.>", "a.b.c") is True
        assert InMemoryEventBus._topic_matches("a.>", "a.b") is True

    @pytest.mark.asyncio
    async def test_metrics(self, bus):
        await bus.connect()
        
        async def handler(env):
            pass
        
        sub_id = await bus.subscribe("sf.scan1.IP_ADDRESS", handler)
        
        assert bus.subscriber_count == 1
        assert bus.topic_count == 1
        
        await bus.unsubscribe(sub_id)
        assert bus.subscriber_count == 0
        
        await bus.disconnect()


class TestFactory:
    """Tests for create_event_bus factory."""

    def test_create_memory_bus(self):
        bus = create_event_bus()
        assert isinstance(bus, InMemoryEventBus)

    def test_create_memory_bus_explicit(self):
        config = EventBusConfig(backend=EventBusBackend.MEMORY)
        bus = create_event_bus(config)
        assert isinstance(bus, InMemoryEventBus)

    def test_create_from_sf_config_default(self):
        sf_config = {}
        bus = create_event_bus_from_config(sf_config)
        assert isinstance(bus, InMemoryEventBus)

    def test_create_from_sf_config_unknown_backend(self):
        sf_config = {"_eventbus_backend": "unknown_backend"}
        bus = create_event_bus_from_config(sf_config)
        assert isinstance(bus, InMemoryEventBus)
