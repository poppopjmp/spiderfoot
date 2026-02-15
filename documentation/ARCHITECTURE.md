# SpiderFoot Architecture Guide

## Overview

SpiderFoot v5.8.0 implements a modular microservices architecture that can run
in two modes:

- **Monolith mode**: All services run in a single process (default, backward-compatible)
- **Microservices mode**: 21 containers behind a Traefik v3 reverse proxy with full observability, AI agents, Celery task processing, and React SPA frontend

## Service Topology (v5.8.0)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Traefik v3 Gateway (:443)                           │
│       Auto-TLS · Rate limiting · Reverse proxy · Path routing           │
├──────────────┬──────────────┬──────────────┬───────────────┬────────────┤
│ Frontend     │ REST API     │  Agents      │ Celery Flower │ Grafana    │
│ React SPA    │ :8001        │  :8100       │ :5555         │ :3000      │
├──────────────┴──────────────┴──────────────┴───────────────┴────────────┤
│                    Task Processing                                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                          │
│  │ Celery     │ │ Celery     │ │ Apache     │                          │
│  │ Worker     │ │ Beat       │ │ Tika :9998 │                          │
│  │ (async)    │ │ (scheduler)│ │ (document) │                          │
│  └────────────┘ └────────────┘ └────────────┘                          │
├───────────────────────────────────────────────────────────────────────┤
│                       Data Layer                                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐          │
│  │ PostgreSQL │ │   Redis    │ │  Qdrant    │ │   MinIO    │          │
│  │ :5432      │ │  :6379     │ │ :6333      │ │ :9000/9001 │          │
│  │ (Primary)  │ │ (EventBus, │ │ (Vector    │ │ (S3 Object │          │
│  │            │ │ Cache,     │ │  Search)   │ │  Storage)  │          │
│  │            │ │ Broker)    │ │            │ │            │          │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘          │
├───────────────────────────────────────────────────────────────────────┤
│                     LLM Gateway                                        │
│  ┌────────────┐                                                        │
│  │  LiteLLM   │ Multi-provider proxy (OpenAI, Anthropic, Ollama)       │
│  │  :4000     │ Cost tracking · Model routing · Redis cache            │
│  └────────────┘                                                        │
├───────────────────────────────────────────────────────────────────────┤
│                   Observability Pipeline                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐          │
│  │ Vector.dev │ │   Loki     │ │ Prometheus │ │   Jaeger   │          │
│  │ :8686      │ │  :3100     │ │  :9090     │ │  :16686    │          │
│  │ :4317/4318 │ │ (Log aggr) │ │ (Metrics)  │ │ (Tracing)  │          │
│  │ :9598      │ │            │ │            │ │            │          │
│  │ (Telemetry │ └────────────┘ └────────────┘ └────────────┘          │
│  │  pipeline) │ ┌────────────┐                                         │
│  └────────────┘ │  Grafana   │ Dashboards · Alerting · Data explorer   │
│                 │  :3000     │                                          │
│                 └────────────┘                                          │
├───────────────────────────────────────────────────────────────────────┤
│                   Sidecars & Infrastructure                             │
│  ┌────────────┐ ┌────────────┐ ┌─────────────────┐                     │
│  │ pg-backup  │ │ minio-init │ │ Docker Socket   │                     │
│  │ (cron)     │ │ (one-shot) │ │ Proxy (Traefik) │                     │
│  │ → MinIO    │ │            │ │                 │                     │
│  └────────────┘ └────────────┘ └─────────────────┘                     │
└───────────────────────────────────────────────────────────────────────┘
```

## Package Structure (v5.245.0+)

The `spiderfoot/` package is organized into **8 domain sub-packages**:

| Sub-package | Purpose | Key modules |
|---|---|---|
| `spiderfoot/config/` | Configuration management | `constants`, `app_config`, `config_schema` |
| `spiderfoot/events/` | Event types and processing | `event`, `event_relay`, `event_dedup`, `event_pipeline`, `event_taxonomy` |
| `spiderfoot/scan/` | Scan lifecycle and orchestration | `scan_state`, `scan_coordinator`, `scan_scheduler`, `scan_queue`, `scan_workflow` |
| `spiderfoot/plugins/` | Module loading and management | `plugin`, `modern_plugin`, `module_loader`, `module_registry`, `module_resolver` |
| `spiderfoot/security/` | Authentication, CSRF, middleware | `auth`, `csrf_protection`, `security_middleware`, `security_logging` |
| `spiderfoot/observability/` | Logging, metrics, auditing | `logger`, `metrics`, `structured_logging`, `audit_log`, `health` |
| `spiderfoot/services/` | External service integrations | `cache_service`, `dns_service`, `http_service`, `grpc_service`, `websocket_service` |
| `spiderfoot/reporting/` | Report generation and export | `report_generator`, `export_service`, `report_formatter`, `visualization_service` |
| `spiderfoot/agents/` | AI analysis agents (LLM-powered) | `base`, `finding_validator`, `credential_analyzer`, `text_summarizer`, `report_generator`, `document_analyzer`, `threat_intel`, `service` |
| `spiderfoot/enrichment/` | Document enrichment pipeline | `converter`, `extractor`, `pipeline`, `service` |
| `spiderfoot/user_input/` | User-defined input ingestion | `service` |

### Import Patterns

```python
# Preferred: import from subpackage init
from spiderfoot.events import SpiderFootEvent
from spiderfoot.plugins import SpiderFootPlugin
from spiderfoot.config import SF_DATA_TYPES

