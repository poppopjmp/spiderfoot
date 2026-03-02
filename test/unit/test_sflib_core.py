"""Unit tests for spiderfoot.sflib.core — the SpiderFoot god object.

Covers: initialization, SSL context isolation, property accessors,
option value resolution, module query helpers, URL helpers, and
loadModules().  Network-dependent methods are tested via mocking.
"""
from __future__ import annotations

import os
import ssl
import unittest
from unittest.mock import patch, MagicMock


class TestSpiderFootInit(unittest.TestCase):
    """Test SpiderFoot construction and basic attributes."""

    def _make(self, opts=None):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot(opts or {})

    def test_init_with_empty_dict(self):
        sf = self._make()
        self.assertIsInstance(sf.opts, dict)

    def test_init_rejects_non_dict(self):
        from spiderfoot.sflib.core import SpiderFoot
        with self.assertRaises(TypeError):
            SpiderFoot("not a dict")

    def test_init_deep_copies_options(self):
        """Options dict is deep-copied so mutations don't leak."""
        orig = {"key": "value", "nested": {"a": 1}}
        sf = self._make(orig)
        sf.opts["key"] = "changed"
        self.assertEqual(orig["key"], "value")


class TestSSLContextIsolation(unittest.TestCase):
    """Verify the scan vs. internal SSL context separation (Cycle 41)."""

    def _make(self):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({})

    def test_scan_ssl_context_is_unverified(self):
        sf = self._make()
        self.assertEqual(sf._scan_ssl_context.verify_mode, ssl.CERT_NONE)
        self.assertFalse(sf._scan_ssl_context.check_hostname)

    def test_internal_ssl_context_is_verified(self):
        sf = self._make()
        self.assertEqual(sf._internal_ssl_context.verify_mode, ssl.CERT_REQUIRED)

    def test_compat_alias_points_to_scan_context(self):
        sf = self._make()
        self.assertIs(sf._ssl_context, sf._scan_ssl_context)


class TestPropertyAccessors(unittest.TestCase):
    """Test dbh, scanId, socksProxy properties."""

    def _make(self):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({})

    def test_scanId_roundtrip(self):
        sf = self._make()
        sf.scanId = "SCAN-001"
        self.assertEqual(sf.scanId, "SCAN-001")

    def test_dbh_default_is_none(self):
        sf = self._make()
        self.assertIsNone(sf.dbh)

    def test_socksProxy_roundtrip(self):
        sf = self._make()
        sf.socksProxy = "socks5://127.0.0.1:9050"
        self.assertEqual(sf.socksProxy, "socks5://127.0.0.1:9050")


class TestOptValueToData(unittest.TestCase):
    """Test the option value resolver (literal / @file / http)."""

    def _make(self):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({"__logging": False})

    def test_plain_string_returns_as_is(self):
        sf = self._make()
        self.assertEqual(sf.optValueToData("hello"), "hello")

    def test_non_string_returns_none(self):
        sf = self._make()
        self.assertIsNone(sf.optValueToData(42))

    def test_file_reference(self):
        """@path should read the file contents."""
        import tempfile
        sf = self._make()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("file contents")
            f.flush()
            path = f.name
        try:
            result = sf.optValueToData(f"@{path}")
            self.assertEqual(result, "file contents")
        finally:
            os.unlink(path)

    def test_missing_file_returns_none(self):
        sf = self._make()
        result = sf.optValueToData("@/nonexistent/path/xyz.txt")
        self.assertIsNone(result)


class TestModulesProducingConsuming(unittest.TestCase):
    """Test module query helpers with pre-loaded module registry."""

    MODULES = {
        "sfp_dns": {
            "provides": ["IP_ADDRESS", "IPV6_ADDRESS"],
            "consumes": ["DOMAIN_NAME", "INTERNET_NAME"],
        },
        "sfp_whois": {
            "provides": ["DOMAIN_WHOIS", "DOMAIN_REGISTRAR"],
            "consumes": ["DOMAIN_NAME"],
        },
        "sfp_ssl": {
            "provides": ["SSL_CERTIFICATE_RAW"],
            "consumes": ["INTERNET_NAME", "IP_ADDRESS"],
        },
    }

    def _make(self):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({"__modules__": self.MODULES})

    def test_modulesProducing_found(self):
        sf = self._make()
        result = sf.modulesProducing(["IP_ADDRESS"])
        self.assertIn("sfp_dns", result)
        self.assertNotIn("sfp_whois", result)

    def test_modulesProducing_wildcard(self):
        sf = self._make()
        result = sf.modulesProducing(["*"])
        self.assertEqual(sorted(result), sorted(list(self.MODULES.keys())))

    def test_modulesProducing_empty_input(self):
        sf = self._make()
        self.assertEqual(sf.modulesProducing([]), [])

    def test_modulesProducing_no_modules_loaded(self):
        from spiderfoot.sflib.core import SpiderFoot
        sf = SpiderFoot({})
        self.assertEqual(sf.modulesProducing(["IP_ADDRESS"]), [])

    def test_modulesConsuming_found(self):
        sf = self._make()
        result = sf.modulesConsuming(["DOMAIN_NAME"])
        self.assertIn("sfp_dns", result)
        self.assertIn("sfp_whois", result)
        self.assertNotIn("sfp_ssl", result)

    def test_modulesConsuming_empty(self):
        sf = self._make()
        self.assertEqual(sf.modulesConsuming([]), [])

    def test_eventsFromModules(self):
        sf = self._make()
        result = sf.eventsFromModules(["sfp_dns"])
        self.assertIn("IP_ADDRESS", result)
        self.assertIn("IPV6_ADDRESS", result)

    def test_eventsFromModules_empty(self):
        sf = self._make()
        self.assertEqual(sf.eventsFromModules([]), [])

    def test_eventsToModules(self):
        sf = self._make()
        result = sf.eventsToModules(["sfp_ssl"])
        self.assertIn("INTERNET_NAME", result)
        self.assertIn("IP_ADDRESS", result)


