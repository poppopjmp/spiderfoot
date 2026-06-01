"""Tests for spiderfoot.tasks.agents — agent task prompt builders + batch task.

The full execute_agent_task is LLM/Redis-bound; here we cover the pure prompt
builders and the batch submission task (including its target-count guard), with
execute_agent_task.apply_async mocked.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import spiderfoot.tasks.agents as agents


class TestPromptBuilders:
    def test_system_prompt_has_structure(self):
        p = agents._build_system_prompt()
        assert "OSINT analyst" in p
        for section in ("summary", "findings", "recommendations", "risk_score"):
            assert section in p

    def test_user_prompt_includes_target_and_instruction(self):
        p = agents._build_user_prompt("enumerate subdomains", "example.com")
        assert "example.com" in p
        assert "enumerate subdomains" in p

    def test_user_prompt_appends_context(self):
        p = agents._build_user_prompt(
            "analyze", "example.com", context={"depth": 2})
        assert "Additional Context" in p
        assert json.dumps({"depth": 2}, indent=2) in p

    def test_user_prompt_without_context(self):
        p = agents._build_user_prompt("analyze", "example.com")
        assert "Additional Context" not in p


class TestBatchAgentAnalysis:
    def test_submits_one_task_per_target(self, monkeypatch):
        ids = iter(["t1", "t2", "t3"])

        def fake_apply_async(*args, **kwargs):
            m = MagicMock()
            m.id = next(ids)
            return m

        monkeypatch.setattr(agents.execute_agent_task, "apply_async",
                            fake_apply_async)
        result = agents.batch_agent_analysis.run(
            ["a.com", "b.com", "c.com"], "analyze")
        assert result["submitted"] == 3
        targets = {t["target"] for t in result["tasks"]}
        assert targets == {"a.com", "b.com", "c.com"}

    def test_rejects_too_many_targets(self, monkeypatch):
        monkeypatch.setenv("SF_AGENT_BATCH_MAX_TARGETS", "2")
        with pytest.raises(ValueError, match="Too many targets"):
            agents.batch_agent_analysis.run(["a", "b", "c"], "analyze")