# Also valid: import from specific module
from spiderfoot.events.event import SpiderFootEvent
from spiderfoot.scan.scan_state import SpiderFootScanState

# Top-level re-exports still work
from spiderfoot import SpiderFootEvent, SpiderFootPlugin
```

> **Note (v5.245.0):** All backward-compatibility shim files in the
> `spiderfoot/` root were removed. Code that used old paths like
> `from spiderfoot.event import ...` or `from spiderfoot.plugin import ...`
> must update to the subpackage paths shown above.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Traefik v3 Gateway (:443)                        │
│            Auto-TLS · Rate limiting · Reverse proxy                │
├──────────┬──────────────┬──────────────┬──────────────┬────────────┤
│ Frontend │ REST API     │  Agents      │ Celery       │ Tika       │
│ React SPA│ :8001        │  :8100       │ Workers/Beat │ :9998      │
├──────────┴──────────────┴──────────────┴──────────────┴────────────┤
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
│                    LLM Gateway                                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐                      │
│  │  LiteLLM   │ │  AI Agents │ │ OTel       │                      │
│  │(multi-LLM  │ │ (6 agents) │ │ Tracing    │                      │
│  │  proxy)    │ │            │ │ (Vector→   │                      │
│  └────────────┘ └────────────┘ │  Jaeger)   │                      │
│                                 └────────────┘                      │
├───────────────────────────────────────────────────────────────────┤
│                    Data Pipeline                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │Vector.dev  │ │   Loki     │ │ Prometheus │ │  Grafana   │      │
│  │(logs/traces│ │ (log aggr) │ │ (metrics)  │ │(dashboards)│      │
│  │ /metrics)  │ │            │ │            │ │            │      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
├───────────────────────────────────────────────────────────────────┤
│                     Module Layer                                   │
│  ┌──────────────────────┐ ┌──────────────────────┐                 │
│  │ SpiderFootPlugin     │ │SpiderFootModernPlugin│                 │
│  │ (legacy, 283         │ │(service-aware, new   │                 │
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

### CacheService (`spiderfoot/services/cache_service.py`)

Three-tier caching:

- **Memory**: LRU eviction, TTL-based expiry
- **File**: SHA-224 hashed filenames, persistent
- **Redis**: Distributed cache for microservices

### ConfigService (`spiderfoot/services/config_service.py`)

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

### ScanScheduler (`spiderfoot/scan/scan_scheduler.py`)

Scan lifecycle management:

- Priority queue (CRITICAL > HIGH > NORMAL > LOW)
- Concurrent scan limiting
- Pause/resume/abort controls
- Timeout detection
- Progress tracking

### CorrelationService (`spiderfoot/services/correlation_service.py`)

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

### Metrics (`spiderfoot/observability/metrics.py`)

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

### gRPC/HTTP RPC (`spiderfoot/services/grpc_service.py`)

Inter-service communication:

- Protobuf service contracts (`proto/spiderfoot.proto`)
- JSON-over-HTTP fallback when gRPC unavailable
- ServiceDirectory for environment-based endpoint discovery
- Health checking

## Docker Microservices

The `docker-compose-microservices.yml` defines 21 containers:

| Container | Image | Purpose |
|---|---|---|
| sf-traefik | traefik:v3 | Reverse proxy + auto-TLS + routing (:443) |
| sf-docker-proxy | tecnativa/docker-socket-proxy | Secure Docker API access for Traefik |
| sf-frontend-ui | spiderfoot-frontend | React SPA served by Nginx (:80) |
| sf-api | spiderfoot-micro | REST API + GraphQL (:8001) |
| sf-agents | spiderfoot-micro | AI analysis agents — 6 agents (:8100) |
| sf-celery-worker | spiderfoot-micro | Celery distributed task workers |
| sf-celery-beat | spiderfoot-micro | Celery periodic task scheduler |
| sf-flower | spiderfoot-micro | Celery monitoring dashboard (:5555) |
| sf-tika | apache/tika | Document parsing — PDF, DOCX, XLSX (:9998) |
| sf-litellm | ghcr.io/berriai/litellm | Unified LLM gateway (:4000) |
| sf-postgres | postgres:15-alpine | Primary database (:5432) |
| sf-redis | redis:7-alpine | Event bus + cache + Celery broker (:6379) |
| sf-qdrant | qdrant/qdrant | Vector similarity search (:6333) |
| sf-minio | minio/minio | S3-compatible object storage (:9000/9001) |
| sf-minio-init | minio/mc | One-shot bucket provisioner |
| sf-pg-backup | postgres:15-alpine | Scheduled PG backup → MinIO |
| sf-vector | timberio/vector | Telemetry pipeline (:8686/:4317/:9598) |
| sf-loki | grafana/loki | Log aggregation (:3100) |
| sf-grafana | grafana/grafana | Dashboards & visualization (:3000) |
| sf-prometheus | prom/prometheus | Metrics collection (:9090) |
| sf-jaeger | jaegertracing/jaeger | Distributed tracing (:16686) |

### Networks

- **sf-frontend**: Traefik ↔ Frontend/API (external-facing)
- **sf-backend**: All services ↔ PostgreSQL/Redis/Qdrant/MinIO (internal)

### Volumes

| Volume | Container | Mount Path |
|---|---|---|
| sf-postgres-data | sf-postgres | /var/lib/postgresql/data |
| sf-redis-data | sf-redis | /data |
| sf-qdrant-data | sf-qdrant | /qdrant/storage |
| sf-qdrant-snapshots | sf-qdrant | /qdrant/snapshots |
| sf-vector-data | sf-vector | /var/lib/vector |
| sf-minio-data | sf-minio | /data |
| sf-logs | sf-api | /app/logs |
| traefik-logs | sf-traefik | /var/log/traefik |

## AI Agents Service (`spiderfoot/agents/`)

### Frontend (React SPA)

The web interface is a modern React SPA built with TypeScript, Vite, and Tailwind CSS. It features a dark theme with cyan accents, responsive layout, and real-time scan updates via GraphQL subscriptions.

**Key pages and features:**

| Page | Description |
|------|-------------|
| Dashboard | Active scans, event totals, risk distribution, recent activity |
| New Scan | Target input, module category selection, scan configuration |
| Scans | Paginated scan list with status, target, events, duration |
| Scan Detail | 8-tab view: Summary, Browse, Graph, GeoMap, Correlations, AI Report, Scan Settings, Log |
| Workspaces | Multi-scan campaign management with notes and analytics |
| Settings | Global settings, module API keys, notification preferences |
| Agents | AI agent status monitoring and analysis results |
| Users / SSO | User management and SSO configuration (OIDC/SAML) |
| API Keys | API key management for programmatic access |

![Dashboard](images/dashboard.png)

![Scan Detail](images/scan_detail_summary.png)

![Graph Visualization](images/scan_detail_graph.png)

---

Six LLM-powered analysis agents that subscribe to Redis event bus
events and produce structured intelligence. All agents extend `BaseAgent`
with concurrency control, timeout handling, and Prometheus metrics.

| Agent | Event Types | Output |
|---|---|---|
| **FindingValidator** | MALICIOUS_*, VULNERABILITY_*, LEAKED_* | verdict, confidence, remediation |
| **CredentialAnalyzer** | LEAKED_CREDENTIALS, PASSWORD_*, API_KEY_* | severity, is_active, risk_factors |
| **TextSummarizer** | RAW_*, TARGET_WEB_CONTENT, PASTE_*, DOCUMENT_* | summary, entities, sentiment |
| **ReportGenerator** | SCAN_COMPLETE, REPORT_REQUEST | executive_summary, threat_assessment |
| **DocumentAnalyzer** | DOCUMENT_UPLOAD, USER_DOCUMENT, REPORT_UPLOAD | entities, IOCs, classification |
| **ThreatIntelAnalyzer** | MALICIOUS_*, BLACKLISTED_*, CVE_*, DARKNET_* | MITRE ATT&CK mapping, threat actors |

All agents route LLM calls through LiteLLM (:4000) for unified
model selection, cost tracking, and provider failover.

### Agent Service API

| Method | Endpoint | Description |
|---|---|---|
| POST | /agents/process | Process a single event through matching agents |
| POST | /agents/analyze | Deep analysis of a specific finding |
| POST | /agents/report | Generate a comprehensive scan report |
| GET | /agents/status | Status of all agents and pending tasks |
| GET | /metrics | Prometheus metrics |
| GET | /health | Health check |

## Document Enrichment Service (`spiderfoot/enrichment/`)

Converts documents to text, extracts entities and IOCs, and stores
results in MinIO.

### Supported Formats

PDF (pypdf), DOCX (python-docx), XLSX (openpyxl), HTML, RTF (striprtf),
plain text. Optional Apache Tika fallback for complex documents.

### Entity Extraction

Pre-compiled regex patterns for: IPv4/IPv6, emails, URLs, domains,
MD5/SHA1/SHA256 hashes, phone numbers, CVEs, Bitcoin/Ethereum addresses,
AWS keys, credit cards. Smart deduplication and private IP filtering.

### Enrichment API

| Method | Endpoint | Description |
|---|---|---|
| POST | /enrichment/upload | Upload and process a document (100MB limit) |
| POST | /enrichment/process-text | Process raw text content |
| POST | /enrichment/batch | Batch process multiple documents |
| GET | /enrichment/results/{id} | Fetch enrichment results |
| GET | /enrichment/results | List all enrichment results |
| GET | /metrics | Prometheus metrics |
| GET | /health | Health check |

## User-Defined Input Service (`spiderfoot/user_input/`)

Allows users to supply their own documents, IOCs, reports, and
context data to augment automated OSINT collection.

### User Input API

| Method | Endpoint | Description |
|---|---|---|
| POST | /input/document | Upload document → enrichment → agent analysis |
| POST | /input/iocs | Submit IOC list with deduplication |
| POST | /input/report | Submit structured report → entity extraction |
| POST | /input/context | Set scope/exclusions/threat model for a scan |
| POST | /input/targets | Batch target list for multi-scan |
| GET | /input/submissions | List all submissions |
| GET | /input/submissions/{id} | Get submission details |

## LLM Gateway (LiteLLM)

Unified proxy supporting 100+ LLM providers through an
OpenAI-compatible API. Configuration in `infra/litellm/config.yaml`.

### Configured Models

| Model Alias | Provider | Purpose |
|---|---|---|
| gpt-4o | OpenAI | Complex analysis (reports, threat intel) |
| gpt-4o-mini | OpenAI | Default for most agents |
| gpt-3.5-turbo | OpenAI | Fast, low-cost tasks |
| claude-sonnet | Anthropic | Alternative for complex reasoning |
| claude-haiku | Anthropic | Fast Anthropic alternative |
| ollama/llama3 | Ollama (local) | Self-hosted, no API key needed |
| ollama/mistral | Ollama (local) | Self-hosted coding/analysis |

### Router Aliases

- `default` → gpt-4o-mini
- `fast` → gpt-3.5-turbo
- `smart` → gpt-4o
- `local` → ollama/llama3

## Observability Stack

### Telemetry Pipeline (Vector.dev)

Vector.dev replaces both Promtail and OpenTelemetry Collector as a
unified telemetry pipeline:

- **Logs**: Docker container logs → JSON parse → route by level → Loki + MinIO
- **Events**: HTTP source (:8686) → enrich with category/risk → MinIO + file
- **Metrics**: Internal metrics → Prometheus exporter (:9598)
- **Traces**: OTLP receiver (:4317 gRPC, :4318 HTTP) → forward to Jaeger

### Grafana Dashboards

Pre-provisioned 12-panel SpiderFoot Overview dashboard:
Active Scans, Total Scans, Events Processed, High-Risk Findings,
API Latency, LLM Token Usage, Event Rate, Risk Level distribution,
Module Execution, Service Logs, Error Rate, Enrichment Pipeline.

### Prometheus Scrape Targets

spiderfoot-api, spiderfoot-scanner, spiderfoot-agents,
spiderfoot-enrichment, vector, qdrant, minio, jaeger, litellm,
prometheus (self-monitoring).

### Distributed Tracing

OpenTelemetry instrumentation via `spiderfoot/observability/tracing.py`
with graceful no-op fallback when SDK not installed. Traces flow:
Service → OTLP → Vector.dev :4317 → Jaeger :4317.

## MinIO Buckets (8)

| Bucket | Purpose |
|---|---|
| `sf-logs` | Vector.dev archived logs and events |
| `sf-reports` | Generated scan reports |
| `sf-pg-backups` | PostgreSQL backups |
| `sf-qdrant-snapshots` | Vector DB snapshots |
| `sf-data` | General application data |
| `sf-loki-data` | Loki chunk/index storage |
| `sf-loki-ruler` | Loki ruler data |
| `sf-enrichment` | Enrichment pipeline documents |

## Qdrant Vector Search

### Client (`spiderfoot/qdrant_client.py`)

Custom HTTP-based Qdrant client (NOT the PyPI `qdrant-client`). Communicates
with Qdrant via `urllib.request` REST calls.

- **Singleton** via `get_qdrant_client()` / `init_qdrant_client()`
- **Backends**: `MemoryVectorBackend` (testing), `HttpVectorBackend` (production)
- **Collection prefix**: `sf_` (configurable via `SF_QDRANT_PREFIX`)
- **Key classes**: `VectorPoint(id, vector, payload, score)`,
  `SearchResult(points, query_time_ms, total_found)`,
  `Filter(must, must_not, should)` with `match()` / `range()` statics,
  `CollectionInfo(name, vector_size, distance, point_count)`
- **Methods**: `ensure_collection`, `search`, `upsert`, `get`, `delete`,
  `scroll`, `count`, `collection_info`, `list_collections`

### Embedding Service (`spiderfoot/services/embedding_service.py`)

Generates vector embeddings for text data:

- **Providers**: MOCK (default), SENTENCE_TRANSFORMER, OPENAI, HUGGINGFACE
- **Default model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Methods**: `embed_text()`, `embed_texts()` with caching and batching

### Vector Correlation (`spiderfoot/vector_correlation.py`)

5 correlation strategies over vectorized scan events:

| Strategy | Description |
|---|---|
| SIMILARITY | Cosine similarity within a scan |
| CROSS_SCAN | Similar events across different scans |
| TEMPORAL | Time-windowed clustering |
| INFRASTRUCTURE | Infrastructure topology grouping |
| MULTI_HOP | Multi-step relationship discovery |

Default collection: `sf_osint_events`

## MinIO Object Storage

S3-compatible object storage for artifacts, reports, and backups.

### Buckets (created by sf-minio-init)

| Bucket | Purpose |
|---|---|
| spiderfoot-reports | Generated scan reports (PDF/HTML/MD) |
| spiderfoot-exports | Exported scan data (CSV/JSON/STIX) |
| spiderfoot-artifacts | Raw scan artifacts and screenshots |
| spiderfoot-backups | PostgreSQL pg_dump archives |
| spiderfoot-logs | Archived log files |

### Storage API (`spiderfoot/storage/minio_client.py`)

- **MinioStorageClient**: Upload, download, list, delete, presigned URLs
- **Singleton**: `get_minio_client()` with automatic bucket creation
- **Lifecycle**: Configurable retention policies per bucket

### PG Backup Sidecar

Runs in the `sf-pg-backup` container:

- Hourly `pg_dump` of the SpiderFoot database
- Compressed archives uploaded to the `spiderfoot-backups` bucket
- Configurable retention (default: 7 days)
- Health check via backup recency validation

## GraphQL API Layer

### Schema (`spiderfoot/api/graphql/`)

Code-first GraphQL using Strawberry ≥ 0.235.0, mounted at `/api/graphql`
with GraphiQL IDE.

#### Queries (13 fields)

| Field | Return Type | Description |
|---|---|---|
| `scan(id)` | ScanType | Single scan by ID |
| `scans(page, pageSize)` | PaginatedScans | Paginated scan list |
| `scanEvents(scanId, filter, pagination)` | PaginatedEvents | Filtered events |
| `eventSummary(scanId)` | [EventTypeSummary] | Event type counts |
| `scanCorrelations(scanId)` | [CorrelationType] | Correlation hits |
| `scanLogs(scanId)` | [ScanLogType] | Module execution logs |
| `scanStatistics(scanId)` | ScanStatistics | Aggregate scan stats |
| `scanGraph(scanId, maxNodes)` | ScanGraph | D3 graph data |
| `eventTypes` | [EventTypeInfo] | Available event types |
| `workspaces` | [WorkspaceType] | Scan workspaces |
| `searchEvents(query, scanId)` | PaginatedEvents | Full-text search |
| `semanticSearch(query, ...)` | VectorSearchResult | Qdrant vector search |
| `vectorCollections` | [VectorCollectionInfo] | Qdrant collections |

#### Mutations (5)

| Mutation | Return Type | Description |
|---|---|---|
| `startScan(input)` | ScanCreateResult | Create and start a scan |
| `stopScan(scanId)` | MutationResult | Abort a running scan |
| `deleteScan(scanId)` | MutationResult | Delete scan + data |
| `setFalsePositive(input)` | FalsePositiveResult | Toggle FP status |
| `rerunScan(scanId)` | ScanCreateResult | Clone and rerun a scan |

#### Subscriptions (2, via WebSocket)

| Subscription | Yields | Description |
|---|---|---|
| `scanProgress(scanId, interval)` | ScanType | Polls scan status changes |
| `scanEventsLive(scanId, interval)` | EventType | New events as they appear |

Protocols: `graphql-transport-ws`, `graphql-ws`

#### Extensions

- **QueryDepthLimiter**: Max depth = 10 (prevents deeply nested abuse)
- **DataLoaders**: `ScanEventLoader`, `ScanCorrelationLoader` (N+1 prevention)

## Module System

### Legacy Modules (`SpiderFootPlugin`)

All 283 existing modules continue to work unchanged. They use `self.sf`
(the SpiderFoot god object) for HTTP, DNS, and other operations.

### Modern Modules (`SpiderFootModernPlugin`)

New modules can extend `SpiderFootModernPlugin` to access services directly:

```python
from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin

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

