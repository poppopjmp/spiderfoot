"""
Unified OpenAI-compatible LLM Client for SpiderFoot.

A single client that works with any OpenAI-compatible API endpoint:
OpenAI, Ollama, vLLM, LocalAI, llama.cpp server, Azure OpenAI, etc.

Replaces the raw urllib.request calls scattered across rag_pipeline.py
with a proper async-ready client featuring retry, streaming, and metrics.

Usage::

    from spiderfoot.llm_client import LLMClient, LLMConfig

    client = LLMClient(LLMConfig(
        api_base="http://localhost:11434/v1",
        model="llama3",
    ))
    response = client.chat("Analyze these OSINT findings...")

    # With explicit messages
    response = client.chat_messages([
        {"role": "system", "content": "You are a security analyst"},
        {"role": "user", "content": "Analyze: ..."},
    ])
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

log = logging.getLogger("spiderfoot.llm_client")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class LLMProvider(Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    OLLAMA = "ollama"
    AZURE = "azure"
    VLLM = "vllm"
    LOCAL = "local"
    MOCK = "mock"


@dataclass
class LLMConfig:
    """Configuration for the LLM client."""
    # Connection
    api_base: str = ""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    provider: LLMProvider = LLMProvider.OPENAI

    # Generation parameters
    temperature: float = 0.1
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None

    # Client behavior
    timeout: float = 120.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0

    # Streaming
    stream: bool = False

    # Azure-specific
    azure_deployment: str = ""
    azure_api_version: str = "2024-02-01"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create config from environment variables."""
        provider_str = os.environ.get("SF_LLM_PROVIDER", "openai").lower()
        provider_map = {
            "openai": LLMProvider.OPENAI,
            "ollama": LLMProvider.OLLAMA,
            "azure": LLMProvider.AZURE,
            "vllm": LLMProvider.VLLM,
            "local": LLMProvider.LOCAL,
            "mock": LLMProvider.MOCK,
        }

        return cls(
            api_base=os.environ.get("SF_LLM_API_BASE", ""),
            api_key=os.environ.get("SF_LLM_API_KEY", ""),
            model=os.environ.get("SF_LLM_MODEL", "gpt-4o-mini"),
            provider=provider_map.get(provider_str, LLMProvider.OPENAI),
            temperature=float(os.environ.get("SF_LLM_TEMPERATURE", "0.1")),
            max_tokens=int(os.environ.get("SF_LLM_MAX_TOKENS", "4096")),
            timeout=float(os.environ.get("SF_LLM_TIMEOUT", "120.0")),
        )

    @property
    def endpoint(self) -> str:
        """Resolve the chat completions endpoint URL."""
        base = self.api_base.rstrip("/")

        if self.provider == LLMProvider.OPENAI:
            if not base:
                base = "https://api.openai.com/v1"
            return f"{base}/chat/completions"

        elif self.provider == LLMProvider.OLLAMA:
            if not base:
                base = "http://localhost:11434"
            # Ollama supports /v1/chat/completions
            if "/v1" not in base:
                return f"{base}/v1/chat/completions"
            return f"{base}/chat/completions"

        elif self.provider == LLMProvider.AZURE:
            # Azure format: {base}/openai/deployments/{deployment}/chat/completions
            deployment = self.azure_deployment or self.model
            return (
                f"{base}/openai/deployments/{deployment}"
                f"/chat/completions?api-version={self.azure_api_version}"
            )

        elif self.provider in (LLMProvider.VLLM, LLMProvider.LOCAL):
            if not base:
                base = "http://localhost:8000/v1"
            return f"{base}/chat/completions"

        elif self.provider == LLMProvider.MOCK:
            return "mock://llm/chat/completions"

        return f"{base}/chat/completions"

    @property
    def headers(self) -> Dict[str, str]:
        """Build request headers."""
        h = {"Content-Type": "application/json"}

        if self.provider == LLMProvider.AZURE:
            if self.api_key:
                h["api-key"] = self.api_key
        elif self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"

        return h


# ---------------------------------------------------------------------------
# Response types
# ---------------------------------------------------------------------------

@dataclass
class LLMMessage:
    """A chat message."""
    role: str = "assistant"
    content: str = ""


