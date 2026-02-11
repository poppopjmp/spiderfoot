#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         plugin_test
# Purpose:      Testing framework for SpiderFoot plugins / modules.
#               Provides helpers to instantiate, configure, feed events,
#               and assert produced output without needing the full scan
#               engine.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot Plugin Testing Framework

Provides :class:`PluginTestHarness` – a drop-in test fixture that wires up
a module (legacy or modern) with mock services, feeds it events, and
captures everything it emits::

    from spiderfoot.plugins.plugin_test import PluginTestHarness

    harness = PluginTestHarness.for_module("sfp_dnsresolve")
    harness.set_options({"_internettlds": "com,net"})
    harness.feed_event("DOMAIN_NAME", "example.com")

    assert harness.produced("IP_ADDRESS")
    assert len(harness.events_of_type("IP_ADDRESS")) >= 1

For modern plugins the harness automatically injects service mocks
accessible via ``harness.http_mock``, ``harness.dns_mock``, etc.
"""

from __future__ import annotations

import importlib
import logging
import re
import types
from dataclasses import dataclass, field
from typing import Any, Callable


from collections.abc import Sequence
from unittest.mock import MagicMock, patch

log = logging.getLogger("spiderfoot.plugin_test")

__all__ = [
    "PluginTestHarness",
    "EventCapture",
    "FakeTarget",
    "FakeSpiderFoot",
    "make_root_event",
    "make_event",
]


# ------------------------------------------------------------------
# Lightweight fakes
# ------------------------------------------------------------------


class FakeTarget:
    """Minimal stand-in for SpiderFootTarget."""

    def __init__(self, value: str, target_type: str = "DOMAIN_NAME") -> None:
        """Initialize a fake target with a value and optional type."""
        self.value = value
        self.target_type = target_type
        self._aliases: list = []

    def matches(self, value: str, *, include_parents: bool = True,
                include_children: bool = True) -> bool:  # noqa: ARG002
        """Check if the given value matches this target."""
        return value == self.value

    def getAliases(self) -> list:  # noqa: N802
        """Return the list of target aliases."""
        return self._aliases

    def setAlias(self, alias: str, typeName: str) -> None:  # noqa: N802, N803
        """Add an alias to the target."""
        self._aliases.append({"value": alias, "type": typeName})

    def __str__(self) -> str:
        """Return the target value as a string."""
        return self.value


class FakeSpiderFoot:
    """Minimal mock of the SpiderFoot god-object façade (``self.sf``).

    Provides stubs for the most commonly used helper methods so legacy
    modules can be instantiated without the full SpiderFoot class.
    Anything not explicitly stubbed falls through to a ``MagicMock``.
    """

    def __init__(self, opts: dict | None = None) -> None:
        """Initialize with optional configuration options."""
        self.opts: dict[str, Any] = opts or _default_opts()
        self._mock = MagicMock()
        self._scan_id = "TEST_SCAN_001"
        self.scanId = self._scan_id  # noqa: N815

    # --- helpers frequently called by modules ---

    def hashstring(self, s: str) -> str:  # noqa: N802
        """Return SHA-256 hex digest of the given string."""
        import hashlib
        return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()

    def validIP(self, ip: str) -> bool:  # noqa: N802
        """Check if the string is a valid IP address."""
        import ipaddress as _ip
        try:
            _ip.ip_address(ip)
            return True
        except ValueError:
            return False

    def validIP6(self, ip: str) -> bool:  # noqa: N802
        """Check if the string is a valid IPv6 address."""
        import ipaddress as _ip
        try:
            return isinstance(_ip.ip_address(ip), _ip.IPv6Address)
        except ValueError:
            return False

    def isDomain(self, hostname: str, tldList: dict | None = None) -> bool:  # noqa: N802, N803
        """Check if the hostname looks like a valid domain name."""
        return bool(re.match(r"^[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}$", hostname))

    def validHost(self, hostname: str) -> bool:  # noqa: N802
        """Check if the hostname contains only valid characters."""
        return bool(re.match(r"^[a-zA-Z0-9._-]+$", hostname))

    def urlFQDN(self, url: str) -> str:  # noqa: N802
        """Extract the fully qualified domain name from a URL."""
        from urllib.parse import urlparse
        return urlparse(url).hostname or ""

    def urlBaseUrl(self, url: str) -> str:  # noqa: N802
        """Extract the base URL (scheme and netloc) from a URL."""
        from urllib.parse import urlparse
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def fetchUrl(self, url: str, *args: Any, **kwargs: Any) -> dict:  # noqa: N802
        """Delegate URL fetching to the internal mock."""
        return self._mock.fetchUrl(url, *args, **kwargs)

    def resolveHost(self, host: str) -> list:  # noqa: N802
        """Delegate host resolution to the internal mock."""
        return self._mock.resolveHost(host)

    def resolveHost6(self, host: str) -> list:  # noqa: N802
        """Delegate IPv6 host resolution to the internal mock."""
        return self._mock.resolveHost6(host)

    def resolveTargets(self) -> None:  # noqa: N802
        """No-op stub for target resolution."""
        pass

    def cacheGet(self, key: str, t: str) -> str | None:  # noqa: N802
        """Delegate cache retrieval to the internal mock."""
        return self._mock.cacheGet(key, t)

    def cachePut(self, key: str, t: str, data: str) -> None:  # noqa: N802
        """Delegate cache storage to the internal mock."""
        self._mock.cachePut(key, t, data)

    def error(self, msg: str) -> None:
        """Log an error message."""
        log.error("sf.error: %s", msg)

    def info(self, msg: str) -> None:
        """Log an informational message."""
        log.info("sf.info: %s", msg)

    def debug(self, msg: str) -> None:
        """Log a debug message."""
        log.debug("sf.debug: %s", msg)

    def status(self, msg: str) -> None:
        """Log a status message."""
        log.info("sf.status: %s", msg)

    def myPath(self) -> str:  # noqa: N802
        """Return the SpiderFoot installation directory path."""
        import os
        # Go up 3 levels: plugins/ -> spiderfoot/ -> project_root/
        return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the internal mock."""
        return getattr(self._mock, name)


