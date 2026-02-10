"""
Redis Streams event bus implementation.

Uses Redis Streams for durable, distributed event routing between
SpiderFoot microservices. Supports consumer groups for load balancing
across multiple worker instances.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Callable

from spiderfoot.eventbus.base import EventBus, EventBusConfig, EventEnvelope


class RedisEventBus(EventBus):
    """Redis Streams-backed event bus for distributed deployments.

    Events are published to Redis Streams keyed by topic. Subscribers
    use consumer groups for at-least-once delivery and load balancing.

    Requires: redis[hiredis] (aioredis)
    """

    def __init__(self, config: EventBusConfig | None = None) -> None:
        super().__init__(config)
        self._redis = None
        self._consumer_group = f"sf-workers-{uuid.uuid4().hex[:8]}"
        self._consumer_name = f"worker-{uuid.uuid4().hex[:8]}"
        self._callbacks: dict[str, Callable] = {}
        self._sub_streams: dict[str, str] = {}  # sub_id -> stream key
        self._listen_tasks: dict[str, asyncio.Task] = {}

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            import redis.asyncio as aioredis
        except ImportError:
            raise ImportError(
                "Redis event bus requires 'redis' package. "
                "Install with: pip install redis[hiredis]"
            )

        self._redis = aioredis.from_url(
            self.config.redis_url,
            decode_responses=True,
            max_connections=20
        )

        # Verify connection
        await self._redis.ping()
        self._running = True
        self.log.info("Redis event bus connected to %s", self.config.redis_url)

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False
        for task in self._listen_tasks.values():
            task.cancel()
        self._listen_tasks.clear()

        if self._redis:
            await self._redis.aclose()
            self._redis = None

        self.log.info("Redis event bus disconnected")

    async def publish(self, envelope: EventEnvelope) -> bool:
        """Publish an event to a Redis Stream.

        Args:
            envelope: Event envelope to publish

        Returns:
            True if published successfully
        """
        if not self._redis or not self._running:
            self.log.warning("Cannot publish: Redis not connected")
            return False

        stream_key = f"{self.config.channel_prefix}:{envelope.topic}"

        payload = {
            "scan_id": envelope.scan_id,
            "event_type": envelope.event_type,
            "module": envelope.module,
            "data": json.dumps(envelope.data) if not isinstance(envelope.data, str) else envelope.data,
            "source_event_hash": envelope.source_event_hash,
            "confidence": str(envelope.confidence),
            "visibility": str(envelope.visibility),
            "risk": str(envelope.risk),
            "timestamp": str(envelope.timestamp),
            "metadata": json.dumps(envelope.metadata),
        }

        for attempt in range(self.config.max_retry):
            try:
                await self._redis.xadd(
                    stream_key, payload,
                    maxlen=100000  # Cap stream length
                )
                return True
            except Exception as e:
                self.log.warning("Publish attempt %s failed: %s", attempt+1, e)
                if attempt < self.config.max_retry - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        return False

    async def subscribe(self, topic: str, callback: Callable[[EventEnvelope], Any]) -> str:
        """Subscribe to a Redis Stream topic.

        Creates a consumer group if it doesn't exist, then starts
        listening for new events.

        Args:
            topic: Topic to subscribe to
            callback: Async callable for received events

        Returns:
            Subscription ID
        """
        sub_id = str(uuid.uuid4())
        stream_key = f"{self.config.channel_prefix}:{topic}"

        # Create consumer group if it doesn't exist
        try:
            await self._redis.xgroup_create(
                stream_key,
                self._consumer_group,
                id="0",
                mkstream=True
            )
        except Exception:
            pass  # Group already exists

        self._callbacks[sub_id] = callback
        self._sub_streams[sub_id] = stream_key

        # Start listener task
        task = asyncio.create_task(
            self._listen_loop(sub_id, stream_key)
        )
        self._listen_tasks[sub_id] = task

        self.log.debug("Subscribed %s to Redis stream '%s'", sub_id, stream_key)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription."""
        if subscription_id in self._listen_tasks:
            self._listen_tasks[subscription_id].cancel()
            del self._listen_tasks[subscription_id]

        self._callbacks.pop(subscription_id, None)
        self._sub_streams.pop(subscription_id, None)

    async def _listen_loop(self, sub_id: str, stream_key: str) -> None:
        """Background task reading from a Redis Stream consumer group."""
        try:
            while self._running and sub_id in self._callbacks:
                try:
                    results = await self._redis.xreadgroup(
                        self._consumer_group,
                        self._consumer_name,
                        {stream_key: ">"},
                        count=self.config.batch_size,
                        block=1000  # 1 second block
                    )

                    for stream, messages in results:
                        for msg_id, fields in messages:
                            try:
                                envelope = self._deserialize(fields, stream_key)
                                callback = self._callbacks.get(sub_id)
                                if callback:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(envelope)
                                    else:
                                        callback(envelope)

                                # Acknowledge message
                                await self._redis.xack(
                                    stream_key, self._consumer_group, msg_id
                                )
                            except Exception as e:
                                self.log.error("Error processing message %s: %s", msg_id, e)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.log.error("Error in listen loop: %s", e)
                    await asyncio.sleep(self.config.retry_delay)

        except asyncio.CancelledError:
            pass

    def _deserialize(self, fields: dict, stream_key: str) -> EventEnvelope:
        """Deserialize Redis Stream fields into an EventEnvelope."""
        metadata = {}
        try:
            metadata = json.loads(fields.get("metadata", "{}"))
        except (json.JSONDecodeError, TypeError):
            pass

        data = fields.get("data", "")
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            pass

        topic = stream_key.replace(f"{self.config.channel_prefix}:", "", 1)

        return EventEnvelope(
            topic=topic,
            scan_id=fields.get("scan_id", ""),
            event_type=fields.get("event_type", ""),
            module=fields.get("module", ""),
            data=data,
            source_event_hash=fields.get("source_event_hash", "ROOT"),
            confidence=int(fields.get("confidence", 100)),
            visibility=int(fields.get("visibility", 100)),
            risk=int(fields.get("risk", 0)),
            timestamp=float(fields.get("timestamp", 0.0)),
            metadata=metadata,
        )
