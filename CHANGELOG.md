# Changelog

All notable changes to SpiderFoot are documented in this file.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [5.62.0] — Module Output Validation (Cycle 64)

### Added
- `spiderfoot/module_output_validator.py` — runtime validation of module event output
  - ModuleOutputValidator with warn/strict/off modes (SF_MODULE_OUTPUT_VALIDATION)
  - Checks emitted events against producedEvents() declarations
  - Per-module statistics tracking (total, valid, undeclared counts)
  - Thread-safe with singleton via get_output_validator()

### Changed
- `spiderfoot/plugin.py` — both notifyListeners() methods now call output validator (best-effort)

## [5.61.0] — API Request Audit Logging (Cycle 63)

### Added
- `spiderfoot/api/audit_middleware.py` — structured audit logging for all API requests
  - AuditLoggingMiddleware: method, path, status, duration_ms, client_ip, request_id
  - User identity extraction (service tokens, bearer, basic — redacted)
  - Configurable: SF_API_AUDIT_ENABLED, SF_API_AUDIT_BODY, SF_API_AUDIT_EXCLUDE
  - Severity-based log levels (info/warning/error by status code)

### Changed
- `spiderfoot/api/main.py` — audit logging middleware installed after error handlers

## [5.60.1] — Wire Service Auth into Clients (Cycle 62)

### Changed
- `spiderfoot/data_service/http_client.py` — ServiceTokenIssuer fallback auth
- `spiderfoot/webui/api_client.py` — ServiceTokenIssuer fallback auth
- `docker-compose-microservices.yml` — SF_SERVICE_SECRET/TOKEN/NAME for all services

## [5.60.0] — Inter-service Authentication (Cycle 61)

### Added
- `spiderfoot/service_auth.py` — service-to-service authentication
  - ServiceTokenIssuer: static token (SF_SERVICE_TOKEN) or HMAC (SF_SERVICE_SECRET)
  - HMAC tokens: `<service>:<timestamp>:<hmac_sha256>`, cached for 80% of TTL
  - ServiceTokenValidator with constant-time comparison, clock skew tolerance
  - generate_service_secret() utility

## [5.59.0] — Module Execution Timeout Guard (Cycle 60)

### Added
- `spiderfoot/module_timeout.py` — per-module timeout enforcement
  - ModuleTimeoutGuard with context manager timed() and decorator wrap()
  - Configurable via SF_MODULE_TIMEOUT (default 300s), SF_MODULE_TIMEOUT_HARD
  - Hard interrupt via ctypes.pythonapi.PyThreadState_SetAsyncExc (CPython)
  - Per-module overrides, timeout log (ring buffer 200), stats()

## [5.58.0] — Scan Lifecycle Event Hooks (Cycle 59)

### Added
- `spiderfoot/scan_hooks.py` — EventBus-integrated scan lifecycle notifications
  - 8 event types: CREATED, STARTED, COMPLETED, ABORTED, FAILED, DELETED, ARCHIVED, UNARCHIVED
  - ScanLifecycleHooks: EventBus publishing to `scan.lifecycle` topic + local listeners
  - Event history tracking, per-scan filtering, statistics

### Changed
- `spiderfoot/api/routers/scan.py` — hooks wired into create/delete/stop/archive/unarchive

## [5.57.0] — Config Source Tracing + Environment API (Cycle 58)

### Added
- `spiderfoot/api/routers/config.py` — two new endpoints:
  - `GET /config/sources` — provenance report for all config keys (filter by source)
  - `GET /config/environment` — active SF_* env overrides, unknown vars, deployment info

## [5.56.1] — Rich OpenAPI Metadata (Cycle 57)

### Changed
- `spiderfoot/api/main.py` — enhanced FastAPI initialization
  - Detailed API description (auth, versioning, error format sections)
  - MIT license_info
  - 13 openapi_tags with descriptions (health, scans, workspaces, data, etc.)

## [5.56.0] — Structured API Error Responses (Cycle 56)

### Added
- `spiderfoot/api/error_handlers.py` — consistent JSON error envelope
  - ErrorDetail/ErrorResponse Pydantic models
  - Handlers for HTTPException, RequestValidationError, unhandled Exception
  - Domain-specific error codes (SCAN_NOT_FOUND, MODULE_NOT_FOUND, etc.)
  - install_error_handlers(app) for easy wiring

### Changed
- `spiderfoot/api/main.py` — error handlers installed after middleware

## [5.55.0] — Wire Pydantic response_model on Scan Router (Cycle 55)

### Added
- `spiderfoot/api/schemas.py` — response envelope models
  - MessageResponse, ScanCreateResponse, ScanDeleteResponse, ScanStopResponse
  - ScanMetadataResponse, ScanNotesResponse, ScanRerunResponse, ScanCloneResponse
  - FalsePositiveResponse

### Changed
- `spiderfoot/api/routers/scan.py` — 15+ endpoints now use response_model=
  - Return values changed from raw dicts to Pydantic model instances

## [5.54.1] — Wire Startup/Shutdown into Entry Points (Cycle 54)

### Changed
- `sfapi.py` — runs StartupSequencer.wait_for_ready_sync() in microservice mode before uvicorn
- `sfapi.py` — installs ShutdownCoordinator signal handlers for SIGTERM/SIGINT
- `docker-entrypoint.sh` — auto-detects SF_SERVICE_ROLE from command arguments

## [5.54.0] — Graceful Shutdown Coordination (Cycle 53)

### Added
- `spiderfoot/graceful_shutdown.py` — priority-ordered shutdown with signal handling
  - ShutdownCoordinator with drain timeout (15s), force timeout (30s)
  - Priority-ordered handler registration (lower = first)
  - In-flight request tracking (track_request/release_request)
  - SIGTERM/SIGINT handlers with atexit fallback
  - Async handler support, singleton via get_shutdown_coordinator()

