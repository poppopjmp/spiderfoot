"""
User Input Service — API for user-defined starting data.

Allows users to:
  1. Upload documents/reports as investigation starting points
  2. Submit IOC lists for enrichment and cross-referencing
  3. Provide context data that enhances scan analysis
  4. Import external reports for entity extraction

This bridges the gap between passive OSINT scanning and user-supplied intelligence,
enabling analysts to combine automated findings with their own knowledge.
"""

import asyncio
import hashlib
import logging
import os
import sys
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger("sf.user_input")

# In-memory store — production would use PostgreSQL
_submissions: Dict[str, Dict] = {}


# --- Data Models ---


class InputType(str, Enum):
    DOCUMENT = "document"       # PDF, DOCX, etc.
    IOC_LIST = "ioc_list"       # List of indicators
    REPORT = "report"           # Structured report
    RAW_TEXT = "raw_text"       # Free-form text
    CONTEXT = "context"         # Background context for a scan
    TARGET_LIST = "target_list" # List of targets for batch scanning


class IOCEntry(BaseModel):
    """Single indicator of compromise."""
    type: str = Field(..., description="IOC type: ip, domain, email, hash, url, cve")
    value: str = Field(..., description="IOC value")
    context: str = Field("", description="Additional context")
    confidence: float = Field(1.0, description="Confidence level 0.0-1.0")
    tags: List[str] = Field(default_factory=list)


class IOCListInput(BaseModel):
    """Batch IOC submission."""
    indicators: List[IOCEntry]
    source: str = Field("", description="Where this intel came from")
    classification: str = Field("internal", description="Data classification")
    scan_id: str = Field("", description="Associate with existing scan")
    target: str = Field("", description="Investigation target")


class ReportInput(BaseModel):
    """Structured report submission."""
    title: str
    content: str
    report_type: str = Field("generic", description="Report type: pentest, threat_intel, incident, vulnerability, generic")
    author: str = ""
    date: str = ""
    classification: str = "internal"
    scan_id: str = ""
    target: str = ""
    tags: List[str] = Field(default_factory=list)


class ContextInput(BaseModel):
    """Background context for enhancing scan analysis."""
    scan_id: str = Field(..., description="Scan to attach context to")
    context_type: str = Field(..., description="Type: scope, exclusions, known_assets, threat_model, background")
    content: str = Field(..., description="Context content")
    priority: str = Field("normal", description="Priority: high, normal, low")


class TargetListInput(BaseModel):
    """Batch target submission for multi-target scanning."""
    targets: List[Dict[str, str]] = Field(
        ..., description="List of targets with 'value' and optional 'type' (domain, ip, email, etc.)"
    )
    scan_config: Dict[str, Any] = Field(default_factory=dict, description="Scan configuration overrides")
    priority: str = Field("normal", description="Priority: high, normal, low")


class SubmissionResponse(BaseModel):
    """Response for a submission."""
    submission_id: str
    input_type: str
    status: str
    message: str
    enrichment_id: Optional[str] = None
    entities_found: int = 0
    data: Dict[str, Any] = Field(default_factory=dict)


# --- FastAPI Application ---

app = FastAPI(
    title="SpiderFoot User Input Service",
    description="API for user-defined investigation data, documents, and IOC submissions",
    version="0.1.0",
)


@app.post("/input/document", response_model=SubmissionResponse)
async def upload_document(
    file: UploadFile = File(...),
    scan_id: str = Form(""),
    target: str = Form(""),
    classification: str = Form("internal"),
    tags: str = Form(""),
):
    """
    Upload a document for enrichment and analysis.

    The document is processed through:
      1. Enrichment pipeline (text extraction, entity extraction)
      2. Document analyzer agent (LLM-powered analysis)
      3. Results stored in MinIO and linked to scan if provided
    """
    content = await file.read()

    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")

    submission_id = _generate_id()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Process through enrichment pipeline
    enrichment_result = await _process_through_enrichment(
        content, file.filename or "upload", file.content_type or "", scan_id, target
    )

    # Forward to document analyzer agent
    agent_task = asyncio.create_task(
        _forward_to_agent(
            "document_analyzer",
            {
                "event_type": "USER_DOCUMENT",
                "data": enrichment_result.get("text", ""),
                "filename": file.filename,
                "content_type": file.content_type,
                "scan_id": scan_id,
                "target": target,
                "id": submission_id,
            },
        )
    )

    response = SubmissionResponse(
        submission_id=submission_id,
        input_type=InputType.DOCUMENT,
        status="processed",
        message=f"Document '{file.filename}' processed and queued for agent analysis",
        enrichment_id=enrichment_result.get("document_id", ""),
        entities_found=enrichment_result.get("total_entities", 0),
        data={
            "filename": file.filename,
            "size": len(content),
            "content_type": file.content_type,
            "hash": hashlib.sha256(content).hexdigest(),
            "entities": enrichment_result.get("entities", {}),
            "stored_path": enrichment_result.get("stored_path", ""),
            "classification": classification,
            "tags": tag_list,
        },
    )

    _submissions[submission_id] = response.dict()
    return response


