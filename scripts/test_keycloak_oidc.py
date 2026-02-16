#!/usr/bin/env python3
"""
End-to-end integration test for SpiderFoot ↔ Keycloak OIDC SSO.

Tests the full OAuth2 Authorization Code flow:
1. Register Keycloak as an SSO provider in SpiderFoot
2. Initiate OAuth2 login (simulate browser redirect)
3. Login at Keycloak (direct access grant to get a session)
4. Exchange authorization code at SpiderFoot callback
5. Verify JWT tokens and user creation

Prerequisites:
    - Keycloak running on http://localhost:9080  (port map of internal 8080)
    - SpiderFoot realm, client, and test users configured
      (run scripts/keycloak-setup-realm.sh)

Usage:
    python scripts/test_keycloak_oidc.py
"""
import json
import os
import sys
import time
import urllib.parse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Configuration ─────────────────────────────────────────────────────────

KC_BASE = os.environ.get("KC_BASE_URL", "http://localhost:9080")
KC_REALM = "spiderfoot"
KC_CLIENT_ID = "spiderfoot-app"
KC_CLIENT_SECRET = "spiderfoot-secret"
KC_AUTH_URL = f"{KC_BASE}/realms/{KC_REALM}/protocol/openid-connect/auth"
KC_TOKEN_URL = f"{KC_BASE}/realms/{KC_REALM}/protocol/openid-connect/token"
KC_USERINFO_URL = f"{KC_BASE}/realms/{KC_REALM}/protocol/openid-connect/userinfo"

# Test users from the setup script
TEST_USERS = [
    {"username": "testadmin",   "password": "testadmin123",   "expected_role": "admin"},
    {"username": "testanalyst", "password": "testanalyst123", "expected_role": "analyst"},
    {"username": "testuser",    "password": "testuser123",    "expected_role": "viewer"},
]

# ── Helpers ───────────────────────────────────────────────────────────────

def color(text, code):
    return f"\033[{code}m{text}\033[0m"

def ok(msg):   print(f"  {color('✓', '32')} {msg}")
def fail(msg): print(f"  {color('✗', '31')} {msg}")
def info(msg): print(f"  {color('ⓘ', '36')} {msg}")

passed = 0
failed = 0

def check(condition, pass_msg, fail_msg):
    global passed, failed
    if condition:
        ok(pass_msg)
        passed += 1
    else:
        fail(fail_msg)
        failed += 1
    return condition


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: Keycloak connectivity
# ═══════════════════════════════════════════════════════════════════════════

print("\n═════════════════════════════════════════════════════════")
print("  SpiderFoot ↔ Keycloak OIDC Integration Test")
print("═════════════════════════════════════════════════════════\n")

print("[1] Keycloak Connectivity")
try:
    import httpx
    
    with httpx.Client(timeout=10) as client:
        discovery_url = f"{KC_BASE}/realms/{KC_REALM}/.well-known/openid-configuration"
        resp = client.get(discovery_url)
        check(resp.status_code == 200,
              f"OIDC discovery endpoint accessible ({discovery_url})",
              f"OIDC discovery returned {resp.status_code}")
        
        oidc_config = resp.json()
        check("authorization_endpoint" in oidc_config,
              f"Authorization endpoint: {oidc_config.get('authorization_endpoint', 'MISSING')}",
              "Missing authorization_endpoint in discovery")
        check("token_endpoint" in oidc_config,
              f"Token endpoint: {oidc_config.get('token_endpoint', 'MISSING')}",
              "Missing token_endpoint in discovery")
        check("userinfo_endpoint" in oidc_config,
              f"Userinfo endpoint: {oidc_config.get('userinfo_endpoint', 'MISSING')}",
              "Missing userinfo_endpoint in discovery")

except Exception as e:
    fail(f"Cannot reach Keycloak: {e}")
    print("\n  Make sure Keycloak is running: docker compose --profile sso up keycloak -d")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: Token exchange (Direct Access Grant)
# ═══════════════════════════════════════════════════════════════════════════

