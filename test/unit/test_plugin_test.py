"""Tests for spiderfoot.plugin_test (Plugin Testing Framework)."""

import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.plugin_test import (
    EventCapture,
    FakeSpiderFoot,
    FakeTarget,
    PluginTestHarness,
    make_event,
    make_root_event,
    _default_opts,
)


class TestFakeTarget(unittest.TestCase):
    """Tests for FakeTarget."""

    def test_basic_attributes(self):
        t = FakeTarget("example.com", "DOMAIN_NAME")
        self.assertEqual(t.value, "example.com")
        self.assertEqual(t.target_type, "DOMAIN_NAME")
        self.assertEqual(str(t), "example.com")

    def test_matches_exact(self):
        t = FakeTarget("example.com")
        self.assertTrue(t.matches("example.com"))
        self.assertFalse(t.matches("other.com"))

    def test_aliases(self):
        t = FakeTarget("example.com")
        self.assertEqual(t.getAliases(), [])
        t.setAlias("www.example.com", "DOMAIN_NAME")
        aliases = t.getAliases()
        self.assertEqual(len(aliases), 1)
        self.assertEqual(aliases[0]["value"], "www.example.com")


class TestFakeSpiderFoot(unittest.TestCase):
    """Tests for FakeSpiderFoot."""

    def setUp(self):
        self.sf = FakeSpiderFoot()

    def test_opts_default(self):
        self.assertIn("_useragent", self.sf.opts)
        self.assertIn("_fetchtimeout", self.sf.opts)

    def test_hashstring(self):
        h = self.sf.hashstring("hello")
        self.assertEqual(len(h), 64)  # SHA-256 hex

    def test_validIP(self):
        self.assertTrue(self.sf.validIP("1.2.3.4"))
        self.assertFalse(self.sf.validIP("not-an-ip"))

    def test_validIP6(self):
        self.assertTrue(self.sf.validIP6("::1"))
        self.assertFalse(self.sf.validIP6("1.2.3.4"))

    def test_isDomain(self):
        self.assertTrue(self.sf.isDomain("example.com"))
        self.assertFalse(self.sf.isDomain(""))

    def test_urlFQDN(self):
        self.assertEqual(self.sf.urlFQDN("https://example.com/path"), "example.com")

    def test_fetchUrl_delegates_to_mock(self):
        self.sf._mock.fetchUrl.return_value = {"content": "ok"}
        result = self.sf.fetchUrl("https://example.com")
        self.assertEqual(result["content"], "ok")

    def test_passthrough_to_mock(self):
        # Accessing any unknown attr returns the mock's attr
        self.sf.someRandomMethod("arg")
        self.sf._mock.someRandomMethod.assert_called_once_with("arg")


class TestEventHelpers(unittest.TestCase):
    """Tests for make_root_event and make_event."""

    def test_make_root_event(self):
        root = make_root_event("example.com")
        self.assertEqual(root.eventType, "ROOT")
        self.assertEqual(root.data, "example.com")

    def test_make_root_event_custom_module(self):
        root = make_root_event("test.com", module="TestModule")
        self.assertEqual(root.module, "TestModule")

    def test_make_event_with_parent(self):
        root = make_root_event()
        evt = make_event("IP_ADDRESS", "1.2.3.4", parent=root)
        self.assertEqual(evt.eventType, "IP_ADDRESS")
        self.assertEqual(evt.data, "1.2.3.4")
        self.assertEqual(evt.module, "sfp_test")

    def test_make_event_auto_root(self):
        evt = make_event("DOMAIN_NAME", "example.com")
        self.assertIsNotNone(evt)
        self.assertEqual(evt.eventType, "DOMAIN_NAME")

    def test_make_event_confidence(self):
        evt = make_event("IP_ADDRESS", "1.2.3.4", confidence=75)
        self.assertEqual(evt.confidence, 75)


