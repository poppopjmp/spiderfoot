"""
SSO / SAML Integration — enterprise single sign-on support.

Provides:
  - SAML 2.0 SP (Service Provider) configuration
  - OIDC (OpenID Connect) provider support
  - SSO session management with IdP metadata
  - JIT (just-in-time) user provisioning
  - Attribute mapping for role and tenant assignment
  - Multi-IdP support for multi-tenant deployments

v5.7.1
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
from urllib.parse import urlencode

_log = logging.getLogger("spiderfoot.sso")


class SSOProtocol(str, Enum):
    SAML2 = "saml2"
    OIDC = "oidc"


class SSOProviderStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    TESTING = "testing"


@dataclass
class SSOProvider:
    """An SSO identity provider configuration."""
    provider_id: str = ""
    name: str = ""
    protocol: str = SSOProtocol.SAML2.value
    status: str = SSOProviderStatus.ACTIVE.value
    tenant_id: str = ""  # Bind to specific tenant (empty = global)

    # SAML settings
    entity_id: str = ""           # IdP Entity ID
    sso_url: str = ""             # IdP SSO endpoint
    slo_url: str = ""             # IdP SLO endpoint (optional)
    certificate: str = ""         # IdP x509 cert (PEM)
    sp_entity_id: str = ""        # Our SP Entity ID
    sp_acs_url: str = ""          # Assertion Consumer Service URL
    name_id_format: str = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    sign_requests: bool = True
    want_assertions_signed: bool = True

    # OIDC settings
    client_id: str = ""
    client_secret: str = ""       # Stored encrypted in production
    authorization_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    jwks_uri: str = ""
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])

    # Attribute mapping
    attr_email: str = "email"
    attr_name: str = "displayName"
    attr_groups: str = "groups"
    attr_role: str = "role"

    # JIT provisioning
    jit_enabled: bool = True      # Auto-create users on first login
    default_role: str = "viewer"
    allowed_domains: list[str] = field(default_factory=list)  # Restrict to email domains

    # Metadata
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        # Mask secrets
        if d.get("client_secret"):
            d["client_secret"] = "***"
        if d.get("certificate") and len(d["certificate"]) > 40:
            d["certificate"] = d["certificate"][:20] + "...REDACTED"
        return d


@dataclass
class SSOSession:
    """An SSO-authenticated session."""
    session_id: str = ""
    provider_id: str = ""
    protocol: str = ""
    user_email: str = ""
    user_name: str = ""
    groups: list[str] = field(default_factory=list)
    role: str = ""
    tenant_id: str = ""
    name_id: str = ""          # SAML NameID or OIDC sub
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    expires_at: float = 0.0
    is_active: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class SSOManager:
    """Manage SSO providers, authentication flows, and sessions.

    Supports SAML 2.0 and OpenID Connect identity providers
    with multi-tenant binding and JIT user provisioning.
    """

    SESSION_TTL = 28800  # 8 hours default

    def __init__(self, redis_client=None, base_url: str = "https://localhost:5001"):
        self._redis = redis_client
        self._base_url = base_url
        self._providers: dict[str, SSOProvider] = {}
        self._sessions: dict[str, SSOSession] = {}

    # ── Provider CRUD ─────────────────────────────────────────────────

    def create_provider(self, config: dict) -> SSOProvider:
        """Register a new SSO identity provider."""
        p = SSOProvider(**{
            k: v for k, v in config.items()
            if k in SSOProvider.__dataclass_fields__
        })
        if not p.provider_id:
            p.provider_id = str(uuid.uuid4())[:12]
        p.created_at = time.time()
        p.updated_at = time.time()

        # Auto-fill SP settings for SAML
        if p.protocol == SSOProtocol.SAML2.value:
            if not p.sp_entity_id:
                p.sp_entity_id = f"{self._base_url}/api/sso/saml/metadata/{p.provider_id}"
            if not p.sp_acs_url:
                p.sp_acs_url = f"{self._base_url}/api/sso/saml/acs/{p.provider_id}"

        self._providers[p.provider_id] = p
        self._persist_provider(p)
        _log.info("SSO provider created: %s (%s, %s)", p.name, p.provider_id, p.protocol)
        return p

    def get_provider(self, provider_id: str) -> SSOProvider | None:
        return self._providers.get(provider_id)

    def list_providers(
        self,
        tenant_id: str | None = None,
        protocol: str | None = None,
        active_only: bool = False,
    ) -> list[SSOProvider]:
        providers = list(self._providers.values())
        if tenant_id is not None:
            providers = [p for p in providers
                        if p.tenant_id == tenant_id or p.tenant_id == ""]
        if protocol:
            providers = [p for p in providers if p.protocol == protocol]
        if active_only:
            providers = [p for p in providers
                        if p.status == SSOProviderStatus.ACTIVE.value]
        return providers

    def update_provider(self, provider_id: str, updates: dict) -> SSOProvider | None:
        p = self._providers.get(provider_id)
        if not p:
            return None
        updates.pop("provider_id", None)
        updates.pop("created_at", None)
        updates["updated_at"] = time.time()
        for k, v in updates.items():
            if hasattr(p, k):
                setattr(p, k, v)
        self._persist_provider(p)
        return p

    def delete_provider(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            del self._providers[provider_id]
            if self._redis:
                try:
                    self._redis.hdel("sf:sso:providers", provider_id)
                except Exception:
                    pass
            return True
        return False

    # ── Authentication flows ──────────────────────────────────────────

    def initiate_saml_login(self, provider_id: str) -> dict:
        """Build a SAML AuthnRequest redirect URL.

        Returns a dict with 'redirect_url' and 'request_id'.
        """
        p = self._providers.get(provider_id)
        if not p or p.protocol != SSOProtocol.SAML2.value:
            return {"error": "SAML provider not found"}

        request_id = f"_sf_{uuid.uuid4().hex[:24]}"
        # In production, this would generate a real SAML AuthnRequest XML
        # Here we build the redirect URL structure
        params = {
            "SAMLRequest": self._build_saml_authn_stub(p, request_id),
            "RelayState": f"{self._base_url}/api/sso/callback",
        }
        redirect_url = f"{p.sso_url}?{urlencode(params)}"

        return {
            "redirect_url": redirect_url,
            "request_id": request_id,
            "provider_id": provider_id,
        }

    def initiate_oidc_login(self, provider_id: str) -> dict:
        """Build an OIDC authorization URL.

        Returns a dict with 'redirect_url' and 'state'.
        """
        p = self._providers.get(provider_id)
        if not p or p.protocol != SSOProtocol.OIDC.value:
            return {"error": "OIDC provider not found"}

        state = uuid.uuid4().hex[:32]
        nonce = uuid.uuid4().hex[:32]
        redirect_uri = f"{self._base_url}/api/sso/oidc/callback/{provider_id}"

        params = {
            "response_type": "code",
            "client_id": p.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(p.scopes),
            "state": state,
            "nonce": nonce,
        }
        redirect_url = f"{p.authorization_url}?{urlencode(params)}"

        return {
            "redirect_url": redirect_url,
            "state": state,
            "nonce": nonce,
            "provider_id": provider_id,
        }

    def process_saml_response(
        self, provider_id: str, saml_response: str,
    ) -> SSOSession | dict:
        """Process a SAML Response and create an SSO session.

        In production, this validates the XML signature and extracts
        attributes. Here we simulate attribute extraction.
        """
        p = self._providers.get(provider_id)
        if not p:
            return {"error": "Provider not found"}

        # Simulate attribute extraction from SAML Response
        # In production: parse XML, validate signature, extract NameID/attrs
        attrs = self._extract_saml_attributes_stub(saml_response, p)

        email = attrs.get(p.attr_email, "")
        name = attrs.get(p.attr_name, "")
        groups = attrs.get(p.attr_groups, [])
        role = attrs.get(p.attr_role, p.default_role)

        # Domain check
        if p.allowed_domains:
            domain = email.split("@")[-1] if "@" in email else ""
            if domain not in p.allowed_domains:
                return {"error": f"Domain '{domain}' not allowed"}

        session = self._create_session(
            provider_id=provider_id,
            protocol=SSOProtocol.SAML2.value,
            email=email,
            name=name,
            groups=groups if isinstance(groups, list) else [],
            role=role,
            tenant_id=p.tenant_id,
            name_id=attrs.get("NameID", email),
            attributes=attrs,
        )
        return session

    def process_oidc_callback(
        self, provider_id: str, code: str, state: str,
    ) -> SSOSession | dict:
        """Process an OIDC authorization code callback.

        In production: exchanges code for tokens, validates ID token,
        calls userinfo endpoint.
        """
        p = self._providers.get(provider_id)
        if not p:
            return {"error": "Provider not found"}

        # Simulate token exchange and userinfo call
        userinfo = self._oidc_userinfo_stub(code, p)

        email = userinfo.get("email", "")
        name = userinfo.get("name", userinfo.get("preferred_username", ""))
        groups = userinfo.get("groups", [])
        role = userinfo.get(p.attr_role, p.default_role)

        # Domain check
        if p.allowed_domains:
            domain = email.split("@")[-1] if "@" in email else ""
            if domain not in p.allowed_domains:
                return {"error": f"Domain '{domain}' not allowed"}

        session = self._create_session(
            provider_id=provider_id,
            protocol=SSOProtocol.OIDC.value,
            email=email,
            name=name,
            groups=groups if isinstance(groups, list) else [],
            role=role,
            tenant_id=p.tenant_id,
            name_id=userinfo.get("sub", email),
            attributes=userinfo,
        )
        return session

    # ── Session management ────────────────────────────────────────────

    def get_session(self, session_id: str) -> SSOSession | None:
        session = self._sessions.get(session_id)
        if session and session.expires_at < time.time():
            session.is_active = False
        return session

    def list_sessions(self, active_only: bool = True) -> list[SSOSession]:
        now = time.time()
        sessions = list(self._sessions.values())
        for s in sessions:
            if s.expires_at < now:
                s.is_active = False
        if active_only:
            sessions = [s for s in sessions if s.is_active]
        return sessions

    def revoke_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False
            if self._redis:
                try:
                    self._redis.hdel("sf:sso:sessions", session_id)
                except Exception:
                    pass
            return True
        return False

    def get_sp_metadata(self, provider_id: str) -> dict:
        """Generate SAML SP metadata for a provider."""
        p = self._providers.get(provider_id)
        if not p or p.protocol != SSOProtocol.SAML2.value:
            return {"error": "SAML provider not found"}

        return {
            "entityID": p.sp_entity_id,
            "assertionConsumerService": {
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                "location": p.sp_acs_url,
            },
            "nameIDFormat": p.name_id_format,
            "wantAssertionsSigned": p.want_assertions_signed,
            "authnRequestsSigned": p.sign_requests,
        }

    def get_stats(self) -> dict:
        """SSO usage statistics."""
        now = time.time()
        all_sessions = list(self._sessions.values())
        active = [s for s in all_sessions if s.is_active and s.expires_at > now]
        return {
            "total_providers": len(self._providers),
            "active_providers": sum(
                1 for p in self._providers.values()
                if p.status == SSOProviderStatus.ACTIVE.value
            ),
            "saml_providers": sum(
                1 for p in self._providers.values()
                if p.protocol == SSOProtocol.SAML2.value
            ),
            "oidc_providers": sum(
                1 for p in self._providers.values()
                if p.protocol == SSOProtocol.OIDC.value
            ),
            "total_sessions": len(all_sessions),
            "active_sessions": len(active),
        }

    # ── Private helpers ───────────────────────────────────────────────

    def _create_session(self, **kwargs) -> SSOSession:
        session = SSOSession(
            session_id=uuid.uuid4().hex[:32],
            created_at=time.time(),
            expires_at=time.time() + self.SESSION_TTL,
            is_active=True,
            **kwargs,
        )
        self._sessions[session.session_id] = session
        if self._redis:
            try:
                self._redis.hset("sf:sso:sessions", session.session_id,
                                 json.dumps(session.to_dict()))
                self._redis.expire(f"sf:sso:sessions:{session.session_id}",
                                   self.SESSION_TTL)
            except Exception:
                pass
        _log.info("SSO session created: %s (provider=%s, email=%s)",
                  session.session_id[:8], kwargs.get("provider_id", ""),
                  kwargs.get("email", ""))
        return session

    def _persist_provider(self, p: SSOProvider) -> None:
        if self._redis:
            try:
                self._redis.hset("sf:sso:providers", p.provider_id,
                                 json.dumps(asdict(p)))
            except Exception:
                pass

    @staticmethod
    def _build_saml_authn_stub(p: SSOProvider, request_id: str) -> str:
        """Build a stub SAML AuthnRequest (base64-encoded placeholder)."""
        import base64
        stub = (
            f'<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" '
            f'ID="{request_id}" Version="2.0" '
            f'AssertionConsumerServiceURL="{p.sp_acs_url}" '
            f'Destination="{p.sso_url}">'
            f'<saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">'
            f'{p.sp_entity_id}</saml:Issuer>'
            f'</samlp:AuthnRequest>'
        )
        return base64.b64encode(stub.encode()).decode()

    @staticmethod
    def _extract_saml_attributes_stub(
        saml_response: str, p: SSOProvider,
    ) -> dict:
        """Stub: extract attributes from SAML response.

        In production, parse the XML, validate signatures, and
        extract real attribute statements.
        """
        # Return simulated attributes for testing/development
        return {
            p.attr_email: "user@example.com",
            p.attr_name: "SSO User",
            p.attr_groups: ["users"],
            p.attr_role: p.default_role,
            "NameID": "user@example.com",
        }

    @staticmethod
    def _oidc_userinfo_stub(code: str, p: SSOProvider) -> dict:
        """Stub: exchange code and get userinfo.

        In production, POST to token_url with code, then GET userinfo_url.
        """
        return {
            "sub": f"oidc-{hashlib.sha256(code.encode()).hexdigest()[:12]}",
            "email": "user@example.com",
            "name": "OIDC User",
            "preferred_username": "oidcuser",
            "groups": ["users"],
            "email_verified": True,
        }