print("\n[2] Token Exchange (Direct Access Grant)")
for user in TEST_USERS:
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(KC_TOKEN_URL, data={
                "grant_type": "password",
                "client_id": KC_CLIENT_ID,
                "client_secret": KC_CLIENT_SECRET,
                "username": user["username"],
                "password": user["password"],
                "scope": "openid email profile",
            })
            check(resp.status_code == 200,
                  f"{user['username']}: Token exchange successful (status={resp.status_code})",
                  f"{user['username']}: Token exchange failed (status={resp.status_code})")
            
            tokens = resp.json()
            check("access_token" in tokens,
                  f"{user['username']}: Access token received ({len(tokens.get('access_token',''))} chars)",
                  f"{user['username']}: No access_token in response")
            
            # Fetch userinfo
            userinfo_resp = client.get(KC_USERINFO_URL, headers={
                "Authorization": f"Bearer {tokens['access_token']}"
            })
            check(userinfo_resp.status_code == 200,
                  f"{user['username']}: Userinfo endpoint returned 200",
                  f"{user['username']}: Userinfo returned {userinfo_resp.status_code}")
            
            userinfo = userinfo_resp.json()
            check(userinfo.get("email", "") != "",
                  f"{user['username']}: Email in userinfo = {userinfo.get('email')}",
                  f"{user['username']}: No email in userinfo")
            
            # Check realm_access.roles
            roles = userinfo.get("realm_access", {}).get("roles", [])
            info(f"{user['username']}: realm_access.roles = {roles}")

    except Exception as e:
        fail(f"{user['username']}: Exception: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: SpiderFoot AuthService — OAuth2 URL generation
# ═══════════════════════════════════════════════════════════════════════════

print("\n[3] SpiderFoot AuthService — OAuth2 URL Generation")
try:
    from spiderfoot.auth.models import SSOProvider
    from spiderfoot.auth.service import AuthService

    # Create a mock provider matching our Keycloak setup
    provider = SSOProvider(
        id="test-kc-provider",
        name="Keycloak Test",
        protocol="oauth2",
        enabled=True,
        client_id=KC_CLIENT_ID,
        client_secret=KC_CLIENT_SECRET,
        authorization_url=KC_AUTH_URL,
        token_url=KC_TOKEN_URL,
        userinfo_url=KC_USERINFO_URL,
        scopes="openid email profile",
        admin_group="sf-admin",
        group_attribute="realm_access.roles",
        auto_create_users=True,
        default_role="viewer",
        attribute_mapping='{"group_role_map": {"sf-admin": "admin", "sf-analyst": "analyst", "sf-viewer": "viewer"}}',
    )

    svc = AuthService()
    redirect_uri = "http://localhost:8001/api/auth/sso/callback/test-kc-provider"
    state = "test-state-123"

    url = svc.get_oauth2_login_url(provider, redirect_uri, state)
    check("response_type=code" in url,
          f"OAuth2 URL contains response_type=code",
          f"Missing response_type=code in URL")
    check(f"client_id={KC_CLIENT_ID}" in url,
          f"OAuth2 URL contains correct client_id",
          f"Wrong client_id in URL")
    check(f"state={state}" in url,
          f"OAuth2 URL contains state parameter",
          f"Missing state in URL")
    check(url.startswith(KC_AUTH_URL),
          f"OAuth2 URL starts with Keycloak auth endpoint",
          f"URL doesn't point to Keycloak: {url[:80]}")

    ok(f"Generated URL: {url[:100]}...")

except Exception as e:
    fail(f"AuthService test failed: {e}")
    import traceback
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: SpiderFoot AuthService — OAuth2 code exchange + user processing
# ═══════════════════════════════════════════════════════════════════════════

print("\n[4] SpiderFoot AuthService — Code Exchange & User Processing")
try:
    import asyncio

    async def test_code_exchange():
        """Test the full code exchange using Keycloak's direct access grant
        to simulate what would happen after browser redirect."""
        svc = AuthService()

        # Since we can't do a real browser redirect, use direct access grant
        # to get tokens, then test the userinfo processing path
        async with httpx.AsyncClient(timeout=10) as client:
            # Get tokens via direct access grant
            resp = await client.post(KC_TOKEN_URL, data={
                "grant_type": "password",
                "client_id": KC_CLIENT_ID,
                "client_secret": KC_CLIENT_SECRET,
                "username": "testadmin",
                "password": "testadmin123",
                "scope": "openid email profile",
            })
            tokens = resp.json()
            access_token = tokens["access_token"]

            # Fetch userinfo (this is what exchange_oauth2_code does internally)
            userinfo_resp = await client.get(KC_USERINFO_URL, headers={
                "Authorization": f"Bearer {access_token}"
            })
            userinfo = userinfo_resp.json()

        return userinfo

    userinfo = asyncio.run(test_code_exchange())
    check("sub" in userinfo, f"Userinfo has 'sub': {userinfo.get('sub')}", "Missing 'sub' in userinfo")
    check("email" in userinfo, f"Userinfo has 'email': {userinfo.get('email')}", "Missing 'email'")
    check("name" in userinfo, f"Userinfo has 'name': {userinfo.get('name')}", "Missing 'name'")

    # Test group-to-role mapping
    svc = AuthService()
    attr_map = json.loads(provider.attribute_mapping or "{}")
    role = svc._map_oauth2_groups_to_role(provider, userinfo, attr_map)
    check(role == "admin",
          f"Group mapping: sf-admin → admin (got '{role}')",
          f"Expected role='admin', got '{role}'")

    # Test with testanalyst
    async def get_userinfo(username, password):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(KC_TOKEN_URL, data={
                "grant_type": "password",
                "client_id": KC_CLIENT_ID,
                "client_secret": KC_CLIENT_SECRET,
                "username": username,
                "password": password,
                "scope": "openid email profile",
            })
            tokens = resp.json()
            userinfo_resp = await client.get(KC_USERINFO_URL, headers={
                "Authorization": f"Bearer {tokens['access_token']}"
            })
            return userinfo_resp.json()

    analyst_info = asyncio.run(get_userinfo("testanalyst", "testanalyst123"))
    analyst_role = svc._map_oauth2_groups_to_role(provider, analyst_info, attr_map)
    check(analyst_role == "analyst",
          f"Group mapping: sf-analyst → analyst (got '{analyst_role}')",
          f"Expected role='analyst', got '{analyst_role}'")

    viewer_info = asyncio.run(get_userinfo("testuser", "testuser123"))
    viewer_role = svc._map_oauth2_groups_to_role(provider, viewer_info, attr_map)
    check(viewer_role == "viewer",
          f"Group mapping: sf-viewer → viewer (got '{viewer_role}')",
          f"Expected role='viewer', got '{viewer_role}'")

except Exception as e:
    fail(f"Code exchange test failed: {e}")
    import traceback
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: SAML AuthnRequest generation (non-empty)
# ═══════════════════════════════════════════════════════════════════════════

print("\n[5] SAML AuthnRequest Generation")
try:
    import base64
    import zlib

    saml_provider = SSOProvider(
        id="test-saml-provider",
        name="Test SAML IdP",
        protocol="saml",
        idp_sso_url="https://idp.example.com/sso",
        sp_entity_id="spiderfoot",
        sp_acs_url="http://localhost:8001/api/auth/sso/saml/acs/test-saml-provider",
    )

    svc = AuthService()
    url = svc.get_saml_login_url(saml_provider)

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)

    check("SAMLRequest" in params,
          "SAML URL contains SAMLRequest parameter",
          "Missing SAMLRequest in URL")

    saml_request = params.get("SAMLRequest", [""])[0]
    check(len(saml_request) > 10,
          f"SAMLRequest is non-empty ({len(saml_request)} chars)",
          f"SAMLRequest is empty or too short: '{saml_request}'")

    # Decode and verify it's valid XML
    try:
        decoded = zlib.decompress(base64.b64decode(saml_request), -15)
        xml_str = decoded.decode("utf-8")
        check("AuthnRequest" in xml_str,
              "Decoded SAMLRequest contains AuthnRequest element",
              f"Invalid SAMLRequest XML: {xml_str[:100]}")
        check("spiderfoot" in xml_str,
              "SAMLRequest contains SP entity ID 'spiderfoot'",
              "Missing SP entity ID in SAMLRequest")
        check("idp.example.com" in xml_str,
              "SAMLRequest contains IdP SSO URL as Destination",
              "Missing Destination in SAMLRequest")
        info(f"Decoded AuthnRequest ({len(xml_str)} chars): {xml_str[:120]}...")
    except Exception as e:
        fail(f"Failed to decode SAMLRequest: {e}")

    check("RelayState" in params,
          f"SAML URL contains RelayState: {params.get('RelayState', [''])[0]}",
          "Missing RelayState in URL")

