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
    ...
```

*For full details, see the original Docker Deployment Guide in the old docs folder. This file is now the canonical version for SpiderFoot Docker deployment.*

---

Authored by poppopjmp
*Last updated: June 2025*
