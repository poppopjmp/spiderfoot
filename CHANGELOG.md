# Changelog

All notable changes to SpiderFoot are documented in this file.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [5.21.1] — Documentation Update

### Changed
- README.md: Updated version badge to 5.21.0, expanded service table to 40+ entries
- ARCHITECTURE.md: Complete version history v5.4.0–v5.21.0 (48 entries), new service descriptions

## [5.21.0] — Database Migration Framework

### Added
- `spiderfoot/db_migrate.py` — Version-controlled schema evolution
  - Sequential numbered migration files with `upgrade()`/`downgrade()`
  - Migration tracking table (`_sf_migrations`) with checksums
  - Dry-run mode, scaffold generation, checksum validation
  - SQLite and PostgreSQL dialect support
  - Migration event callbacks

## [5.20.1] — Module Dependency Resolver

### Added
- `spiderfoot/module_resolver.py` — Runtime module load-order resolution
  - `ModuleDescriptor` with watched/produced/required/optional event interfaces
  - Backward-walking resolution from target events to minimal module set
  - Topological sort (Kahn's algorithm) with cycle detection
  - Dependency satisfaction checking and diagnostics
  - Automatic module directory scanning

## [5.20.0] — Scan Queue with Backpressure

### Added
- `spiderfoot/scan_queue.py` — Bounded priority work queue
  - Three priority lanes: HIGH / NORMAL / LOW with fair-share dequeue
  - Backpressure actions: BLOCK, REJECT, DROP_OLDEST
  - Pressure monitoring (0.0–1.0) with level transition callbacks
  - Batch dequeue, requeue with retry tracking
  - Dead-letter queue for permanently failed items

## [5.19.2] — Error Telemetry

### Added
- `spiderfoot/error_telemetry.py` — Centralised error capture and analysis
  - Full context capture (exception, traceback, module, scan, event type)
  - Fingerprint-based error grouping and deduplication
  - Auto-classification (TRANSIENT_NETWORK, AUTH, DATA_PARSE, TIMEOUT, etc.)
  - Sliding-window error rate tracking (global and per-module)
  - Ring buffer of recent errors with filtered queries
  - Alert rules with configurable thresholds and callbacks

## [5.19.1] — API Versioning Framework

### Added
- `spiderfoot/api_versioning.py` — API version lifecycle management
  - `VersionStrategy`: URL_PREFIX, HEADER, QUERY, ACCEPT negotiation
  - `APIVersion` lifecycle: BETA → CURRENT → DEPRECATED → SUNSET
  - `VersionedRoute` management with cross-version route copying
  - Response transforms between versions
  - Deprecation headers (Sunset, Link successor-version)
  - Compatibility checking

## [5.19.0] — Secret Management

### Added
- `spiderfoot/secret_manager.py` — Secure credential management
  - Four backends: Memory, Environment, File (JSON), Encrypted File (PBKDF2+XOR)
  - Rotation tracking with configurable rotation periods
  - Access auditing with bounded log
  - Redaction of secret values in text output
  - Config injection for module API keys

## [5.18.2] — Performance Benchmarking

### Added
- `spiderfoot/benchmark.py` — Performance benchmarking suite
  - `BenchmarkResult` with ops/sec, p50/p95/p99 latencies, stdev
  - 7 built-in benchmarks: EventBus, Cache, RateLimiter, WorkerPool, Serialization, Threading, Hash
  - GC-disabled high-precision timing
  - `BenchmarkSuite` composable runner with JSON report output

## [5.18.1] — Distributed Scan Coordinator

### Added
- `spiderfoot/scan_coordinator.py` — Multi-node scan distribution
  - `ScannerNode` with capacity tracking, tags, heartbeat monitoring
  - 4 distribution strategies: LEAST_LOADED, ROUND_ROBIN, HASH_BASED, RANDOM
  - Tag-based node filtering
  - Automatic failover with work reassignment
  - Priority queue with timeout detection

## [5.18.0] — Plugin Testing Framework

### Added
- `spiderfoot/plugin_test.py` — Drop-in test harness for modules
  - `PluginTestHarness` with factory methods `for_module()` / `for_class()`
  - `FakeSpiderFoot` mock facade with real helper implementations
  - `EventCapture` with rich query API (of_type, find, has, count)
  - HTTP/DNS response mocking helpers
  - Assertion helpers (assert_produced, assert_not_produced, no_errors)

## [5.17.2] — OpenAPI Specification Generator

### Added
- `spiderfoot/openapi_spec.py` — Programmatic OpenAPI 3.1 spec
  - All REST API endpoints (scans, workspaces, data, config, correlations, etc.)
  - Component schemas, security schemes, reusable parameters
  - JSON/YAML output

## [5.17.1] — Data Retention Policies

### Added
- `spiderfoot/data_retention.py` — Automated data lifecycle management
  - Configurable retention rules with age/size/date criteria
  - Preview (dry-run) and enforce modes
  - `FileResourceAdapter` for file-based retention
  - Retention history tracking and statistics

## [5.17.0] — Scan Diff/Comparison

### Added
- `spiderfoot/scan_diff.py` — Scan result comparison
  - SHA-256 fingerprinted `Finding` objects
  - `ScanSnapshot` with import from event lists
  - `DiffResult` with added/removed/changed/unchanged findings
  - Set-based key comparison with content fingerprinting

## [5.16.2] — Audit Logging

### Added
- `spiderfoot/audit_log.py` — Immutable audit trail
  - 9 audit categories (AUTH, CONFIG, SCAN, DATA, MODULE, SYSTEM, EXPORT, API, ADMIN)
  - Multi-backend writes (Memory, File)
  - Audit hooks and convenience methods

## [5.16.1] — Notification Service

### Added
- `spiderfoot/notification_service.py` — Multi-channel notifications
  - 4 channels: Slack, Webhook, Email (SMTP), Log
  - Wildcard topic subscriptions
  - EventBus bridge for auto-trigger
  - Sync/async dispatch with stats

## [5.16.0] — CI/CD Pipeline Definitions

### Added
- `.github/workflows/ci.yml` — Lint + test matrix (Python 3.9–3.12)
- `.github/workflows/docker.yml` — Multi-stage Docker build + Trivy scan
- `.github/workflows/helm.yml` — Helm chart lint + OCI push
- `.github/workflows/release.yml` — Auto GitHub releases with changelog

## [5.15.2] — Rate Limiter Service

### Added
- `spiderfoot/rate_limiter.py` — Pluggable rate limiting
  - 3 algorithms: TOKEN_BUCKET, SLIDING_WINDOW, FIXED_WINDOW
  - Per-key rate limits with configurable burst
  - Rate limit headers (X-RateLimit-*)

## [5.15.1] — Plugin Marketplace Registry

### Added
- `spiderfoot/plugin_registry.py` — Module discovery and management
  - `PluginManifest` with rich metadata
  - Install from file/URL, uninstall, enable/disable/pin
  - Auto-scan modules directory, state persistence

## [5.15.0] — Kubernetes Helm Chart

### Added
- `helm/spiderfoot/` — Production K8s deployment
  - Chart.yaml, values.yaml, 6 deployment/service templates
  - Ingress, ServiceAccount, PVC, Secrets, HPA
  - PostgreSQL + Redis sub-charts

## [5.14.0] — Retry/Recovery Framework

### Added
- `spiderfoot/retry.py` — Configurable retry with backoff
  - Strategies: FIXED, EXPONENTIAL, LINEAR, NONE
  - Dead-letter queue for permanently failed operations
  - `@retry` decorator

## [5.13.2] — Module Hot-Reload

### Added
- `spiderfoot/hot_reload.py` — File change detection with syntax validation

## [5.13.1] — Scan Profiles/Templates

### Added
- `spiderfoot/scan_profile.py` — 10 built-in scan profiles
  - quick-recon, full-footprint, passive-only, etc.
  - ProfileManager with CRUD + JSON import/export

## [5.13.0] — WebSocket Event Streaming

### Added
- `spiderfoot/websocket_service.py` — Real-time scan events via WebSocket
  - Channel-based subscriptions per scan/module/event type
  - FastAPI WebSocket router integration

## [5.12.2] — Event Schema Validation *(removed in v5.33.0 — dead code)*

### Added *(subsequently deleted)*
- ~~`spiderfoot/event_schema.py` — Declarative event type schemas~~
  - 15 `DataFormat` validators (IPV4, DOMAIN, EMAIL, URL, etc.)
  - 70+ core event type schemas
  - `EventSchemaRegistry` singleton

## [5.12.1] — Module Dependency Graph

### Added
- `spiderfoot/module_graph.py` — Directed graph of module event relationships
  - Topological ordering, cycle detection
  - BFS output resolution
  - Mermaid/DOT export

## [5.12.0] — Export Service

### Added
- `spiderfoot/export_service.py` — Multi-format exporter (JSON/CSV/STIX/SARIF)

## [5.11.1] — Auth Middleware

### Added
- `spiderfoot/auth.py` — JWT/API-key/Basic authentication with RBAC
  - Roles: ADMIN, ANALYST, VIEWER, API
  - ASGI/WSGI integration

## [5.11.0] — Modern CLI

### Added
- `spiderfoot/cli_service.py` — argparse-based CLI (version, status, metrics, config, scan, correlate, modules)

## [5.10.2] — Health Checks

### Added
- `spiderfoot/health.py` — K8s-compatible liveness/readiness/startup probes

## [5.10.1] — Documentation

### Changed
- README.md and ARCHITECTURE.md initial comprehensive documentation

## [5.10.0] — Module Migration

### Added
- `modules/sfp_ipapico_modern.py`, `modules/sfp_ipinfo_modern.py` — Migration examples
- `documentation/MODULE_MIGRATION_GUIDE.md` — 6-step migration guide

## [5.9.2] — Correlation Service

### Added
- `spiderfoot/correlation_service.py` — Standalone correlation engine with EventBus triggers

## [5.9.1] — API Gateway

### Added
- `spiderfoot/api_gateway.py` — Circuit breaker, rate limiting, dual-mode routing

## [5.9.0] — gRPC Interfaces

### Added
- `proto/spiderfoot.proto` — Protobuf service definitions
- `spiderfoot/grpc_service.py` — gRPC/HTTP dual-mode RPC

## [5.8.2] — ConfigService

### Added
- `spiderfoot/config_service.py` — 40+ env-var mappings, validation, hot-reload

## [5.8.1] — Service Integration Wiring

### Added
- `spiderfoot/service_integration.py` — Wires services into scan engine

## [5.8.0] — SpiderFootModernPlugin

### Added
- `spiderfoot/modern_plugin.py` — Service-aware plugin base class

## [5.7.1] — Prometheus Metrics

### Added
- `spiderfoot/metrics.py` — Counter/Gauge/Histogram, 18 pre-defined metrics

## [5.7.0] — Docker Microservices

### Added
- `docker/` — Dockerfile.base/scanner/api/webui, docker-compose-microservices.yml
- `spiderfoot/service_runner.py` — Unified entry point for microservices

## [5.6.2] — ScanScheduler

### Added
- `spiderfoot/scan_scheduler.py` — Priority-queue scan lifecycle management

## [5.6.1] — WorkerPool

### Added
- `spiderfoot/worker_pool.py` — Thread/process pool for module execution

## [5.6.0] — ServiceRegistry

### Added
- `spiderfoot/service_registry.py` — Dependency injection container

## [5.5.3] — CacheService

### Added
- `spiderfoot/cache_service.py` — Memory/File/Redis caching

## [5.5.2] — DnsService

### Added
- `spiderfoot/dns_service.py` — DNS resolution with TTL cache

## [5.5.1] — HttpService

### Added
- `spiderfoot/http_service.py` — Connection-pooled HTTP client

## [5.5.0] — DataService

### Added
- `spiderfoot/data_service/` — DB abstraction layer

## [5.4.2] — Vector.dev Integration

### Added
- `spiderfoot/vector_sink.py` — Event/log/metric pipeline
- `config/vector.toml` — Vector.dev pipeline configuration

## [5.4.1] — Structured Logging

### Added
- `spiderfoot/structured_logging.py` — JSON structured logging

## [5.4.0] — EventBus

### Added
- `spiderfoot/eventbus/` — Pub/sub messaging (Memory, Redis Streams, NATS JetStream)
