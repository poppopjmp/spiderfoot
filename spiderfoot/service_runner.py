#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         service_runner
# Purpose:      Unified entry point for running SpiderFoot as individual
#               microservices (scanner, api, webui) or as a monolith.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Service Runner

Run individual SpiderFoot services for microservice deployment:

    python -m spiderfoot.service_runner --service scanner --port 5003
    python -m spiderfoot.service_runner --service api --port 8001
    python -m spiderfoot.service_runner --service webui --port 5001
    python -m spiderfoot.service_runner --service all  # monolith mode

Environment variables:
    SF_SERVICE           Service to run (scanner|api|webui|all)
    SF_REDIS_URL         Redis connection URL
    SF_POSTGRES_DSN      PostgreSQL DSN
    SF_VECTOR_ENDPOINT   Vector.dev HTTP source endpoint
    SF_LOG_LEVEL         Log level (DEBUG|INFO|WARNING|ERROR)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from spiderfoot.logging_config import LOG_FORMAT_TEXT

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

log = logging.getLogger("spiderfoot.service_runner")


# ---------------------------------------------------------------------------
# Health check HTTP server (lightweight, runs in every service container)
# ---------------------------------------------------------------------------

class _HealthStatus:
    """Shared health state for the running service."""

    def __init__(self) -> None:
        self.ready = False
        self.service_name = "unknown"
        self.started_at = time.time()
        self.details: dict = {}

    def to_dict(self) -> dict:
        return {
            "service": self.service_name,
            "status": "ok" if self.ready else "starting",
            "uptime": round(time.time() - self.started_at, 1),
            "details": self.details,
        }


_health = _HealthStatus()


class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for /health, /healthz, /metrics endpoints."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/healthz", "/ping"):
            payload = json.dumps(_health.to_dict()).encode()
            code = 200 if _health.ready else 503
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/metrics":
            from spiderfoot.metrics import get_registry
            payload = get_registry().expose().encode()
            self.send_response(200)
            self.send_header("Content-Type",
                             "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # silence health-check logs


def _start_health_server(port: int) -> HTTPServer:
    """Start a background health check HTTP server."""
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True, name="health")
    t.start()
    log.info("Health endpoint on :%d", port)
    return server


# ---------------------------------------------------------------------------
# Service configuration from environment
# ---------------------------------------------------------------------------

def _build_sf_config() -> dict:
    """Build SpiderFoot configuration dict from environment variables."""
    config: dict = {}

    # Redis
    redis_url = os.environ.get("SF_REDIS_URL", "")
    if redis_url:
        config["_eventbus_backend"] = "redis"
        config["_eventbus_redis_url"] = redis_url
        config["_cache_backend"] = "redis"
        config["_cache_redis_url"] = redis_url

    # PostgreSQL
    pg_dsn = os.environ.get("SF_POSTGRES_DSN", "")
    if pg_dsn:
        config["_dataservice_backend"] = "http"  # remote data service
        config["_dataservice_url"] = pg_dsn

    # Vector.dev
    vector_ep = os.environ.get("SF_VECTOR_ENDPOINT", "")
    if vector_ep:
        config["_vector_enabled"] = "1"
        config["_vector_endpoint"] = vector_ep

    # Scanner settings
    config["_scheduler_max_scans"] = os.environ.get("SF_SCANNER_MAX_SCANS", "3")
    config["_worker_max"] = os.environ.get("SF_WORKER_MAX", "8")
    config["_worker_strategy"] = os.environ.get("SF_WORKER_STRATEGY", "thread")

    return config


# ---------------------------------------------------------------------------
# Service launchers
# ---------------------------------------------------------------------------

def _run_scanner(port: int, config: dict) -> None:
    """Run the Scanner service (ScanScheduler + WorkerPool)."""
    _health.service_name = "scanner"

    from spiderfoot.scan_scheduler import ScanScheduler, SchedulerConfig
    from spiderfoot.worker_pool import WorkerPool, WorkerPoolConfig
    from spiderfoot.service_registry import initialize_services

    initialize_services(config)

    scheduler_cfg = SchedulerConfig.from_sf_config(config)
    scheduler = ScanScheduler(scheduler_cfg)

    pool_cfg = WorkerPoolConfig.from_sf_config(config)
    pool = WorkerPool(pool_cfg)

    _health.ready = True
    _health.details = {
        "scheduler": scheduler.stats(),
        "worker_pool": pool.stats(),
    }

    log.info("Scanner service ready (max_scans=%d, workers=%d)",
             scheduler_cfg.max_concurrent_scans,
             pool_cfg.effective_max_workers)

    # Keep alive
    shutdown_event = threading.Event()

    def _sig_handler(signum, frame):
        log.info("Received signal %d, shutting down scanner", signum)
        scheduler.shutdown()
        pool.shutdown()
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    shutdown_event.wait()


def _run_api(port: int, config: dict) -> None:
    """Run the FastAPI REST API service."""
    _health.service_name = "api"

    try:
        import uvicorn
    except ImportError:
        log.error("uvicorn is required for the API service")
        sys.exit(1)

    _health.ready = True
    log.info("Starting API service on port %d", port)

    uvicorn.run(
        "spiderfoot.api.main:app",
        host=os.environ.get("SF_API_HOST", "0.0.0.0"),
        port=port,
        workers=int(os.environ.get("SF_API_WORKERS", "4")),
        log_level=os.environ.get("SF_LOG_LEVEL", "info").lower(),
        access_log=True,
    )


def _run_webui(port: int, config: dict) -> None:
    """Run the CherryPy Web UI service."""
    _health.service_name = "webui"
    _health.ready = True

    log.info("Starting WebUI service on port %d", port)

    # Re-use existing sf.py startup path in webui mode
    sys.argv = [
        "sf.py",
        "-l", f"0.0.0.0:{port}",
    ]

    from sf import main as sf_main
    sf_main()


def _run_all(port: int, config: dict) -> None:
    """Run all services in a single process (monolith mode)."""
    _health.service_name = "monolith"
    _health.ready = True

    log.info("Running in monolith mode (all services)")

    sys.argv = [
        "sf.py",
        "--both",
        "-l", f"0.0.0.0:{port}",
        "--api-listen", f"0.0.0.0:8001",
    ]

    from sf import main as sf_main
    sf_main()


_SERVICE_MAP = {
    "scanner": _run_scanner,
    "api": _run_api,
    "webui": _run_webui,
    "all": _run_all,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SpiderFoot Microservice Runner",
    )
    parser.add_argument(
        "--service", "-s",
        choices=list(_SERVICE_MAP.keys()),
        default=os.environ.get("SF_SERVICE", "all"),
        help="Service to run (default: all)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.environ.get("SF_PORT", "5001")),
        help="Main service port",
    )
    parser.add_argument(
        "--health-port",
        type=int,
        default=None,
        help="Health check port (defaults to service port for scanner, "
             "separate port for api/webui)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("SF_LOG_LEVEL", "INFO"),
        help="Log level",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format=LOG_FORMAT_TEXT,
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    log.info("SpiderFoot Service Runner — service=%s port=%d", args.service, args.port)

    # Build config from env
    sf_config = _build_sf_config()

    # Start health check server
    health_port = args.health_port
    if health_port is None:
        # For scanner, health runs on the service port itself
        # For api/webui, pick a sidecar port
        if args.service == "scanner":
            health_port = args.port
        else:
            health_port = args.port + 1000  # e.g. 8001 -> 9001
    _start_health_server(health_port)

    # Run the selected service
    runner = _SERVICE_MAP[args.service]
    runner(args.port, sf_config)


if __name__ == "__main__":
    main()
