# Docker Deployment Guide

This guide covers deploying SpiderFoot using Docker Compose with **profile-based** service activation. Start with just the 5 core services, then enable additional profiles as needed.

---

## Quick Start

```bash
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Copy and configure environment
cp .env.example .env
# Edit .env — change passwords, uncomment profile sections as needed

# Core only (5 services)
docker compose -f docker-compose.yml up --build -d

# Full stack (all services except SSO)
docker compose -f docker-compose.yml --profile full up --build -d

# View logs
docker compose -f docker-compose.yml logs -f

# Stop everything
docker compose -f docker-compose.yml down
```

### Access Points

**Core (no profile)** — `http://localhost:3000`:

| URL | Service |
|-----|---------|
| `http://localhost:3000` | React SPA |
| `http://localhost:3000/api/docs` | Swagger / OpenAPI |

**Full stack (`--profile full`)** — `https://localhost` via Traefik:

| URL | Service |
|-----|---------|
| `https://localhost` | React SPA (via Traefik) |
| `https://localhost/api/docs` | Swagger / OpenAPI |
| `https://localhost/api/graphql` | GraphiQL IDE |
| `https://localhost/flower/` | Celery Flower Monitoring |
| `https://localhost/grafana/` | Grafana Dashboards |
| `https://localhost/minio/` | MinIO Console |
| `https://localhost/traefik/` | Traefik Dashboard |

---

## Docker Compose Profiles

Services are organized into **profiles** — activate only what you need:

| Profile | Services | Description |
|---------|----------|-------------|
| *(core)* | postgres, redis, api, celery-worker, frontend | Always starts — minimal working set |
| `scan` | celery-worker-active | Active recon tools (nmap, nuclei, httpx, …) |
| `proxy` | traefik, docker-socket-proxy | Reverse proxy + TLS termination |
| `storage` | minio, minio-init, qdrant, tika, pg-backup | Object storage, vector DB, document parsing |
| `monitor` | vector, loki, grafana, prometheus, jaeger | Full observability stack |
| `ai` | agents, litellm | AI analysis agents + LLM gateway |
| `scheduler` | celery-beat, flower | Periodic tasks + Celery monitoring |
| `sso` | keycloak | OIDC / SAML identity provider |
| `full` | *all of the above except SSO* | Complete deployment |

```bash
# Mix and match profiles
docker compose -f docker-compose.yml --profile proxy --profile storage up -d

# Full stack + SSO
docker compose -f docker-compose.yml --profile full --profile sso up -d
```

---

## Service Architecture

The stack uses two Docker networks (`sf-frontend`, `sf-backend`) and organizes services by profile:

### Core Services (always running)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **sf-postgres** | postgres:15-alpine | 5432 | Primary relational data store |
| **sf-redis** | redis:7-alpine | 6379 | EventBus pub/sub, caching, Celery broker |
| **sf-api** | spiderfoot-micro | 8001 | FastAPI REST + GraphQL API |
| **sf-celery-worker** | spiderfoot-micro | — | Celery distributed task workers |
| **sf-frontend-ui** | spiderfoot-frontend | 3000 | React SPA served by Nginx |

### Profile Services

| Service | Profile | Image | Port | Purpose |
|---------|---------|-------|------|---------|
| **sf-celery-worker-active** | `scan` | spiderfoot-active | — | Active scanning (33+ recon tools) |
| **sf-traefik** | `proxy` | traefik:v3 | 443 | Reverse proxy, auto-TLS, routing |
| **sf-docker-proxy** | `proxy` | tecnativa/docker-socket-proxy | — | Secure Docker API access |
| **sf-minio** | `storage` | minio/minio | 9000 | S3-compatible object storage |
| **sf-minio-init** | `storage` | minio/mc | — | One-shot bucket creation |
| **sf-qdrant** | `storage` | qdrant/qdrant | 6333 | Vector similarity search |
| **sf-tika** | `storage` | apache/tika | 9998 | Document parsing (PDF, DOCX, etc.) |
| **sf-pg-backup** | `storage` | postgres:15-alpine | — | Cron sidecar: pg_dump → MinIO |
| **sf-vector** | `monitor` | timberio/vector | 8686 | Telemetry pipeline |
| **sf-loki** | `monitor` | grafana/loki | 3100 | Log aggregation |
| **sf-grafana** | `monitor` | grafana/grafana | 3000 | Dashboards & alerting |
| **sf-prometheus** | `monitor` | prom/prometheus | 9090 | Metrics collection |
| **sf-jaeger** | `monitor` | jaegertracing/jaeger | 16686 | Distributed tracing |
| **sf-agents** | `ai` | spiderfoot-micro | 8100 | 6 AI-powered analysis agents |
| **sf-litellm** | `ai` | ghcr.io/berriai/litellm | 4000 | Unified LLM proxy |
| **sf-celery-beat** | `scheduler` | spiderfoot-micro | — | Periodic task scheduler |
| **sf-flower** | `scheduler` | spiderfoot-micro | 5555 | Celery monitoring dashboard |
| **sf-keycloak** | `sso` | keycloak | 9080 | OIDC / SAML identity provider |

