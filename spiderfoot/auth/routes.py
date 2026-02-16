# -*- coding: utf-8 -*-
"""
Authentication & authorization API routes for SpiderFoot.

Provides endpoints for:
- Local login (username/password → JWT)
- Token refresh
- User CRUD (admin only)
- Password management
- Session management
- SSO provider CRUD & login flows (OAuth2, SAML, LDAP)
- Auth status and configuration
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from spiderfoot.rbac import UserContext, require_permission

log = logging.getLogger("spiderfoot.auth.routes")

router = APIRouter(prefix="/auth", tags=["authentication"])

# ── OAuth2 state store (Redis-backed CSRF protection) ─────────────────────

_redis_client = None


def _get_redis():
    """Lazy-init Redis client for OAuth2 state storage."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.environ.get("SF_REDIS_URL", "")
    if not redis_url:
        log.warning("SF_REDIS_URL not set — OAuth2 state validation disabled")
        return None
    try:
        import redis
        _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        log.info("OAuth2 state store: Redis connected")
        return _redis_client
    except Exception as e:
        log.warning("Redis unavailable for OAuth2 state store: %s", e)
        return None


_OAUTH2_STATE_PREFIX = "sf:oauth2:state:"
_OAUTH2_STATE_TTL = 600  # 10 minutes


# ---------- Request / Response models ----------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class LDAPLoginRequest(BaseModel):
    provider_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    password: str = Field(default="", max_length=255)
    role: str = Field(default="viewer")
    display_name: str = Field(default="", max_length=255)


class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(default="", max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)


class SSOProviderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    protocol: str = Field(..., pattern="^(oauth2|saml|ldap)$")
    enabled: bool = True
    # OAuth2
    client_id: str = ""
    client_secret: str = ""
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    scopes: str = "openid email profile"
    # SAML
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_slo_url: str = ""
    idp_certificate: str = ""
    sp_entity_id: str = ""
    sp_acs_url: str = ""
    # LDAP
    ldap_url: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_base_dn: str = ""
    ldap_user_filter: str = "(uid={username})"
    ldap_group_filter: str = "(member={dn})"
    ldap_tls: bool = True
    # Common
    default_role: str = "viewer"
    allowed_domains: str = ""
    auto_create_users: bool = True
    attribute_mapping: str = "{}"
    group_attribute: str = "groups"
    admin_group: str = ""


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="viewer")
    expires_in_days: int = Field(default=0, ge=0)  # 0 = never
    allowed_modules: str = Field(default="")  # JSON list or comma-separated
    allowed_endpoints: str = Field(default="")
    rate_limit: int = Field(default=0, ge=0)


class UpdateApiKeyRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    allowed_modules: Optional[str] = None
    allowed_endpoints: Optional[str] = None
    rate_limit: Optional[int] = None


# ---------- Dependency ----------

def _get_auth_svc():
    from spiderfoot.auth.service import get_auth_service
    svc = get_auth_service()
    svc.initialize()
    return svc


def _get_client_info(request: Request) -> dict[str, str]:
    """Extract client IP and user-agent from request."""
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    return {"ip_address": ip, "user_agent": ua}


# ═══════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════

