"""Tests for spiderfoot.secret_manager."""

import json
import os
import tempfile
import unittest

from spiderfoot.secret_manager import (
    EncryptedFileSecretBackend,
    EnvSecretBackend,
    FileSecretBackend,
    MemorySecretBackend,
    SecretEntry,
    SecretManager,
)


class TestSecretEntry(unittest.TestCase):
    """Tests for SecretEntry."""

    def test_basic(self):
        e = SecretEntry("key1", "value1")
        self.assertEqual(e.key, "key1")
        self.assertEqual(e.value, "value1")

    def test_age_days(self):
        import time
        e = SecretEntry("k", "v", created_at=time.time() - 86400 * 10)
        self.assertAlmostEqual(e.age_days, 10, delta=0.1)

    def test_needs_rotation_no(self):
        e = SecretEntry("k", "v", rotation_days=0)
        self.assertFalse(e.needs_rotation)

    def test_needs_rotation_yes(self):
        import time
        e = SecretEntry("k", "v", rotation_days=5,
                        created_at=time.time() - 86400 * 10)
        self.assertTrue(e.needs_rotation)

    def test_to_dict_without_value(self):
        e = SecretEntry("k", "v")
        d = e.to_dict()
        self.assertNotIn("value", d)
        self.assertIn("key", d)

    def test_to_dict_with_value(self):
        e = SecretEntry("k", "v")
        d = e.to_dict(include_value=True)
        self.assertEqual(d["value"], "v")

    def test_from_dict_roundtrip(self):
        e = SecretEntry("k", "v", description="test", tags=["api"])
        d = e.to_dict(include_value=True)
        e2 = SecretEntry.from_dict(d)
        self.assertEqual(e2.key, "k")
        self.assertEqual(e2.value, "v")


class TestMemorySecretBackend(unittest.TestCase):
    """Tests for MemorySecretBackend."""

    def test_set_get(self):
        b = MemorySecretBackend()
        b.set("key1", "val1")
        self.assertEqual(b.get("key1"), "val1")

    def test_get_missing(self):
        b = MemorySecretBackend()
        self.assertIsNone(b.get("x"))

    def test_delete(self):
        b = MemorySecretBackend()
        b.set("key1", "val1")
        self.assertTrue(b.delete("key1"))
        self.assertFalse(b.delete("key1"))

    def test_exists(self):
        b = MemorySecretBackend()
        b.set("key1", "val1")
        self.assertTrue(b.exists("key1"))
        self.assertFalse(b.exists("x"))

    def test_list_keys(self):
        b = MemorySecretBackend()
        b.set("a", "1")
        b.set("b", "2")
        self.assertEqual(sorted(b.list_keys()), ["a", "b"])

    def test_update_existing(self):
        b = MemorySecretBackend()
        b.set("key1", "old")
        b.set("key1", "new")
        self.assertEqual(b.get("key1"), "new")


class TestEnvSecretBackend(unittest.TestCase):
    """Tests for EnvSecretBackend."""

    def setUp(self):
        self.b = EnvSecretBackend(prefix="TEST_SF_")
        # Clean up
        for k in list(os.environ):
            if k.startswith("TEST_SF_"):
                del os.environ[k]

    def tearDown(self):
        for k in list(os.environ):
            if k.startswith("TEST_SF_"):
                del os.environ[k]

    def test_set_get(self):
        self.b.set("api_key", "12345")
        self.assertEqual(self.b.get("api_key"), "12345")
        self.assertEqual(os.environ.get("TEST_SF_API_KEY"), "12345")

    def test_get_missing(self):
        self.assertIsNone(self.b.get("missing"))

    def test_delete(self):
        self.b.set("api_key", "12345")
        self.assertTrue(self.b.delete("api_key"))
        self.assertIsNone(self.b.get("api_key"))

    def test_list_keys(self):
        self.b.set("key_one", "a")
        self.b.set("key_two", "b")
        keys = self.b.list_keys()
        self.assertIn("key_one", keys)
        self.assertIn("key_two", keys)

    def test_exists(self):
        self.b.set("x", "1")
        self.assertTrue(self.b.exists("x"))
        self.assertFalse(self.b.exists("y"))