## Version History (v5.4.0 – v5.246.0)

| Version | Change |
|---|---|
| 5.246.0 | GraphQL mutations (5), subscriptions (2, WebSocket), Qdrant semantic search resolver, query depth limiter, MinIO object storage (5 buckets), PG backup sidecar, complete documentation overhaul |
| 5.245.0 | Complete shim removal — 79 backward-compat files deleted, 470 imports rewritten to 8 domain sub-packages |
| 5.244.0 | Fix circular imports across all 8 sub-packages (relative imports) |
| 5.243.0 | Populate 8 domain sub-packages (events, scan, plugins, config, security, observability, services, reporting) |
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
| 5.29.0 | Correlation Service Wiring (CorrelationService → router) |
| 5.30.0 | Scan Service Facade (ScanStateMachine + ScanRepository → router) |
| 5.31.0 | Visualization Service Facade (graph/summary/timeline/heatmap → router) |
| 5.32.0 | Scan Service Phase 2 (all 25 endpoints → ScanService, zero raw DB) |
| 5.33.0 | Final Router DB Purge + Dead Code Removal |
| 5.34.0 | WebUI DB Access Centralisation (DbProvider mixin) |
| 5.35.0 | Fix silent error swallowing in service_integration.py |
| 5.36.0 | Add gRPC dependencies to requirements.txt |
| 5.37.0 | Generate gRPC stubs, wire grpc_service.py |
| 5.38.0 | Unified scan state mapping (scan_state_map.py) |
| 5.39.0 | Replace monkey-patching with functools.wraps |
| 5.40.0 | Framework-agnostic security + deprecate Flask |
| 5.41.0 | Migrate ScanService events to EventRepository |
| 5.42.0 | Domain sub-packages for code organization |
| 5.43.0 | HTTP DataService client (REST backend) |
| 5.43.1 | DataService health check endpoints |
| 5.44.0 | gRPC DataService client (Protobuf backend) |
| 5.44.1 | Circuit breaker for remote DataService |
| 5.45.0 | Extract ScanMetadataService |
| 5.46.0 | WebUI API proxy layer |
| 5.47.0 | Per-service Docker network isolation |
| 5.48.0 | API versioning with /api/v1/ prefix |
| 5.49.0 | Pydantic v2 schemas for service boundaries |
| 5.50.0 | Module interface contracts (Protocol + validation) |
| 5.51.0 | ConfigService microservice enhancements |
| 5.52.0 | Proto schema expansion (15 new RPCs + CorrelationService) |
| 5.53.0 | Service startup sequencer |
| 5.54.0 | Graceful shutdown coordination |
| 5.54.1 | Wire startup/shutdown into entry points |
| 5.55.0 | Wire Pydantic response_model on scan router |
| 5.56.0 | Structured API error responses (ErrorResponse envelope) |
| 5.56.1 | Rich OpenAPI metadata (tags, license, description) |
| 5.57.0 | Config source tracing + environment API |
| 5.58.0 | Scan lifecycle event hooks (EventBus integration) |
| 5.59.0 | Module execution timeout guard |
| 5.60.0 | Inter-service authentication (static + HMAC tokens) |
| 5.60.1 | Wire service auth into HTTP clients + docker-compose |
| 5.61.0 | API request audit logging middleware |
| 5.62.0 | Module output validation (producedEvents enforcement) |
| 5.62.1 | Documentation update for Cycles 55-64 |
| 5.63.0 | Unified scan export API (STIX/SARIF/JSON/CSV) |
| 5.63.1 | Wire pagination into workspace + data routers |
| 5.64.0 | Health check deep probes (4 new subsystem checks) |
| 5.64.1 | Comprehensive live config validation endpoint |
| 5.65.0 | Correlation results export API (CSV/JSON) |
| 5.65.1 | Workspace response schemas + response_model |
| 5.66.0 | API key rotation endpoint |
| 5.67.0 | Scan comparison endpoint |
| 5.67.1 | Documentation update for Cycles 65-74 |
| 5.68.0 | Body size limiter middleware |
| 5.68.1 | CORS middleware |
| 5.69.0 | Module runtime statistics endpoint |
| 5.70.0 | Scan tag/label management |
| 5.71.0 | Bulk scan operations |
| 5.72.0 | Per-endpoint rate limit configuration |
| 5.73.0 | Webhook event filtering + discovery |
| 5.74.0 | Module dependency graph endpoint |
| 5.74.1 | Documentation update for Cycles 75-83 |
| 5.75.0 | Recurring scan schedule API (interval/one-shot) |
| 5.75.1 | Response schemas wiring (config + data routers) |
| 5.76.0 | Request ID propagation (HTTP/gRPC/webhooks) |
| 5.77.0 | Scan timeline endpoint (chronological events) |
| 5.78.0 | Module enable/disable API (runtime management) |
| 5.79.0 | Scan search/filter API (faceted results) |
| 5.80.0 | Graceful shutdown manager (signals + FastAPI lifespan) |
| 5.80.1 | Documentation update for Cycles 84-91 |
| 5.81.0 | Streaming JSONL export for large scans |
| 5.82.0 | Per-event annotations API |
| 5.83.0 | API key scoping (predefined permission sets) |
| 5.84.0 | Config change history + diff-against-defaults |
| 5.85.0 | Event deduplication detection endpoint |
| 5.86.0 | Per-module config validation |
| 5.87.0 | Scan retry for failed/aborted scans |
| 5.88.0 | Response compression middleware (gzip) |
| 5.88.1 | Final documentation update — Cycle 100 |

