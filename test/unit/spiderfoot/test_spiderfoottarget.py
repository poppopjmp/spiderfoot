import unittest
from spiderfoot.target import SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestSpiderFootTarget(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.target_value = "example.com"
        self.target_type = "INTERNET_NAME"
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def test_init(self):
        self.assertEqual(self.target.targetType, self.target_type)
        self.assertEqual(self.target.targetValue, self.target_value)
        self.assertEqual(self.target.targetAliases, [])

    def test_targetType_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.target.targetType = 123

    def test_targetType_setter_invalid_value(self):
        with self.assertRaises(ValueError):
            self.target.targetType = "INVALID_TYPE"

    def test_targetValue_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.target.targetValue = 123

    def test_targetValue_setter_empty_value(self):
        with self.assertRaises(ValueError):
            self.target.targetValue = ""

    def test_setAlias(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.target.setAlias(alias_value, alias_type)
        self.assertIn({"type": alias_type, "value": alias_value},
                      self.target.targetAliases)

    def test_setAlias_invalid_value_type(self):
        self.target.setAlias(123, "INTERNET_NAME")
        self.assertNotIn({"type": "INTERNET_NAME", "value": 123},
                         self.target.targetAliases)

    def test_setAlias_empty_value(self):
        self.target.setAlias("", "INTERNET_NAME")
        self.assertNotIn({"type": "INTERNET_NAME", "value": ""},
                         self.target.targetAliases)

    def test_setAlias_invalid_typeName_type(self):
        self.target.setAlias("alias.com", 123)
        self.assertNotIn({"type": 123, "value": "alias.com"},
                         self.target.targetAliases)

    def test_setAlias_empty_typeName(self):
        self.target.setAlias("alias.com", "")
        self.assertNotIn({"type": "", "value": "alias.com"},
                         self.target.targetAliases)

    def test_getEquivalents(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.target.setAlias(alias_value, alias_type)
        equivalents = self.target._getEquivalents(alias_type)
        self.assertIn(alias_value, equivalents)

    def test_getNames(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.target.setAlias(alias_value, alias_type)
        names = self.target.getNames()
        self.assertIn(alias_value, names)
        self.assertIn(self.target_value, names)

    def test_getAddresses(self):
        alias_value = "192.168.1.1"
        alias_type = "IP_ADDRESS"
        self.target.setAlias(alias_value, alias_type)
        addresses = self.target.getAddresses()
        self.assertIn(alias_value, addresses)

    def test_matches(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.target.setAlias(alias_value, alias_type)
        self.assertTrue(self.target.matches(alias_value))
        self.assertTrue(self.target.matches(self.target_value))
        self.assertFalse(self.target.matches("nonexistent.com"))

    def test_matches_ip(self):
        alias_value = "192.168.1.1"
        alias_type = "IP_ADDRESS"
        self.target.setAlias(alias_value, alias_type)
        self.assertTrue(self.target.matches(alias_value))
        self.assertFalse(self.target.matches("10.0.0.1"))

    def test_matches_subnet(self):
        self.target.targetType = "NETBLOCK_OWNER"
        self.target.targetValue = "192.168.1.0/24"
        self.assertTrue(self.target.matches("192.168.1.1"))
        self.assertFalse(self.target.matches("10.0.0.1"))
        
    def test_matches_parent_domain(self):
        # Use a different target that doesn't match the parent domain directly
        target = SpiderFootTarget("sub.example.com", "INTERNET_NAME")
        target.setAlias("www.sub.example.com", "INTERNET_NAME")
        self.assertTrue(target.matches(
            "example.com", includeParents=True))
        self.assertFalse(target.matches(
            "example.com", includeParents=False))

    def test_matches_child_domain(self):
        alias_value = "example.com"
        alias_type = "INTERNET_NAME"
        self.target.setAlias(alias_value, alias_type)
        self.assertTrue(self.target.matches(
            "sub.example.com", includeChildren=True))
        self.assertFalse(self.target.matches(
            "sub.example.com", includeChildren=False))

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