# ------------------------------------------------------------------
# Event helpers
# ------------------------------------------------------------------

def _get_event_class() -> type:
    """Lazily import SpiderFootEvent."""
    try:
        from spiderfoot.events.event import SpiderFootEvent
        return SpiderFootEvent
    except ImportError:
        pass
    # Fallback
    try:
        from spiderfoot import SpiderFootEvent
        return SpiderFootEvent
    except ImportError:
        raise ImportError(
            "Cannot import SpiderFootEvent. Ensure spiderfoot is on sys.path."
        )


def make_root_event(target: str = "example.com",
                    module: str = "SpiderFoot") -> Any:
    """Create a ROOT event for *target*."""
    cls = _get_event_class()
    return cls("ROOT", target, module, None)


def make_event(event_type: str, data: str,
               module: str = "sfp_test",
               parent: Any | None = None,
               confidence: int = 100) -> Any:
    """Create a SpiderFootEvent with optional parent defaulting to ROOT."""
    cls = _get_event_class()
    if parent is None:
        parent = make_root_event()
    evt = cls(event_type, data, module, parent)
    evt.confidence = confidence
    return evt


# ------------------------------------------------------------------
# Event capture
# ------------------------------------------------------------------

@dataclass
class EventCapture:
    """Collects events emitted by a module under test."""

    events: list[Any] = field(default_factory=list)

    def __call__(self, event: Any) -> None:
        """Callable adapter – used as ``notifyListeners`` replacement."""
        self.events.append(event)

    def clear(self) -> None:
        """Remove all captured events."""
        self.events.clear()

    # --- query helpers ---

    def of_type(self, event_type: str) -> list[Any]:
        """Return captured events matching *event_type*."""
        return [e for e in self.events if e.eventType == event_type]

    def types(self) -> list[str]:
        """Return unique event types captured (preserving order)."""
        seen: dict = {}
        for e in self.events:
            seen.setdefault(e.eventType, None)
        return list(seen)

    def data_values(self, event_type: str | None = None) -> list[str]:
        """Return data payloads, optionally filtered by type."""
        source = self.of_type(event_type) if event_type else self.events
        return [e.data for e in source]

    def has(self, event_type: str) -> bool:
        """Check if any captured event matches the given type."""
        return any(e.eventType == event_type for e in self.events)

    def count(self, event_type: str | None = None) -> int:
        """Return the number of captured events, optionally filtered by type."""
        if event_type:
            return len(self.of_type(event_type))
        return len(self.events)

    def first(self, event_type: str | None = None) -> Any:
        """Return the first captured event, optionally filtered by type."""
        source = self.of_type(event_type) if event_type else self.events
        return source[0] if source else None

    def last(self, event_type: str | None = None) -> Any:
        """Return the last captured event, optionally filtered by type."""
        source = self.of_type(event_type) if event_type else self.events
        return source[-1] if source else None

    def find(self, predicate: Callable[[Any], bool]) -> list[Any]:
        """Return all captured events matching the predicate."""
        return [e for e in self.events if predicate(e)]