### Additional Services (v5.10.1 – v5.21.0)

#### Auth Middleware (`spiderfoot/security/auth.py`)
JWT, API key, and Basic authentication with role-based access control
(ADMIN, ANALYST, VIEWER, API roles). Pluggable into any ASGI/WSGI app.

#### Export Service (`spiderfoot/reporting/export_service.py`)
Multi-format scan result export: JSON, CSV, STIX 2.1 bundles, and
SARIF for integration with CI/CD security tooling.

#### WebSocket Service (`spiderfoot/services/websocket_service.py`)
Real-time scan event streaming over WebSocket with channel-based
subscriptions per scan, module, or event type.

#### Notification Service (`spiderfoot/services/notification_service.py`)
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

#### Scan Queue (`spiderfoot/scan/scan_queue.py`)
Bounded priority queue (HIGH/NORMAL/LOW) with backpressure support.
Three overflow strategies (BLOCK/REJECT/DROP_OLDEST), batch dequeue,
retry tracking with dead-letter queue.

#### Module Resolver (`spiderfoot/plugins/module_resolver.py`)
Runtime dependency resolution for modules.  Given desired output event
types, walks backwards through the event dependency chain to compute the
minimal module set and topological load order.

#### Database Migration (`spiderfoot/db_migrate.py`)
Version-controlled schema evolution with numbered migration files,
upgrade/downgrade functions, dry-run mode, and checksum validation.
Supports SQLite and PostgreSQL dialects.