## [5.53.0] — Service Startup Sequencer (Cycle 52)

### Added
- `spiderfoot/startup_sequencer.py` — ordered dependency verification
  - DependencyProbe ABC with TcpProbe, HttpProbe, PostgresProbe, RedisProbe, NatsProbe
  - Auto-discovery of required probes by service role (api/scanner/webui)
  - Async wait_for_ready() with configurable retry/backoff (max 30 retries)
  - ProbeResult/StartupResult dataclasses with summary()

## [5.52.0] — Proto Schema Expansion (Cycle 51)

### Changed
- `proto/spiderfoot.proto` — expanded from ~290 to ~470 lines
  - 15 new DataService RPCs (SetScanStatus, metadata, notes, archive, batch events, etc.)
  - New CorrelationService (AnalyzeScan, ListRules, TestRule)
  - EventRecord expanded with visibility, risk, false_positive, source_data
  - 28 new message types

## [5.51.0] — ConfigService Microservice Enhancements (Cycle 50)

### Changed
- `spiderfoot/config_service.py` — config source tracing + 15 new env vars
  - Source tracking per key (default/file/env/runtime)
  - 15 new SF_* env vars for microservice configuration
  - New properties: is_microservice, service_role, service_name
  - discover_env_vars() flags unknown SF_* vars

## [5.50.0] — Module Interface Contracts (Cycle 49)

### Added
- `spiderfoot/module_contract.py` — typed module interface validation
  - SpiderFootModuleProtocol (runtime-checkable Protocol)
  - ModuleMeta Pydantic schema for meta dict validation
  - validate_module() / validate_module_batch() with diagnostics

### Changed
- `spiderfoot/module_registry.py` — non-blocking contract validation during discover()

## [5.49.0] — Pydantic Schemas for Service Boundaries (Cycle 48)

### Added
- `spiderfoot/api/schemas.py` — Pydantic v2 service boundary contracts
  - EventCreate/EventResponse with from_db_row() migration helper
  - ScanCreate/ScanResponse/ScanListResponse
  - ScanLogEntry/Create, ConfigEntry/Update
  - CorrelationResult/Summary, PaginationMeta/PaginatedResponse
  - ScanStatus enum (8 states)

## [5.48.0] — API Versioning with /api/v1/ Prefix (Cycle 47)

### Added
- `spiderfoot/api/versioning.py` — API versioning infrastructure
  - ApiVersionMiddleware (X-API-Version, Deprecation, Sunset, Link headers)
  - mount_versioned_routers() for dual-mount at /api/v1/ and /api/

### Changed
- `spiderfoot/api/main.py` — routes dual-mounted via versioning system
- `spiderfoot/api/routers/health.py` — added GET /version endpoint

## [5.47.0] — Per-Service Docker Isolation (Cycle 46)

### Changed
- `docker/Dockerfile.webui` — WebUI only on sf-frontend network
- `docker/Dockerfile.scanner` — scanner uses HTTP DataService
- `docker-compose-microservices.yml` — network isolation enforced

## [5.46.0] — WebUI API Proxy Layer (Cycle 45)

### Added
- `spiderfoot/webui/api_client.py` — HTTP client mimicking SpiderFootDb
- `spiderfoot/webui/db_provider.py` — dual-mode mixin (local or API proxy)

## [5.45.0] — Extract ScanMetadataService (Cycle 44)

### Added
- `spiderfoot/scan_metadata_service.py` — extracted from ScanServiceFacade

## [5.44.1] — Circuit Breaker for Remote DataService (Cycle 43)

### Added
- `spiderfoot/data_service/resilient.py` — DataServiceCircuitBreaker + ResilientDataService

## [5.44.0] — gRPC DataService Client (Cycle 42)

### Added
- `spiderfoot/data_service/grpc_client.py` — protobuf DataService backend

## [5.43.1] — DataService Health Check (Cycle 41)

### Changed
- `spiderfoot/api/routers/health.py` — added DataService probe

## [5.43.0] — HTTP DataService Client (Cycle 40)

### Added
- `spiderfoot/data_service/http_client.py` — REST DataService backend
- `spiderfoot/data_service/factory.py` — create_data_service() factory

## [5.42.0] — Domain Sub-Packages (Cycle 39)

### Changed
- Reorganized code into domain sub-packages for better organization

## [5.41.0] — Migrate ScanService Events to EventRepository (Cycle 38)

### Changed
- ScanService now uses EventRepository instead of raw database handles

## [5.40.0] — Framework-Agnostic Security (Cycle 37)

### Changed
- Security middleware decoupled from Flask, works with any ASGI/WSGI framework
- Flask dependency deprecated

## [5.39.0] — Replace Monkey-Patching with functools.wraps (Cycle 36)

### Changed
- Replaced all monkey-patching in decorators with proper functools.wraps

## [5.38.0] — Unified Scan State Mapping (Cycle 35)

### Added
- `spiderfoot/scan_state_map.py` — canonical scan state definitions

## [5.37.0] — Generate gRPC Stubs (Cycle 34)

### Changed
- Generated gRPC Python stubs from proto/spiderfoot.proto
- Wired stubs into grpc_service.py

## [5.36.0] — Add gRPC Dependencies (Cycle 33)

### Changed
- `requirements.txt` — added grpcio, grpcio-tools, protobuf

## [5.35.0] — Fix Silent Error Swallowing (Cycle 32)

### Fixed
- `spiderfoot/service_integration.py` — errors now properly logged instead of silently swallowed

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