class TestFileSecretBackend(unittest.TestCase):
    """Tests for FileSecretBackend."""

    def test_set_get_persist(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            b1 = FileSecretBackend(filepath=path)
            b1.set("key1", "val1")
            self.assertEqual(b1.get("key1"), "val1")

            # Reload
            b2 = FileSecretBackend(filepath=path)
            self.assertEqual(b2.get("key1"), "val1")
        finally:
            os.unlink(path)

    def test_delete(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            b = FileSecretBackend(filepath=path)
            b.set("k", "v")
            self.assertTrue(b.delete("k"))
            self.assertIsNone(b.get("k"))
        finally:
            os.unlink(path)


class TestEncryptedFileSecretBackend(unittest.TestCase):
    """Tests for EncryptedFileSecretBackend."""

    def test_roundtrip(self):
        with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
            path = f.name
        try:
            b1 = EncryptedFileSecretBackend(
                filepath=path, encryption_key="test-pass")
            b1.set("api_key", "super-secret-123")
            self.assertEqual(b1.get("api_key"), "super-secret-123")

            # Reload with same key
            b2 = EncryptedFileSecretBackend(
                filepath=path, encryption_key="test-pass")
            self.assertEqual(b2.get("api_key"), "super-secret-123")
        finally:
            os.unlink(path)

    def test_file_is_not_plaintext(self):
        with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
            path = f.name
        try:
            b = EncryptedFileSecretBackend(
                filepath=path, encryption_key="pass")
            b.set("secret", "my-api-key-12345")
            with open(path) as f:
                content = f.read()
            self.assertNotIn("my-api-key-12345", content)
        finally:
            os.unlink(path)

    def test_delete(self):
        with tempfile.NamedTemporaryFile(suffix=".enc", delete=False) as f:
            path = f.name
        try:
            b = EncryptedFileSecretBackend(
                filepath=path, encryption_key="p")
            b.set("k", "v")
            self.assertTrue(b.delete("k"))
            self.assertIsNone(b.get("k"))
        finally:
            os.unlink(path)


class TestSecretManager(unittest.TestCase):
    """Tests for SecretManager."""

    def test_default_memory(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("key1", "val1")
        self.assertEqual(mgr.get("key1"), "val1")

    def test_get_default(self):
        mgr = SecretManager(backend_type="memory")
        self.assertEqual(mgr.get("missing", "fallback"), "fallback")

    def test_delete(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("k", "v")
        self.assertTrue(mgr.delete("k"))
        self.assertIsNone(mgr.get("k"))

    def test_exists(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("k", "v")
        self.assertTrue(mgr.exists("k"))
        self.assertFalse(mgr.exists("x"))

    def test_list_keys(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("a", "1")
        mgr.set("b", "2")
        self.assertEqual(sorted(mgr.list_keys()), ["a", "b"])

    def test_get_many(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("a", "1")
        mgr.set("b", "2")
        result = mgr.get_many(["a", "b", "c"])
        self.assertEqual(result["a"], "1")
        self.assertEqual(result["b"], "2")
        self.assertIsNone(result["c"])

    def test_set_many(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set_many({"x": "1", "y": "2"})
        self.assertEqual(mgr.get("x"), "1")
        self.assertEqual(mgr.get("y"), "2")

    def test_get_module_secrets(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("sfp_shodan_api_key", "key1")
        mgr.set("sfp_shodan_timeout", "30")
        mgr.set("sfp_other_key", "xxx")
        result = mgr.get_module_secrets("sfp_shodan")
        self.assertIn("sfp_shodan_api_key", result)
        self.assertNotIn("sfp_other_key", result)

    def test_inject_into_config(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("shodan_key", "secret123")
        config = {"api_key": ""}
        result = mgr.inject_into_config(config, {"api_key": "shodan_key"})
        self.assertEqual(result["api_key"], "secret123")

    def test_redact(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("api_key", "supersecret123")
        text = "The key is supersecret123 and more"
        redacted = mgr.redact(text)
        self.assertNotIn("supersecret123", redacted)
        self.assertIn("***api_key***", redacted)

    def test_redact_short_values_skipped(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("short", "ab")  # too short to redact
        text = "ab test"
        self.assertEqual(mgr.redact(text), text)

    def test_access_log(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("k", "v")
        mgr.get("k")
        log_entries = mgr.access_log()
        self.assertEqual(len(log_entries), 2)
        self.assertEqual(log_entries[0]["operation"], "set")
        self.assertEqual(log_entries[1]["operation"], "get")

    def test_stats(self):
        mgr = SecretManager(backend_type="memory")
        mgr.set("k", "v")
        s = mgr.stats()
        self.assertEqual(s["total_secrets"], 1)
        self.assertEqual(s["backend_type"], "MemorySecretBackend")

    def test_custom_backend(self):
        backend = MemorySecretBackend()
        mgr = SecretManager(backend=backend)
        mgr.set("k", "v")
        self.assertEqual(mgr.get("k"), "v")

    def test_unknown_backend_type(self):
        with self.assertRaises(ValueError):
            SecretManager(backend_type="vault")


if __name__ == "__main__":
    unittest.main()
