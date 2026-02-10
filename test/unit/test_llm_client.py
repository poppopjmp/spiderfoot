"""Tests for the unified OpenAI-compatible LLM client."""
from __future__ import annotations

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from spiderfoot.llm_client import (
    LLMAuthError,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    LLMUsage,
    StreamChunk,
    _MockGenerator,
)


# ===========================================================================
# LLMConfig
# ===========================================================================

class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.model == "gpt-4o-mini"
        assert cfg.temperature == 0.1
        assert cfg.max_tokens == 4096
        assert cfg.provider == LLMProvider.OPENAI

    def test_from_env(self):
        env = {
            "SF_LLM_API_BASE": "http://localhost:11434/v1",
            "SF_LLM_API_KEY": "sk-test",
            "SF_LLM_MODEL": "llama3",
            "SF_LLM_PROVIDER": "ollama",
            "SF_LLM_TEMPERATURE": "0.7",
            "SF_LLM_MAX_TOKENS": "2048",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = LLMConfig.from_env()
            assert cfg.api_base == "http://localhost:11434/v1"
            assert cfg.model == "llama3"
            assert cfg.provider == LLMProvider.OLLAMA
            assert cfg.temperature == 0.7
            assert cfg.max_tokens == 2048

    def test_from_env_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = LLMConfig.from_env()
            assert cfg.provider == LLMProvider.OPENAI
            assert cfg.model == "gpt-4o-mini"

    def test_endpoint_openai(self):
        cfg = LLMConfig(provider=LLMProvider.OPENAI)
        assert cfg.endpoint == "https://api.openai.com/v1/chat/completions"

    def test_endpoint_openai_custom_base(self):
        cfg = LLMConfig(provider=LLMProvider.OPENAI, api_base="http://myserver/v1")
        assert cfg.endpoint == "http://myserver/v1/chat/completions"

    def test_endpoint_ollama(self):
        cfg = LLMConfig(provider=LLMProvider.OLLAMA)
        assert cfg.endpoint == "http://localhost:11434/v1/chat/completions"

    def test_endpoint_ollama_with_v1(self):
        cfg = LLMConfig(provider=LLMProvider.OLLAMA, api_base="http://ollama:11434/v1")
        assert cfg.endpoint == "http://ollama:11434/v1/chat/completions"

    def test_endpoint_azure(self):
        cfg = LLMConfig(
            provider=LLMProvider.AZURE,
            api_base="https://myresource.openai.azure.com",
            azure_deployment="gpt-4",
        )
        assert "deployments/gpt-4" in cfg.endpoint
        assert "api-version=" in cfg.endpoint

    def test_endpoint_vllm(self):
        cfg = LLMConfig(provider=LLMProvider.VLLM)
        assert cfg.endpoint == "http://localhost:8000/v1/chat/completions"

    def test_endpoint_mock(self):
        cfg = LLMConfig(provider=LLMProvider.MOCK)
        assert cfg.endpoint == "mock://llm/chat/completions"

    def test_headers_openai(self):
        cfg = LLMConfig(api_key="sk-test")
        headers = cfg.headers
        assert headers["Authorization"] == "Bearer sk-test"
        assert headers["Content-Type"] == "application/json"

    def test_headers_azure(self):
        cfg = LLMConfig(provider=LLMProvider.AZURE, api_key="az-key")
        headers = cfg.headers
        assert headers["api-key"] == "az-key"
        assert "Authorization" not in headers

    def test_headers_no_key(self):
        cfg = LLMConfig(api_key="")
        headers = cfg.headers
        assert "Authorization" not in headers


# ===========================================================================
# LLMUsage / LLMResponse / LLMMessage
# ===========================================================================

class TestLLMDataTypes:
    def test_usage_defaults(self):
        u = LLMUsage()
        assert u.total_tokens == 0

    def test_response_defaults(self):
        r = LLMResponse()
        assert r.success is True
        assert r.content == ""
        assert r.total_tokens == 0

    def test_response_total_tokens(self):
        r = LLMResponse(usage=LLMUsage(total_tokens=500))
        assert r.total_tokens == 500

    def test_message(self):
        m = LLMMessage(role="user", content="Hello")
        assert m.role == "user"

    def test_stream_chunk(self):
        c = StreamChunk(delta="Hello ", finish_reason="", index=0)
        assert c.delta == "Hello "


# ===========================================================================
# Errors
# ===========================================================================

class TestErrors:
    def test_llm_error(self):
        e = LLMError("test", status_code=500, response="body")
        assert "test" in str(e)
        assert e.status_code == 500

    def test_rate_limit_error(self):
        e = LLMRateLimitError("rate limited")
        assert isinstance(e, LLMError)

    def test_auth_error(self):
        e = LLMAuthError("unauthorized")
        assert isinstance(e, LLMError)

    def test_timeout_error(self):
        e = LLMTimeoutError("timed out")
        assert isinstance(e, LLMError)


# ===========================================================================
# MockGenerator
# ===========================================================================

class TestMockGenerator:
    def test_generates_response(self):
        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Analyze this data"},
        ]
        resp = _MockGenerator.generate(messages, "test-model")
        assert resp.success is True
        assert resp.content != ""
        assert "mock" in resp.model
        assert resp.usage.total_tokens > 0
        assert "mock response" in resp.content.lower()

    def test_includes_input_length(self):
        msg = "x" * 100
        resp = _MockGenerator.generate(
            [{"role": "user", "content": msg}], "m"
        )
        assert "100 characters" in resp.content


# ===========================================================================
# LLMClient — Mock mode
# ===========================================================================

