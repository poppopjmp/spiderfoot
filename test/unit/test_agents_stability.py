"""Tests for AI agent stability helpers."""

from __future__ import annotations

import json

import pytest

from spiderfoot.agents.base import AgentConfig, AgentResult, BaseAgent
from spiderfoot.agents.service import ProcessRequest, _persist_agent_result


class DummyAgent(BaseAgent):
    """Small concrete agent used by unit tests."""

    @property
    def event_types(self):
        return ["TEST_*"]

    async def process_event(self, event):
        return AgentResult(
            agent_name=self.config.name,
            event_id=event.get("id", "evt"),
            scan_id=event.get("scan_id", "scan"),
            result_type="dummy",
            data={"ok": True},
            confidence=0.9,
        )


class DummyRedis:
    def __init__(self):
        self.values = {}
        self.published = []

    async def set(self, key, value, ex=None):
        self.values[key] = {"value": value, "ex": ex}

    async def publish(self, channel, payload):
        self.published.append((channel, payload))


def test_parse_json_response_handles_fenced_and_prefixed_json():
    content = "Model output:\n```json\n{\"confidence\": 0.8, \"verdict\": \"confirmed\"}\n```"

    parsed = BaseAgent.parse_json_response(content)

    assert parsed == {"confidence": 0.8, "verdict": "confirmed"}


def test_redact_sensitive_values_masks_common_secret_patterns():
    text = "password = hunter2 token: abc123 Authorization: Bearer secret-token AKIAABCDEFGHIJKLMNOP"

    redacted = BaseAgent.redact_sensitive_values(text)

    assert "hunter2" not in redacted
    assert "abc123" not in redacted
    assert "secret-token" not in redacted
    assert "AKIAABCDEFGHIJKLMNOP" not in redacted
    assert "[REDACTED" in redacted


@pytest.mark.asyncio
async def test_handle_event_updates_metrics_and_serializes_result():
    agent = DummyAgent(AgentConfig(name="dummy", max_concurrent=1))

    result = await agent.handle_event({"id": "evt-1", "scan_id": "scan-1"})

    assert result is not None
    assert result.to_dict()["success"] is True
    metrics = agent.get_metrics()
    assert metrics["processed_total"] == 1
    assert metrics["errors_total"] == 0
    assert metrics["active_tasks"] == 0
    await agent.close()


@pytest.mark.asyncio
async def test_persist_agent_result_sets_ttl_and_publishes(monkeypatch):
    monkeypatch.setenv("SF_AGENT_RESULT_TTL_SECONDS", "120")
    redis = DummyRedis()
    result = AgentResult(
        agent_name="dummy",
        event_id="evt-1",
        scan_id="scan-1",
        result_type="dummy",
        data={"ok": True},
        confidence=0.8,
    )

    await _persist_agent_result(result, redis)

    assert "sf:agent_result:scan-1:dummy:evt-1" in redis.values
    stored = redis.values["sf:agent_result:scan-1:dummy:evt-1"]
    assert stored["ex"] == 120
    assert json.loads(stored["value"])["success"] is True
    assert redis.published[0][0] == "sf:agent_results"


def test_process_request_uses_isolated_default_event_lists():
    first = ProcessRequest()
    second = ProcessRequest()

    first.events.append({"event_type": "TEST_EVENT"})

    assert second.events == []