### Module Loading & Dependency Resolution (v5.25.0)

#### Module Loader (`spiderfoot/plugins/module_loader.py`)
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

### Correlation Service Wiring (v5.29.0)

#### Correlations Router (`spiderfoot/api/routers/correlations.py`)
Rewritten to delegate to `CorrelationService` instead of raw
`SpiderFootDb` / config manipulation. All 7 endpoints now use the
service layer and Cycle 25 pagination.

- **Rule CRUD** — `add_rule()`, `get_rule()`, `update_rule()`,
  `delete_rule()`, `filter_rules()` added to `CorrelationService`
- **`get_correlation_svc`** — FastAPI `Depends()` provider in
  `dependencies.py` returning the singleton service
- **Real execution** — Test/analyze endpoints call
  `svc.run_for_scan()` with actual timing instead of hardcoded results
- **Pagination** — List and detailed endpoints use `PaginationParams`
  + `paginate()` for standardized response envelopes
- **No direct DB access** — All `SpiderFootDb(config.get_config())`
  and `json.dumps()`/`configSet()` calls eliminated from the router

### Scan Service Facade (v5.30.0)

#### Scan Service (`spiderfoot/scan/scan_service_facade.py`)
Unified scan lifecycle management combining `ScanRepository` (Cycle 23)
with `ScanStateMachine` for formal state-transition enforcement.