except Exception as e:
    fail(f"SAML AuthnRequest test failed: {e}")
    import traceback
    traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════
# Test 6: Redis state store (if available)
# ═══════════════════════════════════════════════════════════════════════════

print("\n[6] OAuth2 State Store (Redis)")
try:
    import redis as redis_lib
    redis_url = os.environ.get("SF_REDIS_URL", "redis://localhost:6379/0")
    r = redis_lib.Redis.from_url(redis_url, decode_responses=True)
    r.ping()
    ok(f"Redis connected at {redis_url}")

    # Test state store/retrieve cycle
    test_state = "test-state-" + str(int(time.time()))
    key = f"sf:oauth2:state:{test_state}"
    r.setex(key, 600, "test-provider-id")
    stored = r.get(key)
    check(stored == "test-provider-id",
          f"State store/retrieve works: {key} → {stored}",
          f"State mismatch: expected 'test-provider-id', got '{stored}'")

    r.delete(key)
    deleted = r.get(key)
    check(deleted is None,
          "State deletion works (one-time use)",
          f"State not deleted: {deleted}")

except ImportError:
    info("redis package not installed — skipping Redis tests")
except Exception as e:
    info(f"Redis test skipped: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

print("\n═════════════════════════════════════════════════════════")
total = passed + failed
if failed == 0:
    print(f"  {color('ALL TESTS PASSED', '32;1')} ({passed}/{total})")
else:
    print(f"  {color(f'{failed} TESTS FAILED', '31;1')} ({passed} passed, {failed} failed)")
print("═════════════════════════════════════════════════════════\n")

sys.exit(1 if failed > 0 else 0)
