#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         retry
# Purpose:      Retry and recovery framework for SpiderFoot.
#               Provides configurable retry strategies with exponential
#               backoff, circuit breaker integration, and dead-letter
#               queues for failed operations.
#
# Author:       Van1sh 
# Created:      2025-07-08
# Copyright:    (c) Van1sh  2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Retry and Recovery Framework

Resilient operation execution with pluggable retry strategies::

    from spiderfoot.retry import retry, RetryConfig, with_retry

    # Decorator style
    @retry(max_attempts=3, backoff_base=1.0)
    def fetch_data(url):
        return requests.get(url)

    # Context manager style
    config = RetryConfig(max_attempts=5, retryable_exceptions=[IOError])
    with with_retry(config) as ctx:
        result = ctx.execute(fetch_data, url)

    # Direct usage
    from spiderfoot.retry import RetryExecutor
    executor = RetryExecutor(config)
    result = executor.execute(fetch_data, url)

Strategies:
    - Fixed delay
    - Exponential backoff with jitter
    - Linear backoff
    - Custom callable
"""

import functools
import logging
import random
import threading
import time
import types as types_mod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

log = logging.getLogger("spiderfoot.retry")


class BackoffStrategy(str, Enum):
    """Backoff strategies for retry delays."""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    NONE = "none"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_base: float = 1.0      # Base delay in seconds
    backoff_max: float = 60.0      # Maximum delay cap
    backoff_factor: float = 2.0    # Multiplier for exponential
    jitter: bool = True            # Add randomized jitter
    jitter_range: float = 0.5      # Max jitter as fraction of delay

    retryable_exceptions: list[type[Exception]] = field(
        default_factory=lambda: [
            ConnectionError, TimeoutError, OSError,
        ]
    )
    non_retryable_exceptions: list[type[Exception]] = field(
        default_factory=lambda: [
            KeyboardInterrupt, SystemExit, ValueError,
        ]
    )

    # Optional predicate for retry decision
    retry_predicate: Callable[[Exception], bool] | None = None

    # Callback hooks
    on_retry: Callable[[int, Exception, float], None] | None = None
    on_success: Callable[[int], None] | None = None
    on_failure: Callable[[int, Exception], None] | None = None

    def compute_delay(self, attempt: int) -> float:
        """Compute delay for a given attempt number (1-indexed)."""
        if self.backoff_strategy == BackoffStrategy.NONE:
            return 0.0

        if self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.backoff_base

        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.backoff_base * attempt

        elif self.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.backoff_base * (self.backoff_factor ** (attempt - 1))

        else:
            delay = self.backoff_base

        # Cap
        delay = min(delay, self.backoff_max)

        # Jitter
        if self.jitter and delay > 0:
            jitter_amount = delay * self.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)

        return delay

    def should_retry(self, exception: Exception) -> bool:
        """Determine if an exception should trigger a retry."""
        # Check non-retryable first
        for exc_type in self.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        # Custom predicate
        if self.retry_predicate:
            return self.retry_predicate(exception)

        # Check retryable list (empty = retry everything)
        if self.retryable_exceptions:
            for exc_type in self.retryable_exceptions:
                if isinstance(exception, exc_type):
                    return True
            return False

        return True


# ---------------------------------------------------------------------------
# Retry result
# ---------------------------------------------------------------------------


@dataclass
class RetryResult:
    """Result of a retry-managed operation."""
    success: bool
    result: Any = None
    exception: Exception | None = None
    attempts: int = 0
    total_delay: float = 0.0
    errors: list[tuple[int, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dead Letter Queue
# ---------------------------------------------------------------------------


@dataclass
class DeadLetterEntry:
    """Entry in the dead letter queue."""
    operation_id: str
    func_name: str
    args: tuple
    kwargs: dict
    exception: str
    attempts: int
    timestamp: float = field(default_factory=time.time)
    config: dict | None = None


class DeadLetterQueue:
    """Stores permanently failed operations for later inspection/replay."""

    def __init__(self, max_size: int = 1000) -> None:
        """Initialize the DeadLetterQueue."""
        self._queue: deque[DeadLetterEntry] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._counter = 0

    def add(self, entry: DeadLetterEntry) -> None:
        """Add a failed operation entry to the queue."""
        with self._lock:
            self._queue.append(entry)
            self._counter += 1

    def pop(self) -> DeadLetterEntry | None:
        """Remove and return the oldest entry from the queue."""
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def peek(self, n: int = 10) -> list[DeadLetterEntry]:
        """Return the most recent entries without removing them."""
        with self._lock:
            return list(self._queue)[-n:]

    def clear(self) -> int:
        """Clear all entries and return the count removed."""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count

    @property
    def size(self) -> int:
        """Return the current number of entries in the queue."""
        return len(self._queue)

    @property
    def total_added(self) -> int:
        """Return the total number of entries ever added."""
        return self._counter


# Global DLQ instance
_dlq = DeadLetterQueue()


def get_dead_letter_queue() -> DeadLetterQueue:
    """Return the global dead letter queue instance."""
    return _dlq


# ---------------------------------------------------------------------------
# RetryExecutor
# ---------------------------------------------------------------------------


class RetryExecutor:
    """Execute operations with automatic retry and recovery."""

    def __init__(self, config: RetryConfig | None = None, *,
                 dlq: DeadLetterQueue | None = None) -> None:
        """Initialize the RetryExecutor."""
        self.config = config or RetryConfig()
        self.dlq = dlq or _dlq
        self._stats = {
            "total_calls": 0,
            "successful": 0,
            "failed": 0,
            "total_retries": 0,
        }
        self._lock = threading.Lock()

    def execute(self, func: Callable, *args, **kwargs) -> RetryResult:
        """Execute a function with retry logic.

        Returns RetryResult with outcome details.
        """
        with self._lock:
            self._stats["total_calls"] += 1

        result = RetryResult(success=False)
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            result.attempts = attempt

            try:
                ret = func(*args, **kwargs)
                result.success = True
                result.result = ret

                with self._lock:
                    self._stats["successful"] += 1

                if self.config.on_success:
                    try:
                        self.config.on_success(attempt)
                    except Exception as e:
                        log.debug("on_success callback failed for %s: %s", func.__name__, e)

                return result

            except Exception as e:
                last_exception = e
                result.errors.append((attempt, str(e)))

                if attempt >= self.config.max_attempts:
                    break

                if not self.config.should_retry(e):
                    log.debug(
                        "Non-retryable exception on %s attempt %d: %s",
                        func.__name__, attempt, e)
                    break

                delay = self.config.compute_delay(attempt)
                result.total_delay += delay

                with self._lock:
                    self._stats["total_retries"] += 1

                if self.config.on_retry:
                    try:
                        self.config.on_retry(attempt, e, delay)
                    except Exception as e:
                        log.debug("on_retry callback failed for %s: %s", func.__name__, e)

                log.info(
                    "Retry %d/%d for %s after %.1fs: %s",
                    attempt, self.config.max_attempts,
                    func.__name__, delay, e)

                if delay > 0:
                    time.sleep(delay)

        # Final failure
        result.success = False
        result.exception = last_exception

        with self._lock:
            self._stats["failed"] += 1

        if self.config.on_failure:
            try:
                self.config.on_failure(result.attempts, last_exception)
            except Exception as e:
                log.debug("on_failure callback failed for %s: %s", func.__name__, e)

        # Add to dead letter queue
        import uuid
        self.dlq.add(DeadLetterEntry(
            operation_id=str(uuid.uuid4())[:8],
            func_name=getattr(func, "__name__", str(func)),
            args=args,
            kwargs=kwargs,
            exception=str(last_exception),
            attempts=result.attempts,
        ))

        return result

    @property
    def stats(self) -> dict:
        """Return retry execution statistics."""
        with self._lock:
            return dict(self._stats)


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class RetryContext:
    """Context manager for retry-managed operations."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        """Initialize the RetryContext."""
        self._executor = RetryExecutor(config)

    def __enter__(self) -> RetryContext:
        """Enter the retry context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types_mod.TracebackType | None,
    ) -> bool:
        """Exit the retry context."""
        return False

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with retry, raising on final failure."""
        result = self._executor.execute(func, *args, **kwargs)
        if result.success:
            return result.result
        raise result.exception


def with_retry(config: RetryConfig | None = None) -> RetryContext:
    """Create a retry context manager."""
    return RetryContext(config)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def retry(max_attempts: int = 3, *,
          backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
          backoff_base: float = 1.0,
          backoff_max: float = 60.0,
          retryable_exceptions: list[type[Exception]] | None = None,
          on_retry: Callable | None = None) -> Callable:
    """Decorator to add retry logic to a function.

    Usage::

        @retry(max_attempts=3, backoff_base=0.5)
        def unstable_operation():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        backoff_strategy=backoff_strategy,
        backoff_base=backoff_base,
        backoff_max=backoff_max,
        retryable_exceptions=(retryable_exceptions
                              or [ConnectionError, TimeoutError, OSError]),
        on_retry=on_retry,
    )
    executor = RetryExecutor(config)

    def decorator(func: Callable) -> Callable:
        """Wrap the function with retry logic."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            """Execute the function with automatic retry on failure."""
            result = executor.execute(func, *args, **kwargs)
            if result.success:
                return result.result
            raise result.exception
        wrapper._retry_config = config
        wrapper._retry_executor = executor
        return wrapper

    return decorator


# ── Adaptive Request Backoff for Rate-Limited Endpoints ───────────────


@dataclass
class BackoffState:
    """Tracks backoff state for a single host."""
    consecutive_429s: int = 0
    last_429_time: float = 0.0
    current_delay: float = 0.0
    retry_after: float | None = None
    total_429_count: int = 0


@dataclass
class AdaptiveBackoffConfig:
    """Configuration for adaptive request backoff.

    Attributes:
        initial_delay: First backoff delay in seconds.
        max_delay: Maximum backoff delay cap.
        backoff_factor: Multiplier for exponential increase.
        decay_time: Seconds after which to start reducing delay.
        reset_after: Seconds of no 429s before resetting to zero.
        rate_limit_codes: HTTP status codes that trigger backoff.
    """
    initial_delay: float = 1.0
    max_delay: float = 120.0
    backoff_factor: float = 2.0
    decay_time: float = 60.0
    reset_after: float = 300.0
    rate_limit_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 503})
    )


class AdaptiveBackoff:
    """Per-host adaptive request backoff with exponential delay.

    Thread-safe. Tracks rate-limit responses per host and computes
    appropriate delays for subsequent requests.
    """

    def __init__(self, config: AdaptiveBackoffConfig | None = None) -> None:
        self.config = config or AdaptiveBackoffConfig()
        self._hosts: dict[str, BackoffState] = {}
        self._lock = threading.Lock()

    def get_delay(self, host: str) -> float:
        """Get the recommended delay before making a request to *host*.

        Returns 0.0 if no backoff is needed.
        """
        with self._lock:
            state = self._hosts.get(host)
            if state is None:
                return 0.0

            now = time.time()
            elapsed = now - state.last_429_time

            if elapsed > self.config.reset_after:
                del self._hosts[host]
                return 0.0

            if state.retry_after is not None:
                remaining = state.retry_after - (now - state.last_429_time)
                if remaining > 0:
                    return min(remaining, self.config.max_delay)
                state.retry_after = None

            if elapsed > self.config.decay_time and state.current_delay > 0:
                decay_factor = (elapsed - self.config.decay_time) / self.config.reset_after
                decayed = state.current_delay * max(0.0, 1.0 - decay_factor)
                return max(0.0, decayed)

            return state.current_delay

    def record_response(
        self,
        host: str,
        status_code: int,
        retry_after: str | float | None = None,
    ) -> float:
        """Record an HTTP response and update backoff state.

        Args:
            host: The target host.
            status_code: HTTP response status code.
            retry_after: Value of Retry-After header (seconds or HTTP-date).

        Returns:
            The new delay for this host.
        """
        with self._lock:
            if status_code in self.config.rate_limit_codes:
                return self._handle_rate_limit(host, retry_after)
            else:
                return self._handle_success(host)

    def _handle_rate_limit(
        self,
        host: str,
        retry_after: str | float | None,
    ) -> float:
        """Process a rate-limit response (429/503)."""
        state = self._hosts.get(host)
        if state is None:
            state = BackoffState()
            self._hosts[host] = state

        state.consecutive_429s += 1
        state.total_429_count += 1
        state.last_429_time = time.time()

        if retry_after is not None:
            try:
                state.retry_after = float(retry_after)
                state.current_delay = min(
                    float(retry_after), self.config.max_delay
                )
                log.info(
                    "Host %s: Retry-After=%s, delay=%.1fs",
                    host, retry_after, state.current_delay,
                )
                return state.current_delay
            except (ValueError, TypeError):
                pass

        state.current_delay = min(
            self.config.initial_delay
            * (self.config.backoff_factor ** (state.consecutive_429s - 1)),
            self.config.max_delay,
        )
        log.info(
            "Host %s: 429 #%d, backoff delay=%.1fs",
            host, state.consecutive_429s, state.current_delay,
        )
        return state.current_delay

    def _handle_success(self, host: str) -> float:
        """Process a successful (non-429) response."""
        state = self._hosts.get(host)
        if state is None:
            return 0.0

        if state.consecutive_429s > 0:
            state.consecutive_429s = max(0, state.consecutive_429s - 1)

        if state.current_delay > 0:
            state.current_delay = state.current_delay / 2.0
            if state.current_delay < 0.1:
                state.current_delay = 0.0
                del self._hosts[host]
                return 0.0

        return state.current_delay

    def clear(self, host: str | None = None) -> None:
        """Clear backoff state for a specific host or all hosts."""
        with self._lock:
            if host:
                self._hosts.pop(host, None)
            else:
                self._hosts.clear()

    def stats(self) -> dict[str, Any]:
        """Return backoff statistics for all tracked hosts."""
        with self._lock:
            return {
                "tracked_hosts": len(self._hosts),
                "hosts": {
                    host: {
                        "consecutive_429s": state.consecutive_429s,
                        "total_429s": state.total_429_count,
                        "current_delay": round(state.current_delay, 2),
                    }
                    for host, state in self._hosts.items()
                },
            }
