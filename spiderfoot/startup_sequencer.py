"""
Service startup sequencing for SpiderFoot microservices.

In microservice mode, services must start in dependency order and
verify their upstream dependencies are healthy before accepting
traffic.  This module provides:

- ``StartupSequencer``: orchestrates ordered dependency checks
- ``DependencyProbe``: base class for probing a dependency
- Built-in probes for Postgres, Redis, NATS, API, gRPC
- Configurable retry/backoff and timeout policy
- Integration with health endpoint startup probe

Usage::

    sequencer = StartupSequencer(role="scanner")
    sequencer.add_probe(PostgresProbe(dsn))
    sequencer.add_probe(RedisProbe(url))
    sequencer.add_probe(ApiProbe("http://api:8001"))

    # Blocks until all deps are ready or timeout expires
    result = await sequencer.wait_for_ready(timeout=60)
    if not result.all_ready:
        sys.exit(1)
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("spiderfoot.startup")


# ── Probe Results ────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    """Result of a single dependency probe."""
    name: str
    ready: bool
    latency_ms: float = 0.0
    error: str | None = None
    attempts: int = 0


@dataclass
class StartupResult:
    """Aggregate result of all startup probes."""
    all_ready: bool
    probes: list[ProbeResult] = field(default_factory=list)
    total_wait_seconds: float = 0.0
    role: str = "standalone"

    def summary(self) -> str:
        ready = sum(1 for p in self.probes if p.ready)
        total = len(self.probes)
        status = "READY" if self.all_ready else "NOT READY"
        lines = [f"[{status}] {self.role}: {ready}/{total} dependencies ready "
                 f"(waited {self.total_wait_seconds:.1f}s)"]
        for p in self.probes:
            icon = "OK" if p.ready else "FAIL"
            detail = f" ({p.error})" if p.error else ""
            lines.append(f"  [{icon}] {p.name} ({p.latency_ms:.0f}ms, "
                         f"{p.attempts} attempts){detail}")
        return "\n".join(lines)


# ── Dependency Probes ────────────────────────────────────────────────

class DependencyProbe(ABC):
    """Base class for dependency health probes."""

    def __init__(self, name: str, *, required: bool = True) -> None:
        self.name = name
        self.required = required

    @abstractmethod
    async def check(self) -> bool:
        """Return True if the dependency is ready."""
        ...


class TcpProbe(DependencyProbe):
    """Probe that checks TCP connectivity to host:port."""

    def __init__(self, name: str, host: str, port: int, *,
                 required: bool = True, timeout: float = 5.0) -> None:
        super().__init__(name, required=required)
        self.host = host
        self.port = port
        self.timeout = timeout

    async def check(self) -> bool:
        loop = asyncio.get_event_loop()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            await loop.run_in_executor(
                None, sock.connect, (self.host, self.port)
            )
            sock.close()
            return True
        except (OSError, ConnectionRefusedError):
            return False


class HttpProbe(DependencyProbe):
    """Probe that checks an HTTP endpoint returns 2xx."""

    def __init__(self, name: str, url: str, *,
                 required: bool = True, timeout: float = 5.0) -> None:
        super().__init__(name, required=required)
        self.url = url
        self.timeout = timeout

    async def check(self) -> bool:
        loop = asyncio.get_event_loop()
        try:
            import urllib.request
            req = urllib.request.Request(self.url, method="GET")
            resp = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=self.timeout),
            )
            return 200 <= resp.status < 300
        except Exception:
            return False


class PostgresProbe(DependencyProbe):
    """Probe that verifies Postgres connectivity."""

    def __init__(self, dsn: str | None = None, *, required: bool = True) -> None:
        super().__init__("postgres", required=required)
        self.dsn = dsn or os.environ.get("POSTGRES_DSN", "")

    async def check(self) -> bool:
        if not self.dsn:
            return False
        loop = asyncio.get_event_loop()
        try:
            import psycopg2
            conn = await loop.run_in_executor(
                None, lambda: psycopg2.connect(self.dsn, connect_timeout=5)
            )
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            conn.close()
            return True
        except Exception:
            return False


class RedisProbe(DependencyProbe):
    """Probe that verifies Redis connectivity."""

    def __init__(self, url: str | None = None, *, required: bool = True) -> None:
        super().__init__("redis", required=required)
        self.url = url or os.environ.get("SF_REDIS_URL", "")

    async def check(self) -> bool:
        if not self.url:
            return False
        loop = asyncio.get_event_loop()
        try:
            import redis
            r = redis.Redis.from_url(self.url, socket_timeout=5)
            result = await loop.run_in_executor(None, r.ping)
            return bool(result)
        except Exception:
            return False


class NatsProbe(DependencyProbe):
    """Probe that verifies NATS connectivity."""

    def __init__(self, url: str | None = None, *, required: bool = True) -> None:
        super().__init__("nats", required=required)
        self.url = url or os.environ.get("SF_EVENTBUS_NATS_URL", "")

    async def check(self) -> bool:
        if not self.url:
            return False
        try:
            # NATS uses TCP, extract host:port
            parts = self.url.replace("nats://", "").split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 4222
            probe = TcpProbe("nats-tcp", host, port)
            return await probe.check()
        except (ValueError, IndexError, OSError):
            return False


# ── Predefined probes by service role ────────────────────────────────

def _probes_for_role(role: str) -> list[DependencyProbe]:
    """Return default probes based on service role."""
    probes: list[DependencyProbe] = []

    if role in ("api", "scanner"):
        dsn = os.environ.get("POSTGRES_DSN", "")
        if dsn:
            probes.append(PostgresProbe(dsn))
        redis_url = os.environ.get("SF_REDIS_URL", "")
        if redis_url:
            probes.append(RedisProbe(redis_url))

    if role == "scanner":
        api_url = os.environ.get("SF_DATASERVICE_API_URL", "")
        if api_url:
            probes.append(HttpProbe("data-api", f"{api_url.rstrip('/')}/../../health/live"))

    if role == "webui":
        api_url = os.environ.get("SF_WEBUI_API_URL", "")
        if api_url:
            probes.append(HttpProbe("api", f"{api_url.rstrip('/')}/../../health/live"))

    nats_url = os.environ.get("SF_EVENTBUS_NATS_URL", "")
    if nats_url:
        probes.append(NatsProbe(nats_url, required=False))

    return probes


# ── Sequencer ────────────────────────────────────────────────────────

class StartupSequencer:
    """Orchestrate ordered dependency checks with retry + backoff.

    Args:
        role: Service role (api, scanner, webui, standalone).
        auto_discover: If True, auto-add probes based on env vars.
        retry_interval: Base seconds between retries.
        max_retries: Max probe attempts per dependency.
    """

    def __init__(
        self,
        role: str = "standalone",
        *,
        auto_discover: bool = True,
        retry_interval: float = 2.0,
        max_retries: int = 30,
    ) -> None:
        self.role = role
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self._probes: list[DependencyProbe] = []

        if auto_discover:
            self._probes.extend(_probes_for_role(role))

    def add_probe(self, probe: DependencyProbe) -> StartupSequencer:
        """Add a dependency probe."""
        self._probes.append(probe)
        return self

    async def wait_for_ready(
        self,
        timeout: float = 120.0,
    ) -> StartupResult:
        """Block until all required dependencies are ready or timeout.

        Args:
            timeout: Maximum total wait time in seconds.

        Returns:
            StartupResult with per-probe diagnostics.
        """
        if not self._probes:
            log.info("No dependency probes configured for role=%s", self.role)
            return StartupResult(all_ready=True, role=self.role)

        log.info(
            "Starting dependency checks for role=%s (%d probes, timeout=%ds)",
            self.role, len(self._probes), timeout,
        )

        start = time.monotonic()
        results: dict[str, ProbeResult] = {}
        pending = set(range(len(self._probes)))

        for attempt in range(1, self.max_retries + 1):
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                break

            for idx in list(pending):
                probe = self._probes[idx]
                probe_start = time.monotonic()

                try:
                    ready = await asyncio.wait_for(
                        probe.check(), timeout=min(10, timeout - elapsed)
                    )
                except (asyncio.TimeoutError, Exception) as exc:
                    ready = False
                    error = f"{type(exc).__name__}: {exc}"
                else:
                    error = None

                latency = (time.monotonic() - probe_start) * 1000
                results[probe.name] = ProbeResult(
                    name=probe.name,
                    ready=ready,
                    latency_ms=latency,
                    error=error if not ready else None,
                    attempts=attempt,
                )

                if ready:
                    log.info("  [OK] %s ready (attempt %d, %.0fms)",
                             probe.name, attempt, latency)
                    pending.discard(idx)

            if not pending:
                break

            # Back off, but don't exceed remaining timeout
            remaining = timeout - (time.monotonic() - start)
            if remaining <= 0:
                break
            wait = min(self.retry_interval, remaining)
            await asyncio.sleep(wait)

        # Final result
        total_wait = time.monotonic() - start
        all_ready = all(
            results.get(self._probes[i].name, ProbeResult(name="?", ready=False)).ready
            or not self._probes[i].required
            for i in range(len(self._probes))
        )

        result = StartupResult(
            all_ready=all_ready,
            probes=list(results.values()),
            total_wait_seconds=total_wait,
            role=self.role,
        )
        log.info(result.summary())
        return result

    def wait_for_ready_sync(self, timeout: float = 120.0) -> StartupResult:
        """Synchronous wrapper for wait_for_ready()."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(1) as pool:
                    return pool.submit(
                        asyncio.run,
                        self.wait_for_ready(timeout),
                    ).result()
            return loop.run_until_complete(self.wait_for_ready(timeout))
        except RuntimeError:
            return asyncio.run(self.wait_for_ready(timeout))
