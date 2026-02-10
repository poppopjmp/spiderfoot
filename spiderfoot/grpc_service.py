#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         grpc_service
# Purpose:      gRPC service shim for SpiderFoot microservices.
#               Provides service stubs and a lightweight JSON-over-HTTP
#               fallback for environments without grpcio.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot gRPC Service Layer

Provides both gRPC and JSON-over-HTTP interfaces for inter-service
communication. The JSON-HTTP fallback ensures the system works without
grpcio installed (e.g., in development or resource-constrained envs).

Architecture::

    ┌──────────┐  gRPC/HTTP  ┌──────────┐
    │  WebUI   │ ──────────→ │   API    │
    └──────────┘             └────┬─────┘
                                  │ gRPC/HTTP
                            ┌─────▼─────┐
                            │  Scanner   │
                            └─────┬─────┘
                                  │ gRPC/HTTP
                            ┌─────▼─────┐
                            │   Data     │
                            └───────────┘

Usage (client)::

    from spiderfoot.grpc_service import ServiceClient

    # Auto-detects gRPC or HTTP
    scanner = ServiceClient("scanner", "sf-scanner:5003")
    result = scanner.call("SubmitScan", {
        "scan_name": "Test",
        "target": "example.com",
    })

Usage (server)::

    from spiderfoot.grpc_service import ServiceServer

    server = ServiceServer("scanner", port=5003)
    server.register("SubmitScan", handle_submit_scan)
    server.start()
