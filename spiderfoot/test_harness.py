"""Module test harness for SpiderFoot plugin developers.

Provides a lightweight testing framework for SpiderFoot modules that:
- Sets up module instances with minimal boilerplate
- Provides mock SpiderFoot core and target objects
- Captures produced events for assertion
- Simulates event injection
- Validates module metadata and event declarations

Usage::

    from spiderfoot.test_harness import ModuleTestHarness

    class TestMyModule(unittest.TestCase):
        def setUp(self):
            self.harness = ModuleTestHarness("sfp_mymodule")

        def test_produces_events(self):
            self.harness.inject_event("INTERNET_NAME", "example.com")
            events = self.harness.get_produced_events()
            self.assertTrue(len(events) > 0)

        def test_metadata(self):
            self.harness.assert_valid_metadata()
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

log = logging.getLogger("spiderfoot.test_harness")


class CapturedEvent:
    """Captured event produced during a test."""

    def __init__(self, event_type: str, data: str, module: str,
                 source_event: Any = None) -> None:
        self.event_type = event_type
        self.data = data
        self.module = module
        self.source_event = source_event

    def __repr__(self) -> str:
        return (f"CapturedEvent(type={self.event_type!r}, "
                f"data={self.data[:50]!r}, module={self.module!r})")


class MockSpiderFootTarget:
    """Minimal mock of SpiderFootTarget."""

    def __init__(self, target_value: str = "example.com",
                 target_type: str = "INTERNET_NAME") -> None:
        self.targetValue = target_value
        self.targetType = target_type
        self._aliases: list[dict[str, str]] = []

    def setAlias(self, value: str, type_: str) -> None:
        self._aliases.append({"value": value, "type": type_})

    def getEquivalents(self, type_: str) -> list[str]:
        return [a["value"] for a in self._aliases if a["type"] == type_]

    def matches(self, value: str, includeChildren: bool = True,
                includeParents: bool = True) -> bool:
        if value == self.targetValue:
            return True
        if includeChildren and self.targetValue in value:
            return True
        return False


class MockSpiderFootEvent:
    """Minimal mock of SpiderFootEvent."""

    def __init__(self, event_type: str, data: str, module: str,
                 source_event: MockSpiderFootEvent | None = None) -> None:
        self.eventType = event_type
        self.data = data
        self.module = module
        self.sourceEvent = source_event
        self.moduleDataSource = ""
        self.actualSource = ""
        self.confidence = 100
        self.visibility = 100
        self.risk = 0
        self.generated = 0.0

    @property
    def hash(self) -> str:
        import hashlib
        return hashlib.sha256(
            f"{self.eventType}{self.data}{self.module}".encode()
        ).hexdigest()[:16]


class MockSpiderFoot:
    """Minimal mock of SpiderFoot core for module testing."""

    def __init__(self, target: MockSpiderFootTarget | None = None) -> None:
        self.target = target or MockSpiderFootTarget()
        self.opts = {
            "_debug": False,
            "_useragent": "SpiderFoot-Test/1.0",
            "_dnsserver": "",
            "_fetchtimeout": 5,
            "_internettlds": [],
            "_internettlds_cache": {},
            "_socks1type": "",
            "_socks2addr": "",
            "_socks3port": "",
            "_socks4user": "",
            "_socks5pwd": "",
        }
        self._temp_storage: dict[str, dict] = {}
        self._cache: dict[str, Any] = {}
        self._log = logging.getLogger("test.spiderfoot")

    def debug(self, msg: str) -> None:
        self._log.debug(msg)

    def info(self, msg: str) -> None:
        self._log.info(msg)

    def error(self, msg: str) -> None:
        self._log.error(msg)

    def warning(self, msg: str) -> None:
        self._log.warning(msg)

    def tempStorage(self) -> dict:
        return {}

    def cacheGet(self, key: str, max_age: int = 0) -> str | None:
        return self._cache.get(key)

    def cachePut(self, key: str, value: str) -> None:
        self._cache[key] = value

    def hashstring(self, s: str) -> str:
        import hashlib
        return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()

    def validIP(self, ip: str) -> bool:
        import re
        return bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip))

    def validIP6(self, ip: str) -> bool:
        return ":" in ip

    def validEmail(self, email: str) -> bool:
        return "@" in email and "." in email

    def isDomain(self, hostname: str, tldList: Any = None) -> bool:
        parts = hostname.split(".")
        return len(parts) == 2

    def urlFQDN(self, url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).hostname or ""

    def fetchUrl(self, url: str, **kwargs) -> dict:
        """Mock URL fetch — returns empty result by default."""
        return {
            "content": "",
            "code": "200",
            "status": "OK",
            "headers": {},
            "realurl": url,
        }

    def resolveHost(self, host: str) -> list[str] | None:
        return None

    def resolveHost6(self, host: str) -> list[str] | None:
        return None

    def resolveIP(self, ip: str) -> list[str] | None:
        return None

    def checkForStop(self) -> bool:
        return False


class ModuleTestHarness:
    """Test harness for SpiderFoot modules.

    Provides easy setup, event injection, and event capture
    for plugin testing.
    """

    def __init__(self, module_name: str,
                 target_value: str = "example.com",
                 target_type: str = "INTERNET_NAME",
                 module_opts: dict[str, Any] | None = None) -> None:
        """Initialize the test harness.

        Args:
            module_name: Name of the module class (e.g. "sfp_dns")
            target_value: Target value for scanning
            target_type: Target type (INTERNET_NAME, IP_ADDRESS, etc.)
            module_opts: Optional module options to override
        """
        self.module_name = module_name
        self.target = MockSpiderFootTarget(target_value, target_type)
        self.sf = MockSpiderFoot(self.target)
        self._captured_events: list[CapturedEvent] = []
        self._module_instance = None
        self._module_class = None
        self._module_opts = module_opts or {}

    def _load_module_class(self) -> type:
        """Load the module class from the modules directory."""
        if self._module_class:
            return self._module_class

        # Try importing from modules package
        try:
            mod = importlib.import_module(f"modules.{self.module_name}")
            cls = getattr(mod, self.module_name)
            self._module_class = cls
            return cls
        except (ImportError, AttributeError) as e:
            raise ImportError(
                f"Cannot load module '{self.module_name}': {e}"
            ) from e

    def get_module(self) -> Any:
        """Get the initialized module instance."""
        if self._module_instance:
            return self._module_instance

        cls = self._load_module_class()
        instance = cls()

        # Merge user opts with module defaults
        opts = dict(getattr(instance, 'opts', {}))
        opts.update(self._module_opts)
        opts.update(self.sf.opts)

        instance.setup(self.sf, opts)

        # Use real SpiderFootTarget for type-checking compatibility
        try:
            from spiderfoot import SpiderFootTarget
            real_target = SpiderFootTarget(
                self.target.targetValue, self.target.targetType
            )
            instance.setTarget(real_target)
        except (ImportError, Exception):
            # Fall back to mock if SpiderFootTarget unavailable
            try:
                instance.setTarget(self.target)
            except TypeError:
                instance._currentTarget = self.target

        # Monkey-patch produceEvent to capture events
        original_produce = getattr(instance, 'produceEvent', None)

        def capture_produce(event: Any, *args, **kwargs) -> None:
            self._captured_events.append(CapturedEvent(
                event_type=event.eventType,
                data=event.data,
                module=self.module_name,
                source_event=event.sourceEvent,
            ))
            if original_produce:
                try:
                    original_produce(event, *args, **kwargs)
                except Exception:
                    pass  # Ignore storage errors in test

        instance.produceEvent = capture_produce
        self._module_instance = instance
        return instance

    def inject_event(self, event_type: str, data: str,
                     module: str = "test_module") -> None:
        """Inject an event into the module's handleEvent.

        Args:
            event_type: Event type
            data: Event data
            module: Source module name
        """
        instance = self.get_module()

        # Create a root event first
        root = MockSpiderFootEvent("ROOT", self.target.targetValue,
                                    "SpiderFoot")

        event = MockSpiderFootEvent(event_type, data, module, root)
        event.moduleDataSource = module

        instance.handleEvent(event)

    def get_produced_events(self) -> list[CapturedEvent]:
        """Get all events produced during testing."""
        return list(self._captured_events)

    def get_events_by_type(self, event_type: str) -> list[CapturedEvent]:
        """Get produced events filtered by type."""
        return [e for e in self._captured_events
                if e.event_type == event_type]

    def get_event_types(self) -> set[str]:
        """Get the set of event types produced."""
        return {e.event_type for e in self._captured_events}

    def clear_events(self) -> None:
        """Clear captured events."""
        self._captured_events.clear()

    def assert_valid_metadata(self) -> list[str]:
        """Validate module metadata structure.

        Returns list of warnings.
        """
        cls = self._load_module_class()
        warnings = []

        # Check meta dict
        meta = getattr(cls, 'meta', None)
        if meta is None:
            warnings.append("Module missing 'meta' dict")
        else:
            for key in ("name", "summary"):
                if key not in meta:
                    warnings.append(f"meta missing '{key}'")

        # Check event declarations
        instance = cls()
        watched = instance.watchedEvents()
        produced = instance.producedEvents()

        if not watched:
            warnings.append("watchedEvents() returns empty list")
        if not produced:
            warnings.append("producedEvents() returns empty list")

        # Check opts/optdescs alignment
        opts = getattr(instance, 'opts', {})
        optdescs = getattr(instance, 'optdescs', {})
        for key in opts:
            if key not in optdescs and not key.startswith("_"):
                warnings.append(f"Option '{key}' missing from optdescs")

        return warnings

    def get_module_info(self) -> dict[str, Any]:
        """Get module metadata summary."""
        cls = self._load_module_class()
        instance = cls()

        return {
            "name": self.module_name,
            "meta": getattr(cls, 'meta', {}),
            "watchedEvents": instance.watchedEvents(),
            "producedEvents": instance.producedEvents(),
            "opts": list(getattr(instance, 'opts', {}).keys()),
            "optdescs": list(getattr(instance, 'optdescs', {}).keys()),
        }

    def set_fetch_response(self, url_pattern: str,
                           content: str = "", code: str = "200",
                           headers: dict | None = None) -> None:
        """Set a mock response for URL fetching.

        Args:
            url_pattern: URL substring to match
            content: Response content
            code: HTTP status code
            headers: Response headers
        """
        original_fetch = self.sf.fetchUrl

        def mock_fetch(url: str, **kwargs) -> dict:
            if url_pattern in url:
                return {
                    "content": content,
                    "code": code,
                    "status": "OK",
                    "headers": headers or {},
                    "realurl": url,
                }
            return original_fetch(url, **kwargs)

        self.sf.fetchUrl = mock_fetch

    def reset(self) -> None:
        """Reset harness state."""
        self._captured_events.clear()
        self._module_instance = None
