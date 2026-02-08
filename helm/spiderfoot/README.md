# SpiderFoot Helm Chart

Kubernetes deployment for SpiderFoot OSINT automation platform.

## Prerequisites

- Kubernetes 1.25+
- Helm 3.x
- PV provisioner (for persistence)

## Quick Start

```bash
# Add chart (local)
helm install spiderfoot ./helm/spiderfoot

# With custom values
helm install spiderfoot ./helm/spiderfoot \
  --set postgresql.auth.password=mysecretpassword \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=spiderfoot.example.com

# Production with values file
helm install spiderfoot ./helm/spiderfoot \
  -f helm/spiderfoot/values-production.yaml
```

## Architecture

The chart deploys SpiderFoot as three separate components:

| Component | Purpose | Replicas |
|-----------|---------|----------|
| **WebUI** | Browser-based interface (CherryPy) | 1 |
| **API** | REST API (FastAPI) | 1 |
| **Scanner** | Scan worker processes | 2 (scalable) |

Supporting services:

| Service | Purpose |
|---------|---------|
| PostgreSQL | Primary database |
| Redis | Event bus + cache |
| Vector.dev | Log/event shipping (optional) |

## Configuration

### Key Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.tag` | SpiderFoot version | `5.14.0` |
| `scanner.replicaCount` | Scanner workers | `2` |
| `postgresql.auth.password` | DB password | `""` |
| `ingress.enabled` | Enable Ingress | `false` |
| `autoscaling.enabled` | HPA for scanners | `false` |
| `metrics.enabled` | Prometheus metrics | `false` |
| `config.authMethod` | Auth: none/api_key/basic/jwt | `none` |
| `config.eventBusBackend` | Event bus: memory/redis/nats | `redis` |

### Ingress

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: spiderfoot.example.com
      paths:
        - path: /
          pathType: Prefix
          service: webui
        - path: /api
          pathType: Prefix
          service: api
  tls:
    - secretName: spiderfoot-tls
      hosts:
        - spiderfoot.example.com
```

### Autoscaling

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
```

## Uninstall

```bash
helm uninstall spiderfoot
```
