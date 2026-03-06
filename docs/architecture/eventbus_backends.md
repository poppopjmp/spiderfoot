# EventBus Backends

SpiderFoot v6 uses an EventBus to decouple event producers
(modules) from event consumers. Three backends are available,
each suited to different deployment topologies.

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Module A │────▶│ EventBus │────▶│ Module B │
│ produces │     │ backend  │     │ consumes │
└──────────┘     └──────────┘     └──────────┘
                      │
              ┌───────┼───────┐
              │       │       │
           Memory   Redis   NATS
```

## Backend Comparison

| Feature | Memory | Redis | NATS |
|---------|--------|-------|------|
| Persistence | None | Optional (AOF) | JetStream |
| Multi-process | No | Yes | Yes |
| Multi-node | No | Yes | Yes |
| Ordering | FIFO | FIFO per key | Subject-based |
| Latency | μs | ms | ms |
| Throughput | Very high | High | Very high |
| Setup | None | Redis server | NATS server |
| Best for | Dev/testing | Production single-node | Production cluster |

## Memory Backend

### When to Use

- Development and testing
- Single-process deployments
- CI/CD test pipelines

### Configuration

```python
# In config or environment
EVENTBUS_BACKEND = "memory"
```

### How It Works

Events are dispatched via in-process Python queues. Subscribers
are registered as callbacks and invoked synchronously (or via
`asyncio` for async modules).

```python
from spiderfoot.event.eventbus import EventBus

bus = EventBus(backend="memory")
bus.subscribe("DOMAIN_NAME", my_handler)
bus.publish("DOMAIN_NAME", "example.com", source=root_event)
```

### Limitations

- Events are lost on process restart
- Cannot distribute across multiple workers
- Memory grows with backlog size

## Redis Backend

### When to Use

- Production single-node deployments
- Docker Compose setups
- When you need event persistence
- When multiple Celery workers need event coordination

### Configuration

```python
EVENTBUS_BACKEND = "redis"
EVENTBUS_REDIS_URL = "redis://localhost:6379/1"
```

Or via environment:

```bash
export SF_EVENTBUS_BACKEND=redis
export SF_EVENTBUS_REDIS_URL=redis://redis:6379/1
```

### How It Works

Events are published to Redis Pub/Sub channels. Each event type
maps to a channel. Subscribers receive events via Redis
subscriptions.

For persistence, events are also written to Redis Streams,
allowing replay and consumer groups.

```python
# Redis channel mapping
# DOMAIN_NAME → sf:events:DOMAIN_NAME
# IP_ADDRESS  → sf:events:IP_ADDRESS
```

### Consumer Groups

Multiple workers can form a consumer group, ensuring each event
is processed exactly once:

```python
bus = EventBus(
    backend="redis",
    redis_url="redis://localhost:6379/1",
    consumer_group="scan-workers",
)
```

### Monitoring

Check Redis event backlog:

```bash
redis-cli XLEN sf:events:DOMAIN_NAME
redis-cli XINFO GROUPS sf:events:DOMAIN_NAME
```

## NATS Backend

### When to Use

- Multi-node production clusters
- High-throughput scan pipelines
- When you need JetStream persistence
- Kubernetes deployments with multiple pods

### Configuration

```python
EVENTBUS_BACKEND = "nats"
EVENTBUS_NATS_URL = "nats://localhost:4222"
```

### How It Works

Events are published to NATS subjects. Subject hierarchy follows:

```
sf.events.DOMAIN_NAME
sf.events.IP_ADDRESS
sf.events.VULNERABILITY_CVE_CRITICAL
```

Wildcard subscriptions are supported:

```python
# Subscribe to all vulnerability events
bus.subscribe("VULNERABILITY_*", vuln_handler)

# Subscribe to all events
bus.subscribe("*", audit_logger)
```

### JetStream Persistence

For durable event storage with replay:

```python
bus = EventBus(
    backend="nats",
    nats_url="nats://localhost:4222",
    jetstream=True,
    stream_name="sf-events",
)
```

### Clustering

NATS supports multi-node clustering natively:

```bash
# Node 1
nats-server --cluster nats://0.0.0.0:6222 --routes nats://node2:6222

# Node 2
nats-server --cluster nats://0.0.0.0:6222 --routes nats://node1:6222
```

SpiderFoot workers on any node will receive events from all nodes.

## Choosing a Backend

### Decision Tree

```
Start
 │
 ├─ Development/Testing?
 │   └─ Use Memory
 │
 ├─ Single server?
 │   └─ Use Redis
 │
 └─ Multi-node cluster?
     └─ Use NATS
```

### Migration

Switching backends requires only a configuration change. No code
changes are needed in modules because the EventBus API is
identical across backends.

```python
# Before: Memory
EVENTBUS_BACKEND = "memory"

# After: Redis (just change config, restart)
EVENTBUS_BACKEND = "redis"
EVENTBUS_REDIS_URL = "redis://localhost:6379/1"
```

## Custom Backend

To implement a custom backend:

```python
from spiderfoot.event.eventbus import EventBusBackend

class MyBackend(EventBusBackend):
    def publish(self, event_type: str, data: str,
                source: Any = None) -> None:
        # Your implementation
        pass

    def subscribe(self, event_type: str,
                  handler: Callable) -> None:
        # Your implementation
        pass

    def unsubscribe(self, event_type: str,
                    handler: Callable) -> None:
        # Your implementation
        pass
```

Register it:

```python
from spiderfoot.event.eventbus import EventBus
EventBus.register_backend("mybackend", MyBackend)
```

---

*SpiderFoot v6 — EventBus Backends Documentation*
