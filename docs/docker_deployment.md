# Docker Deployment Guide

This guide covers deploying SpiderFoot using Docker for both development and production environments.

## Quick Start

### Using Docker Hub Image

```bash
# Pull and run SpiderFoot
docker run -d -p 5001:5001 --name spiderfoot spiderfoot/spiderfoot

# Access web interface
open http://localhost:5001
```

### With Persistent Data

```bash
# Create data directory
mkdir spiderfoot-data

# Run with volume mount
docker run -d -p 5001:5001 \
  -v $(pwd)/spiderfoot-data:/var/lib/spiderfoot/data \
  --name spiderfoot \
  spiderfoot/spiderfoot
```

## Building from Source

### Basic Build

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 spiderfoot && \
    chown -R spiderfoot:spiderfoot /app
USER spiderfoot

# Expose port
EXPOSE 5001

# Start SpiderFoot
CMD ["python", "sf.py", "-l", "0.0.0.0:5001"]
```

### Build and Run

```bash
# Build image
docker build -t spiderfoot:local .

# Run container
docker run -d -p 5001:5001 --name spiderfoot spiderfoot:local
```

## Production Deployment

### Multi-Stage Build

```dockerfile
# Multi-stage Dockerfile for production
FROM python:3.9-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.9-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    dumb-init \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 spiderfoot && \
    mkdir -p /var/lib/spiderfoot/data && \
    chown -R spiderfoot:spiderfoot /app /var/lib/spiderfoot
USER spiderfoot

# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5001/ || exit 1

# Expose port
EXPOSE 5001

# Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "sf.py", "-l", "0.0.0.0:5001", "-d", "/var/lib/spiderfoot/data/spiderfoot.db"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  spiderfoot:
    build: .
    ports:
      - "5001:5001"
    volumes:
      - spiderfoot-data:/var/lib/spiderfoot/data
      - ./config:/app/config:ro
    environment:
      - SPIDERFOOT_WEB_ADDR=0.0.0.0
      - SPIDERFOOT_WEB_PORT=5001
      - SPIDERFOOT_DATABASE=/var/lib/spiderfoot/data/spiderfoot.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - spiderfoot
    restart: unless-stopped

volumes:
  spiderfoot-data:
```

### Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream spiderfoot {
        server spiderfoot:5001;
    }

    server {
        listen 80;
        server_name spiderfoot.example.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name spiderfoot.example.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS;

        location / {
            proxy_pass http://spiderfoot;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

## Container Configuration

### Environment Variables

```bash
# Core configuration
SPIDERFOOT_WEB_ADDR=0.0.0.0
SPIDERFOOT_WEB_PORT=5001
SPIDERFOOT_DATABASE=/var/lib/spiderfoot/data/spiderfoot.db

# API keys
SPIDERFOOT_VIRUSTOTAL_API_KEY=your_virustotal_key
SPIDERFOOT_SHODAN_API_KEY=your_shodan_key
SPIDERFOOT_HUNTER_API_KEY=your_hunter_key

# Performance settings
SPIDERFOOT_MAX_CONCURRENT_SCANS=5
SPIDERFOOT_SCAN_TIMEOUT=3600

# Security settings
SPIDERFOOT_AUTHENTICATION=true
SPIDERFOOT_USERNAME=admin
SPIDERFOOT_PASSWORD=secure_password
```

### Volume Mounts

```bash
# Data persistence
-v spiderfoot-data:/var/lib/spiderfoot/data

# Configuration
-v ./spiderfoot.conf:/app/spiderfoot.conf:ro

# Logs
-v ./logs:/var/log/spiderfoot

# SSL certificates
-v ./ssl:/etc/ssl/spiderfoot:ro
```

## Security Hardening

### Secure Container

```dockerfile
# Security-hardened Dockerfile
FROM python:3.9-alpine

# Install security updates
RUN apk update && apk upgrade

# Install minimal required packages
RUN apk add --no-cache \
    dumb-init \
    curl

WORKDIR /app

# Create non-root user
RUN addgroup -g 1000 spiderfoot && \
    adduser -D -u 1000 -G spiderfoot spiderfoot

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=spiderfoot:spiderfoot . .

# Set secure permissions
RUN chmod -R 755 /app && \
    chmod 700 /app/spiderfoot.conf

USER spiderfoot

# Security labels
LABEL security.non-root=true
LABEL security.no-new-privileges=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:5001/ || exit 1

