#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for spiderfoot.retry."""
from __future__ import annotations

import unittest

from spiderfoot.retry import (
    BackoffStrategy,
    DeadLetterQueue,
    RetryConfig,
    RetryExecutor,
    RetryResult,
    get_dead_letter_queue,
    retry,
    with_retry,
)


class TestRetryConfig(unittest.TestCase):
    """Test RetryConfig."""

    def test_defaults(self):
        cfg = RetryConfig()
        self.assertEqual(cfg.max_attempts, 3)
        self.assertEqual(cfg.backoff_strategy, BackoffStrategy.EXPONENTIAL)
        self.assertTrue(cfg.jitter)

    def test_fixed_delay(self):
        cfg = RetryConfig(
            backoff_strategy=BackoffStrategy.FIXED,
            backoff_base=2.0, jitter=False)
        self.assertEqual(cfg.compute_delay(1), 2.0)
        self.assertEqual(cfg.compute_delay(5), 2.0)

    def test_exponential_delay(self):
        cfg = RetryConfig(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_base=1.0, backoff_factor=2.0, jitter=False)
        self.assertAlmostEqual(cfg.compute_delay(1), 1.0)
        self.assertAlmostEqual(cfg.compute_delay(2), 2.0)
        self.assertAlmostEqual(cfg.compute_delay(3), 4.0)

    def test_linear_delay(self):
        cfg = RetryConfig(
            backoff_strategy=BackoffStrategy.LINEAR,
            backoff_base=1.0, jitter=False)
        self.assertAlmostEqual(cfg.compute_delay(1), 1.0)
        self.assertAlmostEqual(cfg.compute_delay(3), 3.0)

    def test_none_delay(self):
        cfg = RetryConfig(backoff_strategy=BackoffStrategy.NONE)
        self.assertEqual(cfg.compute_delay(1), 0.0)

    def test_delay_cap(self):
        cfg = RetryConfig(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_base=10.0, backoff_max=30.0,
            backoff_factor=3.0, jitter=False)
        delay = cfg.compute_delay(10)
        self.assertLessEqual(delay, 30.0)

    def test_jitter_adds_variance(self):
        cfg = RetryConfig(
            backoff_strategy=BackoffStrategy.FIXED,
            backoff_base=10.0, jitter=True, jitter_range=0.5)
        delays = [cfg.compute_delay(1) for _ in range(20)]
        # Should not all be identical
        self.assertTrue(len(set(delays)) > 1)

    def test_should_retry_retryable(self):
        cfg = RetryConfig(retryable_exceptions=[ConnectionError])
        self.assertTrue(cfg.should_retry(ConnectionError("fail")))
        self.assertFalse(cfg.should_retry(ValueError("bad")))

    def test_should_retry_non_retryable(self):
        cfg = RetryConfig()
        self.assertFalse(cfg.should_retry(KeyboardInterrupt()))
        self.assertFalse(cfg.should_retry(ValueError("bad")))

    def test_should_retry_predicate(self):
        cfg = RetryConfig(
            retryable_exceptions=[],
            retry_predicate=lambda e: "retry" in str(e))
        self.assertTrue(cfg.should_retry(Exception("please retry")))
        self.assertFalse(cfg.should_retry(Exception("no")))


class TestRetryExecutor(unittest.TestCase):
    """Test RetryExecutor."""

    def test_success_first_try(self):
        executor = RetryExecutor(RetryConfig(max_attempts=3))
        result = executor.execute(lambda: 42)
        self.assertTrue(result.success)
        self.assertEqual(result.result, 42)
        self.assertEqual(result.attempts, 1)

    def test_success_after_retries(self):
        counter = {"n": 0}

        def flaky():
            counter["n"] += 1
            if counter["n"] < 3:
                raise ConnectionError("fail")
            return "ok"

        cfg = RetryConfig(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.NONE)
        executor = RetryExecutor(cfg)
        result = executor.execute(flaky)

        self.assertTrue(result.success)
        self.assertEqual(result.result, "ok")
        self.assertEqual(result.attempts, 3)

    def test_all_retries_exhausted(self):
        def always_fail():
            raise ConnectionError("fail")

        cfg = RetryConfig(
            max_attempts=3,
            backoff_strategy=BackoffStrategy.NONE)
        executor = RetryExecutor(cfg)
        result = executor.execute(always_fail)

        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 3)
        self.assertIsInstance(result.exception, ConnectionError)
        self.assertEqual(len(result.errors), 3)

    def test_non_retryable_stops_immediately(self):
        counter = {"n": 0}

        def bad_value():
            counter["n"] += 1
            raise ValueError("bad input")

        cfg = RetryConfig(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.NONE)
        executor = RetryExecutor(cfg)
        result = executor.execute(bad_value)

        self.assertFalse(result.success)
        self.assertEqual(counter["n"], 1)

    def test_callbacks(self):
        retries = []
        successes = []
        failures = []

        cfg = RetryConfig(
            max_attempts=3,
            backoff_strategy=BackoffStrategy.NONE,
            on_retry=lambda a, e, d: retries.append(a),
            on_success=lambda a: successes.append(a),
            on_failure=lambda a, e: failures.append(a),
        )

        counter = {"n": 0}
        def flaky():
            counter["n"] += 1
            if counter["n"] < 2:
                raise ConnectionError("fail")
            return "ok"

        executor = RetryExecutor(cfg)
        executor.execute(flaky)

        self.assertEqual(len(retries), 1)
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 0)

    def test_failure_callback(self):
        failures = []
        cfg = RetryConfig(
            max_attempts=2,
            backoff_strategy=BackoffStrategy.NONE,
            on_failure=lambda a, e: failures.append(str(e)))

        def always_fail():
            raise ConnectionError("boom")

        executor = RetryExecutor(cfg)
        executor.execute(always_fail)
        self.assertEqual(len(failures), 1)
        self.assertIn("boom", failures[0])

    def test_stats(self):
        cfg = RetryConfig(
            max_attempts=2,
            backoff_strategy=BackoffStrategy.NONE)
        executor = RetryExecutor(cfg)

        executor.execute(lambda: 1)

        def fail():
            raise ConnectionError("x")
        executor.execute(fail)

        stats = executor.stats
        self.assertEqual(stats["total_calls"], 2)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["failed"], 1)

    def test_dlq_on_failure(self):
        dlq = DeadLetterQueue()
        cfg = RetryConfig(
            max_attempts=1,
            backoff_strategy=BackoffStrategy.NONE)
        executor = RetryExecutor(cfg, dlq=dlq)

        def fail():
            raise ConnectionError("gone")

        executor.execute(fail)
        self.assertEqual(dlq.size, 1)

        entry = dlq.pop()
        self.assertIn("gone", entry.exception)


