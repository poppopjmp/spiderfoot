"""
Lightweight OpenTelemetry tracing integration for SpiderFoot services.

Sends traces to Vector.dev (OTLP endpoint) which forwards to Jaeger.
Falls back to a no-op tracer when opentelemetry-sdk is not installed.

Usage:
    from spiderfoot.observability.tracing import get_tracer, trace_span

    tracer = get_tracer("spiderfoot.api")

    with trace_span(tracer, "handle_scan_request", {"scan.target": target}):
        ...
"""

import os
import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger("sf.tracing")

# OTLP endpoint — defaults to Vector.dev in Docker
OTEL_ENDPOINT = os.environ.get("SF_OTEL_ENDPOINT", "http://vector:4317")
SERVICE_NAME = os.environ.get("SF_SERVICE_NAME", "spiderfoot")

_tracer_provider = None
_initialized = False


def _try_init_otel():
    """Attempt to initialize OpenTelemetry SDK.  Returns True on success."""
    global _tracer_provider, _initialized

    if _initialized:
        return _tracer_provider is not None

    _initialized = True

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        resource = Resource.create(
            {
                "service.name": SERVICE_NAME,
                "service.version": _read_version(),
                "deployment.environment": os.environ.get("SF_ENV", "production"),
            }
        )

        exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
        processor = BatchSpanProcessor(exporter)

        _tracer_provider = TracerProvider(resource=resource)
        _tracer_provider.add_span_processor(processor)
        trace.set_tracer_provider(_tracer_provider)

        logger.info("OpenTelemetry tracing initialized → %s", OTEL_ENDPOINT)
        return True

    except ImportError:
        logger.debug(
            "opentelemetry-sdk not installed — tracing disabled (no-op)"
        )
        return False
    except Exception as exc:
        logger.warning("Failed to initialize OpenTelemetry: %s", exc)
        return False


def _read_version() -> str:
    """Read VERSION file for resource metadata."""
    try:
        version_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "VERSION"
        )
        with open(version_path) as f:
            return f.read().strip()
    except Exception:
        return "unknown"


class _NoOpSpan:
    """Minimal no-op span for when OTel is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exc: BaseException) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpTracer:
    """Minimal no-op tracer."""

    def start_as_current_span(self, name: str, **kwargs):
        return _NoOpSpan()

    def start_span(self, name: str, **kwargs):
        return _NoOpSpan()


_noop_tracer = _NoOpTracer()


def get_tracer(name: str = "spiderfoot"):
    """
    Get an OpenTelemetry tracer.  Returns a no-op tracer if the SDK is
    not installed or initialization fails.
    """
    if _try_init_otel():
        from opentelemetry import trace
        return trace.get_tracer(name)
    return _noop_tracer


@contextmanager
def trace_span(
    tracer,
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Context manager that creates a span with optional attributes.

    Works with both real OTel tracers and the no-op fallback.

    Args:
        tracer: Tracer instance from get_tracer()
        name: Span name (e.g. "scan.execute_module")
        attributes: Optional dict of span attributes
    """
    span_cm = tracer.start_as_current_span(name)
    span = span_cm.__enter__()
    try:
        if attributes and hasattr(span, "set_attribute"):
            for k, v in attributes.items():
                span.set_attribute(k, v)
        yield span
    except Exception as exc:
        if hasattr(span, "record_exception"):
            span.record_exception(exc)
        raise
    finally:
        span_cm.__exit__(None, None, None)


def shutdown():
    """Flush and shut down the tracer provider."""
    global _tracer_provider
    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
        except Exception as exc:
            logger.warning("Error shutting down tracer: %s", exc)
