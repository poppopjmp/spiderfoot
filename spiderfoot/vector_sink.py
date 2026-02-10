"""
Vector.dev integration for SpiderFoot.

Provides an HTTP sink that forwards scan events, logs, and metrics to
a Vector.dev instance for routing to external data stores (ClickHouse,
Loki, Elasticsearch, S3, etc.).
"""

import asyncio
import json
import logging
import threading
import time
import queue
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


class VectorConfig:
    """Configuration for Vector.dev integration.
    
    Attributes:
        enabled: Whether Vector integration is active
        endpoint: Vector HTTP source endpoint URL
        batch_size: Max events per batch
        flush_interval: Seconds between flushes
        max_retries: Retry attempts for failed requests
        timeout: HTTP timeout in seconds
        api_key: Optional API key for auth
        environment: Environment label
        extra_labels: Static labels added to all events
    """
    
    def __init__(
        self,
        enabled: bool = False,
        endpoint: str = "http://localhost:8686",
        batch_size: int = 50,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        timeout: float = 10.0,
        api_key: str = "",
        environment: str = "development",
        extra_labels: Optional[Dict[str, str]] = None,
    ):
        self.enabled = enabled
        self.endpoint = endpoint.rstrip("/")
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.api_key = api_key
        self.environment = environment
        self.extra_labels = extra_labels or {}
    
    @classmethod
    def from_sf_config(cls, config: dict) -> 'VectorConfig':
        """Create VectorConfig from SpiderFoot configuration dict.
        
        Config keys:
            _vector_enabled: bool
            _vector_endpoint: str
            _vector_batch_size: int
            _vector_flush_interval: float
            _vector_api_key: str
        """
        return cls(
            enabled=config.get("_vector_enabled", False),
            endpoint=config.get("_vector_endpoint", "http://localhost:8686"),
            batch_size=int(config.get("_vector_batch_size", 50)),
            flush_interval=float(config.get("_vector_flush_interval", 5.0)),
            max_retries=int(config.get("_vector_max_retries", 3)),
            timeout=float(config.get("_vector_timeout", 10.0)),
            api_key=config.get("_vector_api_key", ""),
            environment="production" if config.get("_production") else "development",
        )