class TestDeadLetterQueue(unittest.TestCase):
    """Test DeadLetterQueue."""

    def test_add_pop(self):
        from spiderfoot.retry import DeadLetterEntry
        dlq = DeadLetterQueue()
        dlq.add(DeadLetterEntry(
            operation_id="1", func_name="test",
            args=(), kwargs={}, exception="err", attempts=3))
        self.assertEqual(dlq.size, 1)

        entry = dlq.pop()
        self.assertEqual(entry.func_name, "test")
        self.assertEqual(dlq.size, 0)

    def test_max_size(self):
        from spiderfoot.retry import DeadLetterEntry
        dlq = DeadLetterQueue(max_size=5)
        for i in range(10):
            dlq.add(DeadLetterEntry(
                operation_id=str(i), func_name=f"f{i}",
                args=(), kwargs={}, exception="err", attempts=1))
        self.assertEqual(dlq.size, 5)
        self.assertEqual(dlq.total_added, 10)

    def test_clear(self):
        from spiderfoot.retry import DeadLetterEntry
        dlq = DeadLetterQueue()
        dlq.add(DeadLetterEntry(
            operation_id="1", func_name="test",
            args=(), kwargs={}, exception="e", attempts=1))
        self.assertEqual(dlq.clear(), 1)
        self.assertEqual(dlq.size, 0)

    def test_peek(self):
        from spiderfoot.retry import DeadLetterEntry
        dlq = DeadLetterQueue()
        for i in range(5):
            dlq.add(DeadLetterEntry(
                operation_id=str(i), func_name=f"f{i}",
                args=(), kwargs={}, exception="e", attempts=1))
        recent = dlq.peek(3)
        self.assertEqual(len(recent), 3)


class TestRetryDecorator(unittest.TestCase):
    """Test @retry decorator."""

    def test_decorator_success(self):
        @retry(max_attempts=3,
               backoff_strategy=BackoffStrategy.NONE)
        def succeed():
            return 42

        self.assertEqual(succeed(), 42)

    def test_decorator_retries(self):
        counter = {"n": 0}

        @retry(max_attempts=3,
               backoff_strategy=BackoffStrategy.NONE,
               retryable_exceptions=[ConnectionError])
        def flaky():
            counter["n"] += 1
            if counter["n"] < 3:
                raise ConnectionError("fail")
            return "ok"

        self.assertEqual(flaky(), "ok")

    def test_decorator_exhausted(self):
        @retry(max_attempts=2,
               backoff_strategy=BackoffStrategy.NONE,
               retryable_exceptions=[ConnectionError])
        def always_fail():
            raise ConnectionError("fail")

        with self.assertRaises(ConnectionError):
            always_fail()


class TestWithRetryContext(unittest.TestCase):
    """Test with_retry context manager."""

    def test_context_success(self):
        cfg = RetryConfig(
            max_attempts=3,
            backoff_strategy=BackoffStrategy.NONE)

        with with_retry(cfg) as ctx:
            result = ctx.execute(lambda: 100)
        self.assertEqual(result, 100)

    def test_context_failure_raises(self):
        cfg = RetryConfig(
            max_attempts=1,
            backoff_strategy=BackoffStrategy.NONE)

        def fail():
            raise ConnectionError("boom")

        with self.assertRaises(ConnectionError):
            with with_retry(cfg) as ctx:
                ctx.execute(fail)


if __name__ == "__main__":
    unittest.main()