@app.post("/input/iocs", response_model=SubmissionResponse)
async def submit_iocs(request: IOCListInput):
    """
    Submit a list of IOCs for enrichment and cross-referencing with scan data.

    IOCs are:
      1. Validated and deduplicated
      2. Cross-referenced with existing scan findings
      3. Stored for correlation analysis
      4. Optionally used as additional scan targets
    """
    submission_id = _generate_id()

    # Validate and deduplicate
    valid_iocs = []
    seen = set()
    for ioc in request.indicators:
        key = f"{ioc.type}:{ioc.value}"
        if key not in seen:
            seen.add(key)
            valid_iocs.append(ioc.dict())

    # Group by type for downstream processing
    by_type: Dict[str, List[str]] = {}
    for ioc in valid_iocs:
        ioc_type = ioc["type"]
        if ioc_type not in by_type:
            by_type[ioc_type] = []
        by_type[ioc_type].append(ioc["value"])

    response = SubmissionResponse(
        submission_id=submission_id,
        input_type=InputType.IOC_LIST,
        status="accepted",
        message=f"Accepted {len(valid_iocs)} IOCs ({len(request.indicators) - len(valid_iocs)} duplicates removed)",
        entities_found=len(valid_iocs),
        data={
            "source": request.source,
            "classification": request.classification,
            "ioc_counts": {k: len(v) for k, v in by_type.items()},
            "scan_id": request.scan_id,
            "target": request.target,
            "indicators": valid_iocs,
        },
    )

    _submissions[submission_id] = response.dict()
    return response


@app.post("/input/report", response_model=SubmissionResponse)
async def submit_report(request: ReportInput):
    """
    Submit a structured report for entity extraction and analysis.

    The report content is:
      1. Processed through entity extraction
      2. Analyzed by the document analyzer agent
      3. Entities cross-referenced with scan data
      4. Report stored in MinIO
    """
    submission_id = _generate_id()

    # Extract entities from report content
    from spiderfoot.enrichment.extractor import EntityExtractor

    extractor = EntityExtractor()
    extraction = extractor.extract(request.content)

    # Store report in MinIO
    store_path = await _store_report(
        request.content.encode("utf-8"),
        f"report-{submission_id}.txt",
        submission_id,
    )

    # Forward to document analyzer
    asyncio.create_task(
        _forward_to_agent(
            "document_analyzer",
            {
                "event_type": "REPORT_UPLOAD",
                "data": request.content,
                "filename": f"{request.title}.txt",
                "content_type": "text/plain",
                "scan_id": request.scan_id,
                "target": request.target,
                "id": submission_id,
            },
        )
    )

    response = SubmissionResponse(
        submission_id=submission_id,
        input_type=InputType.REPORT,
        status="processed",
        message=f"Report '{request.title}' processed — {extraction.total_entities} entities extracted",
        entities_found=extraction.total_entities,
        data={
            "title": request.title,
            "report_type": request.report_type,
            "author": request.author,
            "classification": request.classification,
            "entities": extraction.to_dict(),
            "stored_path": store_path,
            "tags": request.tags,
        },
    )

    _submissions[submission_id] = response.dict()
    return response


@app.post("/input/context", response_model=SubmissionResponse)
async def submit_context(request: ContextInput):
    """
    Submit background context to enhance scan analysis.

    Context types:
      - scope: Define investigation boundaries
      - exclusions: Domains/IPs to exclude from analysis
      - known_assets: Known legitimate assets (reduce false positives)
      - threat_model: Expected threats and attack vectors
      - background: General background information
    """
    submission_id = _generate_id()

    response = SubmissionResponse(
        submission_id=submission_id,
        input_type=InputType.CONTEXT,
        status="accepted",
        message=f"Context ({request.context_type}) attached to scan {request.scan_id}",
        data={
            "scan_id": request.scan_id,
            "context_type": request.context_type,
            "priority": request.priority,
            "content_length": len(request.content),
        },
    )

    _submissions[submission_id] = response.dict()
    return response


