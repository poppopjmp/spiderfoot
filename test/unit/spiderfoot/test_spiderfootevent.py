import unittest

from spiderfoot.event import SpiderFootEvent
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestSpiderFootEvent(SpiderFootModuleTestCase):
    """Test SpiderFootEvent."""

    def setUp(self):
        """Set up test case."""
        self.root_event = SpiderFootEvent("ROOT", "Root Event", "", "", None)
        self.event = SpiderFootEvent("IP_ADDRESS", "192.168.0.1", "example module", "example data", "192.168.0.1")

    def test_generated(self):
        self.assertIsInstance(self.event.generated, float)

    def test_eventType(self):
        self.assertEqual(self.event.eventType, self.eventType)

    def test_confidence(self):
        self.assertEqual(self.event.confidence, 100)

    def test_visibility(self):
        self.assertEqual(self.event.visibility, 100)

    def test_risk(self):
        self.assertEqual(self.event.risk, 0)

    def test_module(self):
        self.assertEqual(self.event.module, self.module)

    def test_data(self):
        self.assertEqual(self.event.data, "192.168.0.1")

    def test_sourceEvent(self):
        self.assertIsNone(self.event.sourceEvent)

    def test_sourceEventHash(self):
        self.assertEqual(self.event.sourceEventHash, "ROOT")

    def test_actualSource(self):
        self.assertIsNone(self.event.actualSource)

    def test_moduleDataSource(self):
        self.assertIsNone(self.event.moduleDataSource)

    def test_hash(self):
        self.assertIsInstance(self.event.hash, str)

    def test_eventType_setter(self):
        new_eventType = "RAW_DATA"
        self.event.eventType = new_eventType
        self.assertEqual(self.event.eventType, new_eventType)

    def test_eventType_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.event.eventType = 123

    def test_eventType_setter_empty_value(self):
        with self.assertRaises(ValueError):
            self.event.eventType = ""

    def test_confidence_setter(self):
        new_confidence = 80
        self.event.confidence = new_confidence
        self.assertEqual(self.event.confidence, new_confidence)

    def test_confidence_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.event.confidence = "high"

    def test_confidence_setter_invalid_value(self):
        with self.assertRaises(ValueError):
            self.event.confidence = 200

    def test_visibility_setter(self):
        new_visibility = 90
        self.event.visibility = new_visibility
        self.assertEqual(self.event.visibility, new_visibility)

    def test_visibility_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.event.visibility = "high"

    def test_visibility_setter_invalid_value(self):
        with self.assertRaises(ValueError):
            self.event.visibility = 200

    def test_risk_setter(self):
        new_risk = 50
        self.event.risk = new_risk
        self.assertEqual(self.event.risk, new_risk)

    def test_risk_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.event.risk = "high"

    def test_risk_setter_invalid_value(self):
        with self.assertRaises(ValueError):
            self.event.risk = 200

    def test_module_setter(self):
        new_module = "new_module"
        self.event.module = new_module
        self.assertEqual(self.event.module, new_module)

    def test_module_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.event.module = 123

    def test_module_setter_empty_value(self):
        with self.assertRaises(ValueError):
            self.event.module = ""

    def test_data_setter(self):
        new_data = "new_data"
        self.event.data = new_data
        self.assertEqual(self.event.data, new_data)

    def test_data_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.event.data = 123

    def test_data_setter_empty_value(self):
        with self.assertRaises(ValueError):
            self.event.data = ""

    def test_sourceEvent_setter(self):
        new_sourceEvent = SpiderFootEvent("ROOT", "root_data", "root_module", None)
        self.event.sourceEvent = new_sourceEvent
        self.assertEqual(self.event.sourceEvent, new_sourceEvent)

    def test_sourceEvent_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.event.sourceEvent = "invalid_event"

    def test_actualSource_setter(self):
        new_actualSource = "new_actual_source"
        self.event.actualSource = new_actualSource
        self.assertEqual(self.event.actualSource, new_actualSource)

    def test_moduleDataSource_setter(self):
        new_moduleDataSource = "new_module_data_source"
        self.event.moduleDataSource = new_moduleDataSource
        self.assertEqual(self.event.moduleDataSource, new_moduleDataSource)

    def test_asDict(self):
        event_dict = self.event.asDict()
        self.assertIsInstance(event_dict, dict)
        self.assertEqual(event_dict['generated'], int(self.event.generated))
        self.assertEqual(event_dict['type'], self.event.eventType)
        self.assertEqual(event_dict['data'], self.event.data)
        self.assertEqual(event_dict['module'], self.event.module)
        self.assertEqual(event_dict['source'], '')


if __name__ == "__main__":
    unittest.main()
