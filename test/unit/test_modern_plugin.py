"""
Tests for the ModernPlugin base class.
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from spiderfoot.modern_plugin import SpiderFootModernPlugin


class FakeModule(SpiderFootModernPlugin):
    """A concrete module for testing."""

    meta = {
        "name": "Test Module",
        "summary": "Test",
        "flags": [],
        "useCases": [],
        "categories": ["Test"],
    }

    opts = {"test_opt": "default"}
    optdescs = {"test_opt": "A test option"}

    def __init__(self):
        super().__init__()
        self.__name__ = "sfp_test"

    def watchedEvents(self):
        return ["IP_ADDRESS"]

    def producedEvents(self):
        return ["RAW_RIR_DATA"]

    def handleEvent(self, event):
        pass


class TestModernPluginInit(unittest.TestCase):
    """Test initialization and setup."""

    def test_inheritance(self):
        from spiderfoot.plugin import SpiderFootPlugin
        mod = FakeModule()
        self.assertIsInstance(mod, SpiderFootPlugin)
        self.assertIsInstance(mod, SpiderFootModernPlugin)

    def test_no_registry(self):
        mod = FakeModule()
        self.assertIsNone(mod._registry)
        self.assertIsNone(mod.http)
        self.assertIsNone(mod.dns)
        self.assertIsNone(mod.cache)
        self.assertIsNone(mod.data)
        self.assertIsNone(mod.event_bus)


class TestModernPluginSetup(unittest.TestCase):
    """Test setup with mocked SpiderFoot facade."""

    def test_setup_stores_sf(self):
        mod = FakeModule()
        mock_sf = MagicMock()
        mod.setup(mock_sf, {"test_opt": "custom"})
        self.assertEqual(mod.sf, mock_sf)
        self.assertEqual(mod.opts["test_opt"], "custom")


class TestModernPluginFetchUrl(unittest.TestCase):
    """Test fetch_url method."""

    def test_fallback_to_sf(self):
        mod = FakeModule()
        mod._enable_metrics = False
        mock_sf = MagicMock()
        mock_sf.fetchUrl.return_value = {"content": "ok", "code": 200}
        mod.sf = mock_sf

        result = mod.fetch_url("https://example.com")
        self.assertIsNotNone(result)
        mock_sf.fetchUrl.assert_called_once()

    def test_uses_http_service(self):
        mod = FakeModule()
        mod._enable_metrics = False
        mock_http = MagicMock()
        mock_http.fetch_url.return_value = {"content": "data", "code": 200}
        mod._http_service = mock_http

        result = mod.fetch_url("https://api.example.com")
        self.assertEqual(result["content"], "data")
        mock_http.fetch_url.assert_called_once()


class TestModernPluginDns(unittest.TestCase):
    """Test DNS methods."""

    def test_resolve_host_fallback(self):
        mod = FakeModule()
        mock_sf = MagicMock()
        mock_sf.resolveHost.return_value = ["1.2.3.4"]
        mod.sf = mock_sf

        result = mod.resolve_host("example.com")
        self.assertEqual(result, ["1.2.3.4"])

    def test_resolve_host_service(self):
        mod = FakeModule()
        mock_dns = MagicMock()
        mock_dns.resolve_host.return_value = ["5.6.7.8"]
        mod._dns_service = mock_dns

        result = mod.resolve_host("example.com")
        self.assertEqual(result, ["5.6.7.8"])


class TestModernPluginCache(unittest.TestCase):
    """Test cache methods."""

    def test_cache_get_put_fallback(self):
        mod = FakeModule()
        mock_sf = MagicMock()
        mock_sf.cacheGet.return_value = "cached_value"
        mod.sf = mock_sf

        val = mod.cache_get("key1")
        self.assertEqual(val, "cached_value")

        mod.cache_put("key2", "value2")
        mock_sf.cachePut.assert_called_with("key2", "value2")


class TestModernPluginAsDict(unittest.TestCase):
    """Test enhanced asdict."""

    def test_includes_modern_flag(self):
        mod = FakeModule()
        d = mod.asdict()
        self.assertTrue(d.get("modern_plugin"))
        self.assertIn("services", d)
        self.assertFalse(d["services"]["http"])


if __name__ == "__main__":
    unittest.main()
