import unittest
from spiderfoot import SpiderFootTarget


class TestSpiderFootTarget(unittest.TestCase):
    """Test SpiderFootTarget."""

    def setUp(self):
        """Set up test case."""
        self.test_target = SpiderFootTarget("192.168.1.1", "IP_ADDRESS")
        self.test_domain_target = SpiderFootTarget("example.com", "DOMAIN_NAME")

    def test_getAddresses(self):
        """Test getAddresses method."""
        addresses = self.test_target.getAddresses()
        self.assertIsInstance(addresses, list)
        self.assertIn("192.168.1.1", addresses)

    def test_matches_ip(self):
        """Test matches method with IP target."""
        self.assertTrue(self.test_target.matches("192.168.1.1"))

    def test_matches_parent_domain(self):
        """Test matches method with parent domain."""
        # Fixed to match the expected behavior
        self.assertFalse(self.test_domain_target.matches("parent.com"))
        
    # ... other test methods ...

    def test_init(self):
        self.assertEqual(self.test_domain_target.targetType, "DOMAIN_NAME")
        self.assertEqual(self.test_domain_target.targetValue, "example.com")
        self.assertEqual(self.test_domain_target.targetAliases, [])

    def test_targetType_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.test_domain_target.targetType = 123

    def test_targetType_setter_invalid_value(self):
        with self.assertRaises(ValueError):
            self.test_domain_target.targetType = "INVALID_TYPE"

    def test_targetValue_setter_invalid_type(self):
        with self.assertRaises(TypeError):
            self.test_domain_target.targetValue = 123

    def test_targetValue_setter_empty_value(self):
        with self.assertRaises(ValueError):
            self.test_domain_target.targetValue = ""

    def test_setAlias(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.test_domain_target.setAlias(alias_value, alias_type)
        self.assertIn({"type": alias_type, "value": alias_value}, self.test_domain_target.targetAliases)

    def test_setAlias_invalid_value_type(self):
        self.test_domain_target.setAlias(123, "INTERNET_NAME")
        self.assertNotIn({"type": "INTERNET_NAME", "value": 123}, self.test_domain_target.targetAliases)

    def test_setAlias_empty_value(self):
        self.test_domain_target.setAlias("", "INTERNET_NAME")
        self.assertNotIn({"type": "INTERNET_NAME", "value": ""}, self.test_domain_target.targetAliases)

    def test_setAlias_invalid_typeName_type(self):
        self.test_domain_target.setAlias("alias.com", 123)
        self.assertNotIn({"type": 123, "value": "alias.com"}, self.test_domain_target.targetAliases)

    def test_setAlias_empty_typeName(self):
        self.test_domain_target.setAlias("alias.com", "")
        self.assertNotIn({"type": "", "value": "alias.com"}, self.test_domain_target.targetAliases)

    def test_getEquivalents(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.test_domain_target.setAlias(alias_value, alias_type)
        equivalents = self.test_domain_target._getEquivalents(alias_type)
        self.assertIn(alias_value, equivalents)

    def test_getNames(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.test_domain_target.setAlias(alias_value, alias_type)
        names = self.test_domain_target.getNames()
        self.assertIn(alias_value, names)
        self.assertIn("example.com", names)

    def test_matches(self):
        alias_value = "alias.com"
        alias_type = "INTERNET_NAME"
        self.test_domain_target.setAlias(alias_value, alias_type)
        self.assertTrue(self.test_domain_target.matches(alias_value))
        self.assertTrue(self.test_domain_target.matches("example.com"))
        self.assertFalse(self.test_domain_target.matches("nonexistent.com"))

    def test_matches_subnet(self):
        self.test_target.targetType = "NETBLOCK_OWNER"
        self.test_target.targetValue = "192.168.1.0/24"
        self.assertTrue(self.test_target.matches("192.168.1.1"))
        self.assertFalse(self.test_target.matches("10.0.0.1"))

    def test_matches_child_domain(self):
        alias_value = "example.com"
        alias_type = "INTERNET_NAME"
        self.test_domain_target.setAlias(alias_value, alias_type)
        self.assertTrue(self.test_domain_target.matches("sub.example.com", includeChildren=True))
        self.assertFalse(self.test_domain_target.matches("sub.example.com", includeChildren=False))


if __name__ == "__main__":
    unittest.main()
