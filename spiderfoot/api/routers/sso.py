"""
SSO / SAML API router — enterprise single sign-on endpoints.

Endpoints for IdP management, SAML/OIDC login flows,
session management, and SP metadata.

v5.7.1
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import Any

from spiderfoot.sso_integration import SSOManager, SSOProtocol, SSOProviderStatus

router = APIRouter()

_manager = SSOManager()


# -------------------------------------------------------------------
# Pydantic schemas
# -------------------------------------------------------------------

class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    protocol: str = Field("saml2", description="saml2 or oidc")
    tenant_id: str = ""

    # SAML
    entity_id: str = ""
    sso_url: str = ""
    slo_url: str = ""
    certificate: str = ""
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    sign_requests: bool = True

    # OIDC
    client_id: str = ""
    client_secret: str = ""
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    jwks_uri: str = ""
    scopes: list[str] = Field(default_factory=lambda: ["openid", "profile", "email"])

    # Attribute mapping
    attr_email: str = "email"
    attr_name: str = "displayName"
    attr_groups: str = "groups"
    attr_role: str = "role"

    # JIT
    jit_enabled: bool = True
    default_role: str = "viewer"
    allowed_domains: list[str] = Field(default_factory=list)


class ProviderUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    sso_url: str | None = None
    slo_url: str | None = None
    certificate: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    authorization_url: str | None = None
    token_url: str | None = None
    jit_enabled: bool | None = None
    default_role: str | None = None
    allowed_domains: list[str] | None = None


class SAMLResponseBody(BaseModel):
    saml_response: str = Field(..., description="Base64-encoded SAML Response")


class OIDCCallbackBody(BaseModel):
    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="State parameter")


# -------------------------------------------------------------------
# Provider CRUD
# -------------------------------------------------------------------

@router.get("/sso/providers", tags=["sso"])
async def list_providers(
    tenant_id: str | None = Query(None),
    protocol: str | None = Query(None),
    active_only: bool = Query(False),
):
    """List SSO identity providers."""
    providers = _manager.list_providers(
        tenant_id=tenant_id, protocol=protocol, active_only=active_only,
    )
    return {"providers": [p.to_dict() for p in providers]}


@router.post("/sso/providers", tags=["sso"], status_code=201)
async def create_provider(body: ProviderCreate):
    """Register a new SSO identity provider."""
    try:
        SSOProtocol(body.protocol)
    except ValueError:
        raise HTTPException(400, f"Invalid protocol: {body.protocol}")

    provider = _manager.create_provider(body.model_dump())
    return {"provider": provider.to_dict()}


@router.get("/sso/providers/{provider_id}", tags=["sso"])
async def get_provider(provider_id: str):
    """Get SSO provider details."""
    p = _manager.get_provider(provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    return p.to_dict()


@router.patch("/sso/providers/{provider_id}", tags=["sso"])
async def update_provider(provider_id: str, body: ProviderUpdate):
    """Update an SSO provider."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    p = _manager.update_provider(provider_id, updates)
    if not p:
        raise HTTPException(404, "Provider not found")
    return {"updated": p.to_dict()}


@router.delete("/sso/providers/{provider_id}", tags=["sso"])
async def delete_provider(provider_id: str):
    """Delete an SSO provider."""
    if not _manager.delete_provider(provider_id):
        raise HTTPException(404, "Provider not found")
    return {"deleted": provider_id}


# -------------------------------------------------------------------
# Authentication flows
# -------------------------------------------------------------------

@router.get("/sso/saml/login/{provider_id}", tags=["sso"])
async def saml_login(provider_id: str):
    """Initiate SAML SSO login — redirects to IdP."""
    result = _manager.initiate_saml_login(provider_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sso/saml/acs/{provider_id}", tags=["sso"])
async def saml_acs(provider_id: str, body: SAMLResponseBody):
    """SAML Assertion Consumer Service — process IdP response."""
    result = _manager.process_saml_response(provider_id, body.saml_response)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(400, result["error"])
    return {"session": result.to_dict()}


@router.get("/sso/saml/metadata/{provider_id}", tags=["sso"])
async def saml_metadata(provider_id: str):
    """Get SAML SP metadata for IdP configuration."""
    meta = _manager.get_sp_metadata(provider_id)
    if "error" in meta:
        raise HTTPException(404, meta["error"])
    return meta


@router.get("/sso/oidc/login/{provider_id}", tags=["sso"])
async def oidc_login(provider_id: str):
    """Initiate OIDC login — returns authorization URL."""
    result = _manager.initiate_oidc_login(provider_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/sso/oidc/callback/{provider_id}", tags=["sso"])
async def oidc_callback(provider_id: str, body: OIDCCallbackBody):
    """Handle OIDC authorization code callback."""
    result = _manager.process_oidc_callback(provider_id, body.code, body.state)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(400, result["error"])
    return {"session": result.to_dict()}


# -------------------------------------------------------------------
# Session management
# -------------------------------------------------------------------

@router.get("/sso/sessions", tags=["sso"])
async def list_sessions(active_only: bool = Query(True)):
    """List SSO sessions."""
    sessions = _manager.list_sessions(active_only=active_only)
    return {"sessions": [s.to_dict() for s in sessions]}


@router.get("/sso/sessions/{session_id}", tags=["sso"])
async def get_session(session_id: str):
    """Get an SSO session."""
    s = _manager.get_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s.to_dict()


@router.delete("/sso/sessions/{session_id}", tags=["sso"])
async def revoke_session(session_id: str):
    """Revoke an SSO session."""
    if not _manager.revoke_session(session_id):
        raise HTTPException(404, "Session not found")
    return {"revoked": session_id}


# -------------------------------------------------------------------
# Statistics
# -------------------------------------------------------------------

@router.get("/sso/stats", tags=["sso"])
async def sso_stats():
    """SSO usage statistics."""
    return _manager.get_stats()


@router.get("/sso/protocols", tags=["sso"])
async def list_protocols():
    """List supported SSO protocols."""
    return {
        "protocols": [
            {"id": "saml2", "name": "SAML 2.0",
             "description": "Security Assertion Markup Language — enterprise SSO standard"},
            {"id": "oidc", "name": "OpenID Connect",
             "description": "OAuth 2.0 based identity layer — modern SSO protocol"},
        ]
    }
