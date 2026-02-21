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
from typing import Any, Callable

from collections.abc import Generator

from spiderfoot.config.constants import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_VLLM_BASE_URL,
)

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
    stop: list[str] | None = None

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
    def from_env(cls) -> LLMConfig:
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
                base = DEFAULT_OPENAI_BASE_URL
            return f"{base}/chat/completions"

        elif self.provider == LLMProvider.OLLAMA:
            if not base:
                base = DEFAULT_OLLAMA_BASE_URL
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
                base = DEFAULT_VLLM_BASE_URL
            return f"{base}/chat/completions"

        elif self.provider == LLMProvider.MOCK:
            return "mock://llm/chat/completions"

        return f"{base}/chat/completions"

    @property
    def headers(self) -> dict[str, str]:
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
    raw: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    success: bool = True

    @property
    def total_tokens(self) -> int:
        """Return the total number of tokens used."""
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
    def __init__(self, message: str, status_code: int = 0, response: str = "") -> None:
        """Initialize the LLMError."""
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
    def generate(
        messages: list[dict[str, str]],
        model: str,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Generate a mock LLM response for testing.

        If *response_format* requests ``json_schema`` mode, returns a
        minimal JSON object that satisfies the schema's required fields.
        """
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        if response_format and response_format.get("type") in (
            "json_schema", "json_object"
        ):
            import json as _json
            # Try to produce a conformant mock from the schema
            schema_spec = response_format.get("json_schema", {})
            schema = schema_spec.get("schema", {})
            content = _json.dumps(
                _MockGenerator._mock_from_schema(schema)
            )
        else:
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

    @staticmethod
    def _mock_from_schema(schema: dict[str, Any]) -> Any:
        """Produce a minimal mock object from a JSON Schema."""
        schema_type = schema.get("type", "object")
        if schema_type == "object":
            props = schema.get("properties", {})
            required = set(schema.get("required", []))
            obj: dict[str, Any] = {}
            for key, prop in props.items():
                if key in required or len(obj) < 3:
                    obj[key] = _MockGenerator._mock_from_schema(prop)
            return obj
        elif schema_type == "array":
            items = schema.get("items", {})
            return [_MockGenerator._mock_from_schema(items)]
        elif schema_type == "string":
            enum_vals = schema.get("enum")
            if enum_vals:
                return enum_vals[0]
            return schema.get("default", "mock_value")
        elif schema_type == "integer":
            return schema.get("default", 50)
        elif schema_type == "number":
            return schema.get("default", 0.5)
        elif schema_type == "boolean":
            return schema.get("default", True)
        elif "anyOf" in schema:
            # Union type — pick the first non-null variant
            for variant in schema["anyOf"]:
                if variant.get("type") != "null":
                    return _MockGenerator._mock_from_schema(variant)
            return None
        return None


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

    def __init__(self, config: LLMConfig | None = None) -> None:
        """Initialize the LLMClient."""
        self.config = config or LLMConfig()
        self._total_requests = 0
        self._total_tokens = 0
        self._total_errors = 0
        self._total_latency_ms = 0.0

    @classmethod
    def from_env(cls) -> LLMClient:
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
        messages: list[dict[str, str]],
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
            return _MockGenerator.generate(
                messages,
                self.config.model,
                response_format=kwargs.get("response_format"),
            )

        return self._call_with_retry(messages, **kwargs)

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Generator[StreamChunk]:
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

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type,
        *,
        strict: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Send a chat request and parse the response into a Pydantic model.

        Uses the OpenAI ``response_format`` parameter (``json_schema`` mode)
        to force the model to return schema-conformant JSON, then validates
        and deserializes via the supplied Pydantic model.

        Args:
            messages: Chat messages in OpenAI format.
            response_model: A Pydantic ``BaseModel`` subclass.
            strict: If True, use ``json_schema`` mode (requires OpenAI / compatible).
                    If False, use ``json_object`` mode and parse best-effort.
            **kwargs: Override config parameters.

        Returns:
            An instance of *response_model* populated from the LLM response.

        Raises:
            LLMError: If the LLM call fails.
            pydantic.ValidationError: If the response doesn't match the schema.
        """
        import json as _json
        from pydantic import BaseModel

        if not (isinstance(response_model, type) and issubclass(response_model, BaseModel)):
            raise TypeError(
                f"response_model must be a Pydantic BaseModel subclass, "
                f"got {type(response_model)}"
            )

        # Build the response_format payload
        if strict:
            json_schema = response_model.model_json_schema()
            # Clean up schema for OpenAI compatibility
            # (remove $defs at top level → inline if simple)
            schema_name = response_model.__name__
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": json_schema,
                    "strict": True,
                },
            }
        else:
            response_format = {"type": "json_object"}

        # Inject a system hint so the model knows to output JSON
        augmented = list(messages)
        has_system = any(m.get("role") == "system" for m in augmented)
        json_hint = (
            f"\n\nRespond ONLY with valid JSON conforming to the "
            f"`{response_model.__name__}` schema. No markdown fences."
        )
        if has_system:
            for m in augmented:
                if m["role"] == "system":
                    m = dict(m)
                    m["content"] = m["content"] + json_hint
                    augmented[augmented.index(m)] = m
                    break
        else:
            augmented.insert(0, {
                "role": "system",
                "content": (
                    "You are a structured data extraction assistant."
                    + json_hint
                ),
            })

        llm_resp = self.chat_messages(
            augmented,
            response_format=response_format,
            **kwargs,
        )

        if not llm_resp.success:
            raise LLMError(
                f"LLM call failed: {llm_resp.error}",
            )

        # Parse JSON from the response content
        content = llm_resp.content.strip()
        # Strip markdown fences if the model added them despite the instruction
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        parsed = _json.loads(content)
        return response_model.model_validate(parsed)

    # -------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
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
        messages: list[dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build the API request body.

        Supports ``response_format`` for structured outputs:
        - ``{"type": "json_object"}`` — JSON mode (model returns arbitrary JSON)
        - ``{"type": "json_schema", "json_schema": {...}}`` — schema-constrained
        """
        body: dict[str, Any] = {
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

        # Structured output / JSON mode
        response_format = kwargs.get("response_format")
        if response_format is not None:
            body["response_format"] = response_format

        return body

    def _call_with_retry(
        self,
        messages: list[dict[str, str]],
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
        messages: list[dict[str, str]],
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
            except Exception as read_err:
                log.debug("Failed to read HTTP error response body: %s", read_err)
            self._classify_and_raise(e.code, body_text)
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason).lower():
                raise LLMTimeoutError(f"Request timed out: {e.reason}") from e
            raise LLMError(f"Connection error: {e.reason}") from e
        except TimeoutError as e:
            raise LLMTimeoutError("Request timed out") from e

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
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Generator[StreamChunk]:
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
            except Exception as read_err:
                log.debug("Failed to read HTTP error response body (streaming): %s", read_err)
            self._classify_and_raise(e.code, body_text)
        except urllib.error.URLError as e:
            raise LLMError(f"Connection error: {e.reason}") from e

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