### Networks

- **sf-frontend** — Browser-facing (Traefik, Frontend, API)
- **sf-backend** — Internal only (PostgreSQL, Redis, Qdrant, MinIO)

### Volumes

| Volume | Service | Purpose |
|--------|---------|---------|
| `postgres-data` | sf-postgres | Database files |
| `redis-data` | sf-redis | RDB/AOF persistence |
| `qdrant-data` | sf-qdrant | Vector index storage |
| `minio-data` | sf-minio | Object store files |
| `vector-data` | sf-vector | Log buffer / checkpoints |
| `grafana-data` | sf-grafana | Dashboard state |
| `prometheus-data` | sf-prometheus | Metrics TSDB |
| `traefik-logs` | sf-traefik | Access logs |

---

## MinIO Object Storage

Seven buckets are auto-created by `sf-minio-init` on first boot:

| Bucket | Contents |
|--------|----------|
| `sf-logs` | Vector.dev log archive |
| `sf-reports` | Generated scan reports (HTML, PDF, JSON, CSV) |
| `sf-pg-backups` | PostgreSQL daily pg_dump files |
| `sf-qdrant-snapshots` | Qdrant vector DB snapshots |
| `sf-data` | General artefacts |
| `sf-loki-data` | Loki log chunk storage |
| `sf-loki-ruler` | Loki alerting rules |

Access the MinIO Console at `https://localhost/minio/` (requires `proxy` + `storage` profiles; default credentials: `minioadmin` / `minioadmin`).

---

## Qdrant Vector Search

Qdrant runs on port 6333 and stores embeddings for semantic OSINT event search. Collections are prefixed with `sf_`.

The GraphQL API exposes `semanticSearch` and `vectorCollections` queries for searching and inspecting vector data.

---

## Configuration

Copy `.env.example` to `.env` and customise:

```bash
cp .env.example .env
# Uncomment profile-specific sections when activating profiles
```

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SF_DEPLOYMENT_MODE` | `microservices` | Service mode |
| `SF_DATABASE_URL` | `postgresql://...` | PostgreSQL connection |
| `SF_REDIS_URL` | `redis://sf-redis:6379` | Redis connection |
| `SF_QDRANT_HOST` | `sf-qdrant` | Qdrant hostname |
| `SF_MINIO_ENDPOINT` | `sf-minio:9000` | MinIO endpoint |
| `SF_MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `SF_MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `SF_EMBEDDING_PROVIDER` | `mock` | Embedding backend |
| `SF_LOG_FORMAT` | `json` | Log format |

---

## TLS / HTTPS

TLS requires the `proxy` profile (Traefik). To enable:

```bash
# Generate a self-signed cert (testing)
./generate-certificate

# Start with proxy profile
docker compose -f docker-compose.yml --profile proxy up -d

# Traefik auto-discovers TLS certificates from the mounted certs directory
```

---

## Health Checks

All services include Docker `HEALTHCHECK` directives. Monitor with:

```bash
# Check all service health
docker compose -f docker-compose.yml ps

# Detailed health for one service
docker inspect --format='{{json .State.Health}}' sf-api
```

API health endpoint: `GET /api/health`

---

## PostgreSQL Backups

The `sf-pg-backup` sidecar runs `pg_dump` on a cron schedule and uploads backups to the `sf-pg-backups` MinIO bucket.

```bash
# List backups
curl http://localhost/api/storage/buckets/sf-pg-backups

# Manual backup trigger
docker exec sf-pg-backup /scripts/pg_backup_minio.sh
```

---

## Scaling

For horizontal scaling, increase replicas of stateless services:

```bash
docker compose -f docker-compose.yml up -d --scale sf-api=3
```

### Active Scan Worker Scaling

The active scan worker requires the `scan` profile. Scale independently:

```bash
docker compose -f docker-compose.yml --profile scan up -d --scale celery-worker-active=3
```

Each instance competes for tasks from the `scan` queue via Celery's fair scheduling.
See [Active Scan Worker Guide](active-scan-worker.md) for full details on the 33+ tools,
resource requirements, and security considerations.

For production deployments, consider the Helm chart in `helm/` for Kubernetes.

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Port 443 in use | Change Traefik port mapping in compose file |
| MinIO init fails | Check `sf-minio` is healthy before `sf-minio-init` runs |
| Qdrant OOM | Increase memory limit for `sf-qdrant` service |
| DB connection refused | Wait for `sf-postgres` healthcheck to pass |
| GraphQL not loading | Check `sf-api` logs: `docker logs sf-api` |

### Viewing Logs

```bash
# All services
docker compose -f docker-compose.yml logs -f

# Specific service
docker logs -f sf-api

# Archived logs in MinIO
# Access via MinIO Console at https://localhost/minio/
```

