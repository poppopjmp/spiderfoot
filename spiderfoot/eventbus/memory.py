"""
In-memory event bus implementation.

This is the default backend that preserves the existing single-process
behavior using asyncio queues. It is used for development, testing,
and single-instance deployments.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Any, Callable

from spiderfoot.eventbus.base import EventBus, EventBusConfig, EventEnvelope


class InMemoryEventBus(EventBus):
    """In-memory event bus using asyncio queues.

    This implementation routes events between subscribers within a single
    process, matching the original SpiderFoot behavior. It supports topic
    wildcards and is fully async-compatible.
    """

    def __init__(self, config: EventBusConfig | None = None) -> None:
        super().__init__(config)
        self._queues: dict[str, asyncio.Queue] = {}
        self._callbacks: dict[str, Callable] = {}  # sub_id -> callback
        self._topic_subs: dict[str, set[str]] = defaultdict(set)  # topic -> set of sub_ids
        self._sub_topics: dict[str, str] = {}  # sub_id -> topic
        self._dispatch_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize the in-memory bus (no-op for memory backend)."""
        self._running = True
        self.log.info("In-memory event bus connected")

    async def disconnect(self) -> None:
        """Shut down the in-memory bus, cancelling all dispatch tasks."""
        self._running = False
        for task in self._dispatch_tasks.values():
            task.cancel()
        self._dispatch_tasks.clear()
        self._queues.clear()
        self._callbacks.clear()
        self._topic_subs.clear()
        self._sub_topics.clear()
        self.log.info("In-memory event bus disconnected")

    async def publish(self, envelope: EventEnvelope) -> bool:
        """Publish an event to all matching subscribers.

        Args:
            envelope: Event envelope to publish

        Returns:
            True if at least one subscriber received the event
        """
        if not self._running:
            self.log.warning("Cannot publish: event bus not running")
            return False

        delivered = False
        topic = envelope.topic

        async with self._lock:
            matching_subs = set()
            # Exact match
            if topic in self._topic_subs:
                matching_subs.update(self._topic_subs[topic])
            # Wildcard match
            for pattern, subs in self._topic_subs.items():
                if self._topic_matches(pattern, topic):
                    matching_subs.update(subs)

        for sub_id in matching_subs:
            if sub_id in self._queues:
                try:
                    await self._queues[sub_id].put(envelope)
                    delivered = True
                except Exception as e:
                    self.log.error("Failed to deliver event to %s: %s", sub_id, e)

        return delivered

    async def subscribe(self, topic: str, callback: Callable[[EventEnvelope], Any]) -> str:
        """Subscribe to a topic with a callback.

        Args:
            topic: Topic pattern (supports '*' wildcards)
            callback: Async or sync callable for received events

        Returns:
            Unique subscription ID
        """
        sub_id = str(uuid.uuid4())

        async with self._lock:
            self._queues[sub_id] = asyncio.Queue(maxsize=self.config.batch_size * 10)
            self._callbacks[sub_id] = callback
            self._topic_subs[topic].add(sub_id)
            self._sub_topics[sub_id] = topic

        # Start dispatch task for this subscription
        task = asyncio.create_task(self._dispatch_loop(sub_id))
        self._dispatch_tasks[sub_id] = task

        self.log.debug("Subscribed %s to topic '%s'", sub_id, topic)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription.

        Args:
            subscription_id: ID from subscribe()
        """
        async with self._lock:
            if subscription_id in self._dispatch_tasks:
                self._dispatch_tasks[subscription_id].cancel()
                del self._dispatch_tasks[subscription_id]

            topic = self._sub_topics.pop(subscription_id, None)
            if topic and subscription_id in self._topic_subs.get(topic, set()):
                self._topic_subs[topic].discard(subscription_id)
                if not self._topic_subs[topic]:
                    del self._topic_subs[topic]

            self._callbacks.pop(subscription_id, None)
            self._queues.pop(subscription_id, None)

        self.log.debug("Unsubscribed %s", subscription_id)

    async def _dispatch_loop(self, sub_id: str) -> None:
        """Background task that dispatches events to a subscriber's callback."""
        try:
            while self._running and sub_id in self._queues:
                try:
                    envelope = await asyncio.wait_for(
                        self._queues[sub_id].get(), timeout=1.0
                    )
                    callback = self._callbacks.get(sub_id)
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(envelope)
                        else:
                            callback(envelope)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.log.error("Error in dispatch loop for %s: %s", sub_id, e)
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a subscription pattern.

        Supports '*' as a single-segment wildcard and '>' as a
        multi-segment wildcard (trailing).

        Args:
            pattern: Subscription pattern
            topic: Published topic

        Returns:
            True if the topic matches the pattern
        """
        if pattern == topic:
            return True

        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")

        for i, pp in enumerate(pattern_parts):
            if pp == ">":
                return True  # '>' matches everything after
            if pp == "*":
                if i >= len(topic_parts):
                    return False
                continue
            if i >= len(topic_parts) or pp != topic_parts[i]:
                return False

        return len(pattern_parts) == len(topic_parts)

    # --- Metrics ---

    @property
    def subscriber_count(self) -> int:
        """Total number of active subscriptions."""
        return len(self._callbacks)

    @property
    def topic_count(self) -> int:
        """Number of unique topics with subscribers."""
        return len(self._topic_subs)

    def queue_depth(self, subscription_id: str) -> int:
        """Get the pending event count for a subscription."""
        q = self._queues.get(subscription_id)
        return q.qsize() if q else 0
