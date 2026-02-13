# Docker Deployment Guide

This guide covers deploying SpiderFoot using Docker Compose with the full 10-service microservices stack.

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
| `http://localhost` | Web UI (via Nginx) |
| `http://localhost/api/docs` | Swagger / OpenAPI |
| `http://localhost/api/graphql` | GraphiQL IDE |
| `http://localhost:9001` | MinIO Console (admin/minioadmin) |

---

## Service Architecture

The stack runs **10 containers** across two Docker networks:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| **sf-nginx** | nginx:alpine | 80 / 443 | Reverse proxy, TLS, rate limiting |
| **sf-api** | spiderfoot | 8001 | FastAPI REST + GraphQL API |
| **sf-webui** | spiderfoot | 5001 | CherryPy web UI |
| **sf-postgres** | postgres:16 | 5432 | Primary relational store |
| **sf-redis** | redis:7-alpine | 6379 | EventBus, cache, sessions |
| **sf-qdrant** | qdrant/qdrant | 6333 | Vector similarity search |
| **sf-minio** | minio/minio | 9000 / 9001 | S3-compatible object storage |
| **sf-vector** | timberio/vector | 8686 | Log collection pipeline |
| **sf-pg-backup** | spiderfoot | — | Cron sidecar for pg_dump → MinIO |
| **sf-minio-init** | minio/mc | — | One-shot bucket creation |

### Networks

- **sf-frontend** — Browser-facing (Nginx, WebUI, API)
- **sf-backend** — Internal only (PostgreSQL, Redis, Qdrant, MinIO)

### Volumes

| Volume | Service | Purpose |
|--------|---------|---------|
| `sf-postgres-data` | sf-postgres | Database files |
| `sf-redis-data` | sf-redis | RDB/AOF persistence |
| `sf-qdrant-data` | sf-qdrant | Vector index storage |
| `sf-minio-data` | sf-minio | Object store files |
| `sf-vector-data` | sf-vector | Log buffer / checkpoints |
| `sf-api-data` | sf-api | Application state |
| `sf-webui-data` | sf-webui | Session / cache |

---

## MinIO Object Storage

Five buckets are auto-created by `sf-minio-init` on first boot:

| Bucket | Contents |
|--------|----------|
| `sf-logs` | Vector.dev log archive |
| `sf-reports` | Generated scan reports (HTML, PDF, JSON, CSV) |
| `sf-pg-backups` | PostgreSQL daily pg_dump files |
| `sf-qdrant` | Qdrant vector DB snapshots |
| `sf-data` | General artefacts |

Access the MinIO Console at `http://localhost:9001` (default credentials: `minioadmin` / `minioadmin`).

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

To enable TLS, place your certificate and key files and configure Nginx:

```bash
# Generate a self-signed cert (testing)
./generate-certificate

# Mount certs in docker-compose override
# See docker/nginx/ for template configurations
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

For production deployments, consider the Helm chart in `helm/` for Kubernetes.

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Port 80 in use | Change Nginx port mapping in compose file |
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
# Access via MinIO Console at http://localhost:9001
```
