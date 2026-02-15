# -*- coding: utf-8 -*-
"""
Data models for the SpiderFoot auth system.

Defines User, Session, and configuration dataclasses used across
the auth service, API routes, and middleware.
"""
from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AuthMethod(str, Enum):
    """Supported authentication methods."""
    LOCAL = "local"
    LDAP = "ldap"
    OAUTH2 = "oauth2"
    SAML = "saml"
    API_KEY = "api_key"


class AccountStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"
    PENDING = "pending"


@dataclass
class User:
    """Represents a user account in the system."""
    id: str = ""
    username: str = ""
    email: str = ""
    password_hash: str = ""
    role: str = "viewer"
    display_name: str = ""
    auth_method: str = "local"
    status: str = "active"
    created_at: float = 0.0
    updated_at: float = 0.0
    last_login: float = 0.0
    failed_logins: int = 0
    locked_until: float = 0.0
    sso_provider_id: str = ""
    sso_subject: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status == AccountStatus.ACTIVE.value

    def is_locked(self) -> bool:
        if self.status == AccountStatus.LOCKED.value:
            if self.locked_until > 0 and time.time() > self.locked_until:
                return False  # Lock expired
            return True
        return False

    def to_dict(self, include_sensitive: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "display_name": self.display_name,
            "auth_method": self.auth_method,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_login": self.last_login,
            "sso_provider_id": self.sso_provider_id,
        }
        if include_sensitive:
            d["failed_logins"] = self.failed_logins
            d["locked_until"] = self.locked_until
        return d


@dataclass
class Session:
    """Represents an active user session."""
    id: str = ""
    user_id: str = ""
    token_hash: str = ""
    created_at: float = 0.0
    expires_at: float = 0.0
    ip_address: str = ""
    user_agent: str = ""
    auth_method: str = "local"
    is_active: bool = True

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


@dataclass
class SSOProvider:
    """SSO provider configuration stored in the database."""
    id: str = ""
    name: str = ""
    protocol: str = ""  # oauth2, saml, ldap
    enabled: bool = True
    # OAuth2/OIDC fields
    client_id: str = ""
    client_secret: str = ""
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    jwks_uri: str = ""
    scopes: str = "openid email profile"
    # SAML fields
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_slo_url: str = ""
    idp_certificate: str = ""
    sp_entity_id: str = ""
    sp_acs_url: str = ""
    # LDAP fields
    ldap_url: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_base_dn: str = ""
    ldap_user_filter: str = "(uid={username})"
    ldap_group_filter: str = "(member={dn})"
    ldap_tls: bool = True
    # Common
    default_role: str = "viewer"
    allowed_domains: str = ""  # comma-separated
    auto_create_users: bool = True
    attribute_mapping: str = ""  # JSON: {"email": "mail", "name": "displayName"}
    # Group → role mapping for OAuth2/OIDC (Keycloak, Azure AD, etc.)
    group_attribute: str = "groups"  # Claim name in userinfo that contains groups
    admin_group: str = ""  # Group name that maps to admin role
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "protocol": self.protocol,
            "enabled": self.enabled,
            "default_role": self.default_role,
            "allowed_domains": self.allowed_domains,
            "auto_create_users": self.auto_create_users,
            "attribute_mapping": self.attribute_mapping,
            "group_attribute": self.group_attribute,
            "admin_group": self.admin_group,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.protocol == "oauth2":
            d.update({
                "client_id": self.client_id,
                "authorization_url": self.authorization_url,
                "token_url": self.token_url,
                "userinfo_url": self.userinfo_url,
                "scopes": self.scopes,
                "jwks_uri": self.jwks_uri,
            })
            if include_secrets:
                d["client_secret"] = self.client_secret
        elif self.protocol == "saml":
            d.update({
                "idp_entity_id": self.idp_entity_id,
                "idp_sso_url": self.idp_sso_url,
                "sp_entity_id": self.sp_entity_id,
                "sp_acs_url": self.sp_acs_url,
            })
        elif self.protocol == "ldap":
            d.update({
                "ldap_url": self.ldap_url,
                "ldap_base_dn": self.ldap_base_dn,
                "ldap_user_filter": self.ldap_user_filter,
                "ldap_group_filter": self.ldap_group_filter,
                "ldap_tls": self.ldap_tls,
            })
            if include_secrets:
                d["ldap_bind_dn"] = self.ldap_bind_dn
                d["ldap_bind_password"] = self.ldap_bind_password
        return d


@dataclass
class AuthConfig:
    """Authentication configuration sourced from environment variables."""
    # JWT
    jwt_secret: str = field(default_factory=lambda: os.environ.get(
        "SF_JWT_SECRET", secrets.token_hex(32)
    ))
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = int(os.environ.get("SF_JWT_EXPIRY_HOURS", "24"))
    jwt_refresh_expiry_days: int = int(os.environ.get("SF_JWT_REFRESH_EXPIRY_DAYS", "30"))

    # RBAC enforcement
    rbac_enforce: bool = os.environ.get(
        "SF_RBAC_ENFORCE", "false"
    ).lower() in ("true", "1", "yes")

    # Password policy
    min_password_length: int = int(os.environ.get("SF_MIN_PASSWORD_LENGTH", "8"))
    max_failed_logins: int = int(os.environ.get("SF_MAX_FAILED_LOGINS", "5"))
    lockout_duration_minutes: int = int(os.environ.get("SF_LOCKOUT_DURATION_MINUTES", "30"))

    # Session
    session_ttl_hours: int = int(os.environ.get("SF_SESSION_TTL_HOURS", "24"))

    # Default admin
    default_admin_username: str = os.environ.get("SF_ADMIN_USERNAME", "admin")
    default_admin_password: str = os.environ.get("SF_ADMIN_PASSWORD", "")
    default_admin_email: str = os.environ.get("SF_ADMIN_EMAIL", "admin@spiderfoot.local")

    # Auth mode
    auth_required: bool = os.environ.get(
        "SF_AUTH_REQUIRED", "false"
    ).lower() in ("true", "1", "yes")

    def to_dict(self) -> dict[str, Any]:
        return {
            "jwt_algorithm": self.jwt_algorithm,
            "jwt_expiry_hours": self.jwt_expiry_hours,
            "rbac_enforce": self.rbac_enforce,
            "min_password_length": self.min_password_length,
            "max_failed_logins": self.max_failed_logins,
            "lockout_duration_minutes": self.lockout_duration_minutes,
            "session_ttl_hours": self.session_ttl_hours,
            "auth_required": self.auth_required,
        }


@dataclass
class ApiKey:
    """Represents an API key for programmatic access."""
    id: str = ""
    user_id: str = ""
    name: str = ""
    key_prefix: str = ""  # first 8 chars for identification
    key_hash: str = ""    # bcrypt hash of the full key
    role: str = "viewer"
    status: str = "active"
    expires_at: float = 0.0  # 0 = never
    allowed_modules: str = ""  # JSON list of module names, empty = all
    allowed_endpoints: str = ""  # JSON list of endpoint patterns, empty = all
    rate_limit: int = 0  # requests per minute, 0 = unlimited
    last_used: float = 0.0
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        if self.status != "active":
            return False
        if self.expires_at > 0 and time.time() > self.expires_at:
            return False
        return True

    def to_dict(self, include_sensitive: bool = False) -> dict[str, Any]:
        d = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "role": self.role,
            "status": self.status,
            "expires_at": self.expires_at,
            "allowed_modules": self.allowed_modules,
            "allowed_endpoints": self.allowed_endpoints,
            "rate_limit": self.rate_limit,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_sensitive:
            d["key_hash"] = self.key_hash
        return d
