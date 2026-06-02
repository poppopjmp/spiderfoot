"""Tests for the concrete LLM agents in spiderfoot.agents.

Each agent's process_event builds a prompt and calls the (network-bound) LLM via
BaseAgent.call_llm, then parses the JSON response into an AgentResult. These
tests replace call_llm with an async stub so the prompt-building, result
construction, and JSON-parse-failure fallback paths run without any LLM.

Also asserts the credential analyzer redacts secret values before they ever
reach the prompt (a security property).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from spiderfoot.agents.base import AgentConfig, AgentResult
from spiderfoot.agents.credential_analyzer import CredentialAnalyzerAgent
from spiderfoot.agents.finding_validator import FindingValidatorAgent
from spiderfoot.agents.text_summarizer import TextSummarizerAgent
from spiderfoot.agents.iac_advisor import IaCAdvisorAgent
from spiderfoot.agents.document_analyzer import DocumentAnalyzerAgent


_GOOD_JSON = json.dumps({
    "confidence": 0.8, "relevance": 0.7, "severity": "high",
    "verdict": "confirmed", "summary": "ok", "risk_score": 0.8,
    "issues": [], "recommendations": [],
})


def _agent(cls, name):
    return cls(AgentConfig(name=name))


class TestEventTypes:
    @pytest.mark.parametrize("cls,name", [
        (CredentialAnalyzerAgent, "credential_analyzer"),
        (FindingValidatorAgent, "finding_validator"),
        (TextSummarizerAgent, "text_summarizer"),
        (IaCAdvisorAgent, "iac_advisor"),
        (DocumentAnalyzerAgent, "document_analyzer"),
    ])
    def test_event_types_non_empty_list(self, cls, name):
        agent = _agent(cls, name)
        types = agent.event_types
        assert isinstance(types, list) and types


class TestProcessEventHappyPath:
    async def test_credential_analyzer(self):
        agent = _agent(CredentialAnalyzerAgent, "credential_analyzer")
        agent.call_llm = AsyncMock(return_value=_GOOD_JSON)
        result = await agent.process_event({
            "event_type": "LEAKED_CREDENTIALS", "data": "ctx",
            "id": "e1", "scan_id": "s1", "target": "example.com",
        })
        assert isinstance(result, AgentResult)
        assert result.result_type == "credential_analysis"
        assert result.confidence == pytest.approx(0.8)

    async def test_finding_validator(self):
        agent = _agent(FindingValidatorAgent, "finding_validator")
        agent.call_llm = AsyncMock(return_value=_GOOD_JSON)
        result = await agent.process_event({
            "event_type": "VULNERABILITY_GENERAL", "data": "finding",
            "id": "e1", "scan_id": "s1",
        })
        assert result.result_type == "finding_validation"
        assert result.confidence == pytest.approx(0.8)

    async def test_text_summarizer(self):
        agent = _agent(TextSummarizerAgent, "text_summarizer")
        agent.call_llm = AsyncMock(return_value=_GOOD_JSON)
        result = await agent.process_event({
            "event_type": "RAW_DATA", "data": "lots of text",
            "id": "e1", "scan_id": "s1",
        })
        assert result.result_type == "text_summary"

    async def test_iac_advisor(self):
        agent = _agent(IaCAdvisorAgent, "iac_advisor")
        agent.call_llm = AsyncMock(return_value=_GOOD_JSON)
        result = await agent.process_event({
            "event_type": "IAC_GENERATED",
            "bundle": {"name": "tf"}, "files": {"main.tf": "resource {}"},
            "provider": "aws", "id": "e1", "scan_id": "s1",
        })
        assert result.result_type == "iac_review"

    async def test_document_analyzer(self):
        agent = _agent(DocumentAnalyzerAgent, "document_analyzer")
        agent.call_llm = AsyncMock(return_value=_GOOD_JSON)
        result = await agent.process_event({
            "event_type": "RAW_FILE_META_DATA", "data": "document body",
            "filename": "doc.txt", "id": "e1", "scan_id": "s1",
        })
        assert result.result_type == "document_analysis"


class TestProcessEventParseFailureFallback:
    @pytest.mark.parametrize("cls,name,rtype", [
        (CredentialAnalyzerAgent, "credential_analyzer", "credential_analysis"),
        (FindingValidatorAgent, "finding_validator", "finding_validation"),
        (TextSummarizerAgent, "text_summarizer", "text_summary"),
    ])
    async def test_invalid_json_yields_low_confidence_result(self, cls, name, rtype):
        agent = _agent(cls, name)
        agent.call_llm = AsyncMock(return_value="I'm sorry, I cannot help.")
        result = await agent.process_event({
            "event_type": "X", "data": "d", "id": "e1", "scan_id": "s1",
        })
        # Falls back to a low-confidence result rather than raising.
        assert result.result_type == rtype
        assert result.confidence == pytest.approx(0.3)


class TestCredentialRedaction:
    async def test_secret_values_redacted_before_prompt(self):
        agent = _agent(CredentialAnalyzerAgent, "credential_analyzer")
        captured = {}

        async def fake_call_llm(messages, **kwargs):
            captured["messages"] = messages
            return _GOOD_JSON

        agent.call_llm = fake_call_llm
        await agent.process_event({
            "event_type": "LEAKED_CREDENTIALS",
            "data": "password = hunter2 token: AKIAABCDEFGHIJKLMNOP",
            "id": "e1", "scan_id": "s1",
        })
        user_prompt = captured["messages"][-1]["content"]
        # The raw secret values must not appear in the prompt sent to the LLM.
        assert "hunter2" not in user_prompt
        assert "AKIAABCDEFGHIJKLMNOP" not in user_prompt
        assert "[REDACTED" in user_prompt
