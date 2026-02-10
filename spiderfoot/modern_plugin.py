#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         modern_plugin
# Purpose:      Modernized SpiderFootPlugin base class that integrates the
#               extracted service layer (HttpService, DnsService, CacheService,
#               DataService, EventBus, Metrics) via ServiceMixin.
#
#               Existing modules continue to work unchanged via self.sf.
#               New/migrated modules can use self.http, self.dns, self.cache, etc.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Modern Plugin Base

Extends SpiderFootPlugin with direct service access and metrics instrumentation.

Usage (new-style module)::

    from spiderfoot.modern_plugin import SpiderFootModernPlugin

    class sfp_example(SpiderFootModernPlugin):
        meta = { ... }

        def setup(self, sfc, userOpts=dict()):
            super().setup(sfc, userOpts)
            # self.http, self.dns, self.cache, self.event_bus now available

        def handleEvent(self, event):
            # Option A: modern service API
            result = self.fetch_url("https://api.example.com/lookup")

            # Option B: legacy (still works)
            result = self.sf.fetchUrl("https://api.example.com/lookup")

Backward Compatibility:
    - Inherits from SpiderFootPlugin, so all legacy methods work
    - self.sf is still injected by setup()
    - Services are lazily resolved from ServiceRegistry
    - If no registry is configured, gracefully falls back to self.sf
