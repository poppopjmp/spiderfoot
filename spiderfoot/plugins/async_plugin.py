"""Async module support for SpiderFoot modern plugins.

**This is the recommended base class for all new SpiderFoot modules.**

Provides an async-capable base class that allows modules to use
async/await for I/O operations while remaining compatible with the
synchronous scan engine. Modules with synchronous ``handleEvent`` methods
work unchanged — the async dispatch is only activated when
``handleEvent`` is an ``async def``.

**v2 (Batch 43)** – HTTP and DNS now use native ``aiohttp`` / ``aiodns``
via :mod:`spiderfoot.sflib.async_network` instead of wrapping the sync
``requests``-based helpers in ``loop.run_in_executor()``.

Usage::

    from spiderfoot.plugins.async_plugin import SpiderFootAsyncPlugin

    class sfp_example_async(SpiderFootAsyncPlugin):
        async def handleEvent(self, event):
            result = await self.async_fetch_url("https://api.example.com")
            if result.ok:
                data = result.data["content"]
            ...
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, TypeVar

from .modern_plugin import SpiderFootModernPlugin


log = logging.getLogger("spiderfoot.async_plugin")

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Shared event loop – lives in a background daemon thread so sync callers
# (the scan engine's threadWorker) can submit coroutines without blocking
# the main thread.
# ---------------------------------------------------------------------------

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
    """Shutdown the shared event loop and close all aiohttp sessions."""
    global _shared_loop, _loop_thread

    if _shared_loop and not _shared_loop.is_closed():
        # Close aiohttp sessions inside the loop
        from ..sflib.async_network import close_all_sessions
        future = asyncio.run_coroutine_threadsafe(
            close_all_sessions(), _shared_loop
        )
        try:
            future.result(timeout=5)
        except Exception:
            pass

        _shared_loop.call_soon_threadsafe(_shared_loop.stop)
        if _loop_thread:
            _loop_thread.join(timeout=5)
        _shared_loop.close()

    _shared_loop = None
    _loop_thread = None


class AsyncResult:
    """Container for async operation results."""

    __slots__ = ("data", "error", "duration", "ok")

    def __init__(self, data: Any = None, error: str | None = None,
                 duration: float = 0.0) -> None:
        self.data = data
        self.error = error
        self.duration = duration
        self.ok = error is None

    def __repr__(self) -> str:
        return f"AsyncResult(ok={self.ok}, duration={self.duration:.3f}s)"


class SpiderFootAsyncPlugin(SpiderFootModernPlugin):
    """Async-capable SpiderFoot plugin base class.

    Extends :class:`SpiderFootModernPlugin` with **native** async I/O:

    - :meth:`async_fetch_url` – non-blocking HTTP via ``aiohttp``
    - :meth:`async_resolve_host` / :meth:`async_reverse_resolve` – non-blocking
      DNS via ``aiodns`` (falls back to threaded ``getaddrinfo``)
    - :meth:`async_batch` – fan-out concurrent tasks with concurrency cap
    - :meth:`run_async` – sync→async bridge for the thread-based engine
    """

    # Maximum concurrent async operations per module instance
    _max_async_concurrency = 10

    def __init__(self) -> None:
        super().__init__()
        self._semaphore: asyncio.Semaphore | None = None

    @property
    def _async_sem(self) -> asyncio.Semaphore:
        """Lazy semaphore for concurrency limiting."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_async_concurrency)
        return self._semaphore

    @property
    def _module_name(self) -> str:
        return getattr(self, "__name__", self.__class__.__name__)

    # ------------------------------------------------------------------
    # Core async bridge (sync thread → async loop)
    # ------------------------------------------------------------------

    def run_async(self, coro: Any) -> Any:
        """Run an async coroutine from synchronous context.

        Submits *coro* to the shared background event-loop and blocks
        the calling thread until it completes (up to 5 min).
        """
        loop = get_event_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=300)

    # ------------------------------------------------------------------
    # Async HTTP – native aiohttp
    # ------------------------------------------------------------------

    async def async_fetch_url(
        self,
        url: str,
        method: str = "GET",
        timeout: float = 30,
        *,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        post_data: str | bytes | dict | None = None,
        head_only: bool = False,
        size_limit: int | None = None,
        verify_ssl: bool = True,
        useragent: str = "SpiderFoot",
    ) -> AsyncResult:
        """Non-blocking HTTP fetch using ``aiohttp``.

        Returns an :class:`AsyncResult` whose ``.data`` is a dict matching
        the shape of ``network.fetchUrl`` (code, status, content, headers,
        realurl).
        """
        from ..sflib.async_network import async_fetch_url as _native_fetch

        t0 = time.monotonic()
        async with self._async_sem:
            try:
                result = await _native_fetch(
                    url,
                    method=method,
                    timeout=timeout,
                    headers=headers,
                    cookies=cookies,
                    post_data=post_data,
                    head_only=head_only,
                    size_limit=size_limit,
                    verify_ssl=verify_ssl,
                    useragent=useragent,
                    module_name=self._module_name,
                )
                duration = time.monotonic() - t0
                if result is None or result.get("code") is None:
                    return AsyncResult(
                        data=result, error="fetch returned no status",
                        duration=duration,
                    )
                return AsyncResult(data=result, duration=duration)
            except Exception as exc:
                return AsyncResult(
                    error=str(exc), duration=time.monotonic() - t0
                )

    # ------------------------------------------------------------------
    # Async DNS – native aiodns / loop.getaddrinfo fallback
    # ------------------------------------------------------------------

    async def async_resolve_host(self, hostname: str) -> AsyncResult:
        """Resolve *hostname* to IPv4 addresses (non-blocking)."""
        from ..sflib.async_network import async_resolve_host as _resolve

        t0 = time.monotonic()
        try:
            addrs = await _resolve(hostname)
            return AsyncResult(data=addrs, duration=time.monotonic() - t0)
        except Exception as exc:
            return AsyncResult(error=str(exc), duration=time.monotonic() - t0)

    async def async_resolve_host6(self, hostname: str) -> AsyncResult:
        """Resolve *hostname* to IPv6 addresses (non-blocking)."""
        from ..sflib.async_network import async_resolve_host6 as _resolve6

        t0 = time.monotonic()
        try:
            addrs = await _resolve6(hostname)
            return AsyncResult(data=addrs, duration=time.monotonic() - t0)
        except Exception as exc:
            return AsyncResult(error=str(exc), duration=time.monotonic() - t0)

    async def async_reverse_resolve(self, ip_address: str) -> AsyncResult:
        """Reverse-resolve an IP address to hostnames (non-blocking)."""
        from ..sflib.async_network import async_reverse_resolve as _rev

        t0 = time.monotonic()
        try:
            names = await _rev(ip_address)
            return AsyncResult(data=names, duration=time.monotonic() - t0)
        except Exception as exc:
            return AsyncResult(error=str(exc), duration=time.monotonic() - t0)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    async def async_batch(
        self,
        items: list[Any],
        handler: Callable,
        max_concurrency: int | None = None,
    ) -> list[AsyncResult]:
        """Execute *handler* on a list of *items* concurrently.

        Parameters
        ----------
        items : list
            Items to process.
        handler : callable
            Async function ``(item) -> Any``.
        max_concurrency : int, optional
            Cap on parallel tasks (default: ``_max_async_concurrency``).

        Returns
        -------
        list[AsyncResult]
            Results in the same order as *items*.
        """
        sem = asyncio.Semaphore(max_concurrency or self._max_async_concurrency)

        async def _wrapped(item: Any) -> AsyncResult:
            t0 = time.monotonic()
            async with sem:
                try:
                    data = await handler(item)
                    return AsyncResult(data=data, duration=time.monotonic() - t0)
                except Exception as exc:
                    return AsyncResult(error=str(exc), duration=time.monotonic() - t0)

        tasks = [asyncio.create_task(_wrapped(item)) for item in items]
        return await asyncio.gather(*tasks)

    def run_batch(
        self,
        items: list[Any],
        handler: Callable,
        max_concurrency: int | None = None,
    ) -> list[AsyncResult]:
        """Synchronous wrapper for :meth:`async_batch`."""
        return self.run_async(
            self.async_batch(items, handler, max_concurrency)
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def finished(self) -> None:
        """Clean up async resources when the module exits."""
        # Close this module's aiohttp session
        try:
            from ..sflib.async_network import close_session
            loop = get_event_loop()
            fut = asyncio.run_coroutine_threadsafe(
                close_session(self._module_name), loop
            )
            fut.result(timeout=5)
        except Exception:
            pass
        super().finished()