class TestUrlFQDN(unittest.TestCase):
    """Test URL → FQDN extraction."""

    def _make(self):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({"__logging": False})

    def test_http_url(self):
        sf = self._make()
        self.assertEqual(sf.urlFQDN("http://example.com/path"), "example.com")

    def test_https_url(self):
        sf = self._make()
        self.assertEqual(sf.urlFQDN("https://sub.example.com/a/b"), "sub.example.com")

    def test_empty_returns_none(self):
        sf = self._make()
        self.assertIsNone(sf.urlFQDN(""))


class TestHelperDelegation(unittest.TestCase):
    """Verify that thin wrapper methods delegate correctly."""

    def _make(self):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({})

    def test_validIP_valid(self):
        sf = self._make()
        self.assertTrue(sf.validIP("192.168.1.1"))

    def test_validIP_invalid(self):
        sf = self._make()
        self.assertFalse(sf.validIP("not-an-ip"))

    def test_validIP6_valid(self):
        sf = self._make()
        self.assertTrue(sf.validIP6("::1"))

    def test_validIP6_invalid(self):
        sf = self._make()
        self.assertFalse(sf.validIP6("192.168.1.1"))

    def test_validIpNetwork_valid(self):
        sf = self._make()
        self.assertTrue(sf.validIpNetwork("10.0.0.0/8"))

    def test_validIpNetwork_invalid(self):
        sf = self._make()
        self.assertFalse(sf.validIpNetwork("not-cidr"))

    def test_hashstring(self):
        sf = self._make()
        h = sf.hashstring("test")
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)  # SHA-256 hex digest

    def test_removeUrlCreds(self):
        sf = self._make()
        result = sf.removeUrlCreds("https://example.com/path?key=SECRET")
        self.assertNotIn("SECRET", result)
        self.assertIn("key=XXX", result)


class TestLoadModules(unittest.TestCase):
    """Test loadModules() discovers and registers modules."""

    def _make(self):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({"__modules__": {}, "__logging": False, "_debug": False})

    def test_loadModules_populates_registry(self):
        """loadModules() should find sfp_*.py files and register them."""
        sf = self._make()
        sf.loadModules()
        modules = sf.opts.get("__modules__", {})
        self.assertGreater(len(modules), 0, "No modules loaded")

    def test_loaded_modules_have_provides(self):
        """Each loaded module should declare 'provides' (producedEvents)."""
        sf = self._make()
        sf.loadModules()
        for name, info in sf.opts["__modules__"].items():
            self.assertIn("provides", info, f"{name} missing 'provides'")

    def test_loaded_modules_have_consumes(self):
        """Each loaded module should declare 'consumes' (watchedEvents)."""
        sf = self._make()
        sf.loadModules()
        for name, info in sf.opts["__modules__"].items():
            self.assertIn("consumes", info, f"{name} missing 'consumes'")

    def test_loaded_modules_have_meta(self):
        """Each loaded module should have a 'meta' dict with 'name'."""
        sf = self._make()
        sf.loadModules()
        for name, info in sf.opts["__modules__"].items():
            self.assertIn("meta", info, f"{name} missing 'meta'")
            meta = info["meta"]
            self.assertIn("name", meta, f"{name} meta missing 'name'")

    def test_modulesProducing_after_load(self):
        """After loadModules(), modulesProducing should return results."""
        sf = self._make()
        sf.loadModules()
        # IP_ADDRESS is one of the most common event types
        result = sf.modulesProducing(["IP_ADDRESS"])
        self.assertGreater(len(result), 0, "No modules produce IP_ADDRESS")


class TestLogging(unittest.TestCase):
    """Test logging helper methods."""

    def _make(self, logging_on=True, debug_on=False):
        from spiderfoot.sflib.core import SpiderFoot
        return SpiderFoot({"__logging": logging_on, "_debug": debug_on})

    def test_error_suppressed_when_logging_off(self):
        sf = self._make(logging_on=False)
        # Should not raise
        sf.error("test error")

    def test_debug_suppressed_when_debug_off(self):
        sf = self._make(logging_on=True, debug_on=False)
        # Should not raise
        sf.debug("test debug")

    def test_debug_enabled(self):
        sf = self._make(logging_on=True, debug_on=True)
        with patch.object(sf.log, 'debug') as mock_debug:
            sf.debug("test message")
            mock_debug.assert_called_once()


if __name__ == "__main__":
    unittest.main()
