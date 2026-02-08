"""Tests for spiderfoot.test_harness."""

import unittest

from spiderfoot.test_harness import (
    CapturedEvent,
    MockSpiderFoot,
    MockSpiderFootEvent,
    MockSpiderFootTarget,
    ModuleTestHarness,
)


class TestCapturedEvent(unittest.TestCase):
    """Tests for CapturedEvent."""

    def test_creation(self):
        e = CapturedEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.assertEqual(e.event_type, "IP_ADDRESS")
        self.assertEqual(e.data, "1.2.3.4")
        self.assertEqual(e.module, "sfp_dns")

    def test_repr(self):
        e = CapturedEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        r = repr(e)
        self.assertIn("IP_ADDRESS", r)
        self.assertIn("1.2.3.4", r)


class TestMockSpiderFootTarget(unittest.TestCase):
    """Tests for MockSpiderFootTarget."""

    def test_creation(self):
        t = MockSpiderFootTarget("example.com", "INTERNET_NAME")
        self.assertEqual(t.targetValue, "example.com")
        self.assertEqual(t.targetType, "INTERNET_NAME")

    def test_matches_exact(self):
        t = MockSpiderFootTarget("example.com")
        self.assertTrue(t.matches("example.com"))

    def test_matches_child(self):
        t = MockSpiderFootTarget("example.com")
        self.assertTrue(t.matches("sub.example.com"))

    def test_no_match(self):
        t = MockSpiderFootTarget("example.com")
        self.assertFalse(t.matches("other.com", includeChildren=False))

    def test_aliases(self):
        t = MockSpiderFootTarget("example.com")
        t.setAlias("www.example.com", "INTERNET_NAME")
        aliases = t.getEquivalents("INTERNET_NAME")
        self.assertIn("www.example.com", aliases)


class TestMockSpiderFootEvent(unittest.TestCase):
    """Tests for MockSpiderFootEvent."""

    def test_creation(self):
        e = MockSpiderFootEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        self.assertEqual(e.eventType, "IP_ADDRESS")
        self.assertEqual(e.data, "1.2.3.4")
        self.assertEqual(e.module, "sfp_dns")

    def test_hash(self):
        e = MockSpiderFootEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns")
        h = e.hash
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 16)

    def test_source_event(self):
        root = MockSpiderFootEvent("ROOT", "example.com", "SpiderFoot")
        child = MockSpiderFootEvent("IP_ADDRESS", "1.2.3.4", "sfp_dns", root)
        self.assertIs(child.sourceEvent, root)


class TestMockSpiderFoot(unittest.TestCase):
    """Tests for MockSpiderFoot."""

    def test_creation(self):
        sf = MockSpiderFoot()
        self.assertIsNotNone(sf.target)
        self.assertIn("_useragent", sf.opts)

    def test_valid_ip(self):
        sf = MockSpiderFoot()
        self.assertTrue(sf.validIP("192.168.1.1"))
        self.assertFalse(sf.validIP("not-an-ip"))

    def test_valid_email(self):
        sf = MockSpiderFoot()
        self.assertTrue(sf.validEmail("test@example.com"))
        self.assertFalse(sf.validEmail("not-email"))

    def test_is_domain(self):
        sf = MockSpiderFoot()
        self.assertTrue(sf.isDomain("example.com"))
        self.assertFalse(sf.isDomain("sub.example.com"))

    def test_url_fqdn(self):
        sf = MockSpiderFoot()
        self.assertEqual(sf.urlFQDN("https://example.com/path"), "example.com")

    def test_hashstring(self):
        sf = MockSpiderFoot()
        h = sf.hashstring("test")
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)

    def test_cache(self):
        sf = MockSpiderFoot()
        sf.cachePut("key1", "value1")
        self.assertEqual(sf.cacheGet("key1"), "value1")
        self.assertIsNone(sf.cacheGet("nonexistent"))

    def test_temp_storage(self):
        sf = MockSpiderFoot()
        s = sf.tempStorage()
        self.assertIsInstance(s, dict)

    def test_fetch_url(self):
        sf = MockSpiderFoot()
        result = sf.fetchUrl("https://example.com")
        self.assertEqual(result["code"], "200")

    def test_check_for_stop(self):
        sf = MockSpiderFoot()
        self.assertFalse(sf.checkForStop())

    def test_logging(self):
        sf = MockSpiderFoot()
        # Should not raise
        sf.debug("test debug")
        sf.info("test info")
        sf.error("test error")
        sf.warning("test warning")


