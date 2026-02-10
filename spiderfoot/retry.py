#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         retry
# Purpose:      Retry and recovery framework for SpiderFoot.
#               Provides configurable retry strategies with exponential
#               backoff, circuit breaker integration, and dead-letter
#               queues for failed operations.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

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
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Callable, Deque, Dict, List, Optional, Set, Tuple, Type,
)

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
    retry_predicate: Optional[Callable[[Exception], bool]] = None

    # Callback hooks
    on_retry: Optional[Callable[[int, Exception, float], None]] = None
    on_success: Optional[Callable[[int], None]] = None
    on_failure: Optional[Callable[[int, Exception], None]] = None

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
    exception: Optional[Exception] = None
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
    config: Optional[dict] = None


class DeadLetterQueue:
    """Stores permanently failed operations for later inspection/replay."""

    def __init__(self, max_size: int = 1000) -> None:
        self._queue: Deque[DeadLetterEntry] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._counter = 0

    def add(self, entry: DeadLetterEntry) -> None:
        with self._lock:
            self._queue.append(entry)
            self._counter += 1

    def pop(self) -> Optional[DeadLetterEntry]:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def peek(self, n: int = 10) -> list[DeadLetterEntry]:
        with self._lock:
            return list(self._queue)[-n:]

    def clear(self) -> int:
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def total_added(self) -> int:
        return self._counter


# Global DLQ instance
_dlq = DeadLetterQueue()


def get_dead_letter_queue() -> DeadLetterQueue:
    return _dlq


# ---------------------------------------------------------------------------
# RetryExecutor
# ---------------------------------------------------------------------------


class RetryExecutor:
    """Execute operations with automatic retry and recovery."""

    def __init__(self, config: Optional[RetryConfig] = None, *,
                 dlq: Optional[DeadLetterQueue] = None) -> None:
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
        with self._lock:
            return dict(self._stats)


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class RetryContext:
    """Context manager for retry-managed operations."""

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        self._executor = RetryExecutor(config)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with retry, raising on final failure."""
        result = self._executor.execute(func, *args, **kwargs)
        if result.success:
            return result.result
        raise result.exception


def with_retry(config: Optional[RetryConfig] = None) -> RetryContext:
    """Create a retry context manager."""
    return RetryContext(config)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def retry(max_attempts: int = 3, *,
          backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
          backoff_base: float = 1.0,
          backoff_max: float = 60.0,
          retryable_exceptions: Optional[list[type[Exception]]] = None,
          on_retry: Optional[Callable] = None):
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

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = executor.execute(func, *args, **kwargs)
            if result.success:
                return result.result
            raise result.exception
        wrapper._retry_config = config
        wrapper._retry_executor = executor
        return wrapper

    return decorator
