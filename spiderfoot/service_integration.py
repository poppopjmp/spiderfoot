#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         service_integration
# Purpose:      Wires the extracted service layer (EventBus, HttpService,
#               DnsService, CacheService, DataService, Metrics) into the
#               existing scan engine (SpiderFootScanner) without breaking
#               backward compatibility.
#
#               Call `integrate_services()` once during application startup.
#               Call `wire_scan_services()` at the start of each scan.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Service Integration

This module connects the new service layer to the existing scan engine.
It is designed to be non-invasive: the scanner and modules continue to
work exactly as before, but gain access to the new services automatically.

Startup::

    from spiderfoot.service_integration import integrate_services
    integrate_services(sf_config)

Per-scan wiring::

    from spiderfoot.service_integration import wire_scan_services
    wire_scan_services(scanner_instance, scan_id)
"""
from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger("spiderfoot.service_integration")


def integrate_services(sf_config: dict[str, Any]) -> bool:
    """Initialize the global service registry from SpiderFoot configuration.

    This should be called once during application startup (sf.py, sfapi.py,
    or service_runner.py). It sets up the service registry with lazy
    factories for all extracted services.

    Args:
        sf_config: SpiderFoot configuration dict (from sf.py or env).

    Returns:
        True if services were initialized, False on error.
    """
    try:
        from spiderfoot.service_registry import initialize_services, get_registry

        initialize_services(sf_config)
        registry = get_registry()

        services = registry.list_services()
        log.info("Service registry initialized with %d services: %s",
                 len(services), ", ".join(services))

        return True

    except ImportError as e:
        log.warning("Service registry not available: %s", e)
        return False
    except Exception as e:
        log.error("Failed to initialize services: %s", e)
        return False


def wire_scan_services(scanner: Any, scan_id: str) -> None:
    """Wire services into a running scan.

    Called at the beginning of __startScan() to connect metrics,
    event bus, event bridge, module loader, and data service to the
    scan lifecycle.

    Args:
        scanner: SpiderFootScanner instance.
        scan_id: The scan instance ID.
    """
    try:
        _wire_scan_metrics(scan_id)
        _wire_scan_eventbus(scan_id)
        _wire_scan_vector(scan_id)
        _wire_scan_event_bridge(scanner, scan_id)
        _wire_module_loader(scanner)
        _wire_repository_factory(scanner)
        log.debug("Services wired for scan %s", scan_id)
    except Exception as e:
        log.warning("Partial service wiring for scan %s: %s", scan_id, e)


def wire_module_services(module: Any, sf_config: dict[str, Any]) -> None:
    """Inject service references into a module if it supports them.

    Called after mod.setup() for each module. If the module is a
    SpiderFootModernPlugin, it already has service access via the
    registry. For legacy SpiderFootPlugin instances, this is a no-op.

    Args:
        module: SpiderFootPlugin or SpiderFootModernPlugin instance.
        sf_config: SpiderFoot configuration dict.
    """
    try:
        from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin
        if isinstance(module, SpiderFootModernPlugin):
            # Service access is already available via properties
            log.debug("Module %s is modern, services auto-available",
                      getattr(module, "__name__", "unknown"))
            return
    except ImportError:
        pass

    # For legacy modules, we can optionally inject a metrics wrapper
    try:
        _inject_legacy_metrics(module)
    except Exception as e:
        log.debug("Legacy metrics injection failed for module: %s", e)


def complete_scan_services(scan_id: str, status: str = "FINISHED",
                           duration: float = 0.0) -> None:
    """Record scan completion in metrics, event bus, event bridge and vector.

    Args:
        scan_id: The completed scan's ID.
        status: Final status (FINISHED, ABORTED, ERROR).
        duration: Total scan duration in seconds.
    """
    # Tear down the scan event bridge (pushes completion + stats)
    try:
        from spiderfoot.scan.scan_event_bridge import teardown_scan_bridge
        teardown_scan_bridge(scan_id, status=status)
    except ImportError:
        log.debug("ScanEventBridge not available — teardown skipped")
    except Exception as e:
        log.warning("Failed to teardown scan event bridge for %s: %s", scan_id, e)

    try:
        from spiderfoot.observability.metrics import SCANS_TOTAL, ACTIVE_SCANS, SCAN_DURATION
        SCANS_TOTAL.labels(status=status.lower()).inc()
        ACTIVE_SCANS.dec()
        if duration > 0:
            SCAN_DURATION.observe(duration)
    except ImportError:
        log.debug("Metrics module not available — scan completion metrics skipped")

    try:
        from spiderfoot.service_registry import get_registry, SERVICE_EVENT_BUS
        registry = get_registry()
        if registry.has(SERVICE_EVENT_BUS):
            bus = registry.get(SERVICE_EVENT_BUS)
            bus.publish(f"scan.{status.lower()}", {
                "scan_id": scan_id,
                "status": status,
                "duration": duration,
                "timestamp": time.time(),
            })
    except ImportError:
        log.debug("EventBus not available — scan completion event not published")
    except Exception as e:
        log.warning("Failed to publish scan completion event for %s: %s", scan_id, e)

    try:
        from spiderfoot.service_registry import get_registry, SERVICE_VECTOR
        registry = get_registry()
        if registry.has(SERVICE_VECTOR):
            vector = registry.get(SERVICE_VECTOR)
            vector.scan_status(scan_id, status, {
                "duration": duration,
            })
    except ImportError:
        log.debug("Vector sink not available — scan completion status not sent")
    except Exception as e:
        log.debug("Vector.dev completion status send failed for %s: %s", scan_id, e)

    # Auto-index scan events into Qdrant for RAG/Rerank correlations
    if status == "FINISHED":
        _index_scan_events_to_qdrant(scan_id)
        _archive_scan_summary_to_minio(scan_id, duration)


# ---------------------------------------------------------------------------
# Qdrant vector indexing at scan completion
# ---------------------------------------------------------------------------

def _index_scan_events_to_qdrant(scan_id: str) -> None:
    """Index all events from a completed scan into a per-scan Qdrant collection.

    This is called automatically at scan completion when vector correlation
    is enabled and auto-indexing is on.  Events are fetched from the database,
    converted to VectorPoints, and batch-upserted into a ``scan_{scan_id}``
    collection.

    The function is fully self-contained and will not propagate exceptions
    to avoid disrupting the normal scan completion flow.
    """
    import os
    # Check if vector correlation auto-indexing is enabled
    enabled = os.environ.get("SF_VECTOR_CORRELATION_ENABLED", "true").lower()
    auto_index = os.environ.get("SF_VECTOR_AUTO_INDEX", "true").lower()
    if enabled not in ("1", "true", "yes") or auto_index not in ("1", "true", "yes"):
        log.debug("Vector auto-indexing disabled for scan %s", scan_id)
        return

    try:
        from spiderfoot.correlations.vector_collection_manager import get_collection_manager
        from spiderfoot.qdrant_client import VectorPoint

        mgr = get_collection_manager()
        mgr.create_scan_collection(scan_id)
        log.info("Created Qdrant collection for scan %s", scan_id)
    except Exception as e:
        log.warning("Failed to create Qdrant collection for scan %s: %s", scan_id, e)
        return

    # Fetch all scan events from the database
    try:
        from spiderfoot.db import SpiderFootDb
        dbh = SpiderFootDb(SpiderFootDb.build_config_from_env())
        rows = dbh.scanResultEvent(scan_id, eventType="ALL", filterFp=True)
        dbh.close()
    except Exception as e:
        log.warning("Failed to fetch events for Qdrant indexing (scan %s): %s", scan_id, e)
        return

    if not rows:
        log.info("No events to index for scan %s", scan_id)
        return

    # Convert DB rows to VectorPoints for the collection manager
    # Row format: (generated, data, module, hash, type, source_event_hash,
    #              confidence, visibility, risk)
    try:
        from spiderfoot.services.embedding_service import EmbeddingService, EmbeddingConfig
        embed_svc = EmbeddingService(EmbeddingConfig.from_env())

        points: list[VectorPoint] = []
        texts: list[str] = []
        metadata_list: list[dict] = []

        for row in rows:
            generated, data, module, evt_hash, evt_type, source_hash, confidence, visibility, risk = (
                row[0], row[1], row[2], row[3], row[4], row[5],
                row[6] if len(row) > 6 else 50,
                row[7] if len(row) > 7 else 50,
                row[8] if len(row) > 8 else 0,
            )

            # Skip empty data or ROOT events
            if not data or evt_type == "ROOT":
                continue

            # Build text representation for embedding
            text = f"[{evt_type}] {data}"
            if len(text) > 2048:
                text = text[:2048]

            texts.append(text)
            metadata_list.append({
                "scan_id": scan_id,
                "event_type": evt_type,
                "module": module or "",
                "hash": evt_hash or "",
                "source_hash": source_hash or "",
                "confidence": confidence,
                "visibility": visibility,
                "risk": risk,
                "generated": generated or 0,
                "data_preview": data[:500] if data else "",
            })

        if not texts:
            log.info("No indexable events for scan %s", scan_id)
            return

        # Batch embed all texts
        log.info("Embedding %d events for scan %s", len(texts), scan_id)
        batch_size = int(os.environ.get("SF_EMBEDDING_BATCH_SIZE", "32"))
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            vectors = embed_svc.embed_texts(batch)
            all_vectors.extend(vectors)

        # Build VectorPoints
        for idx, (vector, meta) in enumerate(zip(all_vectors, metadata_list)):
            points.append(VectorPoint(
                id=meta["hash"] or f"evt_{idx}",
                vector=vector,
                payload=meta,
            ))

        # Upsert into the scan collection
        mgr.index_events(scan_id, points)
        log.info("Indexed %d events into Qdrant for scan %s", len(points), scan_id)

    except Exception as e:
        log.warning("Failed to index events into Qdrant for scan %s: %s", scan_id, e)


# ---------------------------------------------------------------------------
# Internal wiring helpers
# ---------------------------------------------------------------------------

def _wire_scan_metrics(scan_id: str) -> None:
    """Initialize scan-level metrics."""
    try:
        from spiderfoot.observability.metrics import SCANS_TOTAL, ACTIVE_SCANS
        SCANS_TOTAL.labels(status="started").inc()
        ACTIVE_SCANS.inc()
    except ImportError:
        log.debug("Metrics module not available — scan metrics disabled")


def _wire_scan_eventbus(scan_id: str) -> None:
    """Publish scan start event to the event bus."""
    try:
        from spiderfoot.service_registry import get_registry, SERVICE_EVENT_BUS
        registry = get_registry()
        if registry.has(SERVICE_EVENT_BUS):
            bus = registry.get(SERVICE_EVENT_BUS)
            bus.publish("scan.started", {
                "scan_id": scan_id,
                "timestamp": time.time(),
            })
    except ImportError:
        log.debug("EventBus not available — scan start event not published")
    except Exception as e:
        log.warning("Failed to publish scan.started event for %s: %s", scan_id, e)


def _wire_scan_vector(scan_id: str) -> None:
    """Send scan start event to Vector.dev."""
    try:
        from spiderfoot.service_registry import get_registry, SERVICE_VECTOR
        registry = get_registry()
        if registry.has(SERVICE_VECTOR):
            vector = registry.get(SERVICE_VECTOR)
            vector.scan_status(scan_id, "STARTED", {})
    except ImportError:
        log.debug("Vector sink not available — scan start event not sent")
    except Exception as e:
        log.debug("Vector.dev scan status send failed for %s: %s", scan_id, e)


def _inject_legacy_metrics(module) -> None:
    """Wrap a legacy module's handleEvent with metrics instrumentation.

    Uses a wrapper class that preserves the original method's identity
    while adding timing metrics. This avoids monkey-patching which breaks
    isinstance checks and makes debugging opaque.
    """
    try:
        from spiderfoot.observability.metrics import MODULE_DURATION, EVENTS_PROCESSED, MODULE_ERRORS
    except ImportError:
        return

    original_handler = module.handleEvent
    module_name = getattr(module, "__name__", "unknown")

    # Skip if already instrumented (idempotent)
    if getattr(original_handler, '_sf_instrumented', False):
        return

    import functools

    @functools.wraps(original_handler)
    def instrumented_handler(event: Any) -> Any:
        """Invoke the original handler with metrics instrumentation."""
        t0 = time.monotonic()
        try:
            result = original_handler(event)
            MODULE_DURATION.observe(time.monotonic() - t0)
            EVENTS_PROCESSED.labels(module=module_name).inc()
            return result
        except Exception as e:
            MODULE_ERRORS.labels(
                module=module_name, error_type=type(e).__name__
            ).inc()
            raise

    instrumented_handler._sf_instrumented = True
    instrumented_handler._sf_original = original_handler
    module.handleEvent = instrumented_handler


def _wire_scan_event_bridge(scanner, scan_id: str) -> None:
    """Create and attach a ScanEventBridge for real-time event relay.

    The bridge is stored on the scanner so ``waitForThreads()`` can
    call ``bridge.forward(sfEvent)`` for each dispatched event.
    """
    try:
        from spiderfoot.scan.scan_event_bridge import create_scan_bridge
        bridge = create_scan_bridge(scan_id)
        # Attach to scanner for easy access in waitForThreads
        scanner._event_bridge = bridge
        target_value = getattr(scanner, '_SpiderFootScanner__targetValue', '')
        bridge.start(target=target_value)
    except Exception as e:
        log.debug("Scan event bridge not available: %s", e)


def _wire_module_loader(scanner) -> None:
    """Attach a ModuleLoader to the scanner for registry-driven loading.

    The loader is stored as ``scanner._module_loader`` and used by
    ``__startScan()`` as the primary module loading path with fallback
    to the legacy ``__import__`` loop.
    """
    try:
        from spiderfoot.plugins.module_loader import init_module_loader
        loader = init_module_loader()
        scanner._module_loader = loader
        log.debug("ModuleLoader attached to scanner")
    except Exception as e:
        log.debug("ModuleLoader not available: %s", e)


def _wire_repository_factory(scanner) -> None:
    """Initialize the global RepositoryFactory and attach to scanner.

    The factory provides ``ScanRepository``, ``EventRepository``, and
    ``ConfigRepository`` instances for use during scan execution.
    """
    try:
        from spiderfoot.db.repositories import (
            init_repository_factory,
            get_repository_factory,
        )
        config = getattr(scanner, '_SpiderFootScanner__config', None)
        if config is None:
            config = {}
        factory = get_repository_factory()
        if factory is None:
            factory = init_repository_factory(config)
        scanner._repo_factory = factory
        log.debug("RepositoryFactory attached to scanner")
    except Exception as e:
        log.debug("RepositoryFactory not available: %s", e)


# ---------------------------------------------------------------------------
# MinIO scan summary archival at scan completion
# ---------------------------------------------------------------------------

def _archive_scan_summary_to_minio(scan_id: str, duration: float = 0.0) -> None:
    """Archive a JSON summary of the completed scan to MinIO."""
    import os
    enabled = os.environ.get("SF_MINIO_ENABLED", "true").lower()
    if enabled not in ("1", "true", "yes"):
        return

    try:
        import json
        from spiderfoot.storage.minio_manager import get_storage_manager
        from spiderfoot.db import SpiderFootDb

        dbh = SpiderFootDb(SpiderFootDb.build_config_from_env())
        scan_info = dbh.scanInstanceGet(scan_id)
        result_count = len(dbh.scanResultEvent(scan_id) or [])
        dbh.close()

        summary = {
            "scan_id": scan_id,
            "name": scan_info[0] if scan_info else "",
            "target": scan_info[1] if scan_info and len(scan_info) > 1 else "",
            "status": "FINISHED",
            "duration_seconds": duration,
            "result_count": result_count,
            "timestamp": time.time(),
        }

        mgr = get_storage_manager()
        mgr.put_artefact(
            scan_id,
            "scan_summary.json",
            json.dumps(summary, indent=2).encode("utf-8"),
            content_type="application/json",
        )
        log.info("Archived scan summary to MinIO for scan %s", scan_id)

    except ImportError:
        log.debug("MinIO storage not available — scan summary archival skipped")
    except Exception as e:
        log.debug("Failed to archive scan summary to MinIO for %s: %s", scan_id, e)
