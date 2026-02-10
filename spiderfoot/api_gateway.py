#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         api_gateway
# Purpose:      Unified API gateway for SpiderFoot microservices.
#               Routes incoming REST API requests to the appropriate backend
#               service (scanner, data, config) and aggregates responses.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot API Gateway

Provides a single entry point that routes requests to backend microservices.
In monolith mode, calls go directly to in-process services.
In microservices mode, calls go via ServiceClient (HTTP/gRPC).

Features:
    - Request routing to scanner, data, config services
    - Response aggregation for composite queries
    - Rate limiting per client
    - Request/response logging via structured logging
    - Circuit breaker for downstream services
    - FastAPI integration via router

Usage (FastAPI)::

    from spiderfoot.api_gateway import gateway_router
    app.include_router(gateway_router, prefix="/gateway")

Usage (standalone)::

    from spiderfoot.api_gateway import APIGateway
    gateway = APIGateway()
    result = gateway.route("scanner", "SubmitScan", {"target": "example.com"})
"""

import logging
import os
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("spiderfoot.api_gateway")


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for downstream service calls.

    Prevents cascading failures by short-circuiting calls to
    services that are consistently failing.
    """

    def __init__(self, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0,
                 half_open_max: int = 1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max

        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.half_open_max:
                    self._half_open_calls += 1
                    return True
            return False
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                log.warning("Circuit breaker opened (failures=%d)",
                            self._failure_count)

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
        }


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple token-bucket rate limiter per client."""

    def __init__(self, rate: float = 30.0, burst: int = 50):
        """
        Args:
            rate: Requests per second.
            burst: Maximum burst size.
        """
        self.rate = rate
        self.burst = burst
        self._lock = threading.Lock()
        self._clients: Dict[str, dict] = {}

    def allow(self, client_id: str = "default") -> bool:
        """Check if a request from this client is allowed."""
        now = time.monotonic()

        with self._lock:
            if client_id not in self._clients:
                self._clients[client_id] = {
                    "tokens": self.burst,
                    "last_refill": now,
                }

            bucket = self._clients[client_id]
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(
                self.burst,
                bucket["tokens"] + elapsed * self.rate
            )
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True

            return False

    def cleanup(self, max_age: float = 300.0) -> None:
        """Remove stale client entries."""
        now = time.monotonic()
        with self._lock:
            stale = [
                k for k, v in self._clients.items()
                if now - v["last_refill"] > max_age
            ]
            for k in stale:
                del self._clients[k]


# ---------------------------------------------------------------------------
# API Gateway
# ---------------------------------------------------------------------------

class APIGateway:
    """Unified API gateway for routing requests to services.

    In monolith mode, calls are dispatched to in-process service
    instances. In microservices mode, calls are forwarded via
    ServiceClient.
    """

    def __init__(self, mode: Optional[str] = None):
        """
        Args:
            mode: "monolith" or "microservices". Auto-detects from
                  SF_DEPLOYMENT_MODE env var if not specified.
        """
        self.mode = mode or os.environ.get("SF_DEPLOYMENT_MODE", "monolith")
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._rate_limiter = RateLimiter()
        self._local_handlers: Dict[str, Dict[str, Callable]] = {}
        self._clients: Dict[str, Any] = {}

    def register_local_handler(self, service: str, method: str,
                               handler: Callable[[dict], dict]) -> None:
        """Register an in-process handler (monolith mode).

        Args:
            service: Service name (scanner, data, config).
            method: RPC method name.
            handler: Function(dict) -> dict.
        """
        if service not in self._local_handlers:
            self._local_handlers[service] = {}
        self._local_handlers[service][method] = handler

    def route(self, service: str, method: str,
              payload: Dict[str, Any] = None,
              client_id: str = "default") -> Dict[str, Any]:
        """Route a request to the appropriate service.

        Args:
            service: Target service name.
            method: RPC method name.
            payload: Request data.
            client_id: Client identifier for rate limiting.

        Returns:
            Response dict from the service.

        Raises:
            GatewayError: On routing failure.
        """
        payload = payload or {}

        # Rate limit check
        if not self._rate_limiter.allow(client_id):
            raise GatewayError("Rate limit exceeded", status=429)

        # Circuit breaker check
        cb = self._get_circuit_breaker(service)
        if not cb.allow_request():
            raise GatewayError(
                f"Service {service} is unavailable (circuit open)",
                status=503)

        try:
            if self.mode == "monolith":
                result = self._route_local(service, method, payload)
            else:
                result = self._route_remote(service, method, payload)

            cb.record_success()

            # Record metric
            self._record_metric(service, method, "success")

            return result

        except GatewayError:
            cb.record_failure()
            raise
        except Exception as e:
            cb.record_failure()
            self._record_metric(service, method, "error")
            raise GatewayError(f"{service}.{method} failed: {e}") from e

    def _route_local(self, service: str, method: str,
                     payload: dict) -> dict:
        """Route to an in-process handler."""
        handlers = self._local_handlers.get(service)
        if not handlers:
            raise GatewayError(f"No local handlers for service: {service}")

        handler = handlers.get(method)
        if not handler:
            raise GatewayError(f"No handler for {service}.{method}")

        return handler(payload)

    def _route_remote(self, service: str, method: str,
                      payload: dict) -> dict:
        """Route to a remote service via ServiceClient."""
        client = self._get_client(service)
        return client.call(method, payload)

    def _get_client(self, service: str):
        """Get or create a ServiceClient for a service."""
        if service not in self._clients:
            from spiderfoot.grpc_service import ServiceDirectory
            self._clients[service] = ServiceDirectory.get_client(service)
        return self._clients[service]

    def _get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        if service not in self._circuit_breakers:
            self._circuit_breakers[service] = CircuitBreaker()
        return self._circuit_breakers[service]

    def _record_metric(self, service: str, method: str,
                       status: str) -> None:
        """Record gateway routing metric."""
        try:
            from spiderfoot.metrics import Counter, get_registry
            # Lazy-create gateway metrics
            registry = get_registry()
            gate_counter = None
            for m in registry._metrics.values():
                if m.name == "sf_gateway_requests_total":
                    gate_counter = m
                    break
            if gate_counter is None:
                gate_counter = Counter(
                    "sf_gateway_requests_total",
                    "API gateway requests",
                    label_names=["service", "method", "status"],
                )
                registry.register(gate_counter)
            gate_counter.labels(
                service=service, method=method, status=status
            ).inc()
        except Exception as e:
            log.debug("lazy metrics import failed: %s", e)

    # ------------------------------------------------------------------
    # Composite queries
    # ------------------------------------------------------------------

    def get_system_status(self) -> dict:
        """Get aggregated status from all services."""
        status = {
            "mode": self.mode,
            "services": {},
            "circuit_breakers": {},
        }

        for service in ["scanner", "api", "data", "webui"]:
            try:
                result = self.route(service, "HealthCheck", {})
                status["services"][service] = result
            except Exception as e:
                status["services"][service] = {
                    "status": "error", "error": str(e)
                }

        for svc, cb in self._circuit_breakers.items():
            status["circuit_breakers"][svc] = cb.to_dict()

        return status

    def stats(self) -> dict:
        """Gateway stats."""
        return {
            "mode": self.mode,
            "registered_services": list(self._local_handlers.keys()),
            "circuit_breakers": {
                k: v.to_dict() for k, v in self._circuit_breakers.items()
            },
        }


class GatewayError(Exception):
    """Raised on gateway routing failures."""

    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# FastAPI router (optional integration)
# ---------------------------------------------------------------------------

def create_gateway_router():
    """Create a FastAPI router for the gateway.

    Returns None if FastAPI is not available.
    """
    try:
        from fastapi import APIRouter, HTTPException, Request
        from fastapi.responses import JSONResponse
    except ImportError:
        return None

    router = APIRouter(tags=["gateway"])
    gateway = APIGateway()

    @router.post("/route/{service}/{method}")
    async def route_request(service: str, method: str, request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}

        client_id = request.client.host if request.client else "unknown"

        try:
            result = gateway.route(service, method, body, client_id)
            return JSONResponse(content=result)
        except GatewayError as e:
            raise HTTPException(status_code=e.status, detail=str(e))

    @router.get("/status")
    async def system_status():
        return gateway.get_system_status()

    @router.get("/stats")
    async def gateway_stats():
        return gateway.stats()

    return router


# Create router for import convenience
gateway_router = create_gateway_router()
