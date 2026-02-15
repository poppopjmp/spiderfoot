# -*- coding: utf-8 -*-
"""
SpiderFoot Authentication & Authorization Package.

Provides:
- JWT token issuance and validation
- Password hashing (bcrypt)
- User management (PostgreSQL-backed)
- LDAP authentication provider
- SSO (OAuth2/OIDC, SAML) integration
- Auth middleware for FastAPI
"""
from spiderfoot.auth.service import AuthService, get_auth_service
from spiderfoot.auth.models import User, Session, AuthConfig

__all__ = ["AuthService", "get_auth_service", "User", "Session", "AuthConfig"]