class TestLLMClientMock:
    def test_simple_chat(self):
        client = LLMClient(LLMConfig(provider=LLMProvider.MOCK))
        resp = client.chat("Analyze these findings")
        assert resp.success is True
        assert resp.content != ""
        assert resp.total_tokens > 0

    def test_chat_with_system(self):
        client = LLMClient(LLMConfig(provider=LLMProvider.MOCK))
        resp = client.chat("Analyze", system_message="You are an analyst")
        assert resp.success is True

    def test_chat_messages(self):
        client = LLMClient(LLMConfig(provider=LLMProvider.MOCK))
        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"},
        ]
        resp = client.chat_messages(messages)
        assert resp.success is True

    def test_streaming_mock(self):
        client = LLMClient(LLMConfig(provider=LLMProvider.MOCK))
        messages = [{"role": "user", "content": "Hello"}]
        chunks = list(client.chat_stream(messages))
        assert len(chunks) > 0
        # Last chunk should have finish_reason
        assert chunks[-1].finish_reason == "stop"
        # Concatenated should form the full response
        full = "".join(c.delta for c in chunks)
        assert len(full) > 0

    def test_from_env_mock(self):
        with patch.dict(os.environ, {"SF_LLM_PROVIDER": "mock"}, clear=True):
            client = LLMClient.from_env()
            resp = client.chat("test")
            assert resp.success is True


# ===========================================================================
# LLMClient — Stats
# ===========================================================================

class TestLLMClientStats:
    def test_initial_stats(self):
        client = LLMClient(LLMConfig(provider=LLMProvider.MOCK))
        stats = client.stats
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0

    def test_stats_after_requests(self):
        client = LLMClient(LLMConfig(provider=LLMProvider.MOCK))
        client.chat("test1")
        client.chat("test2")
        stats = client.stats
        # Mock requests don't increment real stats but we called them
        # (Mock bypasses _make_request, so only total from mock counts)
        assert stats["total_requests"] == 0  # Mock doesn't go through _make_request
        assert stats["total_tokens"] == 0

    def test_reset_stats(self):
        client = LLMClient(LLMConfig(provider=LLMProvider.MOCK))
        client._total_requests = 10
        client._total_tokens = 5000
        client.reset_stats()
        assert client.stats["total_requests"] == 0
        assert client.stats["total_tokens"] == 0


# ===========================================================================
# LLMClient — Request building
# ===========================================================================

class TestRequestBuilding:
    def test_build_request_body(self):
        client = LLMClient(LLMConfig(
            model="gpt-4",
            temperature=0.5,
            max_tokens=1000,
        ))
        messages = [{"role": "user", "content": "test"}]
        body = client._build_request_body(messages)
        assert body["model"] == "gpt-4"
        assert body["temperature"] == 0.5
        assert body["max_tokens"] == 1000
        assert body["stream"] is False
        assert body["messages"] == messages

    def test_build_request_with_overrides(self):
        client = LLMClient(LLMConfig(model="default"))
        messages = [{"role": "user", "content": "test"}]
        body = client._build_request_body(
            messages, model="override", temperature=0.9
        )
        assert body["model"] == "override"
        assert body["temperature"] == 0.9

    def test_build_request_streaming(self):
        client = LLMClient(LLMConfig())
        messages = [{"role": "user", "content": "test"}]
        body = client._build_request_body(messages, stream=True)
        assert body["stream"] is True

    def test_build_request_with_stop(self):
        client = LLMClient(LLMConfig(stop=["###", "END"]))
        messages = [{"role": "user", "content": "test"}]
        body = client._build_request_body(messages)
        assert body["stop"] == ["###", "END"]

    def test_build_request_with_penalties(self):
        client = LLMClient(LLMConfig(
            frequency_penalty=0.5,
            presence_penalty=0.3,
        ))
        messages = [{"role": "user", "content": "test"}]
        body = client._build_request_body(messages)
        assert body["frequency_penalty"] == 0.5
        assert body["presence_penalty"] == 0.3

    def test_build_request_no_penalties_by_default(self):
        client = LLMClient(LLMConfig())
        messages = [{"role": "user", "content": "test"}]
        body = client._build_request_body(messages)
        assert "frequency_penalty" not in body
        assert "presence_penalty" not in body


# ===========================================================================
# LLMClient — Error classification
# ===========================================================================

class TestErrorClassification:
    def test_classify_401(self):
        client = LLMClient()
        with pytest.raises(LLMAuthError):
            client._classify_and_raise(401, "unauthorized")

    def test_classify_403(self):
        client = LLMClient()
        with pytest.raises(LLMAuthError):
            client._classify_and_raise(403, "forbidden")

    def test_classify_429(self):
        client = LLMClient()
        with pytest.raises(LLMRateLimitError):
            client._classify_and_raise(429, "rate limited")

    def test_classify_500(self):
        client = LLMClient()
        with pytest.raises(LLMError) as exc_info:
            client._classify_and_raise(500, "server error")
        assert exc_info.value.status_code == 500

    def test_classify_400(self):
        client = LLMClient()
        with pytest.raises(LLMError) as exc_info:
            client._classify_and_raise(400, "bad request")
        assert exc_info.value.status_code == 400


# ===========================================================================
# Enums
# ===========================================================================

class TestEnums:
    def test_provider_values(self):
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.OLLAMA.value == "ollama"
        assert LLMProvider.AZURE.value == "azure"
        assert LLMProvider.VLLM.value == "vllm"
        assert LLMProvider.LOCAL.value == "local"
        assert LLMProvider.MOCK.value == "mock"
