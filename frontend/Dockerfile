# =============================================================================
# SpiderFoot React SPA — Self-Contained Frontend
# Multi-stage build: Node (build) → Nginx (serve)
#
# The SPA talks to the API server via /api/* which Nginx reverse-proxies
# to the backend API container (configurable via SF_API_URL at runtime).
#
# Build:
#   docker build -t spiderfoot-frontend:latest ./frontend
#
# Run standalone:
#   docker run -p 3000:80 -e SF_API_URL=http://host.docker.internal:8001 spiderfoot-frontend:latest
# =============================================================================

# ---------- Stage 1: Build ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first (layer caching)
COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* ./
RUN npm ci --prefer-offline --no-audit --no-fund 2>/dev/null || npm install --prefer-offline --no-audit --no-fund

# Copy source & build
COPY . .

# Override the outDir so Vite builds into /app/dist (not ../spiderfoot/static/react)
RUN npx vite build --outDir dist

# ---------- Stage 2: Serve ----------
FROM nginx:1.27-alpine

# Install envsubst for runtime config injection
RUN apk add --no-cache gettext

# Remove default site
RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy Nginx config template (uses $SF_API_URL placeholder)
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Runtime env defaults — injected into Nginx config via envsubst
ENV SF_API_URL=http://api:8001
ENV SF_WS_URL=http://api:8001
ENV SF_AGENTS_URL=http://sf-agents:8100

# ── Security hardening ────────────────────────────────────────────────────
# Remove apk and other package managers to prevent in-container installs
RUN apk --no-cache del apk-tools 2>/dev/null || true

# Create non-root nginx user directories and fix ownership
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx && \
    chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx && \
    chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /etc/nginx/conf.d && \
    chown -R nginx:nginx /etc/nginx/templates

# NOTE: We intentionally do NOT set USER nginx here.
# The nginx Docker entrypoint must run as root to do envsubst template
# processing. Nginx itself drops worker processes to the nginx user via
# the `user nginx;` directive in nginx.conf.
# With read_only: true + tmpfs mounts, running USER nginx breaks envsubst.

EXPOSE 80

# Nginx (PID 1) — template processing happens automatically via
# nginx docker image's entrypoint (20-envsubst-on-templates.sh)
CMD ["nginx", "-g", "daemon off;"]
