"""
Structured logging for SpiderFoot microservices.

Provides JSON-structured log output compatible with Vector.dev, Loki,
Elasticsearch, and other log aggregation systems. Wraps the standard
logging module to emit structured JSON on stdout/stderr while preserving
backward compatibility with the existing SpiderFoot logging setup.
"""

import json
import logging
import socket
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """JSON log formatter for structured output.

    Produces one JSON object per log line, compatible with Vector.dev's
    `stdin` and `file` sources. Includes standard log fields plus
    SpiderFoot-specific context (scan_id, module, event_type).

    Example output:
    {"timestamp":"2026-02-08T12:00:00Z","level":"INFO","logger":"spiderfoot.sfp_dns",
     "message":"Resolved host","scan_id":"abc123","module":"sfp_dnsresolve",
     "service":"spiderfoot","hostname":"worker-01"}
    """

    # Fields to exclude from the extra dict (already handled explicitly)
    RESERVED_ATTRS = {
        'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
        'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'message', 'msg', 'name', 'pathname', 'process', 'processName',
        'relativeCreated', 'stack_info', 'taskName', 'thread', 'threadName',
    }

    def __init__(
        self,
        service_name: str = "spiderfoot",
        environment: str = "development",
        include_timestamp: bool = True,
        include_hostname: bool = True,
        include_caller: bool = False,
        extra_fields: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the structured formatter.

        Args:
            service_name: Service identifier in log output
            environment: Deployment environment (dev/staging/production)
            include_timestamp: Include ISO8601 timestamp
            include_hostname: Include hostname in output
            include_caller: Include file/line/function in output
            extra_fields: Static fields added to every log line
        """
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.include_timestamp = include_timestamp
        self.include_hostname = include_hostname
        self.include_caller = include_caller
        self.extra_fields = extra_fields or {}
        self._hostname = socket.gethostname() if include_hostname else None

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.

        Args:
            record: Standard logging LogRecord

        Returns:
            JSON-encoded log line
        """
        log_entry = {}

        # Timestamp
        if self.include_timestamp:
            log_entry["timestamp"] = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()

        # Core fields
        log_entry["level"] = record.levelname
        log_entry["logger"] = record.name
        log_entry["message"] = record.getMessage()
        log_entry["service"] = self.service_name
        log_entry["environment"] = self.environment

        # Hostname
        if self._hostname:
            log_entry["hostname"] = self._hostname

        # Caller info
        if self.include_caller:
            log_entry["caller"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # SpiderFoot-specific fields from LogRecord extras
        scan_id = getattr(record, 'scanId', None) or getattr(record, 'scan_id', None)
        if scan_id:
            log_entry["scan_id"] = scan_id

        sf_module = getattr(record, 'sf_module', None)
        if sf_module:
            log_entry["module"] = sf_module

        event_type = getattr(record, 'event_type', None)
        if event_type:
            log_entry["event_type"] = event_type

        # Request tracing context (injected by RequestIdFilter or explicit extra)
        request_id = getattr(record, 'request_id', None)
        if request_id:
            log_entry["request_id"] = request_id
        else:
            # Fallback: read directly from contextvar
            try:
                from spiderfoot.request_tracing import get_request_id
                rid = get_request_id()
                if rid:
                    log_entry["request_id"] = rid
            except ImportError:
                pass

        request_method = getattr(record, 'request_method', None)
        if request_method:
            log_entry["request_method"] = request_method

        request_path = getattr(record, 'request_path', None)
        if request_path:
            log_entry["request_path"] = request_path

        # Process/thread info for debugging
        log_entry["pid"] = record.process
        log_entry["thread"] = record.thread

        # Exception info
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        if record.stack_info:
            log_entry["stack_info"] = record.stack_info

        # Extra fields from the log call
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith('_'):
                if key in ('scanId', 'scan_id', 'sf_module', 'event_type'):
                    continue  # Already handled above
                try:
                    json.dumps(value)  # Test serializability
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        # Static extra fields
        log_entry.update(self.extra_fields)

        try:
            return json.dumps(log_entry, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fallback to basic formatting
            return json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "service": self.service_name,
                "format_error": True,
            })


class StructuredLogHandler(logging.Handler):
    """Logging handler that writes structured JSON to a stream.

    This handler can replace the standard StreamHandler in SpiderFoot's
    logging pipeline to produce Vector.dev-compatible output.
    """

    def __init__(
        self,
        stream=None,
        formatter: Optional[StructuredFormatter] = None,
        **kwargs
    ) -> None:
        super().__init__()
        self.stream = stream or sys.stdout
        if formatter:
            self.setFormatter(formatter)
        else:
            self.setFormatter(StructuredFormatter(**kwargs))

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a structured log record.

        Args:
            record: Log record to emit
        """
        try:
            msg = self.format(record)
            self.stream.write(msg + "\n")
            self.stream.flush()
        except Exception:
            self.handleError(record)


class EventLogEmitter:
    """Emits scan events as structured log entries for Vector.dev ingestion.

    This class bridges SpiderFoot scan events and the structured logging
    pipeline, allowing Vector.dev to capture scan data alongside logs.
    """

    def __init__(self, logger_name: str = "spiderfoot.events") -> None:
        self.log = logging.getLogger(logger_name)

    def emit_scan_event(
        self,
        scan_id: str,
        event_type: str,
        module: str,
        data: Any,
        confidence: int = 100,
        risk: int = 0,
        source_hash: str = "ROOT",
    ) -> None:
        """Emit a scan event as a structured log entry.

        Args:
            scan_id: Scan instance ID
            event_type: SpiderFoot event type
            module: Source module
            data: Event data
            confidence: Confidence score
            risk: Risk score
            source_hash: Source event hash
        """
        self.log.info(
            "scan_event",
            extra={
                "scanId": scan_id,
                "event_type": event_type,
                "sf_module": module,
                "event_data": data if isinstance(data, str) else str(data),
                "confidence": confidence,
                "risk": risk,
                "source_event_hash": source_hash,
                "log_type": "scan_event",
            }
        )

    def emit_scan_status(
        self,
        scan_id: str,
        status: str,
        target: str = "",
        modules_count: int = 0,
        events_count: int = 0,
    ) -> None:
        """Emit a scan status change as a structured log entry.

        Args:
            scan_id: Scan instance ID
            status: New scan status
            target: Scan target
            modules_count: Number of active modules
            events_count: Number of events generated so far
        """
        self.log.info(
            "scan_status_change",
            extra={
                "scanId": scan_id,
                "scan_status": status,
                "scan_target": target,
                "modules_count": modules_count,
                "events_count": events_count,
                "log_type": "scan_status",
            }
        )


def setup_structured_logging(
    config: Optional[dict] = None,
    level: int = logging.INFO,
    json_output: bool = True,
) -> logging.Logger:
    """Configure structured logging for SpiderFoot.

    This function sets up the root 'spiderfoot' logger with structured
    JSON output when json_output=True, or standard text format otherwise.

    Designed to be called early in application startup, BEFORE the
    existing logListenerSetup for backward compatibility.

    Args:
        config: SpiderFoot configuration dict
        level: Minimum log level
        json_output: If True, use JSON structured output

    Returns:
        Configured logger
    """
    config = config or {}

    logger = logging.getLogger("spiderfoot")

    if json_output:
        environment = "production" if config.get("_production", False) else "development"

        formatter = StructuredFormatter(
            service_name="spiderfoot",
            environment=environment,
            include_caller=config.get("_debug", False),
            extra_fields={
                "version": config.get("__version__", "unknown"),
            }
        )

        handler = StructuredLogHandler(
            stream=sys.stdout,
            formatter=formatter,
        )
        handler.setLevel(level)

        # Only add if no structured handler exists already
        has_structured = any(
            isinstance(h, StructuredLogHandler) for h in logger.handlers
        )
        if not has_structured:
            logger.addHandler(handler)

    logger.setLevel(level)
    return logger