- **`ScanService`** — High-level facade wrapping repository + state machine
  with CRUD methods: `list_scans`, `get_scan`, `create_scan`, `delete_scan`,
  `delete_scan_full`, `stop_scan`, `get_scan_state`
- **State Machine Integration** — `stop_scan()` validates transitions
  (RUNNING→STOPPING, CREATED→CANCELLED) before persisting; returns
  HTTP 409 Conflict when transition is invalid (e.g. stopping a completed scan)
- **`get_scan_service`** — FastAPI `Depends()` generator provider in
  `dependencies.py` with automatic lifecycle management
- **Pagination** — `list_scans` endpoint uses `PaginationParams` +
  `paginate()` for standardized response envelopes
- **Typed records** — Endpoints return `ScanRecord.to_dict()` instead
  of raw tuple-index dicts (`scan[0]`, `scan[6]`, etc.)
- **Gradual migration** — Service exposes `.dbh` for endpoints not yet
  migrated (export, viz); full migration planned for future cycles
### WebUI DB Access Centralisation (v5.34.0)

#### DbProvider Mixin (`spiderfoot/webui/db_provider.py`)
Centralises all `SpiderFootDb` instantiation across the CherryPy
WebUI into a single overridable `_get_dbh()` method.

- **78 per-request `SpiderFootDb(self.config)` calls replaced** across
  `scan.py` (62), `export.py` (7), `settings.py` (4), `helpers.py` (1),
  `info.py` (1), `routes.py` (3)
