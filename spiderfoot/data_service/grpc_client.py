"""
gRPC-based DataService client for high-performance microservice mode.

Uses the generated protobuf stubs to communicate with a remote
DataService server over gRPC.  Provides the same DataService
interface so it can be swapped in transparently via the factory.

Usage::

    config = DataServiceConfig(
        backend=DataServiceBackend.GRPC,
        api_url="data-service:50051",
    )
    ds = GrpcDataService(config)
    scans = ds.scan_instance_list()
"""

from __future__ import annotations

import logging
from typing import Any

from spiderfoot.data_service.base import DataService, DataServiceConfig

log = logging.getLogger("spiderfoot.dataservice.grpc")


def _ensure_grpc():
    """Validate grpc deps are available; raise ImportError if not."""
    try:
        import grpc  # noqa: F401
        from spiderfoot import spiderfoot_pb2  # noqa: F401
        from spiderfoot import spiderfoot_pb2_grpc  # noqa: F401
        return True
    except ImportError as e:
        raise ImportError(
            "gRPC DataService requires grpcio and generated stubs. "
            "Install with: pip install grpcio grpcio-tools protobuf"
        ) from e


class GrpcDataService(DataService):
    """DataService backed by gRPC calls to a remote DataService server.

    All operations map to the DataService proto RPCs defined in
    proto/spiderfoot.proto.  Channel management is lazy — the gRPC
    channel is created on first use and reused for subsequent calls.
    """

    def __init__(self, config: DataServiceConfig | None = None, **kwargs) -> None:
        super().__init__(config)
        _ensure_grpc()
        self._target = self.config.api_url
        self._channel = None
        self._stub = None

    # ------------------------------------------------------------------
    # gRPC channel management
    # ------------------------------------------------------------------

    def _get_stub(self):
        """Lazy-init a gRPC channel + DataServiceStub."""
        if self._stub is None:
            import grpc
            from spiderfoot import spiderfoot_pb2_grpc

            # Use insecure channel; TLS can be added via channel credentials
            options = [
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.keepalive_time_ms", 30000),
                ("grpc.keepalive_timeout_ms", 10000),
            ]
            self._channel = grpc.insecure_channel(self._target, options=options)
            self._stub = spiderfoot_pb2_grpc.DataServiceStub(self._channel)
            log.info("Connected gRPC DataService to %s", self._target)
        return self._stub

    def _get_metadata(self):
        """Build gRPC metadata with request ID for distributed tracing."""
        metadata = []
        try:
            from spiderfoot.request_tracing import get_request_id
            rid = get_request_id()
            if rid:
                metadata.append(("x-request-id", rid))
        except ImportError:
            pass
        return metadata or None
        return self._stub

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scan_record_to_dict(self, record) -> dict[str, Any]:
        """Convert a ScanRecord protobuf message to a dict."""
        return {
            "id": record.scan_id,
            "name": record.scan_name,
            "target": record.target,
            "status": record.status,
            "created": record.created_at.seconds if record.HasField("created_at") else 0,
            "started": record.started_at.seconds if record.HasField("started_at") else 0,
            "ended": record.finished_at.seconds if record.HasField("finished_at") else 0,
        }

    def _event_record_to_dict(self, record) -> dict[str, Any]:
        """Convert an EventRecord protobuf message to a dict."""
        return {
            "hash": record.event_hash,
            "type": record.event_type,
            "data": record.data,
            "module": record.module,
            "source_event_hash": record.source_event_hash,
            "confidence": record.confidence,
            "generated": record.timestamp.seconds if record.HasField("timestamp") else 0,
            "visibility": 100,
            "risk": 0,
        }

    def _log_record_to_dict(self, record) -> dict[str, Any]:
        """Convert a LogRecord protobuf message to a dict."""
        return {
            "component": record.component,
            "type": record.log_type,
            "message": record.message,
            "generated": record.timestamp.seconds if record.HasField("timestamp") else 0,
            "rowid": 0,
        }

    # ------------------------------------------------------------------
    # Scan Instance Operations
    # ------------------------------------------------------------------

    def scan_instance_create(
        self, scan_id: str, scan_name: str, target: str
    ) -> bool:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.CreateScanRequest(
                scan_id=scan_id, scan_name=scan_name, target=target
            )
            self._get_stub().CreateScan(req, timeout=self.config.timeout)
            return True
        except Exception as e:
            log.error("gRPC CreateScan failed: %s", e)
            return False

    def scan_instance_get(self, scan_id: str) -> dict[str, Any] | None:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.ScanIdRequest(scan_id=scan_id)
            record = self._get_stub().GetScan(req, timeout=self.config.timeout)
            return self._scan_record_to_dict(record)
        except Exception as e:
            log.error("gRPC GetScan failed for %s: %s", scan_id, e)
            return None

    def scan_instance_list(self) -> list[dict[str, Any]]:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.ListScansRequest()
            resp = self._get_stub().ListScanInstances(
                req, timeout=self.config.timeout
            )
            return [self._scan_record_to_dict(r) for r in resp.scans]
        except Exception as e:
            log.error("gRPC ListScanInstances failed: %s", e)
            return []

    def scan_instance_delete(self, scan_id: str) -> bool:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.ScanIdRequest(scan_id=scan_id)
            resp = self._get_stub().DeleteScan(req, timeout=self.config.timeout)
            return resp.success
        except Exception as e:
            log.error("gRPC DeleteScan failed for %s: %s", scan_id, e)
            return False

    def scan_status_set(
        self,
        scan_id: str,
        status: str,
        started: int | None = None,
        ended: int | None = None,
    ) -> bool:
        # The proto DataService doesn't have a dedicated UpdateScanStatus RPC.
        # Fall back to CreateScan re-call or log warning.
        log.warning(
            "gRPC scan_status_set not directly supported by proto; "
            "status=%s for scan=%s",
            status,
            scan_id,
        )
        return False

    # ------------------------------------------------------------------
    # Event Operations
    # ------------------------------------------------------------------

    def event_store(
        self,
        scan_id: str,
        event_hash: str,
        event_type: str,
        module: str,
        data: str,
        source_event_hash: str = "ROOT",
        confidence: int = 100,
        visibility: int = 100,
        risk: int = 0,
    ) -> bool:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.StoreEventRequest(
                scan_id=scan_id,
                event_type=event_type,
                data=data,
                module=module,
                source_event_hash=source_event_hash,
                confidence=confidence,
                visibility=visibility,
                risk=risk,
            )
            self._get_stub().StoreEvent(req, timeout=self.config.timeout)
            return True
        except Exception as e:
            log.debug("gRPC StoreEvent failed: %s", e)
            return False

    def event_get_by_scan(
        self,
        scan_id: str,
        event_type: str | None = None,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.GetEventsRequest(
                scan_id=scan_id,
                event_type=event_type or "",
                limit=limit,
            )
            resp = self._get_stub().GetEvents(req, timeout=self.config.timeout)
            return [self._event_record_to_dict(e) for e in resp.events]
        except Exception as e:
            log.error("gRPC GetEvents failed: %s", e)
            return []

    def event_get_unique(
        self,
        scan_id: str,
        event_type: str,
    ) -> list[str]:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.ScanIdRequest(scan_id=scan_id)
            resp = self._get_stub().GetUniqueEventTypes(
                req, timeout=self.config.timeout
            )
            return list(resp.event_types)
        except Exception as e:
            log.error("gRPC GetUniqueEventTypes failed: %s", e)
            return []

    def event_exists(
        self,
        scan_id: str,
        event_type: str,
        data: str,
    ) -> bool:
        # No dedicated RPC in proto — fetch events and check
        try:
            events = self.event_get_by_scan(scan_id, event_type=event_type)
            return any(e.get("data") == data for e in events)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Log Operations
    # ------------------------------------------------------------------

    def scan_log_event(
        self,
        scan_id: str,
        classification: str,
        message: str,
        component: str | None = None,
    ) -> bool:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.LogEventRequest(
                scan_id=scan_id,
                component=component or "",
                log_type=classification,
                message=message,
            )
            self._get_stub().LogScanEvent(req, timeout=self.config.timeout)
            return True
        except Exception as e:
            log.debug("gRPC LogScanEvent failed: %s", e)
            return False

    def scan_log_get(
        self,
        scan_id: str,
        limit: int = 0,
        offset: int = 0,
        log_type: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.GetScanLogsRequest(
                scan_id=scan_id, limit=limit, offset=offset
            )
            resp = self._get_stub().GetScanLogs(req, timeout=self.config.timeout)
            logs = [self._log_record_to_dict(r) for r in resp.logs]
            if log_type:
                logs = [l for l in logs if l["type"] == log_type]
            return logs
        except Exception as e:
            log.error("gRPC GetScanLogs failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Config Operations
    # ------------------------------------------------------------------

    def config_set(
        self, config_data: dict[str, str], scope: str = "GLOBAL"
    ) -> bool:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            kvs = [
                pb2.KeyValue(key=k, value=str(v))
                for k, v in config_data.items()
            ]
            req = pb2.SetConfigRequest(config=kvs)
            self._get_stub().SetConfig(req, timeout=self.config.timeout)
            return True
        except Exception as e:
            log.error("gRPC SetConfig failed: %s", e)
            return False

    def config_get(self, scope: str = "GLOBAL") -> dict[str, str]:
        try:
            from spiderfoot import spiderfoot_pb2 as pb2

            req = pb2.GetConfigRequest()
            resp = self._get_stub().GetConfig(req, timeout=self.config.timeout)
            return {kv.key: kv.value for kv in resp.config}
        except Exception as e:
            log.error("gRPC GetConfig failed: %s", e)
            return {}

    def scan_config_set(
        self, scan_id: str, config_data: dict[str, str]
    ) -> bool:
        # Reuse SetConfig — proto doesn't distinguish per-scan config
        return self.config_set(config_data, scope=scan_id)

    # ------------------------------------------------------------------
    # Correlation Operations
    # ------------------------------------------------------------------

    def correlation_store(
        self,
        correlation_id: str,
        scan_id: str,
        title: str,
        rule_id: str,
        rule_name: str,
        rule_risk: str,
        rule_descr: str,
        rule_logic: str,
        event_hashes: list[str],
    ) -> bool:
        # No correlation RPC in proto yet — log warning
        log.warning(
            "gRPC correlation_store not yet supported by proto; "
            "correlation_id=%s, scan_id=%s",
            correlation_id,
            scan_id,
        )
        return False

    def correlation_get_by_scan(
        self, scan_id: str
    ) -> list[dict[str, Any]]:
        log.warning("gRPC correlation_get_by_scan not yet supported by proto")
        return []

    # ------------------------------------------------------------------
    # Aggregate / Summary Operations
    # ------------------------------------------------------------------

    def scan_result_summary(self, scan_id: str) -> dict[str, int]:
        # Derive from events — no dedicated RPC
        try:
            events = self.event_get_by_scan(scan_id)
            summary: dict[str, int] = {}
            for e in events:
                et = e.get("type", "UNKNOWN")
                summary[et] = summary.get(et, 0) + 1
            return summary
        except Exception as e:
            log.error("gRPC scan_result_summary failed: %s", e)
            return {}

    def event_types_list(self) -> list[dict[str, str]]:
        # No dedicated RPC — return empty
        log.debug("gRPC event_types_list: no dedicated RPC available")
        return []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None

    def __del__(self):
        self.close()

    def __repr__(self) -> str:
        return f"GrpcDataService(target={self._target!r})"
