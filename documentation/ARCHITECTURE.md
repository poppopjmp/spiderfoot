# SpiderFoot Architecture Guide

## Overview

SpiderFoot v5.21+ implements a modular microservices architecture that can run
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

## Version History (v5.4.0 – v5.21.0)

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
| 5.10.1 | Architecture docs + README overhaul |
| 5.10.2 | K8s health checks (liveness/readiness/startup) |
| 5.11.0 | Modern CLI with subcommands |
| 5.11.1 | Auth middleware (JWT/API-key/Basic + RBAC) |
| 5.12.0 | Export Service (JSON/CSV/STIX/SARIF) |
| 5.12.1 | Module dependency graph + visualization |
| 5.12.2 | Event schema validation (70+ schemas) |
| 5.13.0 | WebSocket real-time event streaming |
| 5.13.1 | Scan profiles/templates (10 built-in) |
| 5.13.2 | Module hot-reload |
| 5.14.0 | Retry/recovery framework + dead-letter queue |
| 5.15.0 | Kubernetes Helm chart |
| 5.15.1 | Plugin marketplace registry |
| 5.15.2 | Rate limiter service (token-bucket/sliding-window) |
| 5.16.0 | CI/CD pipelines (4 GitHub Actions workflows) |
| 5.16.1 | Notification service (Slack/Webhook/Email) |
| 5.16.2 | Audit logging (immutable trail) |
| 5.17.0 | Scan diff/comparison |
| 5.17.1 | Data retention policies |
| 5.17.2 | OpenAPI 3.1 spec generator |
| 5.18.0 | Plugin testing framework |
| 5.18.1 | Distributed scan coordinator |
| 5.18.2 | Performance benchmarking suite |
| 5.19.0 | Secret management (encrypted file backend) |
| 5.19.1 | API versioning framework |
| 5.19.2 | Error telemetry (fingerprinting + alerting) |
| 5.20.0 | Scan queue with backpressure |
| 5.20.1 | Module dependency resolver |
| 5.21.0 | Database migration framework |
| 5.22.0 | Unified structured logging (JSON + correlation) |
| 5.22.1 | Vector.dev pipeline bootstrap + health checks |
| 5.22.2 | LLM Report Preprocessor (chunk / summarize) |
| 5.22.3 | Context window / token budget manager |
| 5.22.4 | OpenAI-compatible LLM client |
| 5.22.5 | Report generator pipeline orchestrator |
| 5.22.6 | Multi-format report renderer (PDF/HTML/MD/JSON) |
| 5.22.7 | Report REST API |
| 5.22.8 | Report storage engine (SQLite + LRU) |
| 5.22.9 | Module Registry (discovery, dependency, categories) |
| 5.23.0 | EventBus Hardening (DLQ, circuit breaker, retry) |
| 5.23.1 | Wire ReportStore into API layer |
| 5.23.2 | Typed AppConfig (11 dataclass sections, validation) |
| 5.23.3 | Health Check API (7 endpoints, 6 subsystem probes) |
| 5.23.4 | Scan Progress API (SSE streaming) |
| 5.23.5 | Task Queue (ThreadPool, callbacks, state machine) |
| 5.23.6 | Webhook/Notification System (HMAC, retries) |
| 5.23.7 | Request Tracing Middleware (X-Request-ID, timing) |
| 5.23.8 | Event Relay + WebSocket rewrite (push, not polling) |
| 5.23.9 | Config API Modernization (AppConfig wired into API) |
| 5.24.0 | Scan Event Bridge (live scanner events → WebSocket) |
| 5.25.0 | Module Dependency Resolution (registry → scanner wiring) |
| 5.26.0 | Database Repository Pattern (Scan/Event/Config repos) |
| 5.27.0 | API Rate Limiting Middleware (per-tier, per-client) |
| 5.28.0 | API Pagination Helpers (PaginationParams, PaginatedResponse) |

### Additional Services (v5.10.1 – v5.21.0)

#### Auth Middleware (`spiderfoot/auth.py`)
JWT, API key, and Basic authentication with role-based access control
(ADMIN, ANALYST, VIEWER, API roles). Pluggable into any ASGI/WSGI app.