@dataclass
class LLMUsage:
    """Token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Response from an LLM API call."""
    content: str = ""
    model: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)
    finish_reason: str = ""
    latency_ms: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    success: bool = True

    @property
    def total_tokens(self) -> int:
        return self.usage.total_tokens


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""
    delta: str = ""
    finish_reason: str = ""
    index: int = 0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """Base error for LLM operations."""
    def __init__(self, message: str, status_code: int = 0, response: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""
    pass


class LLMAuthError(LLMError):
    """Authentication failed."""
    pass


class LLMTimeoutError(LLMError):
    """Request timed out."""
    pass


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------

class _MockGenerator:
    """Generates mock responses for testing."""

    @staticmethod
    def generate(messages: List[Dict[str, str]], model: str) -> LLMResponse:
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        content = (
            f"## Analysis Report\n\n"
            f"Based on the provided OSINT data, here are the key findings:\n\n"
            f"1. **Risk Assessment**: Multiple indicators suggest elevated risk.\n"
            f"2. **Threat Indicators**: Several malicious entities detected.\n"
            f"3. **Recommendations**: Immediate remediation recommended.\n\n"
            f"*This is a mock response generated for testing purposes.*\n"
            f"*Input length: {len(user_msg)} characters*"
        )

        return LLMResponse(
            content=content,
            model=f"mock-{model}",
            usage=LLMUsage(
                prompt_tokens=len(user_msg) // 4,
                completion_tokens=len(content) // 4,
                total_tokens=(len(user_msg) + len(content)) // 4,
            ),
            finish_reason="stop",
            success=True,
        )


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class LLMClient:
    """Unified client for OpenAI-compatible LLM APIs.

    Supports:
    - All OpenAI-compatible endpoints (/v1/chat/completions)
    - Retry with exponential backoff
    - Streaming responses
    - Mock mode for testing
    - Token usage tracking
    - Detailed error classification
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._total_requests = 0
        self._total_tokens = 0
        self._total_errors = 0
        self._total_latency_ms = 0.0

    @classmethod
    def from_env(cls) -> "LLMClient":
        """Create client from environment variables."""
        return cls(LLMConfig.from_env())

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def chat(
        self,
        user_message: str,
        system_message: str = "",
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a simple chat request.

        Args:
            user_message: The user's message.
            system_message: Optional system prompt.
            **kwargs: Override config parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with the model's reply.
        """
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        return self.chat_messages(messages, **kwargs)

    def chat_messages(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a multi-turn chat request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Override config parameters.

        Returns:
            LLMResponse with the model's reply.
        """
        if self.config.provider == LLMProvider.MOCK:
            return _MockGenerator.generate(messages, self.config.model)

        return self._call_with_retry(messages, **kwargs)

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> Generator[StreamChunk, None, None]:
        """Send a streaming chat request.

        Yields:
            StreamChunk objects as they arrive.
        """
        if self.config.provider == LLMProvider.MOCK:
            mock = _MockGenerator.generate(messages, self.config.model)
            # Simulate streaming by yielding words
            words = mock.content.split()
            for i, word in enumerate(words):
                yield StreamChunk(
                    delta=word + " ",
                    finish_reason="" if i < len(words) - 1 else "stop",
                    index=0,
                )
            return

        yield from self._stream_request(messages, **kwargs)

    # -------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, Any]:
        """Get client usage statistics."""
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "total_errors": self._total_errors,
            "avg_latency_ms": (
                self._total_latency_ms / self._total_requests
                if self._total_requests > 0
                else 0.0
            ),
        }

    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self._total_requests = 0
        self._total_tokens = 0
        self._total_errors = 0
        self._total_latency_ms = 0.0

    # -------------------------------------------------------------------
    # Private methods
    # -------------------------------------------------------------------

    def _build_request_body(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Build the API request body."""
        body: Dict[str, Any] = {
            "model": kwargs.get("model", self.config.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stream": stream,
        }

        if self.config.frequency_penalty != 0:
            body["frequency_penalty"] = self.config.frequency_penalty
        if self.config.presence_penalty != 0:
            body["presence_penalty"] = self.config.presence_penalty
        if self.config.stop:
            body["stop"] = self.config.stop

        return body

    def _call_with_retry(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """Make API call with retry logic."""
        last_error = None
        delay = self.config.retry_delay

        for attempt in range(1, self.config.max_retries + 1):
            try:
                return self._make_request(messages, **kwargs)
            except LLMRateLimitError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    log.warning(
                        "Rate limited (attempt %d/%d), retrying in %.1fs",
                        attempt, self.config.max_retries, delay,
                    )
                    time.sleep(delay)
                    delay *= self.config.retry_backoff
            except LLMAuthError:
                raise  # Don't retry auth errors
            except LLMTimeoutError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    log.warning(
                        "Timeout (attempt %d/%d), retrying in %.1fs",
                        attempt, self.config.max_retries, delay,
                    )
                    time.sleep(delay)
                    delay *= self.config.retry_backoff
            except LLMError as e:
                last_error = e
                if attempt < self.config.max_retries and e.status_code >= 500:
                    log.warning(
                        "Server error %d (attempt %d/%d), retrying in %.1fs",
                        e.status_code, attempt, self.config.max_retries, delay,
                    )
                    time.sleep(delay)
                    delay *= self.config.retry_backoff
                else:
                    raise

        self._total_errors += 1
        raise last_error or LLMError("All retries exhausted")

    def _make_request(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """Make a single API request."""
        t0 = time.monotonic()
        self._total_requests += 1

        body = self._build_request_body(messages, stream=False, **kwargs)
        data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            self.config.endpoint,
            data=data,
            headers=self.config.headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8")
            except Exception:
                pass
            self._classify_and_raise(e.code, body_text)
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason).lower():
                raise LLMTimeoutError(f"Request timed out: {e.reason}")
            raise LLMError(f"Connection error: {e.reason}")
        except TimeoutError:
            raise LLMTimeoutError("Request timed out")

        latency_ms = (time.monotonic() - t0) * 1000

        # Parse response
        content = ""
        finish_reason = ""
        choices = resp_data.get("choices", [])
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            finish_reason = choice.get("finish_reason", "")

        usage_data = resp_data.get("usage", {})
        usage = LLMUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        self._total_tokens += usage.total_tokens
        self._total_latency_ms += latency_ms

        response = LLMResponse(
            content=content,
            model=resp_data.get("model", self.config.model),
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            raw=resp_data,
            success=True,
        )

        log.info(
            "LLM response: model=%s, tokens=%d, latency=%.0fms",
            response.model, usage.total_tokens, latency_ms,
        )

        return response

    def _stream_request(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> Generator[StreamChunk, None, None]:
        """Make a streaming API request."""
        body = self._build_request_body(messages, stream=True, **kwargs)
        data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            self.config.endpoint,
            data=data,
            headers=self.config.headers,
            method="POST",
        )

        try:
            resp = urllib.request.urlopen(req, timeout=self.config.timeout)
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8")
            except Exception:
                pass
            self._classify_and_raise(e.code, body_text)
        except urllib.error.URLError as e:
            raise LLMError(f"Connection error: {e.reason}")

        try:
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        chunk_data = json.loads(line[6:])
                        choices = chunk_data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            yield StreamChunk(
                                delta=delta.get("content", ""),
                                finish_reason=choices[0].get("finish_reason", ""),
                                index=choices[0].get("index", 0),
                            )
                    except json.JSONDecodeError:
                        pass
        finally:
            resp.close()

    def _classify_and_raise(self, status_code: int, body: str) -> None:
        """Classify an HTTP error and raise the appropriate exception."""
        if status_code == 401 or status_code == 403:
            raise LLMAuthError(
                f"Authentication failed ({status_code})",
                status_code=status_code,
                response=body,
            )
        elif status_code == 429:
            raise LLMRateLimitError(
                f"Rate limit exceeded ({status_code})",
                status_code=status_code,
                response=body,
            )
        elif status_code >= 500:
            raise LLMError(
                f"Server error ({status_code})",
                status_code=status_code,
                response=body,
            )
        else:
            raise LLMError(
                f"API error ({status_code}): {body[:200]}",
                status_code=status_code,
                response=body,
            )