- **`DbProvider` mixin** added to `WebUiRoutes` MRO — all endpoint
  classes inherit `_get_dbh(config=None)` via diamond inheritance
- **Single override point** — tests or future service migration can
  replace `_get_dbh()` instead of patching 78+ instantiation sites
- **Config override** — `_get_dbh(cfg)` for cases needing `deepcopy`
  config (e.g. `rerunscan`, `rerunscanmulti`)
- **CHANGELOG** — `event_schema.py` entry annotated as deleted in v5.33.0

### Scan Service Phase 2 (v5.32.0)

#### Complete Scan Router Migration
Completes the ScanService facade migration started in Cycle 27,
eliminating all raw `SpiderFootDb` instantiation from the scan router.

- **15 new ScanService methods** — `get_events()`, `search_events()`,
  `get_correlations()`, `get_scan_logs()`, `get_metadata()`/`set_metadata()`,
  `get_notes()`/`set_notes()`, `archive()`/`unarchive()`, `clear_results()`,
  `set_false_positive()`, `get_scan_options()`
- **All 25 scan endpoints** now delegate to `ScanService` via
  `Depends(get_scan_service)` — zero `SpiderFootDb` imports remain
- **Export endpoints** — CSV/XLSX event export, multi-scan JSON export,
  search export, logs export, correlations export
