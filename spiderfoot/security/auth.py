#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         auth
# Purpose:      Authentication and authorization middleware for SpiderFoot
#               API and WebUI services.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
SpiderFoot Auth Middleware

Provides authentication mechanisms for the REST API and WebUI:

    - API key authentication (header or query param)
    - JWT token authentication (optional)
    - Basic auth for WebUI
    - Role-based access control (RBAC)
    - Rate limiting per authenticated user

Usage (FastAPI)::

    from spiderfoot.auth import create_auth_middleware, AuthConfig
    config = AuthConfig(api_keys=["secret-key-1"])
    middleware = create_auth_middleware(config)
    app.middleware("http")(middleware)

Usage (CherryPy)::

    from spiderfoot.auth import AuthGuard
    guard = AuthGuard(config)
    if not guard.check_request(headers, path):
        raise cherrypy.HTTPError(401)
"""

import base64
import binascii
import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum

from spiderfoot.constants import DEFAULT_TTL_ONE_HOUR

log = logging.getLogger("spiderfoot.auth")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class AuthMethod(Enum):
    """Supported authentication methods."""
    NONE = "none"
    API_KEY = "api_key"
    BASIC = "basic"
    JWT = "jwt"


class Role(Enum):
    """Access control roles."""
    ADMIN = "admin"       # Full access
    ANALYST = "analyst"   # Run scans, view results
    VIEWER = "viewer"     # Read-only access
    API = "api"           # API-only access (no WebUI)


# Role permissions mapping
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: {
        "scan:create", "scan:read", "scan:delete", "scan:abort",
        "config:read", "config:write",
        "module:list", "module:configure",
        "correlation:run", "correlation:read",
        "user:manage", "system:admin",
    },
    Role.ANALYST: {
        "scan:create", "scan:read", "scan:abort",
        "config:read",
        "module:list",
        "correlation:run", "correlation:read",
    },
    Role.VIEWER: {
        "scan:read",
        "config:read",
        "module:list",
        "correlation:read",
    },
    Role.API: {
        "scan:create", "scan:read", "scan:abort",
        "module:list",
        "correlation:read",
    },
}


@dataclass
class AuthConfig:
    """Authentication configuration."""

    # Method
    method: AuthMethod = AuthMethod.NONE

    # API keys (for API_KEY method)
    api_keys: list[str] = field(default_factory=list)

    # Basic auth credentials {username: password_hash}
    basic_credentials: dict[str, str] = field(default_factory=dict)

    # JWT secret (for JWT method)
    jwt_secret: str = ""
    jwt_expiry: int = DEFAULT_TTL_ONE_HOUR  # seconds

    # Paths that don't require auth
    public_paths: list[str] = field(default_factory=lambda: [
        "/health", "/health/live", "/health/ready",
        "/health/startup", "/ping", "/metrics",
    ])

    # API key header name
    api_key_header: str = "X-API-Key"

    # API key query parameter name
    api_key_param: str = "api_key"

    # Role assignments {api_key_or_username: role}
    role_assignments: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_config(cls, opts: dict) -> "AuthConfig":
        """Create from SpiderFoot config dict."""
        method_str = opts.get(
            "_auth_method",
            os.environ.get("SF_AUTH_METHOD", "none")
        )
        try:
            method = AuthMethod(method_str)
        except ValueError:
            method = AuthMethod.NONE

        # API keys from env or config
        api_keys_str = opts.get(
            "_auth_api_keys",
            os.environ.get("SF_API_KEYS", "")
        )
        api_keys = [
            k.strip() for k in api_keys_str.split(",") if k.strip()
        ]

        # Basic auth from env
        basic_creds = {}
        basic_str = opts.get(
            "_auth_basic_credentials",
            os.environ.get("SF_AUTH_BASIC", "")
        )
        for entry in basic_str.split(","):
            if ":" in entry:
                user, pwd = entry.strip().split(":", 1)
                basic_creds[user] = _hash_password(pwd)

        return cls(
            method=method,
            api_keys=api_keys,
            basic_credentials=basic_creds,
            jwt_secret=opts.get(
                "_auth_jwt_secret",
                os.environ.get("SF_JWT_SECRET", "")
            ),
        )


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = "spiderfoot"  # Simple salt; use bcrypt in production
    return hashlib.sha256(
        f"{salt}:{password}".encode()
    ).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return hmac.compare_digest(
        _hash_password(password), password_hash
    )


# ---------------------------------------------------------------------------
# Auth Guard
# ---------------------------------------------------------------------------

class AuthResult:
    """Result of an authentication check."""

    def __init__(self, authenticated: bool,
                 identity: str = "",
                 role: Role = Role.VIEWER,
                 error: str = "") -> None:
        """Initialize the AuthResult."""
        self.authenticated = authenticated
        self.identity = identity
        self.role = role
        self.error = error
        self.permissions: set[str] = (
            ROLE_PERMISSIONS.get(role, set()) if authenticated else set()
        )

    def has_permission(self, permission: str) -> bool:
        """Check if the authenticated identity has the given permission."""
        return permission in self.permissions

    def to_dict(self) -> dict:
        """Return a dictionary representation."""
        return {
            "authenticated": self.authenticated,
            "identity": self.identity,
            "role": self.role.value if self.authenticated else None,
            "error": self.error or None,
        }


class AuthGuard:
    """Authentication guard for request validation.

    Supports multiple auth methods and role-based access control.
    """

    def __init__(self, config: AuthConfig) -> None:
        """Initialize the AuthGuard."""
        self.config = config
        self._api_key_set: set[str] = set(config.api_keys)

    def authenticate(self, headers: dict[str, str],
                     path: str = "/",
                     query_params: dict[str, str] | None = None
                     ) -> AuthResult:
        """Authenticate a request.

        Args:
            headers: HTTP request headers.
            path: Request path.
            query_params: URL query parameters.

        Returns:
            AuthResult indicating success/failure.
        """
        # Public paths bypass auth
        if self._is_public_path(path):
            return AuthResult(True, identity="public", role=Role.VIEWER)

        # No auth configured
        if self.config.method == AuthMethod.NONE:
            return AuthResult(True, identity="anonymous", role=Role.ADMIN)

        # API key auth
        if self.config.method == AuthMethod.API_KEY:
            return self._check_api_key(headers, query_params)

        # Basic auth
        if self.config.method == AuthMethod.BASIC:
            return self._check_basic_auth(headers)

        # JWT auth
        if self.config.method == AuthMethod.JWT:
            return self._check_jwt(headers)

        return AuthResult(False, error="Unsupported auth method")

    def _is_public_path(self, path: str) -> bool:
        """Check if a path is in the public paths list."""
        for public_path in self.config.public_paths:
            if path == public_path or path.startswith(public_path + "/"):
                return True
        return False

    def _check_api_key(self, headers: dict[str, str],
                       query_params: dict[str, str] | None
                       ) -> AuthResult:
        """Validate API key from header or query parameter."""
        # Check header
        api_key = headers.get(self.config.api_key_header, "")

        # Check query param as fallback
        if not api_key and query_params:
            api_key = query_params.get(self.config.api_key_param, "")

        if not api_key:
            return AuthResult(False, error="API key required")

        if api_key not in self._api_key_set:
            return AuthResult(False, error="Invalid API key")

        role = self._get_role(api_key)
        return AuthResult(True, identity=f"apikey:{api_key[:8]}...",
                          role=role)

    def _check_basic_auth(self, headers: dict[str, str]) -> AuthResult:
        """Validate Basic auth credentials."""
        import base64

        auth_header = headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return AuthResult(False, error="Basic auth required")

        try:
            decoded = base64.b64decode(
                auth_header[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return AuthResult(False, error="Invalid Basic auth format")

        stored_hash = self.config.basic_credentials.get(username)
        if stored_hash is None:
            return AuthResult(False, error="Unknown user")

        if not _verify_password(password, stored_hash):
            return AuthResult(False, error="Invalid password")

        role = self._get_role(username)
        return AuthResult(True, identity=username, role=role)

    def _check_jwt(self, headers: dict[str, str]) -> AuthResult:
        """Validate JWT token (simplified, no external dependency)."""
        auth_header = headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return AuthResult(False, error="Bearer token required")

        token = auth_header[7:]

        # Simple HMAC-based token validation
        # Format: base64(payload).signature
        parts = token.split(".")
        if len(parts) != 2:
            return AuthResult(False, error="Invalid token format")

        import base64
        try:
            payload_b64, signature = parts
            payload_bytes = base64.urlsafe_b64decode(
                payload_b64 + "==")
            expected_sig = hmac.new(
                self.config.jwt_secret.encode(),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return AuthResult(False, error="Invalid token signature")

            import json
            payload = json.loads(payload_bytes.decode())

            # Check expiry
            if payload.get("exp", 0) < time.time():
                return AuthResult(False, error="Token expired")

            identity = payload.get("sub", "unknown")
            role = self._get_role(identity)
            return AuthResult(True, identity=identity, role=role)

        except Exception as e:
            return AuthResult(False, error=f"Token validation failed: {e}")

    def _get_role(self, identity: str) -> Role:
        """Get role for an identity."""
        role_str = self.config.role_assignments.get(identity, "analyst")
        try:
            return Role(role_str)
        except ValueError:
            return Role.VIEWER

    # ------------------------------------------------------------------
    # Token generation
    # ------------------------------------------------------------------

    def generate_api_key(self) -> str:
        """Generate a new API key."""
        key = secrets.token_urlsafe(32)
        self._api_key_set.add(key)
        self.config.api_keys.append(key)
        return key

    def generate_jwt(self, subject: str,
                     expiry: int | None = None) -> str:
        """Generate a JWT-like token.

        Args:
            subject: Token subject (username/identity).
            expiry: Expiry in seconds from now.

        Returns:
            Token string.
        """
        import base64
        import json

        if not self.config.jwt_secret:
            raise ValueError("JWT secret not configured")

        exp = int(time.time()) + (expiry or self.config.jwt_expiry)
        payload = {
            "sub": subject,
            "exp": exp,
            "iat": int(time.time()),
        }

        payload_bytes = json.dumps(payload).encode()
        payload_b64 = base64.urlsafe_b64encode(
            payload_bytes).decode().rstrip("=")
        signature = hmac.new(
            self.config.jwt_secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return f"{payload_b64}.{signature}"
