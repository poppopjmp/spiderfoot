"""Tests for spiderfoot.config_schema."""
from __future__ import annotations

import unittest

from spiderfoot.config.config_schema import (
    ConfigSchema,
    FieldSchema,
    infer_schema_from_module,
    validate_module_config,
)


class TestFieldSchema(unittest.TestCase):
    """Tests for FieldSchema."""

    def test_valid_string(self):
        fs = FieldSchema(name="api_key", type="str")
        self.assertEqual(fs.validate("hello"), [])

    def test_valid_int(self):
        fs = FieldSchema(name="count", type="int")
        self.assertEqual(fs.validate(42), [])

    def test_valid_bool(self):
        fs = FieldSchema(name="enabled", type="bool")
        self.assertEqual(fs.validate(True), [])

    def test_type_mismatch(self):
        fs = FieldSchema(name="count", type="int")
        errors = fs.validate("not_int")
        self.assertEqual(len(errors), 1)
        self.assertIn("expected type 'int'", errors[0])

    def test_required_missing(self):
        fs = FieldSchema(name="api_key", type="str", required=True)
        errors = fs.validate(None)
        self.assertEqual(len(errors), 1)
        self.assertIn("required", errors[0])

    def test_optional_missing(self):
        fs = FieldSchema(name="api_key", type="str", required=False)
        errors = fs.validate(None)
        self.assertEqual(errors, [])

    def test_min_value(self):
        fs = FieldSchema(name="count", type="int", min_value=1)
        self.assertEqual(fs.validate(1), [])
        errors = fs.validate(0)
        self.assertEqual(len(errors), 1)
        self.assertIn("below minimum", errors[0])

    def test_max_value(self):
        fs = FieldSchema(name="count", type="int", max_value=100)
        self.assertEqual(fs.validate(100), [])
        errors = fs.validate(101)
        self.assertEqual(len(errors), 1)
        self.assertIn("above maximum", errors[0])

    def test_min_length(self):
        fs = FieldSchema(name="name", type="str", min_length=3)
        self.assertEqual(fs.validate("abc"), [])
        errors = fs.validate("ab")
        self.assertEqual(len(errors), 1)
        self.assertIn("below minimum", errors[0])

    def test_max_length(self):
        fs = FieldSchema(name="name", type="str", max_length=5)
        self.assertEqual(fs.validate("abcde"), [])
        errors = fs.validate("abcdef")
        self.assertEqual(len(errors), 1)
        self.assertIn("above maximum", errors[0])

    def test_pattern(self):
        fs = FieldSchema(name="email", type="str", pattern=r"^[\w.]+@[\w.]+$")
        self.assertEqual(fs.validate("user@example.com"), [])
        errors = fs.validate("not-an-email")
        self.assertEqual(len(errors), 1)
        self.assertIn("pattern", errors[0])

    def test_enum(self):
        fs = FieldSchema(name="mode", type="str", enum=["fast", "slow"])
        self.assertEqual(fs.validate("fast"), [])
        errors = fs.validate("medium")
        self.assertEqual(len(errors), 1)
        self.assertIn("not in allowed values", errors[0])

    def test_float_accepts_int(self):
        fs = FieldSchema(name="rate", type="float")
        self.assertEqual(fs.validate(42), [])

    def test_to_dict(self):
        fs = FieldSchema(
            name="api_key", type="str", description="API key",
            required=True, sensitive=True, default="",
            min_length=10, max_length=100
        )
        d = fs.to_dict()
        self.assertEqual(d["name"], "api_key")
        self.assertEqual(d["type"], "str")
        self.assertTrue(d["required"])
        self.assertTrue(d["sensitive"])
        self.assertEqual(d["min_length"], 10)