#### Export Service (`spiderfoot/export_service.py`)
Multi-format scan result export: JSON, CSV, STIX 2.1 bundles, and
SARIF for integration with CI/CD security tooling.

#### WebSocket Service (`spiderfoot/websocket_service.py`)
Real-time scan event streaming over WebSocket with channel-based
subscriptions per scan, module, or event type.

#### Notification Service (`spiderfoot/notification_service.py`)
Multi-channel alerting with wildcard topic subscriptions, supporting
Slack webhooks, generic webhooks, SMTP email, and log output.

#### Secret Manager (`spiderfoot/secret_manager.py`)
Secure API key and credential storage with four backends: in-memory,
environment variables, plain JSON file, and encrypted file (PBKDF2 + XOR).
Includes rotation tracking, access auditing, and config injection.

#### Error Telemetry (`spiderfoot/error_telemetry.py`)
Centralised error capture with fingerprint-based deduplication,
automatic classification (network/auth/parse/timeout/etc.), sliding-window
rate tracking, and configurable alert thresholds with callbacks.

#### Scan Queue (`spiderfoot/scan_queue.py`)
Bounded priority queue (HIGH/NORMAL/LOW) with backpressure support.
Three overflow strategies (BLOCK/REJECT/DROP_OLDEST), batch dequeue,
retry tracking with dead-letter queue.

#### Module Resolver (`spiderfoot/module_resolver.py`)
Runtime dependency resolution for modules.  Given desired output event
types, walks backwards through the event dependency chain to compute the
minimal module set and topological load order.

#### Database Migration (`spiderfoot/db_migrate.py`)
Version-controlled schema evolution with numbered migration files,
upgrade/downgrade functions, dry-run mode, and checksum validation.
Supports SQLite and PostgreSQL dialects.

### Module Loading & Dependency Resolution (v5.25.0)

#### Module Loader (`spiderfoot/module_loader.py`)
Registry-driven module loading adapter that replaces the scanner’s
legacy `__import__` loop with `ModuleRegistry` for discovery/instantiation
and `ModuleGraph` for topological dependency ordering. Features:

- **Registry-first loading** with automatic legacy fallback
- **Topological execution order** via Kahn’s algorithm (replaces `_priority` sort)
- **Minimal-set pruning** — when desired output types are specified,
  only modules in the dependency chain are loaded
- **Cycle detection** with warnings (cycles don’t break execution)
- **LoadResult** dataclass with detailed statistics: loaded/failed/skipped
  counts, ordering method, pruning info, and timing
- **Global singleton** with thread-safe `init_module_loader()` /
  `get_module_loader()` / `reset_module_loader()`
- Wired into scanner via `service_integration._wire_module_loader()`
### Database Repository Pattern (v5.26.0)

#### Repositories (`spiderfoot/db/repositories/`)
Clean abstraction over `SpiderFootDb` using the Repository Pattern.
Replaces 20+ direct `SpiderFootDb(config)` instantiations across API
routers with injectable, testable repository instances.

- **AbstractRepository** — Base class with context-manager lifecycle,
  `dbh` property, `is_connected`, `close()`, `__enter__`/`__exit__`
- **ScanRepository** — Scan CRUD: `create_scan()`, `get_scan()`,
  `list_scans()`, `update_status()`, `delete_scan()`, config, logs,
  errors. Includes `ScanRecord` dataclass with `from_row()`/`to_dict()`
- **EventRepository** — Event/result operations: `store_event()`,
  `get_results()`, `get_unique_results()`, `get_result_summary()`,
  `search()`, element sources/children (direct + recursive),
  false-positive management, batch log events
- **ConfigRepository** — Global config: `set_config()`, `get_config()`,
  `clear_config()`
- **RepositoryFactory** — Creates repos with shared or per-request DB
  handles. Thread-safe singleton via `init_repository_factory()` /
  `get_repository_factory()` / `reset_repository_factory()`
- **FastAPI Depends providers** — `get_scan_repository()`,
  `get_event_repository()`, `get_config_repository()` in
  `api/dependencies.py` with automatic lifecycle management
- Wired into scanner via `service_integration._wire_repository_factory()`