# ------------------------------------------------------------------
# Plugin Test Harness
# ------------------------------------------------------------------

class PluginTestHarness:
    """End-to-end test harness for a single SpiderFoot module.

    Typical usage::

        h = PluginTestHarness.for_module("sfp_shodan")
        h.set_options({"api_key": "test-key"})
        h.mock_http_response(200, '{"data": []}')
        h.feed_event("IP_ADDRESS", "1.2.3.4")
        assert h.produced("RAW_RIR_DATA")
    """

    def __init__(self, module_instance: Any, *,
                 target: str = "example.com",
                 target_type: str = "DOMAIN_NAME") -> None:
        """Initialize the test harness for a module instance.

        Args:
            module_instance: The SpiderFoot module to test.
            target: Default scan target value.
            target_type: Event type of the target.
        """
        self._module = module_instance
        self._sf = FakeSpiderFoot()
        self._capture = EventCapture()
        self._target = FakeTarget(target, target_type)
        self._root = make_root_event(target)
        self._is_modern = False

        # Service mocks for modern plugins
        self.http_mock = MagicMock()
        self.dns_mock = MagicMock()
        self.cache_mock = MagicMock()
        self.data_mock = MagicMock()
        self.event_bus_mock = MagicMock()

        self._setup_done = False

    # --- factories ---

    @classmethod
    def for_module(cls, module_name: str, *,
                   target: str = "example.com",
                   target_type: str = "DOMAIN_NAME") -> PluginTestHarness:
        """Load a module by name and return a harness wrapping it.

        *module_name* should be the Python module name, e.g. ``sfp_shodan``.
        It will be imported from the ``modules`` package.
        """
        mod_module = importlib.import_module(f"modules.{module_name}")
        # The module class lives inside as the same name
        klass = getattr(mod_module, module_name)
        instance = klass()
        harness = cls(instance, target=target, target_type=target_type)
        return harness

    @classmethod
    def for_class(cls, klass: type[Any], *,
                  target: str = "example.com",
                  target_type: str = "DOMAIN_NAME") -> PluginTestHarness:
        """Create a harness from a module class."""
        instance = klass()
        return cls(instance, target=target, target_type=target_type)

    # --- setup ---

    def setup(self, user_opts: dict | None = None) -> PluginTestHarness:
        """Wire and initialise the module."""
        opts = user_opts or {}

        # Detect modern plugin
        try:
            from spiderfoot.plugins.modern_plugin import SpiderFootModernPlugin
            self._is_modern = isinstance(self._module, SpiderFootModernPlugin)
        except ImportError:
            pass

        # Database mock so checkForStop() doesn't crash
        db_mock = MagicMock()
        db_mock.scanInstanceGet.return_value = [
            None, None, None, None, None, "RUNNING"
        ]

        self._module.setDbh(db_mock)
        self._module.__sfdb__ = db_mock
        self._module.__scanId__ = self._sf._scan_id

        # setup() with our fake SpiderFoot
        self._module.setup(self._sf, opts)
        self._module.setTarget(self._target)
        self._module.__name__ = getattr(
            self._module, "__name__",
            self._module.__class__.__name__
        )

        # Inject service mocks for modern plugins
        if self._is_modern:
            self._module._http_service = self.http_mock
            self._module._dns_service = self.dns_mock
            self._module._cache_service = self.cache_mock
            self._module._data_service = self.data_mock
            self._module._event_bus = self.event_bus_mock

        # Intercept notifyListeners to capture emitted events
        self._module.notifyListeners = self._capture

        self._setup_done = True
        return self

    def set_options(self, opts: dict) -> PluginTestHarness:
        """Set module options (calls setup if not done yet)."""
        if not self._setup_done:
            self.setup(opts)
        else:
            for k, v in opts.items():
                self._module.opts[k] = v
        return self

    def set_target(self, value: str,
                   target_type: str = "DOMAIN_NAME") -> PluginTestHarness:
        """Replace the scan target."""
        self._target = FakeTarget(value, target_type)
        self._root = make_root_event(value)
        if self._setup_done:
            self._module.setTarget(self._target)
        return self

    # --- HTTP response mocking ---

    def mock_http_response(self, status_code: int = 200,
                           content: str = "",
                           headers: dict | None = None,
                           url: str = "") -> PluginTestHarness:
        """Configure the default HTTP response for the next fetchUrl call."""
        resp = {
            "content": content,
            "code": str(status_code),
            "headers": headers or {},
            "realurl": url,
            "status": str(status_code),
        }
        self._sf._mock.fetchUrl.return_value = resp
        if self._is_modern:
            self.http_mock.fetch_url.return_value = resp
        return self

    def mock_http_sequence(self, responses: list[dict]) -> PluginTestHarness:
        """Configure a sequence of HTTP responses."""
        formatted = []
        for r in responses:
            formatted.append({
                "content": r.get("content", ""),
                "code": str(r.get("status_code", 200)),
                "headers": r.get("headers", {}),
                "realurl": r.get("url", ""),
                "status": str(r.get("status_code", 200)),
            })
        self._sf._mock.fetchUrl.side_effect = formatted
        if self._is_modern:
            self.http_mock.fetch_url.side_effect = formatted
        return self

    def mock_dns_response(self, hostname: str,
                          ips: list[str] | None = None) -> PluginTestHarness:
        """Configure DNS resolution mock."""
        ips = ips or []
        self._sf._mock.resolveHost.return_value = ips
        if self._is_modern:
            self.dns_mock.resolve_host.return_value = ips
        return self

    # --- event feeding ---

    def feed_event(self, event_type: str, data: str,
                   parent: Any | None = None,
                   confidence: int = 100) -> PluginTestHarness:
        """Feed an event into the module's handleEvent()."""
        if not self._setup_done:
            self.setup()

        if parent is None:
            parent = self._root

        evt = make_event(event_type, data,
                         module="sfp_harness",
                         parent=parent,
                         confidence=confidence)
        self._module.handleEvent(evt)
        return self

    def feed_root(self) -> PluginTestHarness:
        """Feed the ROOT event."""
        if not self._setup_done:
            self.setup()
        self._module.handleEvent(self._root)
        return self

    def feed_events(self, events: Sequence[tuple]) -> PluginTestHarness:
        """Feed multiple events as ``(type, data)`` or ``(type, data, parent)`` tuples."""
        for item in events:
            if len(item) == 2:
                self.feed_event(item[0], item[1])
            elif len(item) >= 3:
                self.feed_event(item[0], item[1], parent=item[2])
        return self

    # --- assertions / queries ---

    @property
    def captured(self) -> EventCapture:
        """Access the raw EventCapture."""
        return self._capture

    def produced(self, event_type: str) -> bool:
        """Did the module produce at least one event of *event_type*?."""
        return self._capture.has(event_type)

    def produced_count(self, event_type: str | None = None) -> int:
        """How many events of *event_type* (or total) were produced?."""
        return self._capture.count(event_type)

    def events_of_type(self, event_type: str) -> list[Any]:
        """Return all captured events of *event_type*."""
        return self._capture.of_type(event_type)

    def all_events(self) -> list[Any]:
        """Return all captured events."""
        return list(self._capture.events)

    def event_types(self) -> list[str]:
        """Unique event types produced."""
        return self._capture.types()

    def event_data(self, event_type: str | None = None) -> list[str]:
        """Return data payloads for captured events."""
        return self._capture.data_values(event_type)

    def assert_produced(self, event_type: str, msg: str = "") -> None:
        """Raise AssertionError if *event_type* was not produced."""
        if not self.produced(event_type):
            available = self._capture.types()
            raise AssertionError(
                msg or f"Expected event type '{event_type}' not produced. "
                       f"Available: {available}"
            )

    def assert_not_produced(self, event_type: str, msg: str = "") -> None:
        """Raise AssertionError if *event_type* WAS produced."""
        if self.produced(event_type):
            raise AssertionError(
                msg or f"Event type '{event_type}' was produced unexpectedly."
            )

    def assert_produced_data(self, event_type: str, data: str,
                             msg: str = "") -> None:
        """Assert a specific data value was produced for *event_type*."""
        values = self._capture.data_values(event_type)
        if data not in values:
            raise AssertionError(
                msg or f"Data '{data}' not found in '{event_type}' events. "
                       f"Got: {values}"
            )

    def assert_produced_count(self, event_type: str, expected: int,
                              msg: str = "") -> None:
        """Assert exact count of events of *event_type*."""
        actual = self._capture.count(event_type)
        if actual != expected:
            raise AssertionError(
                msg or f"Expected {expected} '{event_type}' events, got {actual}"
            )

    def assert_no_errors(self) -> None:
        """Assert the module did not enter errorState."""
        if getattr(self._module, "errorState", False):
            raise AssertionError("Module entered errorState")

    # --- cleanup ---

    def reset(self) -> PluginTestHarness:
        """Clear captured events for a fresh run."""
        self._capture.clear()
        return self

    @property
    def module(self) -> Any:
        """Direct access to the underlying module instance."""
        return self._module


# ------------------------------------------------------------------
# Default options
# ------------------------------------------------------------------

def _default_opts() -> dict:
    """Minimal set of SpiderFoot options needed for most modules."""
    return {
        "_debug": False,
        "__logging": True,
        "__outputfilter": None,
        "_useragent": "SpiderFoot/Test",
        "_dnsserver": "",
        "_fetchtimeout": 5,
        "_internettlds": "com,net,org",
        "_internettlds_cache": 72,
        "_genericusers": "admin,root",
        "_socks1type": "",
        "_socks2addr": "",
        "_socks3port": "",
        "_socks4user": "",
        "_socks5pwd": "",
        "_socks6dns": True,
        "_torctlport": 9051,
        "_modulesenabled": [],
        "__database": "sqlite:///test.db",
        "__webaddr": "127.0.0.1",
        "__webport": 5001,
        "__docroot": "",
        "__modules__": {},
        "__correlationrules__": {},
        "__scanId__": "TEST_SCAN_001",
        "_maxthreads": 3,
    }