class TestConfigSchema(unittest.TestCase):
    """Tests for ConfigSchema."""

    def setUp(self):
        self.schema = ConfigSchema(module_name="sfp_test")
        self.schema.add_field("api_key", type="str", required=True,
                              sensitive=True, description="API key")
        self.schema.add_field("max_pages", type="int", default=10,
                              min_value=1, max_value=100)
        self.schema.add_field("enabled", type="bool", default=True)

    def test_validate_valid(self):
        errors = self.schema.validate({
            "api_key": "abc123",
            "max_pages": 50,
            "enabled": True,
        })
        self.assertEqual(errors, [])

    def test_validate_missing_required(self):
        errors = self.schema.validate({"max_pages": 50})
        self.assertEqual(len(errors), 1)
        self.assertIn("api_key", errors[0])

    def test_validate_range_error(self):
        errors = self.schema.validate({
            "api_key": "abc",
            "max_pages": 999,
        })
        self.assertEqual(len(errors), 1)
        self.assertIn("above maximum", errors[0])

    def test_validate_type_error(self):
        errors = self.schema.validate({
            "api_key": "abc",
            "max_pages": "not_int",
        })
        self.assertEqual(len(errors), 1)

    def test_len(self):
        self.assertEqual(len(self.schema), 3)

    def test_contains(self):
        self.assertIn("api_key", self.schema)
        self.assertNotIn("nonexistent", self.schema)

    def test_required_fields(self):
        self.assertEqual(self.schema.required_fields, ["api_key"])

    def test_sensitive_fields(self):
        self.assertEqual(self.schema.sensitive_fields, ["api_key"])

    def test_get_defaults(self):
        defaults = self.schema.get_defaults()
        self.assertEqual(defaults["max_pages"], 10)
        self.assertEqual(defaults["enabled"], True)
        self.assertNotIn("api_key", defaults)

    def test_find_unknown_keys(self):
        unknown = self.schema.find_unknown_keys({
            "api_key": "abc",
            "extra_key": "value",
            "another": 5,
        })
        self.assertIn("extra_key", unknown)
        self.assertIn("another", unknown)
        self.assertNotIn("api_key", unknown)

    def test_chaining(self):
        s = ConfigSchema("test")
        result = s.add_field("a", type="str").add_field("b", type="int")
        self.assertIs(result, s)
        self.assertEqual(len(s), 2)

    def test_get_field(self):
        f = self.schema.get_field("api_key")
        self.assertIsNotNone(f)
        self.assertEqual(f.name, "api_key")
        self.assertIsNone(self.schema.get_field("nonexistent"))

    def test_to_dict(self):
        d = self.schema.to_dict()
        self.assertEqual(d["module_name"], "sfp_test")
        self.assertIn("fields", d)
        self.assertIn("api_key", d["fields"])


class TestInferSchema(unittest.TestCase):
    """Tests for infer_schema_from_module."""

    def test_infer_types(self):
        opts = {
            "validate": True,
            "max_pages": 10,
            "timeout": 30.5,
            "api_key": "",
            "domains": [],
        }
        optdescs = {
            "validate": "Validate results",
            "max_pages": "Max pages to scan",
            "api_key": "API key for the service",
        }
        schema = infer_schema_from_module(opts, optdescs, "sfp_test")

        self.assertEqual(len(schema), 5)

        f = schema.get_field("validate")
        self.assertEqual(f.type, "bool")
        self.assertEqual(f.default, True)

        f = schema.get_field("max_pages")
        self.assertEqual(f.type, "int")
        self.assertEqual(f.default, 10)

        f = schema.get_field("timeout")
        self.assertEqual(f.type, "float")

        f = schema.get_field("api_key")
        self.assertEqual(f.type, "str")
        self.assertTrue(f.sensitive)
        self.assertTrue(f.required)  # sensitive + empty default

        f = schema.get_field("domains")
        self.assertEqual(f.type, "list")

    def test_infer_description(self):
        schema = infer_schema_from_module(
            {"enabled": True},
            {"enabled": "Enable this module"},
        )
        f = schema.get_field("enabled")
        self.assertEqual(f.description, "Enable this module")

    def test_sensitive_detection(self):
        """Various sensitive field name patterns."""
        opts = {
            "api_key": "",
            "password": "",
            "secret_token": "",
            "normal_field": "value",
        }
        schema = infer_schema_from_module(opts, {})
        self.assertTrue(schema.get_field("api_key").sensitive)
        self.assertTrue(schema.get_field("password").sensitive)
        self.assertTrue(schema.get_field("secret_token").sensitive)
        self.assertFalse(schema.get_field("normal_field").sensitive)


class TestValidateModuleConfig(unittest.TestCase):
    """Tests for validate_module_config convenience function."""

    def test_valid_config(self):
        opts = {"enabled": True, "max_pages": 10}
        optdescs = {"enabled": "Enabled", "max_pages": "Max pages"}
        errors = validate_module_config(
            "sfp_test", {"enabled": True, "max_pages": 5}, opts, optdescs
        )
        self.assertEqual(errors, [])

    def test_type_mismatch(self):
        opts = {"enabled": True}
        errors = validate_module_config(
            "sfp_test", {"enabled": "not_bool"}, opts, {}
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("expected type 'bool'", errors[0])


if __name__ == "__main__":
    unittest.main()
