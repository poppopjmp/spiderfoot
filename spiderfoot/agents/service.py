"""
Agents Service Runner
======================
FastAPI service that hosts all SpiderFoot AI agents.

Exposes (mounted at /agents):
  - POST /process              — Submit events for agent processing
  - POST /analyze              — Analyze uploaded documents
  - POST /report               — Generate scan report
  - GET  /status               — Agent status and metrics
  - GET  /metrics              — Prometheus metrics endpoint
  - GET  /health               — Health check

Agents consume events from the event bus (Redis pub/sub) and can also
be invoked directly via the REST API.
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logger = logging.getLogger("sf.agents.service")

# ---------------------------------------------------------------------------
# Report persistence (found missing 2026-09-12: this /report endpoint is the
# only path exercised by the frontend's ReportTab, but it never saved
# anything server-side — the generated markdown only ever reached
# localStorage in the browser that requested it. sf-api's own
# api/routers/reports.py already has a working Postgres-backed ReportStore;
# this just reuses it so a report survives a different browser/device too.
# Lazily initialised and best-effort: if SF_POSTGRES_DSN isn't set (e.g. a
# standalone/dev run of sf-agents with no DB wired up), persistence is
# silently skipped and the endpoint behaves exactly as before.
# ---------------------------------------------------------------------------
_report_store: Any = None
_report_store_init_attempted = False


def _get_report_store() -> Any:
    """Lazily initialise the shared ReportStore singleton, if available."""
    global _report_store, _report_store_init_attempted
    if _report_store is not None or _report_store_init_attempted:
        return _report_store
    _report_store_init_attempted = True
    try:
        from spiderfoot.reporting.report_storage import ReportStore, StoreConfig
        _report_store = ReportStore(StoreConfig())
        logger.info(
            "Report persistence enabled (backend=%s)",
            _report_store.config.backend.value,
        )
    except Exception as exc:
        logger.info(
            "Report persistence unavailable, generated reports will only "
            "exist client-side (localStorage) until this is fixed: %s", exc,
        )
        _report_store = None
    return _report_store

# Agent registry and background execution state
_agents: Dict[str, Any] = {}
_event_listener_task: Optional[asyncio.Task] = None
_inflight_tasks: set[asyncio.Task] = set()
_dispatch_semaphore: Optional[asyncio.Semaphore] = None


def _positive_int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment."""
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        logger.warning("Invalid integer env var %s; using %s", name, default)
        return max(1, default)


def _init_agents() -> None:
    """Initialize all agent instances."""
    from spiderfoot.agents.credential_analyzer import CredentialAnalyzerAgent
    from spiderfoot.agents.document_analyzer import DocumentAnalyzerAgent
    from spiderfoot.agents.finding_validator import FindingValidatorAgent
    from spiderfoot.agents.iac_advisor import IaCAdvisorAgent
    from spiderfoot.agents.report_generator import ReportGeneratorAgent
    from spiderfoot.agents.text_summarizer import TextSummarizerAgent
    from spiderfoot.agents.threat_intel import ThreatIntelAnalyzerAgent

    agent_classes = [
        FindingValidatorAgent,
        CredentialAnalyzerAgent,
        TextSummarizerAgent,
        ReportGeneratorAgent,
        DocumentAnalyzerAgent,
        ThreatIntelAnalyzerAgent,
        IaCAdvisorAgent,
    ]

    for cls in agent_classes:
        try:
            agent = cls.create()
            if agent.config.enabled:
                _agents[agent.config.name] = agent
                logger.info(
                    "Agent '%s' initialized (model=%s)",
                    agent.config.name,
                    agent.config.llm_model,
                )
            else:
                logger.info("Agent '%s' disabled via config", agent.config.name)
        except Exception as exc:
            logger.error("Failed to initialize agent %s: %s", cls.__name__, exc)


