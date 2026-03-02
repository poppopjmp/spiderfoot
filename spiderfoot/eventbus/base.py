"""
Abstract base class for the SpiderFoot Event Bus.

All event bus implementations must inherit from EventBus and implement
the required publish/subscribe/unsubscribe interface.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class EventBusBackend(str, Enum):
    """Supported event bus backends."""
    MEMORY = "memory"
    REDIS = "redis"
    NATS = "nats"


@dataclass
class EventBusConfig:
    """Configuration for the event bus.

    Attributes:
        backend: Which backend to use (memory, redis, nats)
        redis_url: Redis connection URL (for redis backend)
        nats_url: NATS connection URL (for nats backend)
        nats_stream: NATS JetStream stream name
        channel_prefix: Prefix for all channel/subject names
        max_retry: Maximum retry attempts for failed publishes
        retry_delay: Delay in seconds between retries
        batch_size: Maximum events to process in a single batch
        serializer: Serialization format ('json', 'msgpack')
    """
    backend: EventBusBackend = EventBusBackend.MEMORY
    redis_url: str = "redis://localhost:6379/0"
    nats_url: str = "nats://localhost:4222"
    nats_stream: str = "spiderfoot"
    channel_prefix: str = "sf"
    max_retry: int = 3
    retry_delay: float = 1.0
    batch_size: int = 100
    serializer: str = "json"


@dataclass
class EventEnvelope:
    """Envelope wrapping an event for transport over the bus.

    Attributes:
        topic: The event topic/channel
        scan_id: Scan instance ID
        event_type: SpiderFoot event type (e.g. 'URL_FORM', 'IP_ADDRESS')
        module: Source module name
        data: Event payload data
        source_event_hash: Hash of the parent event
        confidence: Confidence score 0-100
        visibility: Visibility score 0-100
        risk: Risk score 0-100
        timestamp: Event creation timestamp
        metadata: Additional metadata
    """
    topic: str
    scan_id: str
    event_type: str
    module: str
    data: Any
    source_event_hash: str = "ROOT"
    confidence: int = 100
    visibility: int = 100
    risk: int = 0
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class EventBus(ABC):
    """Abstract base class for event bus implementations.

    The EventBus provides a publish/subscribe interface for routing
    SpiderFoot events between modules, either in-process or across
    distributed services.
    """

    def __init__(self, config: EventBusConfig | None = None) -> None:
        """Initialize the EventBus."""
        self.config = config or EventBusConfig()
        self.log = logging.getLogger(f"spiderfoot.eventbus.{self.config.backend.value}")
        self._running = False
        self._subscribers: dict[str, list[Callable]] = {}

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the event bus backend.

        Raises:
            ConnectionError: If connection cannot be established
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the event bus backend."""
        ...

    @abstractmethod
    async def publish(self, envelope: EventEnvelope) -> bool:
        """Publish an event envelope to the bus.

        Args:
            envelope: The event envelope to publish

        Returns:
            True if the event was published successfully

        Raises:
            ConnectionError: If not connected to the backend
        """
        ...

    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable[[EventEnvelope], Any]) -> str:
        """Subscribe to events on a topic.

        Args:
            topic: Topic pattern to subscribe to (supports wildcards)
            callback: Async callable invoked for each received event

        Returns:
            Subscription ID for later unsubscription
        """
        ...

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from a topic.

        Args:
            subscription_id: ID returned by subscribe()
        """
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the event bus is currently connected."""
        return self._running

    def _make_topic(self, event_type: str, scan_id: str = "*") -> str:
        """Build a fully-qualified topic name.

        Args:
            event_type: SpiderFoot event type
            scan_id: Scan instance ID (use '*' for wildcard)

        Returns:
            Fully-qualified topic string
        """
        prefix = self.config.channel_prefix
        return f"{prefix}.{scan_id}.{event_type}"

    # --- Background event loop for sync wrappers ---
    _bg_loop: asyncio.AbstractEventLoop | None = None
    _bg_thread: "threading.Thread | None" = None
    _bg_lock: threading.Lock = threading.Lock()

    @classmethod
    def _get_bg_loop(cls) -> asyncio.AbstractEventLoop:
        """Return a persistent background event loop (created once, reused).

        This avoids spawning a new ThreadPoolExecutor on every sync call,
        which would cause thread exhaustion under load.
        """
        with cls._bg_lock:
            if cls._bg_loop is None or cls._bg_loop.is_closed():
                cls._bg_loop = asyncio.new_event_loop()

                def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
                    asyncio.set_event_loop(loop)
                    loop.run_forever()

                cls._bg_thread = threading.Thread(
                    target=_run_loop,
                    args=(cls._bg_loop,),
                    daemon=True,
                    name="eventbus-bg-loop",
                )
                cls._bg_thread.start()

        return cls._bg_loop

    # --- Synchronous convenience wrappers ---

    def publish_sync(self, envelope: EventEnvelope) -> bool:
        """Synchronous wrapper around publish() for legacy code.

        Uses a persistent background event loop instead of creating a new
        ThreadPoolExecutor on every call. For new code, prefer the async API.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Schedule on the shared background loop
            future = asyncio.run_coroutine_threadsafe(
                self.publish(envelope), self._get_bg_loop()
            )
            return future.result(timeout=10)
        else:
            return asyncio.run(self.publish(envelope))

    def subscribe_sync(self, topic: str, callback: Callable) -> str:
        """Synchronous wrapper around subscribe()."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.subscribe(topic, callback), self._get_bg_loop()
            )
            return future.result(timeout=10)
        else:
            return asyncio.run(self.subscribe(topic, callback))
