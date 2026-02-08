"""
Event bus factory and bridge utilities.

Provides factory function to create the appropriate event bus backend
and a bridge class that adapts the async EventBus to the legacy
synchronous queue.Queue interface used by SpiderFootPlugin.
"""

import asyncio
import logging
import queue
import threading
from typing import Any, Callable, Dict, Optional

from spiderfoot.eventbus.base import EventBus, EventBusBackend, EventBusConfig, EventEnvelope


def create_event_bus(config: Optional[EventBusConfig] = None) -> EventBus:
    """Factory function to create an event bus instance.
    
    Args:
        config: Event bus configuration. If None, uses defaults (memory backend).
        
    Returns:
        An EventBus implementation instance
        
    Raises:
        ValueError: If the backend is not supported
        ImportError: If the required package for the backend is missing
    """
    if config is None:
        config = EventBusConfig()
    
    backend = config.backend
    
    if backend == EventBusBackend.MEMORY:
        from spiderfoot.eventbus.memory import InMemoryEventBus
        return InMemoryEventBus(config)
    
    elif backend == EventBusBackend.REDIS:
        from spiderfoot.eventbus.redis_bus import RedisEventBus
        return RedisEventBus(config)
    
    elif backend == EventBusBackend.NATS:
        from spiderfoot.eventbus.nats_bus import NatsEventBus
        return NatsEventBus(config)
    
    else:
        raise ValueError(f"Unsupported event bus backend: {backend}")


def create_event_bus_from_config(sf_config: dict) -> EventBus:
    """Create an event bus from SpiderFoot's configuration dict.
    
    Reads the event bus settings from the SpiderFoot config and creates
    the appropriate backend.
    
    Args:
        sf_config: SpiderFoot configuration dictionary
        
    Returns:
        Configured EventBus instance
    """
    backend_str = sf_config.get("_eventbus_backend", "memory").lower()
    
    try:
        backend = EventBusBackend(backend_str)
    except ValueError:
        logging.getLogger("spiderfoot.eventbus").warning(
            f"Unknown event bus backend '{backend_str}', falling back to memory"
        )
        backend = EventBusBackend.MEMORY
    
    config = EventBusConfig(
        backend=backend,
        redis_url=sf_config.get("_eventbus_redis_url", "redis://localhost:6379/0"),
        nats_url=sf_config.get("_eventbus_nats_url", "nats://localhost:4222"),
        nats_stream=sf_config.get("_eventbus_nats_stream", "spiderfoot"),
        channel_prefix=sf_config.get("_eventbus_prefix", "sf"),
        max_retry=int(sf_config.get("_eventbus_max_retry", 3)),
        retry_delay=float(sf_config.get("_eventbus_retry_delay", 1.0)),
        batch_size=int(sf_config.get("_eventbus_batch_size", 100)),
    )
    
    return create_event_bus(config)


class EventBusBridge:
    """Bridge between the async EventBus and legacy synchronous queue.Queue.
    
    This class adapts SpiderFootPlugin's existing incomingEventQueue/
    outgoingEventQueue interface to use the EventBus, allowing a gradual
    migration from in-memory queues to distributed messaging.
    
    Usage:
        bridge = EventBusBridge(event_bus, scan_id="abc123")
        bridge.start()
        
        # Legacy code can still use:
        bridge.incoming_queue.get()
        bridge.outgoing_queue.put(event)
        
        bridge.stop()
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        scan_id: str,
        module_name: str,
        watched_events: list,
        max_queue_size: int = 10000,
    ):
        self.event_bus = event_bus
        self.scan_id = scan_id
        self.module_name = module_name
        self.watched_events = watched_events
        self.log = logging.getLogger(f"spiderfoot.eventbus.bridge.{module_name}")
        
        # Legacy-compatible queues
        self.incoming_queue = queue.Queue(maxsize=max_queue_size)
        self.outgoing_queue = queue.Queue(maxsize=max_queue_size)
        
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._sub_ids: list = []
    
    def start(self) -> None:
        """Start the bridge, subscribing to watched events and forwarding outgoing events."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name=f"eventbus-bridge-{self.module_name}"
        )
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the bridge."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
    
    def _run_loop(self) -> None:
        """Run the async event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            self.log.error(f"Bridge loop error: {e}")
        finally:
            self._loop.close()
    
    async def _async_main(self) -> None:
        """Main async entry point for the bridge."""
        # Subscribe to all watched event types
        for event_type in self.watched_events:
            topic = self.event_bus._make_topic(event_type, self.scan_id)
            sub_id = await self.event_bus.subscribe(topic, self._on_event)
            self._sub_ids.append(sub_id)
        
        # Forward outgoing events
        while self._running:
            try:
                # Check for outgoing events to publish
                try:
                    event_data = self.outgoing_queue.get_nowait()
                    await self._publish_event(event_data)
                except queue.Empty:
                    pass
                
                await asyncio.sleep(0.01)  # Yield control
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Bridge error: {e}")
                await asyncio.sleep(0.1)
        
        # Cleanup subscriptions
        for sub_id in self._sub_ids:
            await self.event_bus.unsubscribe(sub_id)
    
    def _on_event(self, envelope: EventEnvelope) -> None:
        """Callback when an event arrives from the bus. Forwards to incoming_queue."""
        try:
            self.incoming_queue.put_nowait(envelope)
        except queue.Full:
            self.log.warning(f"Incoming queue full for {self.module_name}, dropping event")
    
    async def _publish_event(self, event_data: Any) -> None:
        """Publish an event from the outgoing queue to the event bus."""
        if hasattr(event_data, 'eventType'):
            # It's a SpiderFootEvent
            envelope = EventEnvelope(
                topic=self.event_bus._make_topic(event_data.eventType, self.scan_id),
                scan_id=self.scan_id,
                event_type=event_data.eventType,
                module=event_data.module,
                data=event_data.data,
                source_event_hash=getattr(event_data, 'sourceEventHash', 'ROOT') or 'ROOT',
                confidence=event_data.confidence,
                visibility=event_data.visibility,
                risk=event_data.risk,
                timestamp=event_data.generated,
            )
        elif isinstance(event_data, EventEnvelope):
            envelope = event_data
        else:
            self.log.warning(f"Unknown event type: {type(event_data)}")
            return
        
        await self.event_bus.publish(envelope)