async def _start_event_listener() -> None:
    """Listen for events on Redis pub/sub and dispatch to agents."""
    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    client = None
    pubsub = None

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url)
        pubsub = client.pubsub()
        await pubsub.subscribe("sf:events", "sf:agent_requests")

        logger.info("Event listener started on Redis pub/sub")

        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue

            try:
                event = json.loads(message["data"])
                event_type = event.get("event_type", "")

                for agent in _agents.values():
                    if _matches_event_type(event_type, agent.event_types):
                        await _schedule_agent_event(agent, event, client)

            except Exception as exc:
                logger.warning("Error processing event: %s", exc)

    except asyncio.CancelledError:
        logger.info("Event listener cancelled")
        raise
    except ImportError:
        logger.warning("redis package not available — event listener disabled")
    except Exception as exc:
        logger.error("Event listener error: %s", exc)
    finally:
        if pubsub is not None:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe("sf:events", "sf:agent_requests")
            close_pubsub = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
            if close_pubsub is not None:
                result = close_pubsub()
                if asyncio.iscoroutine(result):
                    await result

        if client is not None:
            with contextlib.suppress(Exception):
                await client.aclose()


async def _schedule_agent_event(agent: Any, event: Dict[str, Any], redis_client: Any) -> None:
    """Schedule one agent execution with service-wide backpressure."""
    global _dispatch_semaphore

    if _dispatch_semaphore is None:
        max_inflight = _positive_int_env("SF_AGENTS_MAX_INFLIGHT", 100)
        _dispatch_semaphore = asyncio.Semaphore(max_inflight)

    await _dispatch_semaphore.acquire()
    task = asyncio.create_task(_run_agent_event(agent, event, redis_client))
    _inflight_tasks.add(task)
    task.add_done_callback(_agent_task_done)


async def _run_agent_event(agent: Any, event: Dict[str, Any], redis_client: Any) -> None:
    """Run an agent event and persist the result if available."""
    try:
        result = await agent.handle_event(event)
        if result is not None:
            await _persist_agent_result(result, redis_client)
    finally:
        if _dispatch_semaphore is not None:
            _dispatch_semaphore.release()


def _agent_task_done(task: asyncio.Task) -> None:
    """Remove completed tasks and surface unexpected background failures."""
    _inflight_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("Agent background task failed: %s", exc)


async def _persist_agent_result(result: Any, redis_client: Any) -> None:
    """Store agent outputs for API/UI polling and publish a result event."""
    if redis_client is None:
        return

    ttl = _positive_int_env("SF_AGENT_RESULT_TTL_SECONDS", 86400 * 7)
    payload = json.dumps(result.to_dict(), default=str)
    scan_id = result.scan_id or "global"
    event_id = result.event_id or str(int(time.time() * 1000))
    key = f"sf:agent_result:{scan_id}:{result.agent_name}:{event_id}"

    try:
        await redis_client.set(key, payload, ex=max(60, ttl))
        await redis_client.publish("sf:agent_results", payload)
    except Exception as exc:
        logger.warning("Unable to persist agent result %s: %s", key, exc)


def _matches_event_type(event_type: str, patterns: List[str]) -> bool:
    """Check if event_type matches any of the agent's patterns (supports * wildcard)."""
    for pattern in patterns:
        if pattern.endswith("*"):
            if event_type.startswith(pattern[:-1]):
                return True
        elif event_type == pattern:
            return True
    return False


@asynccontextmanager
async def lifespan(app):
    """Application lifespan — init agents, start listener, and drain on shutdown."""
    global _dispatch_semaphore, _event_listener_task

    _init_agents()
    logger.info("Initialized %d agents", len(_agents))
    max_inflight = _positive_int_env("SF_AGENTS_MAX_INFLIGHT", 100)
    _dispatch_semaphore = asyncio.Semaphore(max_inflight)

    _event_listener_task = asyncio.create_task(_start_event_listener())

    yield

    if _event_listener_task:
        _event_listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _event_listener_task

    if _inflight_tasks:
        _done, pending = await asyncio.wait(_inflight_tasks, timeout=10)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    for agent in _agents.values():
        await agent.close()

    logger.info("Agents service shutdown")


# --- FastAPI Application ---

app = FastAPI(
    title="SpiderFoot Agents Service",
    description="AI-powered analysis agents for OSINT data enrichment",
    version="0.1.0",
    lifespan=lifespan,
)


class ProcessRequest(BaseModel):
    events: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)
    agent_name: Optional[str] = None  # specific agent, or all matching


class DocumentRequest(BaseModel):
    filename: str
    content: str
    content_type: str = "text/plain"
    target: str = ""
    scan_id: str = ""


class ReportRequest(BaseModel):
    scan_id: str = ""
    scan_ids: List[str] = Field(default_factory=list)
    target: str
    scan_name: str = ""
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    correlations: List[Dict[str, Any]] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
    agent_results: List[Dict[str, Any]] = Field(default_factory=list)
    geo_data: Dict[str, Any] = Field(default_factory=dict)


