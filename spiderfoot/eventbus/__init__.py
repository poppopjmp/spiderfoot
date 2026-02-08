"""
SpiderFoot Event Bus - Pluggable event routing for microservices architecture.

This package provides a pluggable event bus abstraction that replaces
in-memory queue.Queue usage with a configurable backend (memory, Redis Streams,
NATS JetStream, etc.), enabling modules to run as independent services.
"""

from spiderfoot.eventbus.base import EventBus, EventBusConfig
from spiderfoot.eventbus.memory import InMemoryEventBus
from spiderfoot.eventbus.factory import create_event_bus

__all__ = [
    'EventBus',
    'EventBusConfig',
    'InMemoryEventBus',
    'create_event_bus',
]
