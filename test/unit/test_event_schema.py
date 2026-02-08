#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for spiderfoot.event_schema."""

import unittest

from spiderfoot.event_schema import (
    DataFormat,
    EventCategory,
    EventSchema,
    EventSchemaRegistry,
    ValidationResult,
    _validate_format,
    validate_event,
)


class TestDataFormatValidation(unittest.TestCase):
    """Test individual format validators."""

    def test_any_format(self):
        self.assertIsNone(_validate_format("anything", DataFormat.ANY))

    def test_non_empty(self):
        self.assertIsNone(_validate_format("hello", DataFormat.NON_EMPTY))
        self.assertIsNotNone(_validate_format("", DataFormat.NON_EMPTY))
        self.assertIsNotNone(_validate_format("   ", DataFormat.NON_EMPTY))

    def test_ipv4_valid(self):
        self.assertIsNone(_validate_format("192.168.1.1", DataFormat.IPV4))
        self.assertIsNone(_validate_format("10.0.0.1", DataFormat.IPV4))
        self.assertIsNone(_validate_format("255.255.255.255", DataFormat.IPV4))

    def test_ipv4_invalid(self):
        self.assertIsNotNone(_validate_format("999.999.999.999", DataFormat.IPV4))
        self.assertIsNotNone(_validate_format("not-an-ip", DataFormat.IPV4))
        self.assertIsNotNone(_validate_format("::1", DataFormat.IPV4))

    def test_ipv6_valid(self):
        self.assertIsNone(_validate_format("::1", DataFormat.IPV6))
        self.assertIsNone(_validate_format("2001:db8::1", DataFormat.IPV6))
        self.assertIsNone(
            _validate_format("fe80::1%eth0", DataFormat.IPV6))

    def test_ipv6_invalid(self):
        self.assertIsNotNone(_validate_format("192.168.1.1", DataFormat.IPV6))

    def test_ip_either(self):
        self.assertIsNone(_validate_format("192.168.1.1", DataFormat.IP))
        self.assertIsNone(_validate_format("::1", DataFormat.IP))
        self.assertIsNotNone(_validate_format("not-ip", DataFormat.IP))

    def test_domain_valid(self):
        self.assertIsNone(_validate_format("example.com", DataFormat.DOMAIN))
        self.assertIsNone(_validate_format("sub.example.com", DataFormat.DOMAIN))

    def test_domain_invalid(self):
        self.assertIsNotNone(_validate_format("not a domain", DataFormat.DOMAIN))
        self.assertIsNotNone(_validate_format("-invalid.com", DataFormat.DOMAIN))

    def test_email_valid(self):
        self.assertIsNone(_validate_format("user@example.com", DataFormat.EMAIL))

    def test_email_invalid(self):
        self.assertIsNotNone(_validate_format("not-email", DataFormat.EMAIL))

    def test_url_valid(self):
        self.assertIsNone(_validate_format("http://example.com", DataFormat.URL))
        self.assertIsNone(
            _validate_format("https://example.com/path", DataFormat.URL))

    def test_url_invalid(self):
        self.assertIsNotNone(_validate_format("ftp://example.com", DataFormat.URL))
        self.assertIsNotNone(_validate_format("example.com", DataFormat.URL))

    def test_netblock_valid(self):
        self.assertIsNone(
            _validate_format("192.168.0.0/24", DataFormat.NETBLOCK))
        self.assertIsNone(
            _validate_format("10.0.0.0/8", DataFormat.NETBLOCK))

    def test_netblock_invalid(self):
        self.assertIsNotNone(
            _validate_format("not-a-cidr", DataFormat.NETBLOCK))

    def test_json_valid(self):
        self.assertIsNone(
            _validate_format('{"key": "value"}', DataFormat.JSON))

    def test_json_invalid(self):
        self.assertIsNotNone(
            _validate_format('not json {', DataFormat.JSON))


class TestEventSchema(unittest.TestCase):
    """Test EventSchema validation."""

    def test_validate_data_valid(self):
        schema = EventSchema("IP_ADDRESS", "IP",
                             EventCategory.ENTITY, DataFormat.IPV4)
        errors = schema.validate_data("192.168.1.1")
        self.assertEqual(errors, [])

    def test_validate_data_invalid_format(self):
        schema = EventSchema("IP_ADDRESS", "IP",
                             EventCategory.ENTITY, DataFormat.IPV4)
        errors = schema.validate_data("not-an-ip")
        self.assertTrue(len(errors) > 0)

    def test_validate_data_none(self):
        schema = EventSchema("TEST", "", EventCategory.DATA,
                             DataFormat.NON_EMPTY)
        errors = schema.validate_data(None)
        self.assertTrue(len(errors) > 0)

    def test_validate_data_wrong_type(self):
        schema = EventSchema("TEST", "", EventCategory.DATA)
        errors = schema.validate_data(123)
        self.assertTrue(len(errors) > 0)

    def test_max_data_length(self):
        schema = EventSchema("TEST", "", EventCategory.DATA,
                             DataFormat.NON_EMPTY, max_data_length=10)
        errors = schema.validate_data("x" * 20)
        self.assertTrue(any("exceeds maximum" in e for e in errors))

    def test_custom_validator(self):
        def must_contain_foo(data):
            if "foo" not in data:
                return "Must contain 'foo'"
            return None

        schema = EventSchema(
            "TEST", "", EventCategory.DATA, DataFormat.NON_EMPTY,
            custom_validators=[must_contain_foo])
        self.assertEqual(schema.validate_data("hello foo"), [])
        self.assertTrue(len(schema.validate_data("hello bar")) > 0)

    def test_to_dict(self):
        schema = EventSchema("IP_ADDRESS", "IPv4 Address",
                             EventCategory.ENTITY, DataFormat.IPV4)
        d = schema.to_dict()
        self.assertEqual(d["event_type"], "IP_ADDRESS")
        self.assertEqual(d["category"], "ENTITY")
        self.assertEqual(d["data_format"], "ipv4")


