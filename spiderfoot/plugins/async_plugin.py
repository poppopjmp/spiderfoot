"""Async module support for SpiderFoot modern plugins.

Provides an async-capable base class that allows modules to use
async/await for I/O operations while remaining compatible with the
synchronous scan engine.

Usage::

    from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

    class sfp_example_async(SpiderFootAsyncPlugin):
        async def handleEvent(self, event):
            result = await self.async_fetch_url("https://api.example.com")
            ...
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from .modern_plugin import SpiderFootModernPlugin


log = logging.getLogger("spiderfoot.async_plugin")

T = TypeVar("T")

# Shared event loop for async plugins
_shared_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: Any | None = None


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a shared event loop for async plugin operations."""
    global _shared_loop, _loop_thread
    if _shared_loop is None or _shared_loop.is_closed():
        import threading
        _shared_loop = asyncio.new_event_loop()

        def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        _loop_thread = threading.Thread(
            target=_run_loop,
            args=(_shared_loop,),
            daemon=True,
            name="spiderfoot-async-loop",
        )
        _loop_thread.start()
    return _shared_loop


def shutdown_event_loop() -> None:
    """Shutdown the shared event loop."""
    global _shared_loop, _loop_thread
    if _shared_loop and not _shared_loop.is_closed():
        _shared_loop.call_soon_threadsafe(_shared_loop.stop)
        if _loop_thread:
            _loop_thread.join(timeout=5)
        _shared_loop.close()
    _shared_loop = None
    _loop_thread = None


class AsyncResult:
    """Container for async operation results."""

    def __init__(self, data: Any = None, error: str | None = None,
                 duration: float = 0.0) -> None:
        """Initialize the AsyncResult."""
        self.data = data
        self.error = error
        self.duration = duration
        self.ok = error is None

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        return f"AsyncResult(ok={self.ok}, duration={self.duration:.3f}s)"


class SpiderFootAsyncPlugin(SpiderFootModernPlugin):
    """
    Async-capable SpiderFoot plugin base class.

    Extends SpiderFootModernPlugin with:
    - async_fetch_url() for non-blocking HTTP requests
    - async_resolve_host() for non-blocking DNS resolution
    - async_batch() for parallel async operations
    - run_async() to bridge sync → async
    """

    # Maximum concurrent async operations per module
    _max_async_concurrency = 10

    def __init__(self) -> None:
        """Initialize the SpiderFootAsyncPlugin."""
        super().__init__()
        self._semaphore: asyncio.Semaphore | None = None
        self._async_executor: ThreadPoolExecutor | None = None

    @property
    def _async_sem(self) -> asyncio.Semaphore:
        """Lazy semaphore for concurrency limiting."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_async_concurrency)
        return self._semaphore

    # ------------------------------------------------------------------
    # Core async bridge
    # ------------------------------------------------------------------

    def run_async(self, coro: Any) -> Any:
        """Run an async coroutine from synchronous context.

        Submits the coroutine to the shared event loop and blocks
        until it completes.

        Parameters
        ----------
        coro : coroutine
            The coroutine to execute.

        Returns
        -------
        Any
            The coroutine's return value.
        """
        loop = get_event_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=300)  # 5 min max

    # ------------------------------------------------------------------
    # Async HTTP
    # ------------------------------------------------------------------

    async def async_fetch_url(self, url: str, method: str = "GET",
                              timeout: int = 30,
                              **kwargs) -> AsyncResult:
        """Async HTTP fetch with concurrency limiting.

        Falls back to sync fetch_url in a thread pool if no async
        HTTP client is available.
        """
        t0 = time.monotonic()
        async with self._async_sem:
            try:
                # Use thread pool to run sync fetch_url
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._get_executor(),
                    functools.partial(
                        self.fetch_url, url, method=method,
                        timeout=timeout, **kwargs
                    )
                )
                duration = time.monotonic() - t0
                if result is None:
                    return AsyncResult(error="fetch returned None", duration=duration)
                return AsyncResult(data=result, duration=duration)
            except Exception as e:
                duration = time.monotonic() - t0
                return AsyncResult(error=str(e), duration=duration)

    # ------------------------------------------------------------------
    # Async DNS
    # ------------------------------------------------------------------

    async def async_resolve_host(self, hostname: str) -> AsyncResult:
        """Async DNS resolution."""
        t0 = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._get_executor(),
                self.resolve_host, hostname
            )
            return AsyncResult(data=result, duration=time.monotonic() - t0)
        except Exception as e:
            return AsyncResult(error=str(e), duration=time.monotonic() - t0)

    async def async_reverse_resolve(self, ip_address: str) -> AsyncResult:
        """Async reverse DNS resolution."""
        t0 = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._get_executor(),
                self.reverse_resolve, ip_address
            )
            return AsyncResult(data=result, duration=time.monotonic() - t0)
        except Exception as e:
            return AsyncResult(error=str(e), duration=time.monotonic() - t0)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    async def async_batch(self, items: list[Any],
                          handler: Callable,
                          max_concurrency: int | None = None) -> list[AsyncResult]:
        """Execute an async handler on a batch of items concurrently.

        Parameters
        ----------
        items : list
            Items to process.
        handler : callable
            Async function taking one item, returning any result.
        max_concurrency : int, optional
            Max parallel tasks. Defaults to _max_async_concurrency.

        Returns
        -------
        list[AsyncResult]
            Results in the same order as input items.
        """
        sem = asyncio.Semaphore(max_concurrency or self._max_async_concurrency)

        async def _wrapped(item: Any) -> AsyncResult:
            t0 = time.monotonic()
            async with sem:
                try:
                    data = await handler(item)
                    return AsyncResult(data=data, duration=time.monotonic() - t0)
                except Exception as e:
                    return AsyncResult(error=str(e), duration=time.monotonic() - t0)

        tasks = [asyncio.create_task(_wrapped(item)) for item in items]
        return await asyncio.gather(*tasks)

    def run_batch(self, items: list[Any],
                  handler: Callable,
                  max_concurrency: int | None = None) -> list[AsyncResult]:
        """Synchronous wrapper for async_batch."""
        return self.run_async(
            self.async_batch(items, handler, max_concurrency)
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _get_executor(self) -> ThreadPoolExecutor:
        """Lazy thread pool executor."""
        if self._async_executor is None:
            self._async_executor = ThreadPoolExecutor(
                max_workers=self._max_async_concurrency,
                thread_name_prefix=f"sf-async-{getattr(self, '__name__', 'mod')}",
            )
        return self._async_executor

    def finished(self) -> None:
        """Clean up async resources on module finish."""
        if self._async_executor:
            self._async_executor.shutdown(wait=False)
            self._async_executor = None
        super().finished()