class VectorSink:
    """Asynchronous sink that batches and sends events to Vector.dev.
    
    Buffers events in memory and flushes them to Vector's HTTP source
    in configurable batches. Thread-safe for use from synchronous code.
    
    Usage:
        sink = VectorSink(config)
        sink.start()
        
        sink.emit_event("scan_event", {
            "scan_id": "abc",
            "event_type": "IP_ADDRESS",
            "data": "1.2.3.4"
        })
        
        sink.stop()
    """
    
    def __init__(self, config: Optional[VectorConfig] = None):
        self.config = config or VectorConfig()
        self.log = logging.getLogger("spiderfoot.vector")
        self._buffer: queue.Queue = queue.Queue(maxsize=10000)
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None
        self._stats = {
            "events_sent": 0,
            "events_dropped": 0,
            "batches_sent": 0,
            "errors": 0,
        }
    
    def start(self) -> None:
        """Start the background flush thread."""
        if not self.config.enabled:
            self.log.info("Vector.dev integration disabled")
            return
        
        if not HTTPX_AVAILABLE:
            self.log.warning(
                "Vector.dev integration requires 'httpx' package. "
                "Install with: pip install httpx"
            )
            return
        
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="vector-sink-flush"
        )
        self._flush_thread.start()
        self.log.info("Vector.dev sink started → %s", self.config.endpoint)
    
    def stop(self) -> None:
        """Stop the sink, flushing remaining events."""
        if not self._running:
            return
        
        self._running = False
        # Final flush
        self._flush_batch()
        if self._flush_thread:
            self._flush_thread.join(timeout=10)
        self.log.info(
            f"Vector.dev sink stopped. Stats: {json.dumps(self._stats)}"
        )
    
    def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Queue an event for sending to Vector.
        
        Args:
            event_type: Category of event (scan_event, scan_status, log, metric)
            data: Event payload
        """
        if not self.config.enabled or not self._running:
            return
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "spiderfoot",
            "type": event_type,
            "environment": self.config.environment,
            **self.config.extra_labels,
            **data,
        }
        
        try:
            self._buffer.put_nowait(event)
        except queue.Full:
            self._stats["events_dropped"] += 1
            self.log.warning("Vector.dev buffer full, dropping event")
    
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
        """Convenience method to emit a SpiderFoot scan event.
        
        Args:
            scan_id: Scan instance ID
            event_type: SpiderFoot event type
            module: Source module name
            data: Event data
            confidence: Confidence score 0-100
            risk: Risk score 0-100
            source_hash: Parent event hash
        """
        self.emit_event("scan_event", {
            "scan_id": scan_id,
            "event_type": event_type,
            "module": module,
            "event_data": str(data) if not isinstance(data, str) else data,
            "confidence": confidence,
            "risk": risk,
            "source_event_hash": source_hash,
        })
    
    def emit_scan_status(
        self,
        scan_id: str,
        status: str,
        target: str = "",
        progress: float = 0.0,
    ) -> None:
        """Emit a scan status change event.
        
        Args:
            scan_id: Scan instance ID
            status: Scan status string
            target: Scan target
            progress: Progress percentage 0-100
        """
        self.emit_event("scan_status", {
            "scan_id": scan_id,
            "status": status,
            "target": target,
            "progress": progress,
        })
    
    def emit_metric(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Emit a metric event.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Additional metric tags
        """
        self.emit_event("metric", {
            "metric_name": name,
            "metric_value": value,
            "tags": tags or {},
        })
    
    def _flush_loop(self) -> None:
        """Background loop that periodically flushes the event buffer."""
        while self._running:
            time.sleep(self.config.flush_interval)
            self._flush_batch()
    
    def _flush_batch(self) -> None:
        """Drain the buffer and send events to Vector."""
        batch: List[Dict] = []
        
        while len(batch) < self.config.batch_size:
            try:
                event = self._buffer.get_nowait()
                batch.append(event)
            except queue.Empty:
                break
        
        if not batch:
            return
        
        payload = "\n".join(json.dumps(e, default=str) for e in batch)
        
        headers = {"Content-Type": "application/x-ndjson"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        for attempt in range(self.config.max_retries):
            try:
                with httpx.Client(timeout=self.config.timeout) as client:
                    response = client.post(
                        self.config.endpoint,
                        content=payload,
                        headers=headers,
                    )
                
                if response.status_code in (200, 201, 202, 204):
                    self._stats["events_sent"] += len(batch)
                    self._stats["batches_sent"] += 1
                    return
                else:
                    self.log.warning(
                        f"Vector.dev responded with {response.status_code} "
                        f"(attempt {attempt+1}/{self.config.max_retries})"
                    )
            except Exception as e:
                self.log.warning(
                    f"Vector.dev send failed (attempt {attempt+1}): {e}"
                )
            
            if attempt < self.config.max_retries - 1:
                time.sleep(1 * (attempt + 1))
        
        self._stats["errors"] += 1
        self._stats["events_dropped"] += len(batch)
        self.log.error("Failed to send %s events to Vector.dev after %s attempts", len(batch), self.config.max_retries)
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get sink statistics."""
        return dict(self._stats)


class VectorLogHandler(logging.Handler):
    """Python logging handler that forwards log records to Vector.dev via VectorSink.
    
    Attach this handler to the root 'spiderfoot' logger to automatically
    ship all log output to Vector.dev alongside scan events.
    """
    
    def __init__(self, sink: VectorSink):
        super().__init__()
        self.sink = sink
    
    def emit(self, record: logging.LogRecord) -> None:
        """Forward a log record to Vector.dev."""
        try:
            data = {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "pid": record.process,
                "thread": record.thread,
            }
            
            scan_id = getattr(record, 'scanId', None)
            if scan_id:
                data["scan_id"] = scan_id
            
            if record.exc_info and record.exc_info[0]:
                data["exception_type"] = record.exc_info[0].__name__
                data["exception_message"] = str(record.exc_info[1])
            
            self.sink.emit_event("log", data)
        except Exception:
            self.handleError(record)
