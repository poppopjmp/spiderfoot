"""
Base agent framework for SpiderFoot AI agents.

Each agent:
  1. Subscribes to specific event types from the event bus
  2. Processes events through LLM-powered analysis
  3. Publishes enriched results back to the event bus
  4. Exposes Prometheus metrics for monitoring
"""

import asyncio
import json
import logging
import os
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sf.agents")


class AgentStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class AgentResult:
    """Result produced by an agent after processing an event."""

    agent_name: str
    event_id: str
    scan_id: str
    result_type: str  # e.g. "finding_validation", "summary", "report"
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # 0.0 - 1.0
    processing_time_ms: float = 0.0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the result for APIs, Redis, and tests."""
        return {
            "agent": self.agent_name,
            "agent_name": self.agent_name,
            "event_id": self.event_id,
            "scan_id": self.scan_id,
            "result_type": self.result_type,
            "data": self.data,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "error": self.error,
            "success": self.is_success,
        }


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""

    name: str
    llm_endpoint: str = "http://litellm:4000"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    max_concurrent: int = 5
    batch_size: int = 10
    timeout_seconds: int = 120
    llm_max_retries: int = 3
    llm_retry_base_seconds: float = 1.0
    llm_retry_max_seconds: float = 30.0
    llm_retry_jitter_seconds: float = 0.25
    enabled: bool = True
    event_types: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, name: str) -> "AgentConfig":
        """Create config from environment variables."""
        prefix = f"SF_AGENT_{name.upper()}_"

        def _int_env(var_name: str, default: int) -> int:
            try:
                return int(os.environ.get(var_name, str(default)))
            except (TypeError, ValueError):
                logger.warning("Invalid integer env var %s; using %s", var_name, default)
                return default

        def _float_env(var_name: str, default: float) -> float:
            try:
                return float(os.environ.get(var_name, str(default)))
            except (TypeError, ValueError):
                logger.warning("Invalid float env var %s; using %s", var_name, default)
                return default

        return cls(
            name=name,
            llm_endpoint=os.environ.get(
                f"{prefix}LLM_ENDPOINT",
                os.environ.get("SF_LLM_API_BASE", "http://litellm:4000"),
            ),
            llm_api_key=os.environ.get(
                f"{prefix}LLM_API_KEY",
                os.environ.get("SF_LLM_API_KEY", ""),
            ),
            llm_model=os.environ.get(
                f"{prefix}LLM_MODEL",
                os.environ.get("SF_LLM_MODEL", "gpt-4o-mini"),
            ),
            max_concurrent=max(1, _int_env(f"{prefix}MAX_CONCURRENT", 5)),
            batch_size=max(1, _int_env(f"{prefix}BATCH_SIZE", 10)),
            timeout_seconds=max(1, _int_env(f"{prefix}TIMEOUT", 120)),
            llm_max_retries=max(1, _int_env(f"{prefix}LLM_MAX_RETRIES", 3)),
            llm_retry_base_seconds=max(
                0.0,
                _float_env(f"{prefix}LLM_RETRY_BASE_SECONDS", 1.0),
            ),
            llm_retry_max_seconds=max(
                0.0,
                _float_env(f"{prefix}LLM_RETRY_MAX_SECONDS", 30.0),
            ),
            llm_retry_jitter_seconds=max(
                0.0,
                _float_env(f"{prefix}LLM_RETRY_JITTER_SECONDS", 0.25),
            ),
            enabled=os.environ.get(f"{prefix}ENABLED", "true").lower() == "true",
        )


class BaseAgent(ABC):
    """
    Abstract base class for all SpiderFoot AI agents.

    Subclasses must implement:
        - process_event(): Core processing logic
        - event_types: Property returning list of event types to handle
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.IDLE
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._active_count = 0
        self._processed_count = 0
        self._error_count = 0
        self._llm_retry_count = 0
        self._total_processing_time = 0.0
        self._last_error: Optional[str] = None
        self._llm_session = None
        self.logger = logging.getLogger(f"sf.agents.{config.name}")

    @property
    @abstractmethod
    def event_types(self) -> List[str]:
        """Event types this agent processes."""
        ...

    @abstractmethod
    async def process_event(
        self, event: Dict[str, Any]
    ) -> AgentResult:
        """
        Process a single event and return an enriched result.

        Args:
            event: Event dict from the event bus

        Returns:
            AgentResult with processing outcome
        """
        ...

    async def handle_event(self, event: Dict[str, Any]) -> Optional[AgentResult]:
        """
        Entry point for event processing with concurrency control,
        timing, and error handling.
        """
        if not self.config.enabled:
            return None

        async with self._semaphore:
            self._active_count += 1
            self.status = AgentStatus.PROCESSING
            start = time.monotonic()

            try:
                result = await asyncio.wait_for(
                    self.process_event(event),
                    timeout=self.config.timeout_seconds,
                )
                result.processing_time_ms = (time.monotonic() - start) * 1000
                self._processed_count += 1
                self._total_processing_time += result.processing_time_ms
                self.status = AgentStatus.IDLE
                return result

            except asyncio.TimeoutError:
                self._error_count += 1
                self.status = AgentStatus.ERROR
                self._last_error = f"Timeout after {self.config.timeout_seconds}s"
                self.logger.warning(
                    "Timeout processing event %s after %ds",
                    event.get("id", "?"),
                    self.config.timeout_seconds,
                )
                return AgentResult(
                    agent_name=self.config.name,
                    event_id=event.get("id", ""),
                    scan_id=event.get("scan_id", ""),
                    result_type="error",
                    error=f"Timeout after {self.config.timeout_seconds}s",
                    processing_time_ms=(time.monotonic() - start) * 1000,
                )

            except Exception as exc:
                self._error_count += 1
                self.status = AgentStatus.ERROR
                self._last_error = str(exc)[:500]
                self.logger.exception(
                    "Error processing event %s: %s",
                    event.get("id", "?"),
                    exc,
                )
                return AgentResult(
                    agent_name=self.config.name,
                    event_id=event.get("id", ""),
                    scan_id=event.get("scan_id", ""),
                    result_type="error",
                    error=str(exc),
                    processing_time_ms=(time.monotonic() - start) * 1000,
                )
            finally:
                self._active_count = max(0, self._active_count - 1)
                if self.status != AgentStatus.STOPPED:
                    if self._active_count > 0:
                        self.status = AgentStatus.PROCESSING
                    elif self.status == AgentStatus.PROCESSING:
                        self.status = AgentStatus.IDLE

    def get_metrics(self) -> Dict[str, Any]:
        """Return agent metrics for Prometheus scraping."""
        avg_time = (
            self._total_processing_time / self._processed_count
            if self._processed_count > 0
            else 0.0
        )
        return {
            "agent_name": self.config.name,
            "status": self.status.value,
            "active_tasks": self._active_count,
            "max_concurrent": self.config.max_concurrent,
            "processed_total": self._processed_count,
            "errors_total": self._error_count,
            "llm_retries_total": self._llm_retry_count,
            "avg_processing_time_ms": round(avg_time, 2),
            "last_error": self._last_error,
        }

    async def close(self) -> None:
        """Release network resources held by the agent."""
        self.status = AgentStatus.STOPPED
        if self._llm_session is not None:
            await self._llm_session.close()
            self._llm_session = None

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Call LLM via LiteLLM proxy (OpenAI-compatible API).

        Args:
            messages: Chat messages in OpenAI format
            model: Override model name (defaults to config)
            temperature: Sampling temperature
            max_tokens: Maximum response tokens
            response_format: Optional structured output format spec
                             (e.g. {"type": "json_schema", "json_schema": {...}})

        Returns:
            LLM response text
        """
        import aiohttp

        model = model or self.config.llm_model
        urls = self._chat_completion_urls()
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.llm_api_key:
            headers["Authorization"] = f"Bearer {self.config.llm_api_key}"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        session = await self._get_llm_session()
        last_error: Optional[BaseException] = None

        for attempt in range(1, self.config.llm_max_retries + 1):
            for url in urls:
                try:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
                    ) as resp:
                        if resp.status == 404 and url == urls[0] and len(urls) > 1:
                            continue

                        if resp.status in {408, 409, 425, 429, 500, 502, 503, 504}:
                            retry_after = self._retry_after_seconds(resp.headers.get("Retry-After"))
                            body = await resp.text()
                            raise RuntimeError(
                                f"Retryable LLM HTTP {resp.status}: {body[:500]}"
                            ) from _RetryAfter(retry_after)

                        resp.raise_for_status()
                        data = await resp.json()
                        return data["choices"][0]["message"].get("content", "")

                except asyncio.CancelledError:
                    raise
                except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, RuntimeError) as exc:
                    last_error = exc
                    if isinstance(exc.__cause__, _RetryAfter):
                        retry_after = exc.__cause__.seconds
                    else:
                        retry_after = None

                    if attempt >= self.config.llm_max_retries:
                        break

                    self._llm_retry_count += 1
                    delay = retry_after if retry_after is not None else self._retry_delay(attempt)
                    self.logger.warning(
                        "LLM call failed for %s (attempt %d/%d): %s; retrying in %.2fs",
                        self.config.name,
                        attempt,
                        self.config.llm_max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    break

        raise RuntimeError(f"LLM call failed after retries: {last_error}") from last_error

    async def _get_llm_session(self):
        """Return a persistent aiohttp session for LLM requests."""
        import aiohttp

        if self._llm_session is None or self._llm_session.closed:
            connector = aiohttp.TCPConnector(
                limit=max(2, self.config.max_concurrent * 2),
                ttl_dns_cache=300,
            )
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self._llm_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._llm_session

    def _chat_completion_urls(self) -> List[str]:
        """Return primary and compatibility chat-completions endpoints."""
        endpoint = self.config.llm_endpoint.rstrip("/")
        if endpoint.endswith("/chat/completions"):
            return [endpoint]
        if endpoint.endswith("/v1"):
            return [f"{endpoint}/chat/completions"]
        return [f"{endpoint}/chat/completions", f"{endpoint}/v1/chat/completions"]

    def _retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with small jitter."""
        base = self.config.llm_retry_base_seconds * (2 ** max(0, attempt - 1))
        delay = min(self.config.llm_retry_max_seconds, base)
        if self.config.llm_retry_jitter_seconds:
            delay += random.uniform(0.0, self.config.llm_retry_jitter_seconds)
        return delay

    @staticmethod
    def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
        """Parse a Retry-After header when provided as seconds."""
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            return None

    @staticmethod
    def strip_markdown_fences(content: str) -> str:
        """Remove common markdown code fences around model JSON."""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        return cleaned

    @classmethod
    def parse_json_response(cls, content: str) -> Any:
        """Parse LLM JSON robustly, including fenced or prefixed JSON."""
        cleaned = cls.strip_markdown_fences(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            candidate = cls._extract_json_candidate(cleaned)
            if candidate is None:
                raise
            return json.loads(candidate)

    @staticmethod
    def _extract_json_candidate(content: str) -> Optional[str]:
        """Extract the first balanced JSON object or array from text."""
        starts = [idx for idx in (content.find("{"), content.find("[")) if idx != -1]
        if not starts:
            return None

        start = min(starts)
        stack: List[str] = []
        in_string = False
        escaped = False
        pairs = {"{": "}", "[": "]"}

        for index, char in enumerate(content[start:], start=start):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char in pairs:
                stack.append(pairs[char])
            elif stack and char == stack[-1]:
                stack.pop()
                if not stack:
                    return content[start:index + 1]
        return None

    @staticmethod
    def redact_sensitive_values(text: Any) -> str:
        """Best-effort redaction before sending untrusted findings to an LLM."""
        redacted = str(text)
        replacements = [
            (
                r"(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]+",
                r"\1=[REDACTED]",
            ),
            (r"(?i)(authorization:\s*bearer\s+)[a-z0-9._\-+/=]+", r"\1[REDACTED]"),
            (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_ACCESS_KEY]"),
            (
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                "[REDACTED_PRIVATE_KEY]",
            ),
        ]
        for pattern, replacement in replacements:
            redacted = re.sub(pattern, replacement, redacted, flags=re.DOTALL)
        return redacted

    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: type,
        *,
        strict: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Any:
        """Call LLM and parse the response into a Pydantic model.

        Uses ``response_format`` (json_schema mode) to force conformant
        JSON, then validates via the provided Pydantic model class.

        Args:
            messages: Chat messages in OpenAI format
            response_model: A Pydantic BaseModel subclass
            strict: Use json_schema mode (True) or json_object mode (False)
            model: Override model name
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum response tokens

        Returns:
            An instance of *response_model*.

        Raises:
            pydantic.ValidationError: If the LLM output doesn't match.
        """
        from pydantic import BaseModel

        if not (isinstance(response_model, type) and issubclass(response_model, BaseModel)):
            raise TypeError(
                f"response_model must be a Pydantic BaseModel subclass, "
                f"got {type(response_model)}"
            )

        if strict:
            json_schema = response_model.model_json_schema()
            response_format: Optional[Dict[str, Any]] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": json_schema,
                    "strict": True,
                },
            }
        else:
            response_format = {"type": "json_object"}

        # Add JSON hint to system message
        json_hint = (
            f"\n\nRespond ONLY with valid JSON conforming to the "
            f"`{response_model.__name__}` schema. No markdown fences."
        )
        augmented = list(messages)
        if augmented and augmented[0].get("role") == "system":
            augmented[0] = dict(augmented[0])
            augmented[0]["content"] += json_hint
        else:
            augmented.insert(0, {
                "role": "system",
                "content": "You are a structured data extraction assistant." + json_hint,
            })

        content = await self.call_llm(
            augmented,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        parsed = self.parse_json_response(content)
        return response_model.model_validate(parsed)


class _RetryAfter(Exception):
    """Internal marker carrying Retry-After delay across exception handling."""

    def __init__(self, seconds: Optional[float]) -> None:
        super().__init__("retry-after")
        self.seconds = seconds
