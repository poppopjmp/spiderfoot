"""
NATS JetStream event bus implementation.

Uses NATS with JetStream for high-performance, durable event routing
between SpiderFoot microservices. Supports subject-based routing and
consumer groups for horizontal scaling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Callable

from spiderfoot.eventbus.base import EventBus, EventBusConfig, EventEnvelope


class NatsEventBus(EventBus):
    """NATS JetStream-backed event bus for distributed deployments.

    Uses NATS JetStream for durable, at-least-once event delivery.
    Subject hierarchy: {prefix}.{scan_id}.{event_type}

    Requires: nats-py
    """

    def __init__(self, config: EventBusConfig | None = None) -> None:
        super().__init__(config)
        self._nc = None
        self._js = None
        self._subscriptions: dict[str, Any] = {}  # sub_id -> nats subscription
        self._callbacks: dict[str, Callable] = {}

    async def connect(self) -> None:
        """Connect to NATS and set up JetStream."""
        try:
            import nats
        except ImportError:
            raise ImportError(
                "NATS event bus requires 'nats-py' package. "
                "Install with: pip install nats-py"
            )

        self._nc = await nats.connect(self.config.nats_url)
        self._js = self._nc.jetstream()

        # Create stream if it doesn't exist
        try:
            await self._js.add_stream(
                name=self.config.nats_stream,
                subjects=[f"{self.config.channel_prefix}.>"],
                retention="limits",
                max_msgs=1_000_000,
                max_bytes=1024 * 1024 * 1024,  # 1GB
                max_age=86400 * 7,  # 7 days
                storage="file",
                num_replicas=1,
            )
        except Exception:
            pass  # Stream may already exist

        self._running = True
        self.log.info("NATS event bus connected to %s", self.config.nats_url)

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        self._running = False

        for sub in self._subscriptions.values():
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.log.debug("Unsubscribe failed: %s", e)
        self._subscriptions.clear()
        self._callbacks.clear()

        if self._nc:
            await self._nc.drain()
            self._nc = None
            self._js = None

        self.log.info("NATS event bus disconnected")

    async def publish(self, envelope: EventEnvelope) -> bool:
        """Publish an event to NATS JetStream.

        Args:
            envelope: Event envelope to publish

        Returns:
            True if published successfully
        """
        if not self._js or not self._running:
            self.log.warning("Cannot publish: NATS not connected")
            return False

        subject = f"{self.config.channel_prefix}.{envelope.topic}"

        payload = {
            "scan_id": envelope.scan_id,
            "event_type": envelope.event_type,
            "module": envelope.module,
            "data": envelope.data,
            "source_event_hash": envelope.source_event_hash,
            "confidence": envelope.confidence,
            "visibility": envelope.visibility,
            "risk": envelope.risk,
            "timestamp": envelope.timestamp,
            "metadata": envelope.metadata,
        }

        data = json.dumps(payload).encode()

        for attempt in range(self.config.max_retry):
            try:
                ack = await self._js.publish(subject, data)
                return True
            except Exception as e:
                self.log.warning("NATS publish attempt %s failed: %s", attempt+1, e)
                if attempt < self.config.max_retry - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        return False

    async def subscribe(self, topic: str, callback: Callable[[EventEnvelope], Any]) -> str:
        """Subscribe to a NATS JetStream subject.

        Args:
            topic: Topic pattern to subscribe to
            callback: Async callable for received events

        Returns:
            Subscription ID
        """
        sub_id = str(uuid.uuid4())
        subject = f"{self.config.channel_prefix}.{topic}"

        # Create a durable consumer
        durable_name = f"sf-{sub_id[:8]}"

        async def msg_handler(msg) -> None:
            try:
                payload = json.loads(msg.data.decode())
                envelope = EventEnvelope(
                    topic=topic,
                    scan_id=payload.get("scan_id", ""),
                    event_type=payload.get("event_type", ""),
                    module=payload.get("module", ""),
                    data=payload.get("data", ""),
                    source_event_hash=payload.get("source_event_hash", "ROOT"),
                    confidence=payload.get("confidence", 100),
                    visibility=payload.get("visibility", 100),
                    risk=payload.get("risk", 0),
                    timestamp=payload.get("timestamp", 0.0),
                    metadata=payload.get("metadata", {}),
                )

                if asyncio.iscoroutinefunction(callback):
                    await callback(envelope)
                else:
                    callback(envelope)

                await msg.ack()
            except Exception as e:
                self.log.error("Error processing NATS message: %s", e)
                await msg.nak()

        sub = await self._js.subscribe(
            subject,
            cb=msg_handler,
            durable=durable_name,
            manual_ack=True,
        )

        self._subscriptions[sub_id] = sub
        self._callbacks[sub_id] = callback

        self.log.debug("Subscribed %s to NATS subject '%s'", sub_id, subject)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a NATS subscription."""
        sub = self._subscriptions.pop(subscription_id, None)
        if sub:
            try:
                await sub.unsubscribe()
            except Exception as e:
                self.log.warning("Error unsubscribing %s: %s", subscription_id, e)

        self._callbacks.pop(subscription_id, None)