class TestEventCapture(unittest.TestCase):
    """Tests for EventCapture."""

    def _mock_event(self, event_type: str, data: str):
        e = MagicMock()
        e.eventType = event_type
        e.data = data
        return e

    def test_capture_events(self):
        cap = EventCapture()
        cap(self._mock_event("IP_ADDRESS", "1.2.3.4"))
        cap(self._mock_event("DOMAIN_NAME", "example.com"))
        self.assertEqual(cap.count(), 2)

    def test_of_type(self):
        cap = EventCapture()
        cap(self._mock_event("IP_ADDRESS", "1.2.3.4"))
        cap(self._mock_event("DOMAIN_NAME", "example.com"))
        cap(self._mock_event("IP_ADDRESS", "5.6.7.8"))
        ips = cap.of_type("IP_ADDRESS")
        self.assertEqual(len(ips), 2)

    def test_types(self):
        cap = EventCapture()
        cap(self._mock_event("A", "1"))
        cap(self._mock_event("B", "2"))
        cap(self._mock_event("A", "3"))
        self.assertEqual(cap.types(), ["A", "B"])

    def test_data_values(self):
        cap = EventCapture()
        cap(self._mock_event("IP_ADDRESS", "1.2.3.4"))
        cap(self._mock_event("IP_ADDRESS", "5.6.7.8"))
        values = cap.data_values("IP_ADDRESS")
        self.assertEqual(values, ["1.2.3.4", "5.6.7.8"])

    def test_has(self):
        cap = EventCapture()
        cap(self._mock_event("IP_ADDRESS", "1.2.3.4"))
        self.assertTrue(cap.has("IP_ADDRESS"))
        self.assertFalse(cap.has("DOMAIN_NAME"))

    def test_count_filtered(self):
        cap = EventCapture()
        cap(self._mock_event("A", "1"))
        cap(self._mock_event("B", "2"))
        self.assertEqual(cap.count("A"), 1)
        self.assertEqual(cap.count(), 2)

    def test_first_last(self):
        cap = EventCapture()
        e1 = self._mock_event("A", "first")
        e2 = self._mock_event("A", "last")
        cap(e1)
        cap(e2)
        self.assertEqual(cap.first("A").data, "first")
        self.assertEqual(cap.last("A").data, "last")

    def test_first_last_empty(self):
        cap = EventCapture()
        self.assertIsNone(cap.first())
        self.assertIsNone(cap.last())

    def test_find(self):
        cap = EventCapture()
        cap(self._mock_event("IP_ADDRESS", "1.2.3.4"))
        cap(self._mock_event("IP_ADDRESS", "10.0.0.1"))
        results = cap.find(lambda e: e.data.startswith("10."))
        self.assertEqual(len(results), 1)

    def test_clear(self):
        cap = EventCapture()
        cap(self._mock_event("A", "1"))
        cap.clear()
        self.assertEqual(cap.count(), 0)


