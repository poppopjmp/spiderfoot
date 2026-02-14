<p align="center">
<img src="https://raw.githubusercontent.com/poppopjmp/spiderfoot/master/spiderfoot/static/img/spiderfoot-header.png" />
</p>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://raw.githubusercontent.com/poppopjmp/spiderfoot/master/LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org)
[![Version](https://img.shields.io/badge/version-5.3.3-green)](VERSION)
[![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker)](docker-compose-microservices.yml)
[![GraphQL](https://img.shields.io/badge/GraphQL-Strawberry-E10098?logo=graphql)](spiderfoot/api/graphql/)
[![CI status](https://github.com/poppopjmp/spiderfoot/workflows/Tests/badge.svg)](https://github.com/poppopjmp/spiderfoot/actions?query=workflow%3A"Tests")
[![codecov](https://codecov.io/github/poppopjmp/spiderfoot/graph/badge.svg?token=ZRD8GIXJSP)](https://codecov.io/github/poppopjmp/spiderfoot)
[![Discord](https://img.shields.io/discord/770524432464216074)](https://discord.gg/vyvztrG)

# SpiderFoot — OSINT Automation Platform

SpiderFoot is an open-source intelligence (OSINT) automation platform. It integrates with **200+ data sources** to gather intelligence on IP addresses, domain names, hostnames, network subnets, ASNs, email addresses, phone numbers, usernames, Bitcoin addresses, and more. Written in **Python 3** and **MIT-licensed**.

---

## Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Deployment Modes](#deployment-modes)
- [Services](#services)
- [Monitoring & Observability](#monitoring--observability)
- [AI Agents](#ai-agents)
- [Document Enrichment](#document-enrichment)
- [User-Defined Input](#user-defined-input)
- [LLM Gateway](#llm-gateway)
- [GraphQL API](#graphql-api)
- [REST API](#rest-api)
- [Vector Search (Qdrant)](#vector-search-qdrant)
- [Object Storage (MinIO)](#object-storage-minio)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Modules](#modules)
- [Correlation Engine](#correlation-engine)
- [Use Cases](#use-cases)
- [Development](#development)
- [Community](#community)

---

## Architecture

```mermaid
graph TB
    subgraph External
        Browser[Browser / Client]
    end

    subgraph Docker["Docker Compose Stack (17 containers)"]
        NGINX[Nginx :80/:443<br/>Reverse Proxy]

        subgraph Application
            API[sf-api :8001<br/>FastAPI + GraphQL]
            WEBUI[sf-webui :5001<br/>CherryPy Web UI]
        end

        subgraph Analysis["Analysis Services"]
            AGENTS[sf-agents :8100<br/>6 AI Agents]
            ENRICHMENT[sf-enrichment :8200<br/>Document Pipeline]
            USERINPUT[sf-user-input :8300<br/>User-Defined Input]
        end

        subgraph LLM["LLM Gateway"]
            LITELLM[LiteLLM :4000<br/>Multi-Provider Proxy]
        end

        subgraph Data
            PG[(PostgreSQL :5432<br/>Primary Database)]
            REDIS[(Redis :6379<br/>EventBus / Cache)]
            QDRANT[(Qdrant :6333<br/>Vector Search)]
            MINIO[(MinIO :9000<br/>Object Storage)]
        end

        subgraph Observability["Observability Stack"]
            VECTOR[Vector.dev :8686<br/>Telemetry Pipeline]
            LOKI[Loki :3100<br/>Log Aggregation]
            GRAFANA[Grafana :3000<br/>Dashboards]
            PROMETHEUS[Prometheus :9090<br/>Metrics]
            JAEGER[Jaeger :16686<br/>Distributed Tracing]
        end

        subgraph Maintenance
            PGBACKUP[pg-backup<br/>Cron Sidecar]
            MINIOINIT[minio-init<br/>Bucket Bootstrap]
        end
    end

    Browser --> NGINX
    NGINX --> API
    NGINX --> WEBUI
    NGINX --> AGENTS
    NGINX --> ENRICHMENT
    NGINX --> USERINPUT
    NGINX --> GRAFANA
    WEBUI --> API
    API --> PG
    API --> REDIS
    API --> QDRANT
    API --> MINIO
    API --> LITELLM
    AGENTS --> LITELLM
    AGENTS --> REDIS
    USERINPUT --> ENRICHMENT
    USERINPUT --> AGENTS
    ENRICHMENT --> MINIO
    VECTOR --> LOKI
    VECTOR --> MINIO
    VECTOR --> JAEGER
    PROMETHEUS --> VECTOR
    GRAFANA --> LOKI
    GRAFANA --> PROMETHEUS
    GRAFANA --> PG
    PGBACKUP --> PG
    PGBACKUP --> MINIO
    MINIOINIT --> MINIO
```

---

## Quick Start

### Option 1 — Docker Microservices (Recommended)

```bash
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Copy and configure environment
cp docker/env.example .env
# Edit .env with your API keys (OpenAI, Anthropic, etc.)

# Start the full 17-service stack
docker compose -f docker-compose-microservices.yml up --build -d
```

| URL | Service |
|-----|---------|
| `http://localhost` | Web UI (via Nginx) |
| `http://localhost/api/docs` | Swagger / OpenAPI |
| `http://localhost/api/graphql` | GraphiQL IDE |
| `http://localhost:3000` | Grafana Dashboards |
| `http://localhost:9090` | Prometheus |
| `http://localhost:16686` | Jaeger Tracing |
| `http://localhost:4000` | LiteLLM Gateway |
| `http://localhost:9001` | MinIO Console |

### Option 2 — Standalone (Monolith)

```bash
pip install -r requirements.txt
python3 sf.py -l 127.0.0.1:5001
```

---

## Deployment Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Monolith** | `python3 sf.py -l 0.0.0.0:5001` | Single process, SQLite, zero dependencies |
| **Docker Compose** | `docker compose -f docker-compose-microservices.yml up -d` | 10 services, PostgreSQL, Redis, Qdrant, MinIO |
| **Kubernetes** | `helm install sf helm/` | Horizontal scaling with Helm chart |

---

## Services

The microservices deployment runs **17 containers** on two Docker networks (`sf-frontend`, `sf-backend`):

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **sf-nginx** | nginx:alpine | 80 / 443 | Reverse proxy, TLS termination, rate limiting |
| **sf-api** | spiderfoot | 8001 | FastAPI REST + GraphQL API, scan orchestration |
| **sf-webui** | spiderfoot | 5001 | CherryPy web UI, proxies all data through API |
| **sf-agents** | spiderfoot | 8100 | 6 AI-powered analysis agents (LLM-backed) |
| **sf-enrichment** | spiderfoot | 8200 | Document conversion + entity extraction pipeline |
| **sf-user-input** | spiderfoot | 8300 | User-defined document/IOC/report ingestion |
| **sf-litellm** | litellm | 4000 | Unified LLM proxy (OpenAI, Anthropic, Ollama) |
| **sf-postgres** | postgres:15 | 5432 | Primary relational data store |
| **sf-redis** | redis:7-alpine | 6379 | EventBus pub/sub, caching, session store |
| **sf-qdrant** | qdrant/qdrant | 6333 | Vector similarity search for semantic OSINT correlation |
| **sf-minio** | minio/minio | 9000 / 9001 | S3-compatible object storage (logs, reports, backups) |
| **sf-vector** | timberio/vector | 8686 / 4317 / 9598 | Unified telemetry pipeline (logs, metrics, traces) |
| **sf-loki** | grafana/loki | 3100 | Log aggregation backend |
| **sf-grafana** | grafana/grafana | 3000 | Dashboards, alerting, data exploration |
| **sf-prometheus** | prom/prometheus | 9090 | Metrics collection and alerting |
| **sf-jaeger** | jaegertracing/jaeger | 16686 | Distributed tracing UI |
| **sf-pg-backup** | spiderfoot | — | Cron sidecar: pg_dump → MinIO (`sf-pg-backups` bucket) |
| **sf-minio-init** | minio/mc | — | One-shot: creates 8 MinIO buckets on first boot |

### Docker Volumes

| Volume | Mounted By | Purpose |
|--------|-----------|---------|
| `sf-postgres-data` | sf-postgres | Database files |
| `sf-redis-data` | sf-redis | RDB/AOF persistence |
| `sf-qdrant-data` | sf-qdrant | Vector index storage |
| `sf-minio-data` | sf-minio | Object storage files |
| `sf-vector-data` | sf-vector | Buffer / checkpoints |
| `sf-api-data` | sf-api | Application state |
| `sf-webui-data` | sf-webui | Session / cache |

### MinIO Buckets

| Bucket | Contents |
|--------|----------|
| `sf-logs` | Vector.dev log archive |
| `sf-reports` | Generated scan reports (HTML, PDF, JSON, CSV) |
| `sf-pg-backups` | PostgreSQL daily pg_dump files |
| `sf-qdrant` | Qdrant vector DB snapshots |
| `sf-data` | General application artefacts |
| `sf-loki-data` | Loki chunk/index storage |
| `sf-loki-ruler` | Loki ruler data |
| `sf-enrichment` | Enrichment pipeline documents |

---

## Monitoring & Observability

SpiderFoot v5.3.3 includes a complete observability stack, with **Vector.dev** serving as the unified telemetry pipeline (replacing both Promtail and OpenTelemetry Collector).

| Component | Purpose | Access |
|-----------|---------|--------|
| **Grafana** | Dashboards, alerting, log/metric exploration | `http://localhost:3000` |
| **Loki** | Log aggregation (backed by MinIO S3 storage) | via Grafana |
| **Prometheus** | Metrics collection from all services | `http://localhost:9090` |
| **Jaeger** | Distributed tracing (OTLP via Vector.dev) | `http://localhost:16686` |
| **Vector.dev** | Log/metrics/traces pipeline | Internal |

### Pre-built Dashboard

A 12-panel Grafana dashboard is auto-provisioned with: Active Scans, Events Processed, High-Risk Findings, API Latency, LLM Token Usage, Event Rate, Risk Level distribution, Module Execution times, Service Logs, Error Rate, and Enrichment Pipeline metrics.

---

## AI Agents

Six LLM-powered agents automatically analyze high-risk findings and produce structured intelligence. They subscribe to Redis event bus topics and process events asynchronously.

| Agent | Trigger Events | Output |
|-------|---------------|--------|
| **FindingValidator** | `MALICIOUS_*`, `VULNERABILITY_*` | Verdict (confirmed/likely_false_positive), confidence, remediation |
| **CredentialAnalyzer** | `LEAKED_CREDENTIALS`, `API_KEY_*` | Severity, active status, affected services |
| **TextSummarizer** | `RAW_*`, `TARGET_WEB_CONTENT` | Summary, entities, sentiment, relevance score |
| **ReportGenerator** | `SCAN_COMPLETE` | Executive summary, threat assessment, recommendations |
| **DocumentAnalyzer** | `DOCUMENT_UPLOAD`, `USER_DOCUMENT` | Entities, IOCs, classification, scan targets |
| **ThreatIntelAnalyzer** | `MALICIOUS_*`, `CVE_*`, `DARKNET_*` | MITRE ATT&CK mapping, threat actor attribution |

API: `http://localhost/agents/` — see [Architecture Guide](documentation/ARCHITECTURE.md) for endpoints.

---

## Document Enrichment

Upload documents (PDF, DOCX, XLSX, HTML, RTF, plain text) for automated entity and IOC extraction.

### Pipeline

1. **Convert** — Document → plain text (pypdf, python-docx, openpyxl, etc.)
2. **Extract** — Regex-based entity extraction (IPs, domains, hashes, CVEs, crypto addresses, etc.)
3. **Store** — Original + extracted content → MinIO `sf-enrichment` bucket
4. **Analyze** — Forward to DocumentAnalyzer agent for LLM-powered intelligence

API: `POST http://localhost/enrichment/upload` (100MB limit)

---

## User-Defined Input

Supply your own documents, IOCs, reports, and context to augment automated OSINT collection.

| Endpoint | Description |
|----------|-------------|
| `POST /input/document` | Upload document → enrichment → agent analysis |
| `POST /input/iocs` | Submit IOC list (IPs, domains, hashes) with dedup |
| `POST /input/report` | Structured report → entity extraction → analysis |
| `POST /input/context` | Set scope, exclusions, threat model for a scan |
| `POST /input/targets` | Batch target list for multi-scan |

---

## LLM Gateway

[LiteLLM](https://litellm.ai/) provides a unified OpenAI-compatible API for all LLM interactions, supporting OpenAI, Anthropic, and self-hosted Ollama models.

| Alias | Model | Use Case |
|-------|-------|----------|
| `default` | gpt-4o-mini | Most agent tasks |
| `fast` | gpt-3.5-turbo | Low-cost, fast tasks |
| `smart` | gpt-4o | Complex reports & threat intel |
| `local` | ollama/llama3 | Self-hosted, no API key |

Configure API keys in `.env` — see `docker/env.example` for all options.

---

## GraphQL API

The GraphQL API is served by [Strawberry](https://strawberry.rocks/) at `/api/graphql` with a built-in GraphiQL IDE. It supports **queries**, **mutations**, and real-time **subscriptions** via WebSocket.

### Queries

| Field | Description |
|-------|-------------|
| `scan(scanId)` | Fetch a single scan by ID |
| `scans(pagination, statusFilter)` | Paginated scan listing |
| `scanEvents(scanId, filter, pagination)` | Filtered & paginated events |
| `eventSummary(scanId)` | Aggregated event type counts |
| `scanCorrelations(scanId)` | Correlation findings for a scan |
| `scanLogs(scanId, logType, limit)` | Scan execution logs |
| `scanStatistics(scanId)` | Dashboard-ready aggregate stats |
| `scanGraph(scanId, maxNodes)` | Event relationship graph for visualization |
| `eventTypes` | All available event type definitions |
| `workspaces` | List workspaces |
| `searchEvents(query, scanIds, eventTypes)` | Cross-scan text search |
| `semanticSearch(query, collection, limit, scoreThreshold, scanId)` | Qdrant vector similarity search |
| `vectorCollections` | List Qdrant collections and stats |

### Mutations

| Mutation | Description |
|----------|-------------|
| `startScan(input: ScanCreateInput!)` | Create and start a new OSINT scan |
| `stopScan(scanId!)` | Abort a running scan |
| `deleteScan(scanId!)` | Delete a scan and all related data |
| `setFalsePositive(input: FalsePositiveInput!)` | Mark/unmark results as false positive |
| `rerunScan(scanId!)` | Clone and restart a completed scan |

### Subscriptions (WebSocket)

| Subscription | Description |
|--------------|-------------|
| `scanProgress(scanId, interval)` | Real-time scan status changes |
| `scanEventsLive(scanId, interval)` | Stream new events as they are discovered |

Connect via `ws://localhost/api/graphql` using the `graphql-transport-ws` protocol.

### Example Queries

```graphql
# Fetch scan with dashboard statistics
query {
  scan(scanId: "abc-123") {
    name
    target
    status
    durationSeconds
    isRunning
  }
  scanStatistics(scanId: "abc-123") {
    totalEvents
    uniqueEventTypes
    totalCorrelations
    riskDistribution { level count percentage }
    topModules { module count }
  }
}

# Semantic vector search across OSINT events
query {
  semanticSearch(query: "phishing domain", limit: 10, scoreThreshold: 0.7) {
    hits { id score eventType data scanId risk }
    totalFound
    queryTimeMs
  }
}

# Start a new scan
mutation {
  startScan(input: { name: "Recon scan", target: "example.com" }) {
    success
    message
    scanId
    scan { status }
  }
}

# Subscribe to live scan progress
subscription {
  scanProgress(scanId: "abc-123") {
    status
    durationSeconds
    isRunning
  }
}
```

---

## REST API

Full OpenAPI / Swagger documentation is available at `/api/docs` when the API service is running.

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/scans` | List all scans |
| `POST` | `/api/scans` | Create and start a new scan |
| `GET` | `/api/scans/{id}` | Get scan details |
| `POST` | `/api/scans/{id}/stop` | Stop a running scan |
| `DELETE` | `/api/scans/{id}` | Delete a scan |
| `GET` | `/api/scans/{id}/results` | Scan result events |
| `GET` | `/api/scans/{id}/correlations` | Correlation findings |
| `GET` | `/api/scans/{id}/export/{format}` | Export (CSV/JSON/STIX/SARIF) |
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/modules` | List available modules |
| `GET` | `/api/storage/buckets` | List MinIO buckets |

### Example

```bash
# Start a scan
curl -X POST http://localhost/api/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "type": "DOMAIN_NAME", "modules": ["sfp_dnsresolve"]}'

# Get scan results
curl http://localhost/api/scans/{scan_id}/results
```

---

## Vector Search (Qdrant)

SpiderFoot uses [Qdrant](https://qdrant.tech/) for semantic vector search and OSINT event correlation.

### How It Works

1. **Embedding** — Scan events are embedded into 384-dimensional vectors using `all-MiniLM-L6-v2` (configurable).
2. **Indexing** — Vectors are stored in Qdrant collections prefixed with `sf_`.
3. **Search** — Natural language queries are embedded and matched against stored events using cosine similarity.
4. **Correlation** — The Vector Correlation Engine supports 5 strategies: `SIMILARITY`, `CROSS_SCAN`, `TEMPORAL`, `INFRASTRUCTURE`, `MULTI_HOP`.

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SF_QDRANT_HOST` | `sf-qdrant` | Qdrant server hostname |
| `SF_QDRANT_PORT` | `6333` | Qdrant REST API port |
| `SF_QDRANT_PREFIX` | `sf_` | Collection name prefix |
| `SF_EMBEDDING_PROVIDER` | `mock` | `mock`, `sentence_transformer`, `openai`, `huggingface` |
| `SF_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |
| `SF_EMBEDDING_DIMENSIONS` | `384` | Vector dimensionality |

---

## Object Storage (MinIO)

[MinIO](https://min.io/) provides S3-compatible object storage for logs, reports, backups, and vector snapshots.

### Storage API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/storage/buckets` | List all buckets |
| `GET` | `/api/storage/buckets/{name}` | List objects in a bucket |
| `GET` | `/api/storage/buckets/{name}/{key}` | Download an object |
| `POST` | `/api/storage/buckets/{name}` | Upload an object |
| `DELETE` | `/api/storage/buckets/{name}/{key}` | Delete an object |

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SF_MINIO_ENDPOINT` | `sf-minio:9000` | MinIO server |
| `SF_MINIO_ACCESS_KEY` | `minioadmin` | Access key |
| `SF_MINIO_SECRET_KEY` | `minioadmin` | Secret key |
| `SF_MINIO_SECURE` | `false` | Use TLS |

---

## Configuration

All services are configured via environment variables (see `docker/env.example`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `SF_DEPLOYMENT_MODE` | `monolith` or `microservices` | `monolith` |
| `SF_DATABASE_URL` | PostgreSQL connection string | SQLite |
| `SF_REDIS_URL` | Redis URL for EventBus/Cache | None |
| `SF_EVENTBUS_BACKEND` | `memory`, `redis`, or `nats` | `memory` |
| `SF_VECTOR_ENDPOINT` | Vector.dev HTTP endpoint | None |
| `SF_LOG_FORMAT` | `json` or `text` | `text` |
| `SF_QDRANT_HOST` | Qdrant hostname | `sf-qdrant` |
| `SF_MINIO_ENDPOINT` | MinIO endpoint | `sf-minio:9000` |
| `SF_EMBEDDING_PROVIDER` | Embedding backend | `mock` |
| `SF_LLM_API_BASE` | LiteLLM proxy URL | `http://litellm:4000` |
| `SF_LLM_DEFAULT_MODEL` | Default LLM model | `default` |
| `OPENAI_API_KEY` | OpenAI API key (for LiteLLM) | None |
| `ANTHROPIC_API_KEY` | Anthropic API key (for LiteLLM) | None |
| `OLLAMA_API_BASE` | Ollama server URL | `http://host.docker.internal:11434` |
| `OTEL_ENDPOINT` | OTLP endpoint for tracing | `http://vector:4317` |
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password | `spiderfoot` |

---

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](documentation/installation.md) | System requirements and setup |
| [Quick Start](documentation/quickstart.md) | Get scanning in minutes |
| [User Guide](documentation/user_guide.md) | Core concepts and usage |
| [API Reference](documentation/api_reference.md) | REST + GraphQL API docs |
| [Architecture Guide](documentation/ARCHITECTURE.md) | Microservices design |
| [Docker Deployment](documentation/docker_deployment.md) | Container deployment guide |
| [Module Guide](documentation/modules.md) | Understanding and writing modules |
| [Module Migration](documentation/MODULE_MIGRATION_GUIDE.md) | Migrating to ModernPlugin |
| [Correlation Rules](correlations/README.md) | YAML correlation engine reference |
| [Security Guide](documentation/security.md) | Authentication, hardening, audit |
| [Developer Guide](documentation/developer_guide.md) | Contributing and code structure |
| [FAQ](documentation/faq.md) | Frequently asked questions |
| [Troubleshooting](documentation/troubleshooting.md) | Common issues and solutions |

---

## Modules

SpiderFoot has **200+ modules**, most of which do not require API keys. Modules feed each other in a publisher/subscriber model for maximum data extraction.

### Module Categories

| Category | Examples | Count |
|----------|----------|-------|
| **DNS & Infrastructure** | DNS resolver, zone transfer, brute-force | ~20 |
| **Social Media** | Twitter, Instagram, Reddit, Telegram, TikTok | ~15 |
| **Threat Intelligence** | Shodan, VirusTotal, AlienVault, GreyNoise | ~30 |
| **Search Engines** | Google, Bing, DuckDuckGo, Baidu | ~10 |
| **Data Breaches** | HaveIBeenPwned, LeakCheck, Dehashed | ~10 |
| **Crypto & Blockchain** | Bitcoin, Ethereum, Tron, BNB | ~8 |
| **Reputation / Blacklists** | Spamhaus, SURBL, PhishTank, DNSBL | ~30 |
| **Internal Analysis** | Extractors, validators, identifiers | ~25 |
| **External Tools** | Nmap, DNSTwist, Nuclei, WhatWeb, CMSeeK | ~12 |
| **Cloud Storage** | S3, Azure Blob, Google Cloud, DigitalOcean | ~5 |

For the full module list, see [documentation/modules.md](documentation/modules.md).

---

## Correlation Engine

SpiderFoot includes a YAML-configurable rule engine with **37+ pre-defined correlation rules**.

```bash
# View all rules
ls correlations/*.yaml

# Template for writing new rules
cat correlations/template.yaml
```

Rule categories: vulnerability severity, exposure detection, cross-scan outliers, stale hosts, infrastructure analysis, blockchain risk aggregation.

See [correlations/README.md](correlations/README.md) for the full reference.

---

## Use Cases

### Offensive Security (Red Team / Pen Test)

- Target reconnaissance and attack surface mapping
- Sub-domain discovery and hijack detection
- Credential exposure discovery
- Technology stack fingerprinting

### Defensive Security (Blue Team)

- Asset inventory and shadow IT detection
- Data breach monitoring
- Brand protection and phishing detection
- Threat intelligence enrichment

### Scan Targets

IP addresses · domains · subdomains · hostnames · CIDR subnets · ASNs · email addresses · phone numbers · usernames · person names · Bitcoin/Ethereum addresses

---

## Development

### Project Structure

```
spiderfoot/
├── api/                  # FastAPI application
│   ├── graphql/          # Strawberry GraphQL (queries, mutations, subscriptions)
│   ├── routers/          # REST endpoint routers
│   ├── schemas.py        # Pydantic v2 contracts
│   └── versioning.py     # /api/v1/ prefix
├── agents/               # AI analysis agents (6 LLM-powered)
│   ├── base.py           # BaseAgent ABC + framework
│   ├── service.py        # FastAPI agent service (:8100)
│   ├── finding_validator.py
│   ├── credential_analyzer.py
│   ├── text_summarizer.py
│   ├── report_generator.py
│   ├── document_analyzer.py
│   └── threat_intel.py
├── enrichment/           # Document enrichment pipeline
│   ├── converter.py      # Multi-format document conversion
│   ├── extractor.py      # Entity/IOC regex extraction
│   ├── pipeline.py       # Convert → extract → store orchestrator
│   └── service.py        # FastAPI enrichment service (:8200)
├── user_input/           # User-defined input ingestion
│   └── service.py        # FastAPI user input service (:8300)
├── config/               # App configuration
├── db/                   # Database layer (repositories, migrations)
├── events/               # Event types, relay, dedup
├── plugins/              # Module loading and registry
├── security/             # Auth, CSRF, middleware
├── services/             # External integrations (embedding, cache, DNS)
├── observability/        # Logging, metrics, health, tracing
├── reporting/            # Report generation and export
├── data_service/         # HTTP/gRPC DataService clients
├── webui/                # CherryPy web UI
├── qdrant_client.py      # Qdrant vector store client
└── vector_correlation.py # Vector correlation engine
infra/                    # Infrastructure configs
├── grafana/              # Dashboards + datasource provisioning
├── loki/                 # Loki local config (MinIO S3 backend)
├── litellm/              # LiteLLM model config
└── prometheus/           # Scrape targets config
modules/                  # 200+ OSINT modules
correlations/             # 37+ YAML correlation rules
documentation/            # Comprehensive docs
scripts/                  # Utility and maintenance scripts
docker/                   # Docker build files + nginx config
helm/                     # Kubernetes Helm chart
```

### Running Tests

```bash
pip install -r requirements.txt
pytest --tb=short -q
```

### Version Management

```bash
cat VERSION                            # Check current version
python update_version.py --set 5.247.0 # Update all references
python update_version.py --check       # Validate consistency
```

---

## Community

Join the [Discord server](https://discord.gg/vyvztrG) for help, feature requests, or general OSINT discussion.

**Maintainer:** Poppopjmp <van1sh@van1shland.io>

---

## License

SpiderFoot is licensed under the [MIT License](LICENSE).

---

*Actively developed since 2012 — 200+ modules, 37+ correlation rules, 17-service Docker deployment with AI agents, document enrichment, and full observability.*