class IaCReviewRequest(BaseModel):
    """Request body for the IaC Advisor review endpoint."""

    scan_id: str = ""
    target: str = ""
    provider: str = "aws"
    bundle: Dict[str, Any] = Field(default_factory=dict)
    files: Dict[str, Any] = Field(default_factory=dict)


@app.post("/process")
async def process_events(request: ProcessRequest):
    """Submit events for agent processing."""
    results = []

    for event in request.events:
        event_type = event.get("event_type", "")

        for name, agent in _agents.items():
            if request.agent_name and name != request.agent_name:
                continue
            if _matches_event_type(event_type, agent.event_types):
                result = await agent.handle_event(event)
                if result:
                    results.append(result.to_dict())

    return {"results": results, "total": len(results)}


@app.post("/analyze")
async def analyze_document(request: DocumentRequest):
    """Analyze an uploaded document."""
    if "document_analyzer" not in _agents:
        raise HTTPException(status_code=503, detail="Document analyzer agent not available")

    agent = _agents["document_analyzer"]
    event = {
        "event_type": "DOCUMENT_UPLOAD",
        "data": request.content,
        "filename": request.filename,
        "content_type": request.content_type,
        "target": request.target,
        "scan_id": request.scan_id,
        "id": f"doc-{int(time.time())}",
    }

    result = await agent.handle_event(event)
    if result is None:
        raise HTTPException(status_code=500, detail="Agent returned no result")

    return result.to_dict()


@app.post("/report")
async def generate_report(request: ReportRequest):
    """Generate a scan report."""
    if "report_generator" not in _agents:
        raise HTTPException(status_code=503, detail="Report generator agent not available")

    agent = _agents["report_generator"]
    event = {
        "event_type": "REPORT_REQUEST",
        "scan_id": request.scan_id,
        "scan_ids": request.scan_ids,
        "target": request.target,
        "scan_name": request.scan_name,
        "findings": request.findings,
        "correlations": request.correlations,
        "stats": request.stats,
        "agent_results": request.agent_results,
        "geo_data": request.geo_data,
        "id": f"report-{int(time.time())}",
    }

    start = time.perf_counter()
    result = await agent.handle_event(event)
    if result is None:
        raise HTTPException(status_code=500, detail="Agent returned no result")

    result_dict = result.to_dict()
    # store.save() uses psycopg2, which is blocking — run it off the event
    # loop thread so a slow/contended DB write can't stall every other
    # in-flight request this async service is handling. Everything else in
    # this handler (the LLM call inside agent.handle_event) is already
    # properly async; this keeps that property rather than regressing it.
    await asyncio.to_thread(
        _persist_report, request, result_dict, (time.perf_counter() - start) * 1000,
    )
    return result_dict


def _persist_report(
    request: "ReportRequest", result_dict: Dict[str, Any], elapsed_ms: float,
) -> None:
    """Best-effort save of a generated report to the shared ReportStore.

    Found 2026-09-12: this endpoint is the only path the frontend's
    ReportTab actually calls, and it never saved anything server-side —
    the generated markdown only ever reached the requesting browser's own
    localStorage, so a different browser/device saw no report at all even
    though the underlying scan data was fine. sf-api's own
    api/routers/reports.py already has a working Postgres-backed
    ReportStore for a separate (unused-by-the-UI) report pipeline; this
    reuses it so a report survives a different browser/device too.

    Failure here must never break the response the caller already has —
    it's logged and swallowed, matching this endpoint's existing
    graceful-degradation style (e.g. Qdrant-unavailable handling above).
    """
    if result_dict.get("result_type") != "scan_report":
        return  # generation failed (result_type == "error") — nothing to save
    store = _get_report_store()
    if store is None:
        return
    data = result_dict.get("data", {})
    scan_id = result_dict.get("scan_id") or request.scan_id
    try:
        store.save({
            "report_id": str(uuid.uuid4()),
            "scan_id": scan_id,
            "title": f"AI Threat Intelligence Report: {data.get('target', request.target)}",
            "status": "completed",
            "report_type": "full",
            "progress_pct": 100.0,
            "message": "Report generation completed",
            "executive_summary": None,
            "recommendations": None,
            "sections": [{
                "title": "AI Threat Intelligence Report",
                "content": data.get("report", ""),
                "section_type": "full_report",
                "source_event_count": data.get("events_analysed", 0),
                "token_count": None,
            }],
            "metadata": {
                "source": "spiderfoot.agents.report_generator",
                "model": data.get("model"),
                "generated_at": data.get("generated_at"),
                "scan_ids": data.get("scan_ids", []),
                "target": data.get("target"),
                "qdrant_available": data.get("qdrant_available"),
            },
            "generation_time_ms": elapsed_ms,
            "total_tokens_used": 0,  # not tracked by this generator yet
            "created_at": time.time(),
        })
    except Exception as exc:
        logger.warning("Failed to persist report for scan_id=%s: %s", scan_id, exc)