@router.post("/login")
async def login(body: LoginRequest, request: Request):
    """Authenticate with username/password and receive JWT tokens."""
    svc = _get_auth_svc()
    client = _get_client_info(request)
    try:
        result = svc.login(
            body.username,
            body.password,
            ip_address=client["ip_address"],
            user_agent=client["user_agent"],
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/ldap/login")
async def ldap_login(body: LDAPLoginRequest, request: Request):
    """Authenticate with LDAP credentials and receive JWT tokens."""
    svc = _get_auth_svc()
    client = _get_client_info(request)
    try:
        result = svc.ldap_login(
            body.provider_id,
            body.username,
            body.password,
            ip_address=client["ip_address"],
            user_agent=client["user_agent"],
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.post("/refresh")
async def refresh_token(body: RefreshRequest):
    """Refresh an access token using a refresh token."""
    svc = _get_auth_svc()
    try:
        return svc.refresh_access_token(body.refresh_token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout(request: Request):
    """Revoke all sessions for the current user."""
    user: UserContext | None = getattr(request.state, "user", None)
    if not user or not user.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    svc = _get_auth_svc()
    count = svc.revoke_all_sessions(user.user_id)
    return {"message": f"Revoked {count} sessions"}


@router.get("/me")
async def get_current_user(request: Request):
    """Get the current authenticated user's profile."""
    user: UserContext | None = getattr(request.state, "user", None)
    if not user or not user.user_id:
        # Return anonymous context when auth not enforced
        from spiderfoot.rbac import get_default_user
        default = get_default_user()
        return {
            "authenticated": False,
            "user": default.to_dict(),
        }

    svc = _get_auth_svc()
    db_user = svc.get_user_by_id(user.user_id)
    if not db_user:
        return {
            "authenticated": True,
            "user": user.to_dict(),
        }

    return {
        "authenticated": True,
        "user": db_user.to_dict(),
    }


@router.get("/status")
async def auth_status():
    """Get authentication system status and configuration."""
    svc = _get_auth_svc()
    return svc.get_auth_status()


# ═══════════════════════════════════════════════════════════
# USER MANAGEMENT (admin only)
# ═══════════════════════════════════════════════════════════

@router.get("/users")
async def list_users(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserContext = Depends(require_permission("user:read")),
):
    """List all users (admin only)."""
    svc = _get_auth_svc()
    users = svc.list_users(limit=limit, offset=offset)
    return {
        "items": [u.to_dict() for u in users],
        "total": svc.count_users(),
        "limit": limit,
        "offset": offset,
    }


@router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    user: UserContext = Depends(require_permission("user:create")),
):
    """Create a new user (admin only)."""
    svc = _get_auth_svc()
    try:
        new_user = svc.create_user(
            username=body.username,
            email=body.email,
            password=body.password,
            role=body.role,
            display_name=body.display_name,
        )
        return new_user.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    user: UserContext = Depends(require_permission("user:read")),
):
    """Get a specific user (admin only)."""
    svc = _get_auth_svc()
    target = svc.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return target.to_dict()


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    user: UserContext = Depends(require_permission("user:update")),
):
    """Update a user (admin only)."""
    svc = _get_auth_svc()
    updates = body.model_dump(exclude_unset=True)
    try:
        updated = svc.update_user(user_id, updates)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        return updated.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    user: UserContext = Depends(require_permission("user:delete")),
):
    """Delete a user (admin only)."""
    if user.user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    svc = _get_auth_svc()
    if not svc.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")


@router.post("/users/{user_id}/password")
async def admin_change_password(
    user_id: str,
    body: ChangePasswordRequest,
    user: UserContext = Depends(require_permission("user:update")),
):
    """Change a user's password (admin only)."""
    svc = _get_auth_svc()
    try:
        svc.change_password(user_id, body.new_password)
        return {"message": "Password changed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/password")
