# -*- coding: utf-8 -*-
# =============================================================================
# SpiderFoot — Celery Agent Tasks
# =============================================================================
# AI-powered agent execution tasks (LLM-driven autonomous scanning).
# =============================================================================

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from spiderfoot.celery_app import celery_app

logger = logging.getLogger("sf.tasks.agents")


@celery_app.task(
    name="spiderfoot.tasks.agents.execute_agent_task",
    queue="agents",
    bind=True,
    max_retries=1,
    soft_time_limit=3600,
    time_limit=7200,
)
def execute_agent_task(
    self,
    agent_id: str,
    instruction: str,
    target: str,
    context: dict[str, Any] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Execute an AI agent task using the LiteLLM proxy.

    The agent receives an instruction and target, then autonomously
    decides which SpiderFoot modules to invoke to accomplish the goal.
    Results are stored in Redis and optionally fed back for iterative
    refinement.
    """
    import redis as redis_lib

    redis_url = os.environ.get("SF_REDIS_URL", "redis://redis:6379/0")
    r = redis_lib.from_url(redis_url)

    status_key = f"sf:agent:{agent_id}:status"
    results_key = f"sf:agent:{agent_id}:results"

    try:
        # Update agent status
        r.hset(status_key, mapping={
            "status": "running",
            "started_at": str(time.time()),
            "instruction": instruction,
            "target": target,
        })
        r.expire(status_key, 86400 * 7)

        self.update_state(state="RUNNING", meta={
            "agent_id": agent_id,
            "instruction": instruction,
            "target": target,
        })

        # Build the agent prompt
        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(instruction, target, context)

        # Call LiteLLM proxy via the shared retrying OpenAI-compatible client.
        litellm_url = os.environ.get(
            "SF_LITELLM_URL",
            os.environ.get("SF_LLM_API_BASE", "http://litellm:4000"),
        ).rstrip("/")
        if not litellm_url.endswith("/v1"):
            litellm_url = f"{litellm_url}/v1"
        model_name = model or os.environ.get("SF_AGENT_MODEL", "openrouter/google/gemini-2.0-flash-001")

        from spiderfoot.ai.llm_client import LLMClient, LLMConfig, LLMProvider

        client = LLMClient(LLMConfig(
            api_base=litellm_url,
            api_key=os.environ.get("SF_LLM_API_KEY", ""),
            model=model_name,
            provider=LLMProvider.OPENAI,
            temperature=0.3,
            max_tokens=4096,
            timeout=120,
            max_retries=int(os.environ.get("SF_AGENT_LLM_MAX_RETRIES", "3")),
        ))
        llm_response = client.chat_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        assistant_message = llm_response.content

        # Parse agent response for tool calls / actions
        result = {
            "agent_id": agent_id,
            "target": target,
            "instruction": instruction,
            "response": assistant_message,
            "model": model_name,
            "completed_at": time.time(),
        }

        # Store results
        r.set(results_key, json.dumps(result), ex=86400 * 7)
        r.hset(status_key, mapping={
            "status": "completed",
            "completed_at": str(time.time()),
        })
        r.expire(status_key, 86400 * 7)

        logger.info("agents.task_completed", extra={"agent_id": agent_id, "target": target})
        return result

    except Exception as e:
        r.hset(status_key, mapping={
            "status": "failed",
            "error": str(e)[:1000],
            "failed_at": str(time.time()),
        })
        r.expire(status_key, 86400 * 7)
        logger.error(f"agents.task_failed: {e}", extra={"agent_id": agent_id})
        raise


@celery_app.task(
    name="spiderfoot.tasks.agents.batch_agent_analysis",
    queue="agents",
    ignore_result=False,
)
def batch_agent_analysis(
    targets: list[str],
    instruction: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Submit multiple agent tasks for batch analysis."""
    import uuid

    max_targets = int(os.environ.get("SF_AGENT_BATCH_MAX_TARGETS", "100"))
    if len(targets) > max_targets:
        raise ValueError(f"Too many targets for batch agent analysis: {len(targets)} > {max_targets}")

    task_ids = []
    for target in targets:
        agent_id = str(uuid.uuid4())
        result = execute_agent_task.apply_async(
            kwargs={
                "agent_id": agent_id,
                "instruction": instruction,
                "target": target,
                "model": model,
            },
            queue="agents",
        )
        task_ids.append({"target": target, "agent_id": agent_id, "task_id": result.id})

    return {"submitted": len(task_ids), "tasks": task_ids}


def _build_system_prompt() -> str:
    """Build the system prompt for the SpiderFoot AI agent."""
    return """You are an OSINT analyst agent for SpiderFoot, an automated intelligence
collection tool. Your job is to analyze targets and provide structured intelligence
reports. You have expertise in:

- Domain/subdomain reconnaissance
- IP address and network analysis
- Email and identity correlation
- Dark web and data breach monitoring
- Social media intelligence (SOCMINT)
- Technology stack fingerprinting
- Certificate transparency analysis

Provide your analysis in structured JSON format with the following sections:
- summary: Brief executive summary
- findings: Array of key findings with severity (critical/high/medium/low/info)
- recommendations: Actionable next steps
- iocs: Indicators of compromise if applicable
- risk_score: Overall risk score from 0-100
"""


def _build_user_prompt(
    instruction: str,
    target: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Build the user prompt with target and context."""
    prompt = f"""Target: {target}
Instruction: {instruction}
"""
    if context:
        prompt += f"\nAdditional Context:\n{json.dumps(context, indent=2)}"

    return prompt