"""

import json
import logging
import threading
from http.client import HTTPConnection
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

log = logging.getLogger("spiderfoot.grpc_service")

# Try to import grpcio; fall back to HTTP if unavailable
_GRPC_AVAILABLE = False
_STUBS_AVAILABLE = False
try:
    import grpc
    from concurrent import futures
    _GRPC_AVAILABLE = True
    try:
        from spiderfoot import spiderfoot_pb2
        from spiderfoot import spiderfoot_pb2_grpc
        _STUBS_AVAILABLE = True
    except ImportError:
        log.debug("gRPC stubs not found — run 'python -m grpc_tools.protoc' to generate")
except ImportError:
    log.debug("grpcio not installed — using JSON-over-HTTP fallback")


# ---------------------------------------------------------------------------
# Service Client — calls remote services
# ---------------------------------------------------------------------------

class ServiceClient:
    """Client for calling remote SpiderFoot services.

    Automatically uses gRPC if available, otherwise falls back to
    JSON-over-HTTP.
    """

    def __init__(self, service_name: str, endpoint: str,
                 timeout: float = 30.0,
                 use_grpc: Optional[bool] = None) -> None:
        """
        Args:
            service_name: Logical service name (scanner, data, etc.).
            endpoint: Host:port of the remote service.
            timeout: Default call timeout in seconds.
            use_grpc: Force gRPC (True) or HTTP (False). None = auto-detect.
        """
        self.service_name = service_name
        self.endpoint = endpoint
        self.timeout = timeout
        self._use_grpc = use_grpc if use_grpc is not None else _GRPC_AVAILABLE

    def call(self, method: str, payload: dict[str, Any] = None,
             timeout: Optional[float] = None) -> dict[str, Any]:
        """Call a remote service method.

        Args:
            method: RPC method name (e.g., "SubmitScan").
            payload: Request data as a dict.
            timeout: Override default timeout.

        Returns:
            Response data as a dict.

        Raises:
            ServiceCallError: On communication failure.
        """
        payload = payload or {}
        timeout = timeout or self.timeout

        if self._use_grpc:
            return self._call_grpc(method, payload, timeout)
        else:
            return self._call_http(method, payload, timeout)

    def _call_http(self, method: str, payload: dict,
                   timeout: float) -> dict:
        """Make an HTTP POST call."""
        parsed = urlparse(f"http://{self.endpoint}")
        host = parsed.hostname or self.endpoint.split(":")[0]
        port = parsed.port or int(self.endpoint.split(":")[-1])

        try:
            conn = HTTPConnection(host, port, timeout=timeout)
            body = json.dumps(payload).encode("utf-8")
            path = f"/rpc/{self.service_name}/{method}"

            conn.request("POST", path, body=body, headers={
                "Content-Type": "application/json",
                "X-Service": self.service_name,
            })

            resp = conn.getresponse()
            data = resp.read().decode("utf-8")
            conn.close()

            if resp.status != 200:
                raise ServiceCallError(
                    f"{method} failed: HTTP {resp.status}: {data}")

            return json.loads(data)

        except ServiceCallError:
            raise
        except (json.JSONDecodeError, ValueError, OSError) as e:
            raise ServiceCallError(
                f"Failed to call {self.service_name}.{method}: {e}") from e

    def _call_grpc(self, method: str, payload: dict,
                   timeout: float) -> dict:
        """Make a gRPC call (simplified unary-unary)."""
        if not _GRPC_AVAILABLE:
            raise ServiceCallError("grpcio not installed")

        if not _STUBS_AVAILABLE:
            log.debug("gRPC stubs not compiled, falling back to HTTP for %s.%s",
                      self.service_name, method)
            return self._call_http(method, payload, timeout)

        try:
            channel = grpc.insecure_channel(self.endpoint)
            # Use reflection to find the correct stub based on service name
            stub_class_name = f"{self.service_name.title().replace('_', '')}ServiceStub"
            stub_class = getattr(spiderfoot_pb2_grpc, stub_class_name, None)
            if stub_class is None:
                log.debug("No gRPC stub found for %s, falling back to HTTP",
                          self.service_name)
                return self._call_http(method, payload, timeout)

            stub = stub_class(channel)
            rpc_method = getattr(stub, method, None)
            if rpc_method is None:
                log.debug("No gRPC method %s on %s, falling back to HTTP",
                          method, stub_class_name)
                return self._call_http(method, payload, timeout)

            # Build request message from payload
            request_class_name = f"{method}Request"
            request_class = getattr(spiderfoot_pb2, request_class_name, None)
            if request_class is None:
                # Try ScanIdRequest as a common fallback
                request_class = getattr(spiderfoot_pb2, 'ScanIdRequest', None)

            if request_class and payload:
                request = request_class(**payload)
            elif request_class:
                request = request_class()
            else:
                return self._call_http(method, payload, timeout)

            response = rpc_method(request, timeout=timeout)

            # Convert protobuf response to dict
            from google.protobuf.json_format import MessageToDict
            return MessageToDict(response, preserving_proto_field_name=True)

        except grpc.RpcError as e:
            log.warning("gRPC call %s.%s failed (%s), falling back to HTTP",
                        self.service_name, method, e.code())
            return self._call_http(method, payload, timeout)
        except Exception as e:
            log.debug("gRPC call error for %s.%s: %s - falling back to HTTP",
                      self.service_name, method, e)
            return self._call_http(method, payload, timeout)

    def health_check(self) -> dict:
        """Check the health of the remote service."""
        try:
            return self.call("HealthCheck", {}, timeout=5.0)
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}


class ServiceCallError(Exception):
    """Raised when a service call fails."""
    pass


# ---------------------------------------------------------------------------
# Service Server — hosts RPC endpoints
# ---------------------------------------------------------------------------

class ServiceServer:
    """Lightweight RPC server for SpiderFoot services.

    Registers method handlers and serves them over HTTP (with gRPC
    support when stubs are compiled).
    """

    def __init__(self, service_name: str, port: int = 5003) -> None:
        self.service_name = service_name
        self.port = port
        self._handlers: dict[str, Callable] = {}
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def register(self, method: str,
                 handler: Callable[[dict], dict]) -> None:
        """Register a method handler.

        Args:
            method: RPC method name.
            handler: Function that takes a dict and returns a dict.
        """
        self._handlers[method] = handler
        log.debug("Registered handler: %s.%s", self.service_name, method)

    def start(self, background: bool = True) -> None:
        """Start the RPC server.

        Args:
            background: If True, run in a daemon thread.
        """
        factory = _make_handler_factory(self.service_name, self._handlers)
        self._server = HTTPServer(("0.0.0.0", self.port), factory)
        self._running = True

        if background:
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name=f"rpc-{self.service_name}",
            )
            self._thread.start()
            log.info("RPC server %s started on :%d (background)",
                     self.service_name, self.port)
        else:
            log.info("RPC server %s starting on :%d",
                     self.service_name, self.port)
            self._server.serve_forever()

    def stop(self) -> None:
        """Stop the RPC server."""
        if self._server:
            self._server.shutdown()
            self._running = False
            log.info("RPC server %s stopped", self.service_name)

    @property
    def is_running(self) -> bool:
        return self._running


def _make_handler_factory(service_name: str,
                          handlers: dict[str, Callable]):
    """Create an HTTP request handler class with bound handlers."""

    class _RPCHandler(BaseHTTPRequestHandler):

        def do_POST(self):  # noqa: N802
            # Expected path: /rpc/{service_name}/{method}
            parts = self.path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "rpc":
                method = parts[2]
            elif len(parts) >= 2:
                method = parts[1]
            else:
                method = parts[-1] if parts else ""

            handler = handlers.get(method)
            if handler is None:
                self.send_error(404, f"Unknown method: {method}")
                return

            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body) if body else {}

                result = handler(payload)

                response = json.dumps(result).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            except Exception as e:
                error_body = json.dumps(
                    {"error": str(e), "method": method}
                ).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(error_body)))
                self.end_headers()
                self.wfile.write(error_body)

        def log_message(self, format, *args):  # noqa: A002
            pass

    return _RPCHandler


# ---------------------------------------------------------------------------
# Service discovery helper
# ---------------------------------------------------------------------------

class ServiceDirectory:
    """Simple service discovery via environment variables.

    Each service endpoint is configured via SF_{SERVICE}_ENDPOINT env var.
    """

    # Default ports for each service
    DEFAULTS = {
        "scanner": "localhost:5003",
        "api": "localhost:8001",
        "webui": "localhost:5001",
        "data": "localhost:5004",
    }

    @classmethod
    def get_endpoint(cls, service_name: str) -> str:
        """Get the endpoint for a service.

        Checks SF_{SERVICE}_ENDPOINT env var first, then falls back
        to defaults.
        """
        import os
        env_key = f"SF_{service_name.upper()}_ENDPOINT"
        return os.environ.get(env_key, cls.DEFAULTS.get(service_name, ""))

    @classmethod
    def get_client(cls, service_name: str,
                   timeout: float = 30.0) -> ServiceClient:
        """Create a ServiceClient for the named service."""
        endpoint = cls.get_endpoint(service_name)
        if not endpoint:
            raise ServiceCallError(
                f"No endpoint configured for service: {service_name}")
        return ServiceClient(service_name, endpoint, timeout=timeout)