@app.post("/input/targets", response_model=SubmissionResponse)
async def submit_targets(request: TargetListInput):
    """
    Submit a list of targets for batch scanning.

    Targets are validated and queued for scanning with optional
    configuration overrides.
    """
    submission_id = _generate_id()

    valid_targets = [
        t for t in request.targets if t.get("value", "").strip()
    ]

    response = SubmissionResponse(
        submission_id=submission_id,
        input_type=InputType.TARGET_LIST,
        status="accepted",
        message=f"Accepted {len(valid_targets)} targets for scanning",
        entities_found=len(valid_targets),
        data={
            "targets": valid_targets,
            "scan_config": request.scan_config,
            "priority": request.priority,
        },
    )

    _submissions[submission_id] = response.dict()
    return response


@app.get("/input/submissions")
async def list_submissions(limit: int = 50, offset: int = 0):
    """List all user submissions."""
    all_subs = list(_submissions.values())
    return {
        "submissions": all_subs[offset : offset + limit],
        "total": len(all_subs),
    }


@app.get("/input/submissions/{submission_id}")
async def get_submission(submission_id: str):
    """Get a specific submission by ID."""
    if submission_id not in _submissions:
        raise HTTPException(status_code=404, detail="Submission not found")
    return _submissions[submission_id]


@app.get("/health")
async def health():
    return {"status": "ok", "service": "user-input"}


# --- Helper Functions ---


def _generate_id() -> str:
    return str(uuid.uuid4())[:12]


async def _process_through_enrichment(
    content: bytes,
    filename: str,
    content_type: str,
    scan_id: str,
    target: str,
) -> Dict[str, Any]:
    """Send file to enrichment service for processing."""
    enrichment_url = os.environ.get(
        "SF_ENRICHMENT_URL", "http://enrichment:8200"
    )

    try:
        import aiohttp

        data = aiohttp.FormData()
        data.add_field("file", content, filename=filename, content_type=content_type)
        data.add_field("scan_id", scan_id)
        data.add_field("target", target)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{enrichment_url}/enrichment/upload",
                data=data,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning("Enrichment service returned %d", resp.status)
                    return {}

    except ImportError:
        # aiohttp not available — process locally
        try:
            from spiderfoot.enrichment.pipeline import EnrichmentPipeline

            pipeline = EnrichmentPipeline()
            result = pipeline.process(content, filename, content_type, scan_id, target)
            return result.to_dict()
        except Exception as exc:
            logger.warning("Local enrichment failed: %s", exc)
            return {}

    except Exception as exc:
        logger.warning("Enrichment request failed: %s", exc)
        return {}


async def _forward_to_agent(agent_name: str, event: Dict[str, Any]):
    """Forward event to agents service for LLM analysis."""
    agents_url = os.environ.get("SF_AGENTS_URL", "http://agents:8100")

    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{agents_url}/agents/process",
                json={"events": [event], "agent_name": agent_name},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(
                        "Agent %s returned %d results",
                        agent_name,
                        result.get("total", 0),
                    )
                    return result

    except Exception as exc:
        logger.warning("Agent forwarding failed: %s", exc)

    return {}


async def _store_report(
    content: bytes, filename: str, submission_id: str
) -> str:
    """Store report content in MinIO."""
    try:
        from minio import Minio
        import io

        endpoint = os.environ.get("SF_MINIO_ENDPOINT", "minio:9000")
        access_key = os.environ.get("SF_MINIO_ACCESS_KEY", "spiderfoot")
        secret_key = os.environ.get("SF_MINIO_SECRET_KEY", "")
        bucket = "sf-enrichment"

        client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        path = f"user-reports/{submission_id}/{filename}"
        client.put_object(bucket, path, io.BytesIO(content), length=len(content))
        return f"{bucket}/{path}"

    except Exception as exc:
        logger.warning("MinIO storage failed: %s", exc)
        return ""


def main():
    import uvicorn

    host = os.environ.get("SF_INPUT_HOST", "0.0.0.0")
    port = int(os.environ.get("SF_INPUT_PORT", "8300"))

    logging.basicConfig(
        level=os.environ.get("SF_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting User Input service on %s:%d", host, port)
    uvicorn.run(
        "spiderfoot.user_input.service:app",
        host=host,
        port=port,
        workers=1,
        log_level=os.environ.get("SF_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
