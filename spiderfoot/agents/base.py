"""
Base agent framework for SpiderFoot AI agents.

Each agent:
  1. Subscribes to specific event types from the event bus
  2. Processes events through LLM-powered analysis
  3. Publishes enriched results back to the event bus
  4. Exposes Prometheus metrics for monitoring
"""

import asyncio
import logging
import os
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
    enabled: bool = True
    event_types: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls, name: str) -> "AgentConfig":
        """Create config from environment variables."""
        prefix = f"SF_AGENT_{name.upper()}_"
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
            max_concurrent=int(os.environ.get(f"{prefix}MAX_CONCURRENT", "5")),
            batch_size=int(os.environ.get(f"{prefix}BATCH_SIZE", "10")),
            timeout_seconds=int(os.environ.get(f"{prefix}TIMEOUT", "120")),
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
        self._processed_count = 0
        self._error_count = 0
        self._total_processing_time = 0.0
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
            "processed_total": self._processed_count,
            "errors_total": self._error_count,
            "avg_processing_time_ms": round(avg_time, 2),
        }

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """
        Call LLM via LiteLLM proxy (OpenAI-compatible API).

        Args:
            messages: Chat messages in OpenAI format
            model: Override model name (defaults to config)
            temperature: Sampling temperature
            max_tokens: Maximum response tokens

        Returns:
            LLM response text
        """
        import aiohttp

        model = model or self.config.llm_model
        url = f"{self.config.llm_endpoint}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.llm_api_key}",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