class TestPluginTestHarness(unittest.TestCase):
    """Tests for PluginTestHarness using a mock module."""

    def _make_module(self):
        """Create a minimal mock module that behaves like SpiderFootPlugin."""
        mod = MagicMock()
        mod.errorState = False
        mod.opts = {}
        mod.__name__ = "sfp_mock"
        mod.__scanId__ = None
        mod.__sfdb__ = None
        mod.tempStorage.return_value = {}
        mod.results = {}

        # handleEvent produces events when called
        def handle_event(event):
            if hasattr(mod, "_test_produce"):
                for et, data in mod._test_produce:
                    evt = MagicMock()
                    evt.eventType = et
                    evt.data = data
                    mod.notifyListeners(evt)

        mod.handleEvent.side_effect = handle_event
        return mod

    def test_basic_harness(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.setup()
        self.assertTrue(h._setup_done)

    def test_mock_http_response(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.setup()
        h.mock_http_response(200, '{"test": true}')
        resp = h._sf.fetchUrl("https://example.com")
        self.assertEqual(resp["content"], '{"test": true}')
        self.assertEqual(resp["code"], "200")

    def test_mock_dns_response(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.setup()
        h.mock_dns_response("example.com", ["1.2.3.4"])
        result = h._sf.resolveHost("example.com")
        self.assertEqual(result, ["1.2.3.4"])

    def test_feed_event_and_capture(self):
        mod = self._make_module()
        mod._test_produce = [("GEOINFO", "US")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("IP_ADDRESS", "1.2.3.4")
        self.assertTrue(h.produced("GEOINFO"))
        self.assertEqual(h.produced_count("GEOINFO"), 1)

    def test_feed_events_batch(self):
        mod = self._make_module()
        mod._test_produce = [("RESULT", "data")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_events([
            ("IP_ADDRESS", "1.2.3.4"),
            ("IP_ADDRESS", "5.6.7.8"),
        ])
        self.assertEqual(h.produced_count("RESULT"), 2)

    def test_assert_produced(self):
        mod = self._make_module()
        mod._test_produce = [("FOUND", "data")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        h.assert_produced("FOUND")

    def test_assert_not_produced(self):
        mod = self._make_module()
        mod._test_produce = []
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        h.assert_not_produced("ANYTHING")

    def test_assert_produced_raises(self):
        mod = self._make_module()
        mod._test_produce = []
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        with self.assertRaises(AssertionError):
            h.assert_produced("MISSING")

    def test_assert_not_produced_raises(self):
        mod = self._make_module()
        mod._test_produce = [("EXISTS", "data")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        with self.assertRaises(AssertionError):
            h.assert_not_produced("EXISTS")

    def test_assert_produced_data(self):
        mod = self._make_module()
        mod._test_produce = [("IP_ADDRESS", "1.2.3.4")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        h.assert_produced_data("IP_ADDRESS", "1.2.3.4")

    def test_assert_produced_data_raises(self):
        mod = self._make_module()
        mod._test_produce = [("IP_ADDRESS", "1.2.3.4")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        with self.assertRaises(AssertionError):
            h.assert_produced_data("IP_ADDRESS", "5.6.7.8")

    def test_assert_produced_count(self):
        mod = self._make_module()
        mod._test_produce = [("A", "1"), ("A", "2")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        h.assert_produced_count("A", 2)

    def test_assert_produced_count_raises(self):
        mod = self._make_module()
        mod._test_produce = [("A", "1")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        with self.assertRaises(AssertionError):
            h.assert_produced_count("A", 5)

    def test_assert_no_errors(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.setup()
        h.assert_no_errors()

    def test_assert_no_errors_raises(self):
        mod = self._make_module()
        mod.errorState = True
        h = PluginTestHarness(mod)
        h.setup()
        with self.assertRaises(AssertionError):
            h.assert_no_errors()

    def test_reset(self):
        mod = self._make_module()
        mod._test_produce = [("A", "1")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        self.assertEqual(h.produced_count(), 1)
        h.reset()
        self.assertEqual(h.produced_count(), 0)

    def test_set_target(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.setup()
        h.set_target("other.com")
        self.assertEqual(h._target.value, "other.com")

    def test_set_options_triggers_setup(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.set_options({"api_key": "test"})
        self.assertTrue(h._setup_done)

    def test_event_data_query(self):
        mod = self._make_module()
        mod._test_produce = [("IP", "1.2.3.4"), ("IP", "5.6.7.8")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        self.assertEqual(h.event_data("IP"), ["1.2.3.4", "5.6.7.8"])

    def test_event_types_query(self):
        mod = self._make_module()
        mod._test_produce = [("A", "1"), ("B", "2"), ("A", "3")]
        h = PluginTestHarness(mod)
        h.setup()
        h.feed_event("ROOT", "test")
        self.assertEqual(h.event_types(), ["A", "B"])

    def test_mock_http_sequence(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.setup()
        h.mock_http_sequence([
            {"content": "page1", "status_code": 200},
            {"content": "page2", "status_code": 200},
        ])
        r1 = h._sf.fetchUrl("https://example.com/1")
        r2 = h._sf.fetchUrl("https://example.com/2")
        self.assertEqual(r1["content"], "page1")
        self.assertEqual(r2["content"], "page2")

    def test_module_property(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        self.assertIs(h.module, mod)

    def test_captured_property(self):
        mod = self._make_module()
        h = PluginTestHarness(mod)
        h.setup()
        self.assertIsInstance(h.captured, EventCapture)

    def test_for_class(self):
        # Test the for_class factory with a simple class
        class FakePlugin:
            def __init__(self):
                self.opts = {}
                self.errorState = False
                self.results = {}
                self.__name__ = "FakePlugin"
                self.__scanId__ = None
                self.__sfdb__ = None
                self._listenerModules = []

            def setup(self, sfc, userOpts=None):
                self.sf = sfc

            def setTarget(self, target):
                self._target = target

            def setDbh(self, dbh):
                self.__sfdb__ = dbh

            def handleEvent(self, event):
                pass

            def notifyListeners(self, event):
                pass

            def tempStorage(self):
                return {}

        h = PluginTestHarness.for_class(FakePlugin)
        h.setup()
        self.assertTrue(h._setup_done)


class TestDefaultOpts(unittest.TestCase):
    """Test default options."""

    def test_default_opts_has_useragent(self):
        opts = _default_opts()
        self.assertIn("_useragent", opts)

    def test_default_opts_has_fetchtimeout(self):
        opts = _default_opts()
        self.assertEqual(opts["_fetchtimeout"], 5)


if __name__ == "__main__":
    unittest.main()
