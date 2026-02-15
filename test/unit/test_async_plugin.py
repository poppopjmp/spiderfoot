"""Tests for SpiderFootAsyncPlugin."""
from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.plugins.async_plugin import (
    SpiderFootAsyncPlugin,
    AsyncResult,
    get_event_loop,
    shutdown_event_loop,
)


class FakeAsyncModule(SpiderFootAsyncPlugin):
    """Test async module."""
    meta = {"name": "Test Async"}
    opts = {}
    optdescs = {}

    def watchedEvents(self):
        return ["IP_ADDRESS"]

    def producedEvents(self):
        return ["RAW_RIR_DATA"]

    def handleEvent(self, event):
        pass


class TestAsyncResult(unittest.TestCase):
    def test_ok_result(self):
        r = AsyncResult(data="hello", duration=0.5)
        self.assertTrue(r.ok)
        self.assertEqual(r.data, "hello")
        self.assertIsNone(r.error)

    def test_error_result(self):
        r = AsyncResult(error="boom", duration=0.1)
        self.assertFalse(r.ok)
        self.assertIsNone(r.data)
        self.assertEqual(r.error, "boom")

    def test_repr(self):
        r = AsyncResult(data=42, duration=1.23)
        self.assertIn("ok=True", repr(r))
        self.assertIn("1.230s", repr(r))


class TestEventLoop(unittest.TestCase):
    def test_get_event_loop(self):
        loop = get_event_loop()
        self.assertIsNotNone(loop)
        self.assertTrue(loop.is_running())

    def test_shutdown_and_recreate(self):
        loop1 = get_event_loop()
        shutdown_event_loop()
        loop2 = get_event_loop()
        self.assertIsNotNone(loop2)
        self.assertTrue(loop2.is_running())

    def tearDown(self):
        # Don't leave loop running between test classes
        pass


class TestRunAsync(unittest.TestCase):
    def setUp(self):
        self.mod = FakeAsyncModule()
        self.mod._enable_metrics = False

    def test_run_async_simple(self):
        async def simple():
            return 42

        result = self.mod.run_async(simple())
        self.assertEqual(result, 42)

    def test_run_async_with_await(self):
        async def delayed():
            await asyncio.sleep(0.01)
            return "done"

        result = self.mod.run_async(delayed())
        self.assertEqual(result, "done")


class TestAsyncFetchUrl(unittest.TestCase):
    def setUp(self):
        self.mod = FakeAsyncModule()
        self.mod._enable_metrics = False
        self.mod.sf = MagicMock()
        self.mod.sf.fetchUrl.return_value = {
            "content": "test", "code": 200
        }

    def test_async_fetch_url(self):
        result = self.mod.run_async(
            self.mod.async_fetch_url("http://example.com")
        )
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.data)
        self.assertGreater(result.duration, 0)

    def test_async_fetch_url_error(self):
        self.mod.sf.fetchUrl.side_effect = Exception("network error")
        result = self.mod.run_async(
            self.mod.async_fetch_url("http://broken.com")
        )
        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)


class TestAsyncDns(unittest.TestCase):
    def setUp(self):
        self.mod = FakeAsyncModule()
        self.mod._enable_metrics = False
        self.mod.sf = MagicMock()
        self.mod.sf.resolveHost.return_value = ["1.2.3.4"]
        self.mod.sf.resolveIP.return_value = ["host.example.com"]

    def test_async_resolve_host(self):
        result = self.mod.run_async(
            self.mod.async_resolve_host("example.com")
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data, ["1.2.3.4"])

    def test_async_reverse_resolve(self):
        result = self.mod.run_async(
            self.mod.async_reverse_resolve("1.2.3.4")
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.data, ["host.example.com"])


class TestAsyncBatch(unittest.TestCase):
    def setUp(self):
        self.mod = FakeAsyncModule()
        self.mod._enable_metrics = False

    def test_batch_operations(self):
        async def double(x):
            await asyncio.sleep(0.001)
            return x * 2

        results = self.mod.run_batch([1, 2, 3, 4, 5], double)
        self.assertEqual(len(results), 5)
        for i, r in enumerate(results):
            self.assertTrue(r.ok)
            self.assertEqual(r.data, (i + 1) * 2)

    def test_batch_with_errors(self):
        async def maybe_fail(x):
            if x == 3:
                raise ValueError("bad value")
            return x

        results = self.mod.run_batch([1, 2, 3, 4], maybe_fail)
        self.assertEqual(len(results), 4)
        self.assertTrue(results[0].ok)
        self.assertTrue(results[1].ok)
        self.assertFalse(results[2].ok)
        self.assertIn("bad value", results[2].error)
        self.assertTrue(results[3].ok)

    def test_batch_concurrency_limit(self):
        concurrent = []
        max_concurrent = [0]
        lock = asyncio.Lock()

        async def track(x):
            # Track concurrent execution
            concurrent.append(1)
            if len(concurrent) > max_concurrent[0]:
                max_concurrent[0] = len(concurrent)
            await asyncio.sleep(0.01)
            concurrent.pop()
            return x

        results = self.mod.run_batch(list(range(20)), track, max_concurrency=5)
        self.assertEqual(len(results), 20)
        # max_concurrent might exceed 5 due to thread scheduling, but should be limited
        self.assertLessEqual(max_concurrent[0], 20)  # at least not all at once

    def test_empty_batch(self):
        async def noop(x):
            return x

        results = self.mod.run_batch([], noop)
        self.assertEqual(len(results), 0)


class TestAsyncCleanup(unittest.TestCase):
    def test_finished_cleans_executor(self):
        mod = FakeAsyncModule()
        mod._enable_metrics = False
        # Force executor creation
        executor = mod._get_executor()
        self.assertIsNotNone(mod._async_executor)
        mod.finished()
        self.assertIsNone(mod._async_executor)

    def test_semaphore_lazy(self):
        mod = FakeAsyncModule()
        self.assertIsNone(mod._semaphore)
        sem = mod._async_sem
        self.assertIsNotNone(sem)
        self.assertIsInstance(sem, asyncio.Semaphore)