async def change_own_password(body: ChangePasswordRequest, request: Request):
    """Change the current user's password."""
    user: UserContext | None = getattr(request.state, "user", None)
    if not user or not user.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    svc = _get_auth_svc()
    db_user = svc.get_user_by_id(user.user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify current password (skip if SSO user without password)
    if db_user.password_hash and body.current_password:
        if not svc.verify_password(body.current_password, db_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password incorrect")

    try:
        svc.change_password(user.user_id, body.new_password)
        return {"message": "Password changed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════

@router.get("/sessions")
async def list_sessions(request: Request):
    """List active sessions for the current user."""
    user: UserContext | None = getattr(request.state, "user", None)
    if not user or not user.user_id:
        return {"items": []}

    svc = _get_auth_svc()
    sessions = svc.get_user_sessions(user.user_id)
    return {"items": sessions}


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, request: Request):
    """Revoke a specific session."""
    user: UserContext | None = getattr(request.state, "user", None)
    if not user or not user.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    svc = _get_auth_svc()
    if not svc.revoke_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session revoked"}


# ═══════════════════════════════════════════════════════════
# API KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════

@router.get("/api-keys")
async def list_api_keys(
    user_id: str = Query(default="", description="Filter by user ID (admin only)"),
    user: UserContext = Depends(require_permission("user:read")),
):
    """List API keys. Admins see all; others see only their own."""
    svc = _get_auth_svc()
    from spiderfoot.rbac import has_permission
    if user_id and has_permission(user.role, "user:read"):
        keys = svc.list_api_keys(user_id=user_id)
    elif has_permission(user.role, "user:read"):
        keys = svc.list_api_keys()
    else:
        keys = svc.list_api_keys(user_id=user.user_id)
    return {"items": [k.to_dict() for k in keys]}


@router.get("/api-keys/mine")
async def list_my_api_keys(request: Request):
    """List current user's API keys."""
    ctx: UserContext | None = getattr(request.state, "user", None)
    if not ctx or not ctx.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    svc = _get_auth_svc()
    keys = svc.list_api_keys(user_id=ctx.user_id)
    return {"items": [k.to_dict() for k in keys]}


@router.post("/api-keys", status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    request: Request,
):
    """Create an API key for the current user."""
    ctx: UserContext | None = getattr(request.state, "user", None)
    if not ctx or not ctx.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    svc = _get_auth_svc()

    # Validate role: user can only create keys with their role or lower
    from spiderfoot.rbac import parse_role
    requested_role = parse_role(body.role)
    user_role = parse_role(ctx.role.value if hasattr(ctx.role, 'value') else str(ctx.role))
    if requested_role.level > user_role.level:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot create API key with role '{body.role}' (higher than your role)"
        )

    expires_at = 0.0
    if body.expires_in_days > 0:
        expires_at = time.time() + body.expires_in_days * 86400

    try:
        api_key, raw_key = svc.create_api_key(
            user_id=ctx.user_id,
            name=body.name,
            role=body.role,
            expires_at=expires_at,
            allowed_modules=body.allowed_modules,
            allowed_endpoints=body.allowed_endpoints,
            rate_limit=body.rate_limit,
        )
        result = api_key.to_dict()
        result["key"] = raw_key  # Only returned at creation time
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api-keys/for-user/{target_user_id}", status_code=201)
async def create_api_key_for_user(
    target_user_id: str,
    body: CreateApiKeyRequest,
    user: UserContext = Depends(require_permission("user:create")),
):
    """Create an API key for another user (admin only)."""
    svc = _get_auth_svc()
    expires_at = 0.0
    if body.expires_in_days > 0:
        expires_at = time.time() + body.expires_in_days * 86400

    try:
        api_key, raw_key = svc.create_api_key(
            user_id=target_user_id,
            name=body.name,
            role=body.role,
            expires_at=expires_at,
            allowed_modules=body.allowed_modules,
            allowed_endpoints=body.allowed_endpoints,
            rate_limit=body.rate_limit,
        )
        result = api_key.to_dict()
        result["key"] = raw_key
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api-keys/{key_id}")
async def get_api_key(
    key_id: str,
    request: Request,
):
    """Get API key details."""
    ctx: UserContext | None = getattr(request.state, "user", None)
    if not ctx or not ctx.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    svc = _get_auth_svc()
    api_key = svc.get_api_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Non-admins can only see their own keys
    from spiderfoot.rbac import has_permission
    if api_key.user_id != ctx.user_id and not has_permission(ctx.role, "user:read"):
        raise HTTPException(status_code=403, detail="Access denied")

    return api_key.to_dict()


@router.patch("/api-keys/{key_id}")
async def update_api_key(
    key_id: str,
    body: UpdateApiKeyRequest,
    user: UserContext = Depends(require_permission("user:update")),
):
    """Update an API key (admin only)."""
    svc = _get_auth_svc()
    updates = body.model_dump(exclude_none=True)
    try:
        api_key = svc.update_api_key(key_id, updates)
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return api_key.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api-keys/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    request: Request,
):
    """Delete an API key. Users can delete their own; admins can delete any."""
    ctx: UserContext | None = getattr(request.state, "user", None)
    if not ctx or not ctx.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    svc = _get_auth_svc()
    api_key = svc.get_api_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    from spiderfoot.rbac import has_permission
    if api_key.user_id != ctx.user_id and not has_permission(ctx.role, "user:delete"):
        raise HTTPException(status_code=403, detail="Access denied")

    svc.delete_api_key(key_id)


