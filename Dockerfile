# =============================================================================
# SpiderFoot — Convenience Dockerfile (delegates to docker/Dockerfile.base)
# =============================================================================
# For the full microservice image hierarchy, use docker/build.sh or build
# individual images with the Dockerfiles in docker/:
#
#   docker/Dockerfile.base           → spiderfoot-base
#   docker/Dockerfile.api            → spiderfoot-api
#   docker/Dockerfile.scanner        → spiderfoot-scanner  (passive Celery worker)
#   docker/Dockerfile.active-scanner → spiderfoot-active-scanner (scan worker + recon tools)
#   frontend/Dockerfile              → spiderfoot-frontend  (React SPA / Nginx)
#
# This file builds the API image directly for backwards compatibility:
#   docker build -t spiderfoot .
# =============================================================================

# ── Stage 1: Build Python dependencies ──────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential libxml2-dev libxslt-dev libjpeg-dev \
    zlib1g-dev libffi-dev libssl-dev python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --no-cache-dir -U pip==25.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

LABEL maintainer="Van1sh  <van1sh@van1shland.io>" \
      org.opencontainers.image.title="SpiderFoot" \
      org.opencontainers.image.description="OSINT automation platform — API service" \
      org.opencontainers.image.source="https://github.com/poppopjmp/spiderfoot" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 libjpeg62-turbo zlib1g \
    dnsutils ca-certificates curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV SPIDERFOOT_DATA=/home/spiderfoot/data \
    SPIDERFOOT_LOGS=/home/spiderfoot/logs \
    SPIDERFOOT_CACHE=/home/spiderfoot/cache \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/home/spiderfoot" \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV="/opt/venv" \
    SF_SERVICE_ROLE=api

RUN addgroup --system spiderfoot && \
    adduser --system --ingroup spiderfoot --home /home/spiderfoot \
            --shell /usr/sbin/nologin --gecos "SpiderFoot User" spiderfoot

WORKDIR /home/spiderfoot

# Copy application source (selective COPY for smaller image / better caching)
COPY --chown=spiderfoot:spiderfoot spiderfoot/   spiderfoot/
COPY --chown=spiderfoot:spiderfoot modules/      modules/
COPY --chown=spiderfoot:spiderfoot correlations/  correlations/
COPY --chown=spiderfoot:spiderfoot sfapi.py      sfapi.py
COPY --chown=spiderfoot:spiderfoot VERSION       VERSION
COPY --chown=spiderfoot:spiderfoot setup.py      setup.py
COPY --chown=spiderfoot:spiderfoot setup.cfg     setup.cfg
COPY --chown=spiderfoot:spiderfoot config/       config/

COPY --chown=root:root docker-entrypoint.sh /usr/local/bin/
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

RUN mkdir -p /home/spiderfoot/data /home/spiderfoot/logs \
             /home/spiderfoot/cache /home/spiderfoot/.spiderfoot/logs && \
    touch /home/spiderfoot/__init__.py /home/spiderfoot/modules/__init__.py && \
    chown -R spiderfoot:spiderfoot /home/spiderfoot

USER spiderfoot

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "sfapi.py", "-H", "0.0.0.0", "-p", "8001"]