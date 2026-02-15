"""
Agents Service Runner
======================
FastAPI service that hosts all SpiderFoot AI agents.

Exposes:
  - POST /agents/process       — Submit events for agent processing
  - POST /agents/analyze       — Analyze uploaded documents
  - POST /agents/report        — Generate scan report
  - GET  /agents/status        — Agent status and metrics
  - GET  /metrics              — Prometheus metrics endpoint
  - GET  /health               — Health check

Agents consume events from the event bus (Redis pub/sub) and can also
be invoked directly via the REST API.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logger = logging.getLogger("sf.agents.service")

# Agent registry
_agents = {}
_event_listener_task = None


def _init_agents():
    """Initialize all agent instances."""
    from spiderfoot.agents.finding_validator import FindingValidatorAgent
    from spiderfoot.agents.credential_analyzer import CredentialAnalyzerAgent
    from spiderfoot.agents.text_summarizer import TextSummarizerAgent
    from spiderfoot.agents.report_generator import ReportGeneratorAgent
    from spiderfoot.agents.document_analyzer import DocumentAnalyzerAgent
    from spiderfoot.agents.threat_intel import ThreatIntelAnalyzerAgent

    agent_classes = [
        FindingValidatorAgent,
        CredentialAnalyzerAgent,
        TextSummarizerAgent,
        ReportGeneratorAgent,
        DocumentAnalyzerAgent,
        ThreatIntelAnalyzerAgent,
    ]

    for cls in agent_classes:
        try:
            agent = cls.create()
            if agent.config.enabled:
                _agents[agent.config.name] = agent
                logger.info("Agent '%s' initialized (model=%s)", agent.config.name, agent.config.llm_model)
            else:
                logger.info("Agent '%s' disabled via config", agent.config.name)
        except Exception as exc:
            logger.error("Failed to initialize agent %s: %s", cls.__name__, exc)


async def _start_event_listener():
    """Listen for events on Redis pub/sub and dispatch to agents."""
    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url)
        pubsub = client.pubsub()
        await pubsub.subscribe("sf:events", "sf:agent_requests")

        logger.info("Event listener started on Redis pub/sub")

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                import json
                event = json.loads(message["data"])
                event_type = event.get("event_type", "")

                # Dispatch to matching agents
                for agent in _agents.values():
                    if _matches_event_type(event_type, agent.event_types):
                        asyncio.create_task(agent.handle_event(event))

            except Exception as exc:
                logger.warning("Error processing event: %s", exc)

    except ImportError:
        logger.warning("redis package not available — event listener disabled")
    except Exception as exc:
        logger.error("Event listener error: %s", exc)


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
    """Application lifespan — init agents and start event listener."""
    global _event_listener_task

    _init_agents()
    logger.info("Initialized %d agents", len(_agents))

    # Start Redis event listener in background
    _event_listener_task = asyncio.create_task(_start_event_listener())

    yield

    # Shutdown
    if _event_listener_task:
        _event_listener_task.cancel()
    logger.info("Agents service shutdown")


# --- FastAPI Application ---

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

app = FastAPI(
    title="SpiderFoot Agents Service",
    description="AI-powered analysis agents for OSINT data enrichment",
    version="0.1.0",
    lifespan=lifespan,
)


class ProcessRequest(BaseModel):
    events: List[Dict[str, Any]]
    agent_name: Optional[str] = None  # specific agent, or all matching


class DocumentRequest(BaseModel):
    filename: str
    content: str
    content_type: str = "text/plain"
    target: str = ""
    scan_id: str = ""


class ReportRequest(BaseModel):
    scan_id: str
    target: str
    scan_name: str = ""
    findings: List[Dict[str, Any]] = []
    correlations: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {}
    agent_results: List[Dict[str, Any]] = []
    geo_data: Dict[str, Any] = {}


@app.post("/agents/process")
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
                    results.append({
                        "agent": result.agent_name,
                        "event_id": result.event_id,
                        "result_type": result.result_type,
                        "data": result.data,
                        "confidence": result.confidence,
                        "processing_time_ms": result.processing_time_ms,
                        "error": result.error,
                    })

    return {"results": results, "total": len(results)}


@app.post("/agents/analyze")
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

    return {
        "agent": result.agent_name,
        "result_type": result.result_type,
        "data": result.data,
        "confidence": result.confidence,
        "processing_time_ms": result.processing_time_ms,
        "error": result.error,
    }


@app.post("/agents/report")
async def generate_report(request: ReportRequest):
    """Generate a scan report."""
    if "report_generator" not in _agents:
        raise HTTPException(status_code=503, detail="Report generator agent not available")

    agent = _agents["report_generator"]
    event = {
        "event_type": "REPORT_REQUEST",
        "scan_id": request.scan_id,
        "target": request.target,
        "scan_name": request.scan_name,
        "findings": request.findings,
        "correlations": request.correlations,
        "stats": request.stats,
        "agent_results": request.agent_results,
        "geo_data": request.geo_data,
        "id": f"report-{int(time.time())}",
    }

    result = await agent.handle_event(event)
    if result is None:
        raise HTTPException(status_code=500, detail="Agent returned no result")

    return {
        "agent": result.agent_name,
        "result_type": result.result_type,
        "data": result.data,
        "confidence": result.confidence,
        "processing_time_ms": result.processing_time_ms,
        "error": result.error,
    }


@app.get("/agents/status")
async def agent_status():
    """Return status and metrics for all agents."""
    return {
        "agents": {
            name: agent.get_metrics() for name, agent in _agents.items()
        },
        "total_agents": len(_agents),
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

    lines.append("# HELP sf_agent_avg_processing_time_ms Average processing time in ms")
    lines.append("# TYPE sf_agent_avg_processing_time_ms gauge")
    for name, agent in _agents.items():
        m = agent.get_metrics()
        lines.append(
            f'sf_agent_avg_processing_time_ms{{agent="{name}"}} {m["avg_processing_time_ms"]}'
        )

    lines.append("# HELP sf_agents_active Number of active agents")
    lines.append("# TYPE sf_agents_active gauge")
    lines.append(f"sf_agents_active {len(_agents)}")

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
