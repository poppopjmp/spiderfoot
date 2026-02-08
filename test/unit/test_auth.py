"""Unit tests for spiderfoot.auth."""

import base64
import time
import unittest

from spiderfoot.auth import (
    AuthConfig,
    AuthGuard,
    AuthMethod,
    AuthResult,
    Role,
    ROLE_PERMISSIONS,
    _hash_password,
    _verify_password,
)


class TestPasswordHashing(unittest.TestCase):

    def test_hash_deterministic(self):
        h1 = _hash_password("secret")
        h2 = _hash_password("secret")
        self.assertEqual(h1, h2)

    def test_verify_correct(self):
        h = _hash_password("mypassword")
        self.assertTrue(_verify_password("mypassword", h))

    def test_verify_incorrect(self):
        h = _hash_password("mypassword")
        self.assertFalse(_verify_password("wrong", h))


class TestAuthConfig(unittest.TestCase):

    def test_defaults(self):
        cfg = AuthConfig()
        self.assertEqual(cfg.method, AuthMethod.NONE)
        self.assertEqual(cfg.api_keys, [])
        self.assertIn("/health", cfg.public_paths)

    def test_from_config_api_key(self):
        cfg = AuthConfig.from_config({
            "_auth_method": "api_key",
            "_auth_api_keys": "key1, key2",
        })
        self.assertEqual(cfg.method, AuthMethod.API_KEY)
        self.assertEqual(cfg.api_keys, ["key1", "key2"])

    def test_from_config_basic(self):
        cfg = AuthConfig.from_config({
            "_auth_method": "basic",
            "_auth_basic_credentials": "admin:secret",
        })
        self.assertEqual(cfg.method, AuthMethod.BASIC)
        self.assertIn("admin", cfg.basic_credentials)

    def test_from_config_invalid_method(self):
        cfg = AuthConfig.from_config({"_auth_method": "bogus"})
        self.assertEqual(cfg.method, AuthMethod.NONE)


class TestAuthResult(unittest.TestCase):

    def test_authenticated(self):
        r = AuthResult(True, identity="user1", role=Role.ADMIN)
        self.assertTrue(r.authenticated)
        self.assertTrue(r.has_permission("scan:create"))
        self.assertTrue(r.has_permission("system:admin"))

    def test_unauthenticated(self):
        r = AuthResult(False, error="bad key")
        self.assertFalse(r.authenticated)
        self.assertFalse(r.has_permission("scan:create"))

    def test_viewer_permissions(self):
        r = AuthResult(True, identity="viewer", role=Role.VIEWER)
        self.assertTrue(r.has_permission("scan:read"))
        self.assertFalse(r.has_permission("scan:create"))
        self.assertFalse(r.has_permission("system:admin"))

    def test_to_dict(self):
        r = AuthResult(True, identity="user1", role=Role.ANALYST)
        d = r.to_dict()
        self.assertTrue(d["authenticated"])
        self.assertEqual(d["identity"], "user1")
        self.assertEqual(d["role"], "analyst")


class TestAuthGuard(unittest.TestCase):

    def test_no_auth_allows_all(self):
        guard = AuthGuard(AuthConfig(method=AuthMethod.NONE))
        result = guard.authenticate({}, "/api/scan")
        self.assertTrue(result.authenticated)
        self.assertEqual(result.role, Role.ADMIN)

    def test_public_path_bypasses_auth(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.API_KEY,
            api_keys=["secret"],
        ))
        result = guard.authenticate({}, "/health")
        self.assertTrue(result.authenticated)

    def test_api_key_valid(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.API_KEY,
            api_keys=["valid-key-123"],
        ))
        result = guard.authenticate(
            {"X-API-Key": "valid-key-123"}, "/api/scan")
        self.assertTrue(result.authenticated)

    def test_api_key_invalid(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.API_KEY,
            api_keys=["valid-key-123"],
        ))
        result = guard.authenticate(
            {"X-API-Key": "wrong-key"}, "/api/scan")
        self.assertFalse(result.authenticated)
        self.assertIn("Invalid", result.error)

    def test_api_key_missing(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.API_KEY,
            api_keys=["key1"],
        ))
        result = guard.authenticate({}, "/api/scan")
        self.assertFalse(result.authenticated)
        self.assertIn("required", result.error)

    def test_api_key_from_query_param(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.API_KEY,
            api_keys=["query-key"],
        ))
        result = guard.authenticate(
            {}, "/api/scan",
            query_params={"api_key": "query-key"},
        )
        self.assertTrue(result.authenticated)

    def test_basic_auth_valid(self):
        pwd_hash = _hash_password("secret")
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.BASIC,
            basic_credentials={"admin": pwd_hash},
        ))
        cred = base64.b64encode(b"admin:secret").decode()
        result = guard.authenticate(
            {"Authorization": f"Basic {cred}"}, "/api/scan")
        self.assertTrue(result.authenticated)

    def test_basic_auth_wrong_password(self):
        pwd_hash = _hash_password("secret")
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.BASIC,
            basic_credentials={"admin": pwd_hash},
        ))
        cred = base64.b64encode(b"admin:wrong").decode()
        result = guard.authenticate(
            {"Authorization": f"Basic {cred}"}, "/api/scan")
        self.assertFalse(result.authenticated)

    def test_basic_auth_missing_header(self):
        guard = AuthGuard(AuthConfig(method=AuthMethod.BASIC))
        result = guard.authenticate({}, "/api/scan")
        self.assertFalse(result.authenticated)

    def test_generate_api_key(self):
        guard = AuthGuard(AuthConfig(method=AuthMethod.API_KEY))
        key = guard.generate_api_key()
        self.assertIsInstance(key, str)
        self.assertGreater(len(key), 20)
        # Should be usable immediately
        result = guard.authenticate(
            {"X-API-Key": key}, "/api/scan")
        self.assertTrue(result.authenticated)

    def test_jwt_roundtrip(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.JWT,
            jwt_secret="test-secret-key",
        ))
        token = guard.generate_jwt("testuser", expiry=60)
        result = guard.authenticate(
            {"Authorization": f"Bearer {token}"}, "/api/scan")
        self.assertTrue(result.authenticated)
        self.assertEqual(result.identity, "testuser")

    def test_jwt_expired(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.JWT,
            jwt_secret="test-secret-key",
        ))
        token = guard.generate_jwt("testuser", expiry=-10)
        result = guard.authenticate(
            {"Authorization": f"Bearer {token}"}, "/api/scan")
        self.assertFalse(result.authenticated)
        self.assertIn("expired", result.error.lower())

    def test_role_assignment(self):
        guard = AuthGuard(AuthConfig(
            method=AuthMethod.API_KEY,
            api_keys=["admin-key"],
            role_assignments={"admin-key": "admin"},
        ))
        result = guard.authenticate(
            {"X-API-Key": "admin-key"}, "/api/scan")
        self.assertTrue(result.authenticated)
        self.assertEqual(result.role, Role.ADMIN)


class TestRolePermissions(unittest.TestCase):

    def test_admin_has_all(self):
        perms = ROLE_PERMISSIONS[Role.ADMIN]
        self.assertIn("system:admin", perms)
        self.assertIn("scan:create", perms)

    def test_viewer_limited(self):
        perms = ROLE_PERMISSIONS[Role.VIEWER]
        self.assertNotIn("scan:create", perms)
        self.assertIn("scan:read", perms)


if __name__ == "__main__":
    unittest.main()