class TestEventSchemaRegistry(unittest.TestCase):
    """Test schema registry with core types."""

    def test_core_schemas_loaded(self):
        """Core schemas should be auto-registered on import."""
        self.assertTrue(EventSchemaRegistry.has("IP_ADDRESS"))
        self.assertTrue(EventSchemaRegistry.has("DOMAIN_NAME"))
        self.assertTrue(EventSchemaRegistry.has("ROOT"))
        self.assertTrue(EventSchemaRegistry.has("EMAILADDR"))

    def test_get_schema(self):
        schema = EventSchemaRegistry.get("IP_ADDRESS")
        self.assertIsNotNone(schema)
        self.assertEqual(schema.data_format, DataFormat.IPV4)

    def test_by_category(self):
        entities = EventSchemaRegistry.by_category(EventCategory.ENTITY)
        self.assertTrue(len(entities) > 5)
        for s in entities:
            self.assertEqual(s.category, EventCategory.ENTITY)

    def test_validate_valid_event(self):
        result = EventSchemaRegistry.validate({
            "type": "IP_ADDRESS",
            "data": "192.168.1.1",
            "module": "sfp_test",
            "confidence": 100,
            "visibility": 100,
            "risk": 0,
        })
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_validate_invalid_data_format(self):
        result = EventSchemaRegistry.validate({
            "type": "IP_ADDRESS",
            "data": "not-an-ip",
            "module": "sfp_test",
        })
        self.assertFalse(result.valid)
        self.assertTrue(any("IPv4" in e for e in result.errors))

    def test_validate_missing_type(self):
        result = EventSchemaRegistry.validate({"data": "test"})
        self.assertFalse(result.valid)

    def test_validate_missing_data(self):
        result = EventSchemaRegistry.validate({
            "type": "IP_ADDRESS",
            "module": "sfp_test",
        })
        self.assertFalse(result.valid)

    def test_validate_invalid_confidence(self):
        result = EventSchemaRegistry.validate({
            "type": "IP_ADDRESS",
            "data": "192.168.1.1",
            "module": "sfp_test",
            "confidence": 150,
        })
        self.assertFalse(result.valid)

    def test_validate_bad_type_name(self):
        result = EventSchemaRegistry.validate({
            "type": "bad-type-name",
            "data": "test",
            "module": "sfp_test",
        })
        self.assertFalse(result.valid)

    def test_validate_unknown_type_lenient(self):
        EventSchemaRegistry.set_strict(False)
        result = EventSchemaRegistry.validate({
            "type": "CUSTOM_NEW_TYPE",
            "data": "test",
            "module": "sfp_custom",
        })
        self.assertTrue(result.valid)
        self.assertTrue(len(result.warnings) > 0)

    def test_validate_root_event(self):
        result = EventSchemaRegistry.validate({
            "type": "ROOT",
            "data": "target.com",
        })
        self.assertTrue(result.valid)

    def test_validate_deprecated_warning(self):
        EventSchemaRegistry.register(
            EventSchema("OLD_TYPE", "Deprecated type",
                        EventCategory.DATA, DataFormat.NON_EMPTY,
                        deprecated=True))
        result = EventSchemaRegistry.validate({
            "type": "OLD_TYPE",
            "data": "test",
            "module": "sfp_test",
        })
        self.assertTrue(any("deprecated" in w for w in result.warnings))

    def test_validate_event_helper(self):
        errors = validate_event({
            "type": "IP_ADDRESS",
            "data": "10.0.0.1",
            "module": "sfp_test",
        })
        self.assertEqual(errors, [])

    def test_generate_docs(self):
        docs = EventSchemaRegistry.generate_docs()
        self.assertIn("Event Type Reference", docs)
        self.assertIn("IP_ADDRESS", docs)
        self.assertIn("ENTITY", docs)

    def test_all_types(self):
        types = EventSchemaRegistry.all_types()
        self.assertIn("IP_ADDRESS", types)
        self.assertTrue(len(types) > 20)

    def test_eventType_key_fallback(self):
        """Validate events using 'eventType' key (SpiderFootEvent format)."""
        result = EventSchemaRegistry.validate({
            "eventType": "DOMAIN_NAME",
            "data": "example.com",
            "module": "sfp_test",
        })
        self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
