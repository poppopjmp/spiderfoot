"""
Enrichment Service — FastAPI application for document processing.

Endpoints:
  POST /enrichment/upload       — Upload and process a document
  POST /enrichment/process-text — Process raw text content
  GET  /enrichment/status/{id}  — Get processing status
  GET  /enrichment/results/{id} — Get enrichment results
  GET  /metrics                 — Prometheus metrics
  GET  /health                  — Health check
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from spiderfoot.enrichment.pipeline import EnrichmentPipeline, EnrichmentResult

logger = logging.getLogger("sf.enrichment.service")

# In-memory result store (in production, use PostgreSQL)
_results: Dict[str, Dict] = {}
_pipeline: Optional[EnrichmentPipeline] = None

# Metrics counters
_metrics = {
    "documents_processed": 0,
    "documents_failed": 0,
    "total_entities_extracted": 0,
    "total_bytes_processed": 0,
    "total_processing_time_ms": 0.0,
}


def _get_pipeline() -> EnrichmentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = EnrichmentPipeline()
    return _pipeline


app = FastAPI(
    title="SpiderFoot Enrichment Service",
    description="Document and file enrichment pipeline for OSINT data",
    version="0.1.0",
)


class TextProcessRequest(BaseModel):
    text: str
    filename: str = "input.txt"
    content_type: str = "text/plain"
    scan_id: str = ""
    target: str = ""


class BatchProcessRequest(BaseModel):
    items: List[TextProcessRequest]


@app.post("/enrichment/upload")
async def upload_document(
    file: UploadFile = File(...),
    scan_id: str = Form(""),
    target: str = Form(""),
):
    """Upload and process a document through the enrichment pipeline."""
    content = await file.read()

    if len(content) > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")

    pipeline = _get_pipeline()

    # Process in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        pipeline.process,
        content,
        file.filename or "upload",
        file.content_type or "",
        scan_id,
        target,
        True,  # store in MinIO
    )

    _update_metrics(result)
    _results[result.document_id] = result.to_dict()

    return result.to_dict()


@app.post("/enrichment/process-text")
async def process_text(request: TextProcessRequest):
    """Process raw text content through the enrichment pipeline."""
    content = request.text.encode("utf-8")

    pipeline = _get_pipeline()

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        pipeline.process,
        content,
        request.filename,
        request.content_type,
        request.scan_id,
        request.target,
        True,
    )

    _update_metrics(result)
    _results[result.document_id] = result.to_dict()

    return result.to_dict()


@app.post("/enrichment/batch")
async def batch_process(request: BatchProcessRequest):
    """Process multiple text items in batch."""
    pipeline = _get_pipeline()
    results = []

    for item in request.items:
        content = item.text.encode("utf-8")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            pipeline.process,
            content,
            item.filename,
            item.content_type,
            item.scan_id,
            item.target,
            True,
        )
        _update_metrics(result)
        _results[result.document_id] = result.to_dict()
        results.append(result.to_dict())

    return {"results": results, "total": len(results)}


@app.get("/enrichment/results/{document_id}")
async def get_results(document_id: str):
    """Get enrichment results for a specific document."""
    if document_id not in _results:
        raise HTTPException(status_code=404, detail="Document not found")
    return _results[document_id]


@app.get("/enrichment/results")
async def list_results(limit: int = 50, offset: int = 0):
    """List recent enrichment results."""
    all_results = list(_results.values())
    return {
        "results": all_results[offset : offset + limit],
        "total": len(all_results),
        "limit": limit,
        "offset": offset,
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    lines = [
        "# HELP sf_enrichment_documents_total Documents processed",
        "# TYPE sf_enrichment_documents_total counter",
        f'sf_enrichment_documents_total{{status="success"}} {_metrics["documents_processed"]}',
        f'sf_enrichment_documents_total{{status="failed"}} {_metrics["documents_failed"]}',
        "",
        "# HELP sf_enrichment_entities_total Total entities extracted",
        "# TYPE sf_enrichment_entities_total counter",
        f"sf_enrichment_entities_total {_metrics['total_entities_extracted']}",
        "",
        "# HELP sf_enrichment_bytes_total Total bytes processed",
        "# TYPE sf_enrichment_bytes_total counter",
        f"sf_enrichment_bytes_total {_metrics['total_bytes_processed']}",
        "",
        "# HELP sf_enrichment_processing_time_ms Total processing time in ms",
        "# TYPE sf_enrichment_processing_time_ms counter",
        f"sf_enrichment_processing_time_ms {_metrics['total_processing_time_ms']:.1f}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "enrichment"}


def _update_metrics(result: EnrichmentResult):
    """Update Prometheus metrics from enrichment result."""
    if result.is_success:
        _metrics["documents_processed"] += 1
    else:
        _metrics["documents_failed"] += 1

    if result.extraction:
        _metrics["total_entities_extracted"] += result.extraction.total_entities
    _metrics["total_bytes_processed"] += result.file_size
    _metrics["total_processing_time_ms"] += result.processing_time_ms


def main():
    import uvicorn

    host = os.environ.get("SF_ENRICHMENT_HOST", "0.0.0.0")
    port = int(os.environ.get("SF_ENRICHMENT_PORT", "8200"))
    workers = int(os.environ.get("SF_ENRICHMENT_WORKERS", "2"))

    logging.basicConfig(
        level=os.environ.get("SF_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting Enrichment service on %s:%d", host, port)
    uvicorn.run(
        "spiderfoot.enrichment.service:app",
        host=host,
        port=port,
        workers=workers,
        log_level=os.environ.get("SF_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