### API Rate Limiting (v5.27.0)

#### Rate Limit Middleware (`spiderfoot/api/rate_limit_middleware.py`)
Starlette/FastAPI middleware bridging the existing `RateLimiterService`
into the API layer. Every incoming request is checked against per-tier
rate limits before reaching the router.

- **Per-client identity** extraction from API key, `X-Forwarded-For`, or direct IP
- **Route-tier mapping** — `/api/scans` → scan tier, `/api/data` → data tier, etc.
- **429 Too Many Requests** with `Retry-After` header on limit exceeded
- **X-RateLimit-*** response headers (Limit, Remaining, Reset) on every response
- **Exempt paths** for health checks, docs, OpenAPI spec
- **Per-client buckets** — different API keys/IPs have independent limits
- **RateLimitStats** with tier-level and top-offender tracking
- **`install_rate_limiting(app, config)`** wiring function
- Installed in `api/main.py` after request tracing middleware

### API Pagination (v5.28.0)

#### Pagination Helpers (`spiderfoot/api/pagination.py`)
Standardized pagination across all API list endpoints with consistent
request parameters and response envelopes.

- **PaginationParams** — FastAPI `Depends()`-compatible query extractor
  supporting page-based (`page`/`page_size`) and offset-based
  (`offset`/`limit`) modes with automatic mapping between them
- **PaginatedResponse** — Standardized envelope: `items`, `total`,
  `page`, `page_size`, `pages`, `has_next`, `has_previous`
- **`paginate()`** — In-memory slicing with optional sort support
- **`paginate_query()`** — For pre-sliced DB results with total count
- **Sort helpers** — `dict_sort_key()`, `attr_sort_key()` for common patterns
- **RFC 8288 Link headers** — `generate_link_header()` for `next`/`prev`/
  `first`/`last` navigation
- **`make_params()`** — Convenience constructor for programmatic/test use
### Real-Time Event Infrastructure (v5.22.0 – v5.24.0)

#### Event Relay (`spiderfoot/event_relay.py`)
Central fan-out hub bridging the EventBus to WebSocket/SSE consumers.
Per-scan consumer queues with bounded overflow (drop-oldest policy),
EventBus subscription management, and lifecycle helpers for
`scan_started` / `scan_completed` / `status_update` events.

#### Scan Event Bridge (`spiderfoot/scan_event_bridge.py`)
Lightweight synchronous adapter that sits in the scanner's
`waitForThreads()` dispatch loop. Forwards each `SpiderFootEvent`
to the EventRelay for real-time WebSocket delivery. Features:
configurable per-event-type throttling, large-data truncation,
per-scan statistics, and a bridge registry for lifecycle management.

#### Request Tracing (`spiderfoot/request_tracing.py`)
Starlette middleware that generates/echoes `X-Request-ID` headers,
sets `contextvars` for request context, and logs request start/end
with timing. Warns on slow requests exceeding a configurable threshold.

#### Webhook Dispatcher (`spiderfoot/webhook_dispatcher.py`)
Outbound HTTP notification delivery with HMAC-SHA256 signing
(`X-SpiderFoot-Signature`), exponential backoff retries, delivery
history (bounded deque), and stats. Uses `httpx` with `urllib` fallback.

#### Notification Manager (`spiderfoot/notification_manager.py`)
Webhook CRUD operations, event routing to matching/enabled webhooks,
fire-and-forget async delivery, webhook testing, and integration
with the Task Queue and Alert Engine for automated notifications.

#### Task Queue (`spiderfoot/task_queue.py`)
`ThreadPoolExecutor`-backed task execution with `TaskRecord` state
machine (PENDING → RUNNING → COMPLETED/FAILED/CANCELLED), progress
tracking, completion callbacks, and a singleton task manager.

#### Typed AppConfig (`spiderfoot/app_config.py`)
11-section typed dataclass configuration replacing the legacy flat
dict. Sections: Core, Network, Database, Web, API, Cache, EventBus,
Vector, Worker, Redis, Elasticsearch. Features: `from_dict()` /
`to_dict()` round-trip, `apply_env_overrides()` for SF_* variables,
20+ validation rules, and merge semantics for layered overrides.
