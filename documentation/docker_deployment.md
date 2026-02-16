# Docker Deployment Guide

This guide covers deploying SpiderFoot using Docker Compose with the full 21-service microservices stack, including the optional **active scan worker** with 33+ external recon tools.

---

## Quick Start

```bash
git clone https://github.com/poppopjmp/spiderfoot.git
cd spiderfoot

# Start the full stack
docker compose -f docker-compose-microservices.yml up --build -d

# View logs
docker compose -f docker-compose-microservices.yml logs -f

# Stop everything
docker compose -f docker-compose-microservices.yml down
```

### Access Points

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

## Service Architecture

The stack runs **21 containers** across two Docker networks:

| Service | Image | Port | Purpose |
|---------|-------|------|--------|
| **sf-traefik** | traefik:v3 | 443 | Reverse proxy, auto-TLS, routing, rate limiting |
| **sf-docker-proxy** | tecnativa/docker-socket-proxy | — | Secure Docker API access for Traefik |
| **sf-frontend-ui** | spiderfoot-frontend | 80 | React SPA served by Nginx |
| **sf-api** | spiderfoot-micro | 8001 | FastAPI REST + GraphQL API |
| **sf-agents** | spiderfoot-micro | 8100 | 6 AI-powered analysis agents |
| **sf-celery-worker** | spiderfoot-micro | — | Celery distributed task workers |
| **sf-celery-beat** | spiderfoot-micro | — | Celery periodic task scheduler |
| **sf-flower** | spiderfoot-micro | 5555 | Celery monitoring dashboard |
| **sf-tika** | apache/tika | 9998 | Document parsing (PDF, DOCX, XLSX, etc.) |
| **sf-litellm** | ghcr.io/berriai/litellm | 4000 | Unified LLM proxy (OpenAI, Anthropic, Ollama) |
| **sf-postgres** | postgres:15-alpine | 5432 | Primary relational store |
| **sf-redis** | redis:7-alpine | 6379 | EventBus, cache, Celery broker |
| **sf-qdrant** | qdrant/qdrant | 6333 | Vector similarity search |
| **sf-minio** | minio/minio | 9000 / 9001 | S3-compatible object storage |
| **sf-vector** | timberio/vector | 8686 | Telemetry pipeline |
| **sf-loki** | grafana/loki | 3100 | Log aggregation |
| **sf-grafana** | grafana/grafana | 3000 | Dashboards, alerting, data exploration |
| **sf-prometheus** | prom/prometheus | 9090 | Metrics collection |
| **sf-jaeger** | jaegertracing/jaeger | 16686 | Distributed tracing UI |
| **sf-pg-backup** | postgres:15-alpine | — | Cron sidecar for pg_dump → MinIO |
| **sf-minio-init** | minio/mc | — | One-shot bucket creation |
| **sf-celery-worker-active** | spiderfoot-active | — | Active scan worker (33+ tools) |

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

Access the MinIO Console at `https://localhost/minio/` (default credentials: `minioadmin` / `minioadmin`).

---

## Qdrant Vector Search

Qdrant runs on port 6333 and stores embeddings for semantic OSINT event search. Collections are prefixed with `sf_`.

The GraphQL API exposes `semanticSearch` and `vectorCollections` queries for searching and inspecting vector data.

---

## Configuration

Copy `docker/env.example` to `.env` and customise:

```bash
cp docker/env.example .env
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

To enable TLS, Traefik handles certificate management automatically:

```bash
# Generate a self-signed cert (testing)
./generate-certificate

# Traefik auto-discovers TLS certificates from the mounted certs directory
# See docker-compose-microservices.yml for Traefik TLS configuration
```

---

## Health Checks

All services include Docker `HEALTHCHECK` directives. Monitor with:

```bash
# Check all service health
docker compose -f docker-compose-microservices.yml ps

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
docker compose -f docker-compose-microservices.yml up -d --scale sf-api=3
```

### Active Scan Worker Scaling

Scale the active scan worker independently for more concurrent scanning capacity:

```bash
docker compose -f docker-compose-microservices.yml up -d --scale celery-worker-active=3
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
docker compose -f docker-compose-microservices.yml logs -f

# Specific service
docker logs -f sf-api

# Archived logs in MinIO
# Access via MinIO Console at https://localhost/minio/
```