@router.post("/api-keys/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    request: Request,
):
    """Revoke an API key. Users can revoke their own; admins can revoke any."""
    ctx: UserContext | None = getattr(request.state, "user", None)
    if not ctx or not ctx.user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    svc = _get_auth_svc()
    api_key = svc.get_api_key(key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    from spiderfoot.rbac import has_permission
    if api_key.user_id != ctx.user_id and not has_permission(ctx.role, "user:update"):
        raise HTTPException(status_code=403, detail="Access denied")

    svc.revoke_api_key(key_id)
    return {"message": "API key revoked"}


# ═══════════════════════════════════════════════════════════
# SSO PROVIDER MANAGEMENT (admin only)
# ═══════════════════════════════════════════════════════════

@router.get("/sso/providers")
async def list_sso_providers():
    """List configured SSO providers (public — for login page)."""
    svc = _get_auth_svc()
    providers = svc.list_sso_providers()
    return {
        "items": [p.to_dict(include_secrets=False) for p in providers if p.enabled],
    }


@router.get("/sso/providers/all")
async def list_all_sso_providers(
    user: UserContext = Depends(require_permission("config:write")),
):
    """List all SSO providers including disabled (admin only)."""
    svc = _get_auth_svc()
    providers = svc.list_sso_providers()
    return {"items": [p.to_dict(include_secrets=True) for p in providers]}


@router.post("/sso/providers", status_code=201)
async def create_sso_provider(
    body: SSOProviderRequest,
    user: UserContext = Depends(require_permission("config:write")),
):
    """Create an SSO provider (admin only)."""
    svc = _get_auth_svc()
    provider = svc.create_sso_provider(body.model_dump())
    return provider.to_dict(include_secrets=True)


@router.get("/sso/providers/{provider_id}")
async def get_sso_provider(
    provider_id: str,
    user: UserContext = Depends(require_permission("config:read")),
):
    """Get SSO provider details (admin only)."""
    svc = _get_auth_svc()
    provider = svc.get_sso_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider.to_dict(include_secrets=True)


@router.patch("/sso/providers/{provider_id}")
async def update_sso_provider(
    provider_id: str,
    body: dict,
    user: UserContext = Depends(require_permission("config:write")),
):
    """Update an SSO provider (admin only)."""
    svc = _get_auth_svc()
    provider = svc.update_sso_provider(provider_id, body)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider.to_dict(include_secrets=True)


@router.delete("/sso/providers/{provider_id}", status_code=204)
async def delete_sso_provider(
    provider_id: str,
    user: UserContext = Depends(require_permission("config:write")),
):
    """Delete an SSO provider (admin only)."""
    svc = _get_auth_svc()
    if not svc.delete_sso_provider(provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")


# ═══════════════════════════════════════════════════════════
# SSO LOGIN FLOWS
# ═══════════════════════════════════════════════════════════

@router.get("/sso/oauth2/login/{provider_id}")
async def oauth2_login(provider_id: str, request: Request):
    """Initiate OAuth2/OIDC login — redirects to the IdP authorization page."""
    svc = _get_auth_svc()
    provider = svc.get_sso_provider(provider_id)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=404, detail="Provider not found or disabled")
    if provider.protocol != "oauth2":
        raise HTTPException(status_code=400, detail="Not an OAuth2 provider")

    state = secrets.token_urlsafe(32)

    # Store state in Redis for CSRF validation in callback
    r = _get_redis()
    if r:
        try:
            r.setex(f"{_OAUTH2_STATE_PREFIX}{state}", _OAUTH2_STATE_TTL, provider_id)
        except Exception as e:
            log.warning("Failed to store OAuth2 state in Redis: %s", e)

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/auth/sso/callback/{provider_id}"

    url = svc.get_oauth2_login_url(provider, redirect_uri, state)
    return RedirectResponse(url=url, status_code=302)


@router.get("/sso/callback/{provider_id}")
async def oauth2_callback(
    provider_id: str,
    code: str = Query(...),
    state: str = Query(default=""),
    request: Request = None,
):
    """OAuth2/OIDC callback — exchange code for tokens."""
    svc = _get_auth_svc()
    provider = svc.get_sso_provider(provider_id)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Validate OAuth2 state parameter (CSRF protection)
    r = _get_redis()
    if r and state:
        try:
            stored = r.get(f"{_OAUTH2_STATE_PREFIX}{state}")
            r.delete(f"{_OAUTH2_STATE_PREFIX}{state}")  # one-time use
            if stored is None:
                log.warning("OAuth2 state expired or invalid: %s", state[:8])
                return RedirectResponse(
                    url="/login?error=OAuth2+state+expired+or+invalid.+Please+try+again.",
                    status_code=302,
                )
            if stored != provider_id:
                log.warning("OAuth2 state provider mismatch: expected=%s got=%s", stored, provider_id)
                return RedirectResponse(
                    url="/login?error=OAuth2+state+mismatch", status_code=302,
                )
        except Exception as e:
            log.warning("Redis state check failed (allowing request): %s", e)
    elif r and not state:
        log.warning("OAuth2 callback missing state parameter — possible CSRF")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/auth/sso/callback/{provider_id}"

    try:
        # Exchange code for tokens and get user info
        result = await svc.exchange_oauth2_code(provider, code, redirect_uri)
        userinfo = result.get("userinfo", {})

        # Find or create user
        user = svc.process_oauth2_userinfo(provider, userinfo)

        # Issue JWT tokens
        access_token = svc.create_access_token(user)
        refresh_token = svc.create_refresh_token(user)

        client = _get_client_info(request)
        svc._create_session(
            user, access_token,
            client["ip_address"], client["user_agent"], "oauth2"
        )

        # Redirect to frontend with token
        return RedirectResponse(
            url=f"/?access_token={access_token}&refresh_token={refresh_token}",
            status_code=302,
        )
    except Exception as e:
        log.error("OAuth2 callback error: %s", e)
        return RedirectResponse(url=f"/login?error={str(e)}", status_code=302)


@router.post("/sso/saml/acs/{provider_id}")
async def saml_acs(provider_id: str, request: Request):
    """SAML Assertion Consumer Service — process SAML response."""
    svc = _get_auth_svc()
    provider = svc.get_sso_provider(provider_id)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=404, detail="Provider not found")

    form = await request.form()
    saml_response = form.get("SAMLResponse", "")
    if not saml_response:
        raise HTTPException(status_code=400, detail="Missing SAMLResponse")

    try:
        attrs = svc.process_saml_response(provider, saml_response)
        email = attrs.get("email", "")
        name = attrs.get("name", "")
        subject = attrs.get("subject", email)

        # Find or create user
        user_obj = svc.get_user_by_sso(provider.id, subject)
        if not user_obj:
            user_obj = svc.get_user_by_email(email)

        if not user_obj:
            if not provider.auto_create_users:
                raise ValueError("User not found and auto-creation is disabled")
            username = email.split("@")[0] if email else f"saml_{subject}"
            if svc.get_user_by_username(username):
                username = f"{username}_{secrets.token_hex(4)}"
            user_obj = svc.create_user(
                username=username,
                email=email,
                role=provider.default_role,
                display_name=name or username,
                auth_method="saml",
                sso_provider_id=provider.id,
                sso_subject=subject,
            )

        access_token = svc.create_access_token(user_obj)
        refresh_token = svc.create_refresh_token(user_obj)

        client = _get_client_info(request)
        svc._create_session(
            user_obj, access_token,
            client["ip_address"], client["user_agent"], "saml"
        )

        from fastapi.responses import RedirectResponse as _Redir
        return _Redir(
            url=f"/?access_token={access_token}&refresh_token={refresh_token}",
            status_code=302,
        )
    except Exception as e:
        log.error("SAML ACS error: %s", e)
        from fastapi.responses import RedirectResponse as _Redir
        return _Redir(url=f"/login?error={str(e)}", status_code=302)


@router.get("/sso/saml/login/{provider_id}")
async def saml_login(provider_id: str, request: Request):
    """Initiate SAML login — redirects to IdP SSO URL."""
    svc = _get_auth_svc()
    provider = svc.get_sso_provider(provider_id)
    if not provider or not provider.enabled:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider.protocol != "saml":
        raise HTTPException(status_code=400, detail="Not a SAML provider")

    base_url = str(request.base_url).rstrip("/")
    acs_url = f"{base_url}/api/auth/sso/saml/acs/{provider_id}"
    url = svc.get_saml_login_url(provider, acs_url)
    return RedirectResponse(url=url, status_code=302)