@app.post("/iac/review")
async def iac_review(request: IaCReviewRequest):
    """Review an IaC bundle for security, best-practice and hardening issues."""
    if "iac_advisor" not in _agents:
        raise HTTPException(status_code=503, detail="IaC Advisor agent not available")

    agent = _agents["iac_advisor"]
    result = await agent.review_bundle(
        bundle=request.bundle,
        files=request.files,
        provider=request.provider,
        scan_id=request.scan_id,
        target=request.target,
    )

    if result is None:
        raise HTTPException(status_code=500, detail="Agent returned no result")

    return result.to_dict()


@app.get("/status")
async def agent_status():
    """Return status and metrics for all agents."""
    return {
        "agents": {
            name: agent.get_metrics() for name, agent in _agents.items()
        },
        "total_agents": len(_agents),
        "inflight_tasks": len(_inflight_tasks),
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    lines = []
    lines.append("# HELP sf_agent_processed_total Total events processed by agent")
    lines.append("# TYPE sf_agent_processed_total counter")
    for name, agent in _agents.items():
        m = agent.get_metrics()
        lines.append(f'sf_agent_processed_total{{agent="{name}"}} {m["processed_total"]}')

    lines.append("# HELP sf_agent_errors_total Total errors by agent")
    lines.append("# TYPE sf_agent_errors_total counter")
    for name, agent in _agents.items():
        m = agent.get_metrics()
        lines.append(f'sf_agent_errors_total{{agent="{name}"}} {m["errors_total"]}')

    lines.append("# HELP sf_agent_llm_retries_total Total LLM retries by agent")
    lines.append("# TYPE sf_agent_llm_retries_total counter")
    for name, agent in _agents.items():
        m = agent.get_metrics()
        lines.append(f'sf_agent_llm_retries_total{{agent="{name}"}} {m["llm_retries_total"]}')

    lines.append("# HELP sf_agent_avg_processing_time_ms Average processing time in ms")
    lines.append("# TYPE sf_agent_avg_processing_time_ms gauge")
    for name, agent in _agents.items():
        m = agent.get_metrics()
        lines.append(
            f'sf_agent_avg_processing_time_ms{{agent="{name}"}} {m["avg_processing_time_ms"]}'
        )

    lines.append("# HELP sf_agent_active_tasks Active tasks by agent")
    lines.append("# TYPE sf_agent_active_tasks gauge")
    for name, agent in _agents.items():
        m = agent.get_metrics()
        lines.append(f'sf_agent_active_tasks{{agent="{name}"}} {m["active_tasks"]}')

    lines.append("# HELP sf_agents_active Number of active agents")
    lines.append("# TYPE sf_agents_active gauge")
    lines.append(f"sf_agents_active {len(_agents)}")

    lines.append("# HELP sf_agents_inflight_tasks Number of service-level in-flight agent tasks")
    lines.append("# TYPE sf_agents_inflight_tasks gauge")
    lines.append(f"sf_agents_inflight_tasks {len(_inflight_tasks)}")

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agents", "agents": len(_agents)}


# --- CLI Entry Point ---

def main():
    import uvicorn

    host = os.environ.get("SF_AGENTS_HOST", "0.0.0.0")
    port = int(os.environ.get("SF_AGENTS_PORT", "8100"))
    workers = int(os.environ.get("SF_AGENTS_WORKERS", "1"))

    logging.basicConfig(
        level=os.environ.get("SF_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting Agents service on %s:%d", host, port)
    uvicorn.run(
        "spiderfoot.agents.service:app",
        host=host,
        port=port,
        workers=workers,
        log_level=os.environ.get("SF_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
