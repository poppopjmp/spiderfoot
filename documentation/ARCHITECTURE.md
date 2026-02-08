# SpiderFoot Architecture Guide

## Overview

SpiderFoot v5.10+ implements a modular microservices architecture that can run
in two modes:

- **Monolith mode**: All services run in a single process (default, backward-compatible)
- **Microservices mode**: Services run as separate containers behind an Nginx gateway

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Nginx Gateway (:80)                         │
│               Rate limiting · WebSocket · Reverse proxy            │
├──────────┬──────────────┬──────────────┬───────────────────────────┤
│ WebUI    │ REST API     │ API Gateway  │ Prometheus Metrics        │
│ :5001    │ :8001        │ /gateway/*   │ /metrics                  │
├──────────┴──────────────┴──────────────┴───────────────────────────┤
│                      Service Layer                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │ServiceReg. │ │ConfigSvc   │ │ Metrics    │ │ Structured │      │
│  │(DI Contain)│ │(env+file)  │ │(Prometheus)│ │  Logging   │      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
├───────────────────────────────────────────────────────────────────┤
│                     Core Services                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │HttpService │ │ DnsService │ │CacheService│ │DataService │      │
│  │(pooled HTTP│ │(DNS+cache) │ │(Mem/File/  │ │(SQLite/PG/ │      │
│  │ +proxy)    │ │            │ │  Redis)    │ │  gRPC)     │      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
├───────────────────────────────────────────────────────────────────┤
│                   Execution Layer                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │ WorkerPool │ │   Scan     │ │Correlation │ │ EventBus   │      │
│  │(Thread/Proc│ │ Scheduler  │ │  Service   │ │(Mem/Redis/ │      │
│  │  pool)     │ │(priority Q)│ │(auto+batch)│ │  NATS)     │      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
├───────────────────────────────────────────────────────────────────┤
│                    Data Pipeline                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                      │
│  │Vector.dev  │ │  gRPC/HTTP │ │ API Gateway│                      │
│  │ Sink       │ │  RPC Layer │ │ (circuit   │                      │
│  │(→ES/S3)    │ │  (fallback)│ │  breaker)  │                      │
│  └────────────┘ └────────────┘ └────────────┘                      │
├───────────────────────────────────────────────────────────────────┤
│                     Module Layer                                   │
│  ┌──────────────────────┐ ┌──────────────────────┐                 │
│  │ SpiderFootPlugin     │ │SpiderFootModernPlugin│                 │
│  │ (legacy, 200+        │ │(service-aware, new   │                 │
│  │  modules)            │ │ modules)             │                 │
│  └──────────────────────┘ └──────────────────────┘                 │
└───────────────────────────────────────────────────────────────────┘
```

## Service Descriptions

### EventBus (`spiderfoot/eventbus/`)

Abstracted publish/subscribe messaging with three backends:

- **Memory** (default): In-process `asyncio.Queue`-based, zero config
- **Redis Streams**: Consumer groups, at-least-once delivery
- **NATS JetStream**: High-throughput, durable messaging

Topics follow a dot-notation pattern: `scan.started`, `scan.completed`,
`module.event.new`, etc.

### DataService (`spiderfoot/data_service/`)

Database abstraction layer supporting:

- **Local**: Direct SQLite/PostgreSQL via `SpiderFootDb`
- **HTTP**: Remote REST API for microservices mode
- **gRPC**: High-performance binary protocol

Provides CRUD for scans, events, configs, and correlations.

### HttpService (`spiderfoot/http_service.py`)

Extracted HTTP client from the legacy `SpiderFoot` god object:

- Connection pooling
- SOCKS4/5 and HTTP proxy support
- Configurable timeouts and user-agents
- TLS certificate parsing
- Google/Bing API pagination helpers

### DnsService (`spiderfoot/dns_service.py`)

Extracted DNS resolver with built-in TTL cache:

- A/AAAA/MX/TXT/NS/PTR record types
- Wildcard detection
- Zone transfer checks
- Configurable resolvers

### CacheService (`spiderfoot/cache_service.py`)

Three-tier caching:

- **Memory**: LRU eviction, TTL-based expiry
- **File**: SHA-224 hashed filenames, persistent
- **Redis**: Distributed cache for microservices

### ConfigService (`spiderfoot/config_service.py`)

Centralized configuration management:

- 40+ environment variable mappings
- Type coercion (bool, int, float, str)
- Validation rules (min/max, choices, required)
- Hot-reload with watcher callbacks
- Snapshot isolation for per-scan configs

### ServiceRegistry (`spiderfoot/service_registry.py`)

Dependency injection container:

- Lazy factory pattern (services created on first access)
- Well-known service constants
- Thread-safe singleton
- `ServiceMixin` for convenient property access

### WorkerPool (`spiderfoot/worker_pool.py`)

Module execution infrastructure:

- Thread pool (default) or process pool strategies
- Per-module workers with event queues
- Health monitoring with automatic restart
- Graceful shutdown with drain

### ScanScheduler (`spiderfoot/scan_scheduler.py`)

Scan lifecycle management:

- Priority queue (CRITICAL > HIGH > NORMAL > LOW)
- Concurrent scan limiting
- Pause/resume/abort controls
- Timeout detection
- Progress tracking

### CorrelationService (`spiderfoot/correlation_service.py`)

Standalone correlation engine:

- Wraps the existing `RuleExecutor` pipeline
- EventBus subscription for auto-trigger on scan completion
- Async queue for batch processing
- Result caching and callbacks
- Prometheus metrics integration

### API Gateway (`spiderfoot/api_gateway.py`)

Unified request routing:

- Circuit breaker per downstream service
- Token-bucket rate limiting per client
- Monolith/microservices dual mode
- FastAPI router integration
- System status aggregation

### Metrics (`spiderfoot/metrics.py`)

Zero-dependency Prometheus-compatible instrumentation:

- Counter, Gauge, Histogram types
- Label support for dimensional metrics
- `/metrics` endpoint in Prometheus text format
- Pre-defined metrics for scans, events, HTTP, DNS, cache

### Vector.dev Sink (`spiderfoot/vector_sink.py`)

Data pipeline to external systems:

- Batched HTTP posting to Vector.dev
- Separate channels for events, logs, metrics
- Configurable transforms and routing
- Elasticsearch/S3/file sinks via Vector config

### gRPC/HTTP RPC (`spiderfoot/grpc_service.py`)

Inter-service communication:

- Protobuf service contracts (`proto/spiderfoot.proto`)
- JSON-over-HTTP fallback when gRPC unavailable
- ServiceDirectory for environment-based endpoint discovery
- Health checking

## Docker Microservices

The `docker/` directory contains production-ready Docker configuration:

| File | Purpose |
|---|---|
| `Dockerfile.base` | Multi-stage base image with Python deps |
| `Dockerfile.scanner` | Scanner service |
| `Dockerfile.api` | REST API service |
| `Dockerfile.webui` | Web UI service |
| `docker-compose-microservices.yml` | Full stack orchestration |
| `nginx-microservices.conf` | Reverse proxy with rate limiting |
| `config/vector.toml` | Vector.dev pipeline configuration |
| `env.example` | Environment variable reference |
| `build.sh` | Build all images |

### Networks

- **sf-frontend**: Nginx ↔ WebUI/API
- **sf-backend**: Services ↔ PostgreSQL
- **sf-events**: Services ↔ Redis/NATS EventBus

## Module System

### Legacy Modules (`SpiderFootPlugin`)

All 200+ existing modules continue to work unchanged. They use `self.sf`
(the SpiderFoot god object) for HTTP, DNS, and other operations.

### Modern Modules (`SpiderFootModernPlugin`)

New modules can extend `SpiderFootModernPlugin` to access services directly:

```python
from spiderfoot.modern_plugin import SpiderFootModernPlugin

class sfp_example(SpiderFootModernPlugin):
    def handleEvent(self, event):
        # Modern: uses HttpService with metrics
        res = self.fetch_url("https://api.example.com/lookup")

        # Cache results
        self.cache_put("key", data, ttl=3600)

        # DNS resolution via DnsService
        addrs = self.resolve_host(hostname)
```

See [MODULE_MIGRATION_GUIDE.md](MODULE_MIGRATION_GUIDE.md) for step-by-step
migration instructions.

## Version History (v5.4.0 – v5.10.0)

| Version | Change |
|---|---|
| 5.4.0 | EventBus abstraction (Memory/Redis/NATS) |
| 5.4.1 | Structured JSON logging |
| 5.4.2 | Vector.dev integration |
| 5.5.0 | DataService abstraction |
| 5.5.1 | HttpService extraction |
| 5.5.2 | DnsService extraction |
| 5.5.3 | CacheService (Memory/File/Redis) |
| 5.6.0 | ServiceRegistry + dependency injection |
| 5.6.1 | Module WorkerPool |
| 5.6.2 | ScanScheduler |
| 5.7.0 | Docker microservices decomposition |
| 5.7.1 | Prometheus metrics |
| 5.8.0 | SpiderFootModernPlugin base class |
| 5.8.1 | Service integration wiring |
| 5.8.2 | ConfigService with env overrides |
| 5.9.0 | gRPC service interfaces + protobuf |
| 5.9.1 | API Gateway with circuit breaker |
| 5.9.2 | Correlation Service (standalone) |
| 5.10.0 | Module migration samples + guide |
