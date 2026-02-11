"""
Tests for the Config Service.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from spiderfoot.services.config_service import (
    ConfigService,
    ConfigValidator,
    get_config_service,
    reset_config_service,
    _coerce,
    ENV_MAP,
)


class TestCoerce(unittest.TestCase):
    """Test type coercion helper."""

    def test_bool_true(self):
        for v in ["1", "true", "yes", "on", "True", "YES"]:
            self.assertTrue(_coerce(v, bool), f"Failed for {v}")

    def test_bool_false(self):
        for v in ["0", "false", "no", "off", ""]:
            self.assertFalse(_coerce(v, bool), f"Failed for {v}")

    def test_int(self):
        self.assertEqual(_coerce("42", int), 42)
        self.assertEqual(_coerce(3.14, int), 3)

    def test_float(self):
        self.assertAlmostEqual(_coerce("3.14", float), 3.14)

    def test_list(self):
        self.assertEqual(_coerce("a, b, c", list), ["a", "b", "c"])
        self.assertEqual(_coerce(["x"], list), ["x"])

    def test_none(self):
        self.assertIsNone(_coerce(None, int))


class TestConfigValidator(unittest.TestCase):
    """Test ConfigValidator."""

    def test_required_missing(self):
        v = ConfigValidator()
        v.add_rule("_apikey", required=True)
        errors = v.validate({})
        self.assertEqual(len(errors), 1)
        self.assertIn("_apikey", errors[0])

    def test_type_coercion(self):
        v = ConfigValidator()
        v.add_rule("_port", type=int)
        config = {"_port": "8080"}
        errors = v.validate(config)
        self.assertEqual(len(errors), 0)
        self.assertEqual(config["_port"], 8080)

    def test_min_max(self):
        v = ConfigValidator()
        v.add_rule("_threads", type=int, min_value=1, max_value=10)

        config = {"_threads": 0}
        errors = v.validate(config)
        self.assertEqual(len(errors), 1)

    def test_choices(self):
        v = ConfigValidator()
        v.add_rule("_mode", type=str, choices={"a", "b"})

        config = {"_mode": "c"}
        errors = v.validate(config)
        self.assertEqual(len(errors), 1)

    def test_apply_defaults(self):
        v = ConfigValidator()
        v.add_rule("_timeout", type=int, default=30)
        config = {}
        v.apply_defaults(config)
        self.assertEqual(config["_timeout"], 30)


class TestConfigService(unittest.TestCase):
    """Test ConfigService."""

    def setUp(self):
        self.svc = ConfigService()

    def test_load_defaults(self):
        self.svc.load_defaults()
        self.assertFalse(self.svc.get("_debug"))
        self.assertEqual(self.svc.get("_maxthreads"), 3)

    def test_load_dict(self):
        self.svc.load_dict({"_custom": "value"})
        self.assertEqual(self.svc.get("_custom"), "value")

    def test_get_with_cast(self):
        self.svc.set("_port", "8080")
        self.assertEqual(self.svc.get("_port", cast=int), 8080)

    def test_get_default(self):
        self.assertEqual(self.svc.get("_nonexistent", default=42), 42)

    def test_has(self):
        self.svc.set("_exists", True)
        self.assertTrue(self.svc.has("_exists"))
        self.assertFalse(self.svc.has("_nope"))

    def test_snapshot(self):
        self.svc.set("_key", "original")
        snap = self.svc.snapshot()
        self.svc.set("_key", "changed")
        # Snapshot should have old value
        self.assertEqual(snap["_key"], "original")

    def test_validate(self):
        self.svc.load_defaults()
        errors = self.svc.validate()
        self.assertEqual(len(errors), 0)

    def test_watch(self):
        changes = []
        self.svc.watch(lambda k, old, new: changes.append((k, old, new)))
        self.svc.set("_x", "a")
        self.svc.set("_x", "b")
        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[1], ("_x", "a", "b"))

    def test_load_from_json_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"_test_key": "test_value"}, f)
            f.flush()
            path = f.name

        try:
            result = self.svc.load_from_file(path)
            self.assertTrue(result)
            self.assertEqual(self.svc.get("_test_key"), "test_value")
        finally:
            os.unlink(path)

    def test_load_from_missing_file(self):
        result = self.svc.load_from_file("/nonexistent/path.json")
        self.assertFalse(result)

    @patch.dict(os.environ, {"SF_DEBUG": "true", "SF_MAX_THREADS": "16"})
    def test_env_overrides(self):
        self.svc.apply_env_overrides()
        self.assertEqual(self.svc.get("_debug"), "true")
        self.assertEqual(self.svc.get("_maxthreads"), "16")

    def test_stats(self):
        self.svc.load_defaults()
        stats = self.svc.stats()
        self.assertGreater(stats["total_keys"], 0)
        self.assertEqual(stats["watchers"], 0)

    def test_keys(self):
        self.svc.set("_a", 1)
        self.svc.set("_b", 2)
        keys = self.svc.keys()
        self.assertIn("_a", keys)
        self.assertIn("_b", keys)


class TestConfigSingleton(unittest.TestCase):
    """Test singleton behavior."""

    def setUp(self):
        reset_config_service()

    def tearDown(self):
        reset_config_service()

    def test_same_instance(self):
        c1 = get_config_service()
        c2 = get_config_service()
        self.assertIs(c1, c2)

    def test_reset(self):
        c1 = get_config_service()
        reset_config_service()
        c2 = get_config_service()
        self.assertIsNot(c1, c2)


class TestEnvMap(unittest.TestCase):
    """Test env var mapping coverage."""

    def test_env_map_not_empty(self):
        self.assertGreater(len(ENV_MAP), 20)

    def test_all_values_start_with_underscore(self):
        for env_var, config_key in ENV_MAP.items():
            self.assertTrue(
                config_key.startswith("_"),
                f"{env_var} → {config_key} doesn't start with _"
            )


if __name__ == "__main__":
    unittest.main()