"""

from __future__ import annotations

import logging
import queue
import time
from typing import Any

from spiderfoot.plugin import SpiderFootPlugin
from spiderfoot.constants import DEFAULT_TTL_ONE_HOUR


log = logging.getLogger("spiderfoot.modern_plugin")


class SpiderFootModernPlugin(SpiderFootPlugin):
    """
    Enhanced SpiderFootPlugin with first-class service integration.

    Provides:
        - self.http → HttpService (extracted HTTP client)
        - self.dns  → DnsService (extracted DNS resolver)
        - self.cache → CacheService (extracted cache layer)
        - self.data  → DataService (extracted DB layer)
        - self.event_bus → EventBus (publish/subscribe)
        - self.emit_metric() → Prometheus metrics
    """

    # Override in subclass to disable auto-metrics
    _enable_metrics = True

    def __init__(self) -> None:
        super().__init__()
        self._registry = None
        self._http_service = None
        self._dns_service = None
        self._cache_service = None
        self._data_service = None
        self._event_bus = None
        self._metrics_imported = False
        self._log = None

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @property
    def log(self) -> logging.Logger:
        """Module-specific logger."""
        if self._log is None:
            name = getattr(self, "__name__", None) or self.__class__.__name__
            self._log = logging.getLogger(f"spiderfoot.module.{name}")
        return self._log

    # ------------------------------------------------------------------
    # Setup (called by scan engine)
    # ------------------------------------------------------------------

    def setup(self, sfc, userOpts=None) -> None:
        """Initialize the module with SpiderFoot facade and user options.

        Extends the legacy setup to also resolve services from the registry
        if available.
        """
        if userOpts is None:
            userOpts = {}

        # Set self.sf and merge user opts (legacy parent setup is a no-op)
        self.sf = sfc
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        # Try to attach to the service registry
        try:
            from spiderfoot.service_registry import get_registry
            self._registry = get_registry()
        except ImportError:
            self._registry = None

    # ------------------------------------------------------------------
    # Service accessors (lazy resolution)
    # ------------------------------------------------------------------

    @property
    def http(self) -> Any | None:
        """Access the HttpService."""
        if self._http_service is None:
            self._http_service = self._get_service("http")
        return self._http_service

    @property
    def dns(self) -> Any | None:
        """Access the DnsService."""
        if self._dns_service is None:
            self._dns_service = self._get_service("dns")
        return self._dns_service

    @property
    def cache(self) -> Any | None:
        """Access the CacheService."""
        if self._cache_service is None:
            self._cache_service = self._get_service("cache")
        return self._cache_service

    @property
    def data(self) -> Any | None:
        """Access the DataService."""
        if self._data_service is None:
            self._data_service = self._get_service("data")
        return self._data_service

    @property
    def event_bus(self) -> Any | None:
        """Access the EventBus."""
        if self._event_bus is None:
            self._event_bus = self._get_service("event_bus")
        return self._event_bus

    def _get_service(self, name: str):
        """Resolve a service from the registry, returning None if unavailable."""
        if self._registry is None:
            return None
        try:
            from spiderfoot.service_registry import (
                SERVICE_HTTP, SERVICE_DNS, SERVICE_CACHE,
                SERVICE_DATA, SERVICE_EVENT_BUS,
            )
            mapping = {
                "http": SERVICE_HTTP,
                "dns": SERVICE_DNS,
                "cache": SERVICE_CACHE,
                "data": SERVICE_DATA,
                "event_bus": SERVICE_EVENT_BUS,
            }
            svc_name = mapping.get(name)
            if svc_name and self._registry.has(svc_name):
                return self._registry.get(svc_name)
        except (KeyError, AttributeError):
            pass
        return None

    # ------------------------------------------------------------------
    # Modern convenience methods (delegate to services or fallback)
    # ------------------------------------------------------------------

    def fetch_url(self, url: str, method: str = "GET",
                  headers: dict | None = None,
                  data: Any | None = None,
                  timeout: int = 30,
                  use_cache: bool = True,
                  cache_ttl: int = DEFAULT_TTL_ONE_HOUR,
                  **kwargs) -> dict | None:
        """Fetch a URL using HttpService (or fallback to self.sf.fetchUrl).

        Accepts all legacy fetchUrl kwargs (useragent, postData, etc.)
        and passes them through automatically.

        Returns a dict with keys: content, code, headers, realurl, status
        """
        t0 = time.monotonic()
        try:
            if self.http is not None:
                result = self.http.fetch_url(
                    url, method=method, headers=headers,
                    data=data, timeout=timeout, **kwargs
                )
                self._record_http_metric(method, result.get("code", 0), t0)
                return result

            # Fallback to legacy — translate modern kwargs to legacy API
            if hasattr(self, "sf") and self.sf:
                legacy_kwargs = dict(kwargs)
                legacy_kwargs["timeout"] = timeout
                if data is not None:
                    legacy_kwargs["postData"] = data
                if method == "HEAD":
                    legacy_kwargs["headOnly"] = True
                result = self.sf.fetchUrl(url, **legacy_kwargs)
                self._record_http_metric(method, 200, t0)
                return result

        except Exception as e:
            self.log.error("fetch_url error: %s", e)
            self._record_http_metric(method, 0, t0)

        return None

    def resolve_host(self, hostname: str) -> list[str]:
        """Resolve a hostname to IPv4 addresses."""
        try:
            if self.dns is not None:
                return self.dns.resolve_host(hostname)

            if hasattr(self, "sf") and self.sf:
                return self.sf.resolveHost(hostname) or []

        except Exception as e:
            self.log.error("resolve_host error: %s", e)

        return []

    def resolve_host6(self, hostname: str) -> list[str]:
        """Resolve a hostname to IPv6 addresses."""
        try:
            if self.dns is not None:
                return self.dns.resolve_host6(hostname)

            if hasattr(self, "sf") and self.sf:
                return self.sf.resolveHost6(hostname) or []

        except Exception as e:
            self.log.error("resolve_host6 error: %s", e)

        return []

    def reverse_resolve(self, ip_address: str) -> list[str]:
        """Reverse-resolve an IP address."""
        try:
            if self.dns is not None:
                return self.dns.reverse_resolve(ip_address)

            if hasattr(self, "sf") and self.sf:
                return self.sf.resolveIP(ip_address) or []

        except Exception as e:
            self.log.error("reverse_resolve error: %s", e)

        return []

    def cache_get(self, key: str) -> Any | None:
        """Get a value from the cache."""
        try:
            if self.cache is not None:
                return self.cache.get(key)

            if hasattr(self, "sf") and self.sf:
                return self.sf.cacheGet(key, 24)

        except (KeyError, OSError) as e:
            self.log.debug("cache_get error for %s: %s", key, e)

        return None

    def cache_put(self, key: str, value: Any, ttl: int = DEFAULT_TTL_ONE_HOUR) -> bool:
        """Put a value into the cache."""
        try:
            if self.cache is not None:
                self.cache.put(key, value, ttl=ttl)
                return True

            if hasattr(self, "sf") and self.sf:
                self.sf.cachePut(key, value)
                return True

        except (TypeError, ValueError, OSError) as e:
            self.log.debug("cache_put error for %s: %s", key, e)

        return False

    def store_event(self, event) -> None:
        """Store an event to the data service."""
        try:
            if self.data is not None:
                self.data.event_store({
                    "scan_id": self.getScanId(),
                    "event_type": event.eventType,
                    "data": event.data,
                    "module": self.__name__,
                    "source_event": getattr(event, "sourceEventHash", ""),
                })
                return

            # Legacy: scan engine handles storage
        except Exception as e:
            self.log.error("store_event error: %s", e)

    def publish_event(self, topic: str, data: Any) -> None:
        """Publish an event to the event bus."""
        try:
            if self.event_bus is not None:
                self.event_bus.publish(topic, data)
        except (AttributeError, RuntimeError) as e:
            self.log.debug("publish_event error for %s: %s", topic, e)

    # ------------------------------------------------------------------
    # Enhanced event dispatch with metrics
    # ------------------------------------------------------------------

    def notifyListeners(self, sfEvent) -> None:
        """Override to add metrics instrumentation."""
        # Record event production metric
        self._record_event_produced(sfEvent.eventType)

        # Delegate to parent implementation
        super().notifyListeners(sfEvent)

    def sendEvent(self, eventType, eventData, parentEvent,
                  confidenceLevel=100) -> None:
        """Enhanced sendEvent with metrics."""
        self._record_event_produced(eventType)
        super().sendEvent(eventType, eventData, parentEvent, confidenceLevel)

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    def _record_http_metric(self, method: str, status_code: int,
                            start_time: float) -> None:
        """Record HTTP request metric."""
        if not self._enable_metrics:
            return
        try:
            from spiderfoot.metrics import HTTP_REQUESTS, HTTP_DURATION
            HTTP_REQUESTS.labels(
                method=method, status_code=str(status_code)
            ).inc()
            HTTP_DURATION.observe(time.monotonic() - start_time)
        except ImportError:
            pass

    def _record_event_produced(self, event_type: str) -> None:
        """Record event production metric."""
        if not self._enable_metrics:
            return
        try:
            from spiderfoot.metrics import EVENTS_PRODUCED
            EVENTS_PRODUCED.labels(event_type=event_type).inc()
        except ImportError:
            pass

    def _record_module_duration(self, duration: float) -> None:
        """Record module handleEvent duration."""
        if not self._enable_metrics:
            return
        try:
            from spiderfoot.metrics import MODULE_DURATION, EVENTS_PROCESSED
            MODULE_DURATION.observe(duration)
            EVENTS_PROCESSED.labels(module=self.__name__).inc()
        except ImportError:
            pass

    def _record_module_error(self, error_type: str) -> None:
        """Record module error metric."""
        if not self._enable_metrics:
            return
        try:
            from spiderfoot.metrics import MODULE_ERRORS
            MODULE_ERRORS.labels(
                module=self.__name__, error_type=error_type
            ).inc()
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Instrumented handleEvent wrapper
    # ------------------------------------------------------------------

    def threadWorker(self) -> None:
        """Override threadWorker to instrument handleEvent with metrics.

        This wraps each handleEvent call with timing and error tracking.
        """
        if not self._enable_metrics:
            super().threadWorker()
            return

        while True:
            if self.checkForStop():
                break

            try:
                sfEvent = self.incomingEventQueue.get(timeout=1)
            except queue.Empty:
                continue

            if sfEvent is None:
                # Poison pill
                break

            self._currentEvent = sfEvent

            try:
                t0 = time.monotonic()
                self.handleEvent(sfEvent)
                self._record_module_duration(time.monotonic() - t0)
            except Exception as e:
                self.log.error("Module %s failed: %s", self.__name__, e)
                self._record_module_error(type(e).__name__)
                self.errorState = True

            self.incomingEventQueue.task_done()

    # ------------------------------------------------------------------
    # Module info
    # ------------------------------------------------------------------

    def asdict(self) -> dict:
        """Enhanced module serialization with service status."""
        d = super().asdict()
        d["modern_plugin"] = True
        d["services"] = {
            "http": self.http is not None,
            "dns": self.dns is not None,
            "cache": self.cache is not None,
            "data": self.data is not None,
            "event_bus": self.event_bus is not None,
        }
        return d
