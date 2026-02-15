"""
Request Tracing Middleware for SpiderFoot FastAPI.

Provides correlation IDs for every HTTP request, propagated through
logging context via :mod:`contextvars`.  Each request gets a unique
``X-Request-ID`` header (generated or echoed from the client) that
appears in every log line emitted during that request's lifecycle.

Integration points:
  - ``StructuredFormatter`` reads ``get_request_id()`` automatically
  - Vector.dev / Loki can group logs by ``request_id``
  - Downstream services can propagate the header for distributed tracing

Usage::

    from spiderfoot.request_tracing import install_tracing_middleware

    install_tracing_middleware(app)

Accessing the current request ID anywhere in the call stack::

    from spiderfoot.request_tracing import get_request_id

    log.info("Processing", extra={"request_id": get_request_id()})
"""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from typing import Any, Callable

log = logging.getLogger("spiderfoot.tracing")

# -----------------------------------------------------------------------
# Context variable — available anywhere in the async/sync call stack
# -----------------------------------------------------------------------

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None,
)

# Additional context variables for richer tracing
_request_method_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_method", default=None,
)
_request_path_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_path", default=None,
)


def get_request_id() -> str | None:
    """Get the current request ID from context.

    Returns ``None`` if called outside a request context.
    """
    return _request_id_var.get()


def set_request_id(request_id: str) -> contextvars.Token:
    """Manually set a request ID (useful for background tasks)."""
    return _request_id_var.set(request_id)


def get_request_context() -> dict[str, Any]:
    """Get all tracing context variables as a dict.

    Useful for propagating context to background threads or
    downstream service calls.
    """
    ctx: dict[str, Any] = {}
    rid = _request_id_var.get()
    if rid:
        ctx["request_id"] = rid
    method = _request_method_var.get()
    if method:
        ctx["request_method"] = method
    path = _request_path_var.get()
    if path:
        ctx["request_path"] = path
    return ctx


def generate_request_id() -> str:
    """Generate a new unique request ID."""
    return str(uuid.uuid4())


# -----------------------------------------------------------------------
# Logging filter — auto-injects request_id into every LogRecord
# -----------------------------------------------------------------------

class RequestIdFilter(logging.Filter):
    """Logging filter that adds ``request_id`` to every log record.

    Install on a handler or logger to automatically include the
    current request's correlation ID without needing ``extra={}``
    on every log call.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach request context to the log record."""
        record.request_id = _request_id_var.get() or ""
        record.request_method = _request_method_var.get() or ""
        record.request_path = _request_path_var.get() or ""
        return True


# -----------------------------------------------------------------------
# FastAPI Middleware
# -----------------------------------------------------------------------

# Header names
REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_RESPONSE_HEADER = "X-Request-ID"

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    HAS_STARLETTE = True
except ImportError:
    HAS_STARLETTE = False


if HAS_STARLETTE:

    class RequestTracingMiddleware(BaseHTTPMiddleware):
        """FastAPI/Starlette middleware for request tracing.

        For every incoming request:
        1. Reads or generates ``X-Request-ID``
        2. Sets context variables for the request scope
        3. Logs request start/completion with timing
        4. Adds ``X-Request-ID`` to the response headers

        Args:
            app: The ASGI application.
            trust_client_id: If ``True``, use the client-supplied
                ``X-Request-ID`` if present.  Default ``True``.
            log_requests: If ``True``, log request start/end at INFO level.
            slow_request_threshold: Requests taking longer than this
                (seconds) are logged at WARNING level.
        """

        def __init__(
            self,
            app: Any,
            trust_client_id: bool = True,
            log_requests: bool = True,
            slow_request_threshold: float = 5.0,
        ) -> None:
            """Initialize the RequestTracingMiddleware."""
            super().__init__(app)
            self.trust_client_id = trust_client_id
            self.log_requests = log_requests
            self.slow_request_threshold = slow_request_threshold

        async def dispatch(self, request: Request, call_next: Callable) -> Response:
            """Process the request with tracing context."""
            # 1. Determine request ID
            client_id = request.headers.get(REQUEST_ID_HEADER)
            if client_id and self.trust_client_id:
                request_id = client_id
            else:
                request_id = generate_request_id()

            # 2. Set context variables
            tok_id = _request_id_var.set(request_id)
            tok_method = _request_method_var.set(request.method)
            tok_path = _request_path_var.set(request.url.path)

            start_time = time.monotonic()

            try:
                if self.log_requests:
                    log.info(
                        "Request started: %s %s",
                        request.method,
                        request.url.path,
                        extra={
                            "request_id": request_id,
                            "client_ip": request.client.host if request.client else "unknown",
                        },
                    )

                # 3. Process request
                response = await call_next(request)

                # 4. Add request ID to response
                response.headers[REQUEST_ID_RESPONSE_HEADER] = request_id

                duration = time.monotonic() - start_time

                if self.log_requests:
                    level = logging.WARNING if duration > self.slow_request_threshold else logging.INFO
                    log.log(
                        level,
                        "Request completed: %s %s -> %d (%.3fs)",
                        request.method,
                        request.url.path,
                        response.status_code,
                        duration,
                        extra={
                            "request_id": request_id,
                            "status_code": response.status_code,
                            "duration_ms": round(duration * 1000, 1),
                        },
                    )

                return response

            except Exception as exc:
                duration = time.monotonic() - start_time
                log.error(
                    "Request failed: %s %s (%.3fs) - %s",
                    request.method,
                    request.url.path,
                    duration,
                    str(exc),
                    extra={
                        "request_id": request_id,
                        "duration_ms": round(duration * 1000, 1),
                        "error": str(exc),
                    },
                    exc_info=True,
                )
                raise

            finally:
                # 5. Reset context
                _request_id_var.reset(tok_id)
                _request_method_var.reset(tok_method)
                _request_path_var.reset(tok_path)


def install_tracing_middleware(
    app: Any,
    *,
    trust_client_id: bool = True,
    log_requests: bool = True,
    slow_request_threshold: float = 5.0,
    install_log_filter: bool = True,
) -> None:
    """Install the request tracing middleware on a FastAPI app.

    Also installs the :class:`RequestIdFilter` on the root logger
    so that ``request_id`` appears in every log line automatically.

    Args:
        app: FastAPI or Starlette application instance.
        trust_client_id: Trust client-supplied ``X-Request-ID``.
        log_requests: Log start/end of each request.
        slow_request_threshold: Warn on requests exceeding this duration.
        install_log_filter: Add ``RequestIdFilter`` to root logger.
    """
    if not HAS_STARLETTE:
        log.warning("Starlette not available; request tracing middleware not installed")
        return

    app.add_middleware(
        RequestTracingMiddleware,
        trust_client_id=trust_client_id,
        log_requests=log_requests,
        slow_request_threshold=slow_request_threshold,
    )

    if install_log_filter:
        _install_request_id_filter()

    log.info("Request tracing middleware installed")


def _install_request_id_filter() -> None:
    """Add RequestIdFilter to the root logger (idempotent)."""
    root = logging.getLogger()
    # Avoid duplicate filters
    for f in root.filters:
        if isinstance(f, RequestIdFilter):
            return
    root.addFilter(RequestIdFilter())