class TestModuleTestHarnessBasic(unittest.TestCase):
    """Basic tests for ModuleTestHarness (without loading real modules)."""

    def test_creation(self):
        h = ModuleTestHarness("sfp_example")
        self.assertEqual(h.module_name, "sfp_example")
        self.assertIsNotNone(h.target)
        self.assertIsNotNone(h.sf)

    def test_captured_events_empty(self):
        h = ModuleTestHarness("sfp_example")
        self.assertEqual(h.get_produced_events(), [])

    def test_clear_events(self):
        h = ModuleTestHarness("sfp_example")
        h._captured_events.append(
            CapturedEvent("IP_ADDRESS", "1.2.3.4", "test")
        )
        h.clear_events()
        self.assertEqual(len(h.get_produced_events()), 0)

    def test_get_events_by_type(self):
        h = ModuleTestHarness("sfp_example")
        h._captured_events.append(
            CapturedEvent("IP_ADDRESS", "1.2.3.4", "test")
        )
        h._captured_events.append(
            CapturedEvent("INTERNET_NAME", "example.com", "test")
        )
        ips = h.get_events_by_type("IP_ADDRESS")
        self.assertEqual(len(ips), 1)
        self.assertEqual(ips[0].data, "1.2.3.4")

    def test_get_event_types(self):
        h = ModuleTestHarness("sfp_example")
        h._captured_events.append(
            CapturedEvent("IP_ADDRESS", "1.2.3.4", "test")
        )
        h._captured_events.append(
            CapturedEvent("INTERNET_NAME", "example.com", "test")
        )
        types = h.get_event_types()
        self.assertEqual(types, {"IP_ADDRESS", "INTERNET_NAME"})

    def test_set_fetch_response(self):
        h = ModuleTestHarness("sfp_example")
        h.set_fetch_response("example.com", content="hello", code="200")
        result = h.sf.fetchUrl("https://example.com/api")
        self.assertEqual(result["content"], "hello")
        # Non-matching URL returns default
        result2 = h.sf.fetchUrl("https://other.com")
        self.assertEqual(result2["content"], "")

    def test_reset(self):
        h = ModuleTestHarness("sfp_example")
        h._captured_events.append(
            CapturedEvent("IP_ADDRESS", "1.2.3.4", "test")
        )
        h.reset()
        self.assertEqual(len(h.get_produced_events()), 0)
        self.assertIsNone(h._module_instance)


class TestModuleTestHarnessRealModule(unittest.TestCase):
    """Tests using a real module (sfp_dnsresolve)."""

    def test_load_module(self):
        h = ModuleTestHarness("sfp_dnsresolve")
        mod = h.get_module()
        self.assertIsNotNone(mod)

    def test_module_info(self):
        h = ModuleTestHarness("sfp_dnsresolve")
        info = h.get_module_info()
        self.assertEqual(info["name"], "sfp_dnsresolve")
        self.assertIn("watchedEvents", info)
        self.assertIn("producedEvents", info)
        self.assertTrue(len(info["watchedEvents"]) > 0)
        self.assertTrue(len(info["producedEvents"]) > 0)

    def test_validate_metadata(self):
        h = ModuleTestHarness("sfp_dnsresolve")
        warnings = h.assert_valid_metadata()
        # sfp_dnsresolve should have valid metadata
        self.assertEqual(warnings, [])

    def test_load_nonexistent_module(self):
        h = ModuleTestHarness("sfp_nonexistent_xyz_123")
        with self.assertRaises(ImportError):
            h.get_module()


if __name__ == "__main__":
    unittest.main()