EXPOSE 5001

ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "sf.py", "-l", "0.0.0.0:5001"]
```

### Run with Security Options

```bash
docker run -d \
  --name spiderfoot \
  --user 1000:1000 \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  --cap-add=NET_BIND_SERVICE \
  --read-only \
  --tmpfs /tmp:noexec,nosuid,size=100m \
  -v spiderfoot-data:/var/lib/spiderfoot/data \
  -p 5001:5001 \
  spiderfoot:latest
```

## Scaling and High Availability

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  spiderfoot:
    build: .
    environment:
      - SPIDERFOOT_WEB_ADDR=0.0.0.0
      - SPIDERFOOT_WEB_PORT=5001
    volumes:
      - spiderfoot-data:/var/lib/spiderfoot/data
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
        max_attempts: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - spiderfoot
    deploy:
      replicas: 1

volumes:
  spiderfoot-data:
```

### Load Balancer Configuration

```nginx
# nginx-lb.conf
upstream spiderfoot_backend {
    least_conn;
    server spiderfoot_1:5001 max_fails=3 fail_timeout=30s;
    server spiderfoot_2:5001 max_fails=3 fail_timeout=30s;
    server spiderfoot_3:5001 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://spiderfoot_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Health check
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    }
}
```

## Monitoring and Logging

### Container Monitoring

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  spiderfoot:
    build: .
    # ... other configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  grafana-data:
```

### Log Aggregation

```yaml
# ELK Stack integration
version: '3.8'

services:
  spiderfoot:
    build: .
    logging:
      driver: "fluentd"
      options:
        fluentd-address: "localhost:24224"
        tag: "spiderfoot"

  fluentd:
    image: fluent/fluentd:v1.14-debian
    ports:
      - "24224:24224"
    volumes:
      - ./fluentd.conf:/fluentd/etc/fluent.conf

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.15.0
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"

  kibana:
    image: docker.elastic.co/kibana/kibana:7.15.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

## Backup and Recovery

### Data Backup

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/spiderfoot"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup container data
docker run --rm \
  -v spiderfoot-data:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/spiderfoot_data_$DATE.tar.gz -C /data .

# Backup configuration
docker cp spiderfoot:/app/spiderfoot.conf $BACKUP_DIR/spiderfoot_conf_$DATE.conf

# Clean old backups (keep 7 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

### Disaster Recovery

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

# Stop running container
docker stop spiderfoot
docker rm spiderfoot

# Restore data
docker run --rm \
  -v spiderfoot-data:/data \
  -v $(dirname $BACKUP_FILE):/backup \
  alpine tar xzf /backup/$(basename $BACKUP_FILE) -C /data

# Start new container
docker-compose up -d spiderfoot
```

## Development Workflow

### Development Environment

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  spiderfoot-dev:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "5001:5001"
    volumes:
      - .:/app
      - dev-data:/var/lib/spiderfoot/data
    environment:
      - FLASK_DEBUG=1
      - SPIDERFOOT_LOG_LEVEL=DEBUG
    command: python sf.py -l 0.0.0.0:5001

volumes:
  dev-data:
```

### Development Dockerfile

```dockerfile
# Dockerfile.dev
FROM python:3.9-slim

WORKDIR /app

# Install development dependencies
RUN apt-get update && apt-get install -y \
    git \
    vim \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

# Create non-root user
RUN useradd -m -u 1000 spiderfoot
USER spiderfoot

EXPOSE 5001

CMD ["python", "sf.py", "-l", "0.0.0.0:5001"]
```

## Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check container logs
docker logs spiderfoot

# Check resource usage
docker stats spiderfoot

# Verify port availability
netstat -tlnp | grep 5001
```

#### Permission Issues
```bash
# Fix volume permissions
docker run --rm -v spiderfoot-data:/data alpine chown -R 1000:1000 /data

# Check container user
docker exec spiderfoot id
```

#### Network Connectivity
```bash
# Test container network
docker exec spiderfoot curl -I http://google.com

# Check DNS resolution
docker exec spiderfoot nslookup google.com
```

### Performance Tuning

```bash
# Resource limits
docker run -d \
  --memory=2g \
  --cpus=2.0 \
  --name spiderfoot \
  spiderfoot:latest

# Monitoring resource usage
docker stats --no-stream spiderfoot
```

For more advanced deployment scenarios, see [Performance Tuning](performance_tuning.md) and [Security Considerations](security_considerations.md).