- **Lifecycle endpoints** — create, rerun, rerun-multi, clone
- **Results management** — false-positive with parent/child validation,
  clear results
- **Metadata/notes/archive** — CRUD with `hasattr` guards for optional
  DB methods
- **Static route ordering** — `/scans/export-multi`, `/scans/viz-multi`,
  `/scans/rerun-multi` registered before `/{scan_id}` routes

### Final Router DB Purge (v5.33.0)

#### Complete Router-Layer SpiderFootDb Elimination
Removes the last 3 raw `SpiderFootDb` instantiations from all API
routers, achieving a clean architectural boundary between the router
layer and the database.

- **config.py** — `GET /event-types` now uses `ConfigRepository` via
  `Depends(get_config_repository)`. New `ConfigRepository.get_event_types()`
  method wraps `dbh.eventTypes()`.
- **reports.py** — `_get_scan_events()` helper rewritten to accept an
  injected `ScanService`. Endpoints `POST /reports/generate` and
  `POST /reports/preview` pass their `Depends(get_scan_service)` instance.
- **websocket.py** — `_polling_mode()` rewritten to build a `ScanService`
  from `RepositoryFactory` instead of raw `SpiderFootDb`. Proper cleanup
  via `svc.close()` in `finally` block.
- **Dead code removal** — `event_schema.py` (655 lines) and its test file
  deleted (zero production imports).
- **Verification** — `grep -r "SpiderFootDb" spiderfoot/api/routers/`
  returns only docstring/comment references, zero actual imports.

### Visualization Service Facade (v5.31.0)

#### Visualization Service (`spiderfoot/visualization_service.py`)
Dedicated service layer for scan data visualization, removing raw
`SpiderFootDb` from all 5 visualization router endpoints.

- **`VisualizationService`** — Composes `ScanRepository` + raw `dbh`
  with methods: `get_graph_data`, `get_multi_scan_graph_data`,
  `get_summary_data`, `get_timeline_data`, `get_heatmap_data`
- **Smart scan validation** — `_require_scan()` uses `ScanRepository`
  first, with raw `dbh.scanInstanceGet()` fallback
- **Timeline aggregation** — Handles both `datetime` and epoch
  timestamps; supports hour/day/week bucketing
- **Heatmap matrix** — Builds x/y matrix from result dimensions
  (module/type/risk) with configurable axes
- **Multi-scan graph** — Merges results across scan IDs, skipping
  invalid scans with warning logs
- **`get_visualization_service`** — FastAPI `Depends()` generator
  provider in `dependencies.py` with automatic lifecycle management
- **Static route ordering** — `/visualization/graph/multi` registered
  before `/{scan_id}` to avoid path parameter capture

### Real-Time Event Infrastructure (v5.22.0 – v5.24.0)

#### Event Relay (`spiderfoot/events/event_relay.py`)
Central fan-out hub bridging the EventBus to WebSocket/SSE consumers.
Per-scan consumer queues with bounded overflow (drop-oldest policy),
EventBus subscription management, and lifecycle helpers for
`scan_started` / `scan_completed` / `status_update` events.

#### Scan Event Bridge (`spiderfoot/scan/scan_event_bridge.py`)
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

#### Typed AppConfig (`spiderfoot/config/app_config.py`)
11-section typed dataclass configuration replacing the legacy flat
dict. Sections: Core, Network, Database, Web, API, Cache, EventBus,
Vector, Worker, Redis, Elasticsearch. Features: `from_dict()` /
`to_dict()` round-trip, `apply_env_overrides()` for SF_* variables,
20+ validation rules, and merge semantics for layered overrides.
