#!/bin/bash
# =============================================================================
# Keycloak Realm Setup for SpiderFoot SSO Testing
# =============================================================================
# Creates:
#   - Realm:  spiderfoot
#   - Client: spiderfoot-app  (OIDC confidential, authorization code flow)
#   - Roles:  sf-admin, sf-analyst, sf-viewer
#   - Users:  testadmin (sf-admin), testanalyst (sf-analyst), testuser (sf-viewer)
#
# Usage (inside the Keycloak container):
#   /bin/bash /opt/keycloak/scripts/setup-realm.sh
#
# Or from the host:
#   docker compose -f docker-compose-microservices.yml --profile sso \
#     exec keycloak /bin/bash /opt/keycloak/scripts/setup-realm.sh
# =============================================================================

set -euo pipefail

KC_HOST="${KC_HOST:-http://localhost:8080}"
KC_ADMIN="${KC_BOOTSTRAP_ADMIN_USERNAME:-admin}"
KC_PASS="${KC_BOOTSTRAP_ADMIN_PASSWORD:-admin}"
REALM="spiderfoot"
CLIENT_ID="spiderfoot-app"
CLIENT_SECRET="spiderfoot-secret"

# SpiderFoot frontend URL — used for Valid Redirect URIs
SF_BASE_URL="${SF_BASE_URL:-http://localhost:3000}"
SF_API_URL="${SF_API_URL:-https://localhost}"

# The external (browser-facing) Keycloak URL — used for authorization_url
# which the user's browser must reach.  Back-channel URLs (token, userinfo)
# use KC_HOST which is the URL reachable from the SpiderFoot API container.
KC_EXTERNAL_URL="${KC_EXTERNAL_URL:-http://localhost:9080}"

echo "═══════════════════════════════════════════════════════════"
echo "  Keycloak Realm Setup for SpiderFoot"
echo "═══════════════════════════════════════════════════════════"
echo "  Keycloak:    $KC_HOST"
echo "  Realm:       $REALM"
echo "  Client:      $CLIENT_ID"
echo "  SF Frontend: $SF_BASE_URL"
echo "  SF API:      $SF_API_URL"
echo "═══════════════════════════════════════════════════════════"

# ── Helper: kcadm wrapper ─────────────────────────────────────────────────

KCADM="/opt/keycloak/bin/kcadm.sh"

kcadm() {
    "$KCADM" "$@" 2>/dev/null
}

# ── Authenticate ──────────────────────────────────────────────────────────

echo ""
echo "[1/7] Authenticating with Keycloak admin..."
"$KCADM" config credentials \
    --server "$KC_HOST" \
    --realm master \
    --user "$KC_ADMIN" \
    --password "$KC_PASS" 2>/dev/null
echo "  ✓ Authenticated as '$KC_ADMIN'"

# ── Create realm ─────────────────────────────────────────────────────────

echo ""
echo "[2/7] Creating realm '$REALM'..."
if kcadm get "realms/$REALM" > /dev/null 2>&1; then
    echo "  ⓘ Realm '$REALM' already exists — skipping creation"
else
    kcadm create realms -s "realm=$REALM" -s enabled=true \
        -s "displayName=SpiderFoot OSINT" \
        -s registrationAllowed=false \
        -s loginWithEmailAllowed=true \
        -s duplicateEmailsAllowed=false
    echo "  ✓ Realm '$REALM' created"
fi

# ── Create realm roles ───────────────────────────────────────────────────

echo ""
echo "[3/7] Creating realm roles..."
for ROLE in sf-admin sf-analyst sf-viewer; do
    if kcadm get "roles/$ROLE" -r "$REALM" > /dev/null 2>&1; then
        echo "  ⓘ Role '$ROLE' already exists"
    else
        kcadm create roles -r "$REALM" -s "name=$ROLE" -s "description=SpiderFoot $ROLE role"
        echo "  ✓ Created role '$ROLE'"
    fi
done

# ── Create OIDC client ──────────────────────────────────────────────────

echo ""
echo "[4/7] Creating OIDC client '$CLIENT_ID'..."

# Check if client exists
EXISTING_CLIENT=$(kcadm get clients -r "$REALM" -q "clientId=$CLIENT_ID" --fields id 2>/dev/null | grep -o '"id" *: *"[^"]*"' | head -1 | grep -o '"[^"]*"$' | tr -d '"' || true)

if [ -n "$EXISTING_CLIENT" ]; then
    echo "  ⓘ Client '$CLIENT_ID' already exists (id=$EXISTING_CLIENT)"
    CLIENT_UUID="$EXISTING_CLIENT"
else
    CLIENT_UUID=$(kcadm create clients -r "$REALM" \
        -s "clientId=$CLIENT_ID" \
        -s "name=SpiderFoot App" \
        -s "description=SpiderFoot OSINT Platform — OIDC client for SSO" \
        -s enabled=true \
        -s "protocol=openid-connect" \
        -s "publicClient=false" \
        -s "secret=$CLIENT_SECRET" \
        -s "standardFlowEnabled=true" \
        -s "directAccessGrantsEnabled=true" \
        -s "serviceAccountsEnabled=false" \
        -s "authorizationServicesEnabled=false" \
        -s "redirectUris=[\"${SF_BASE_URL}/*\",\"${SF_API_URL}/*\",\"http://localhost:*/*\",\"https://localhost/*\"]" \
        -s "webOrigins=[\"${SF_BASE_URL}\",\"${SF_API_URL}\",\"http://localhost:3000\",\"https://localhost\"]" \
        -s "attributes={\"post.logout.redirect.uris\":\"${SF_BASE_URL}/*##${SF_API_URL}/*\"}" \
        --id 2>/dev/null || true)

    if [ -z "$CLIENT_UUID" ]; then
        CLIENT_UUID=$(kcadm get clients -r "$REALM" -q "clientId=$CLIENT_ID" --fields id 2>/dev/null | grep -o '"id" *: *"[^"]*"' | head -1 | grep -o '"[^"]*"$' | tr -d '"')
    fi
    echo "  ✓ Created client '$CLIENT_ID' (uuid=$CLIENT_UUID)"
fi

# ── Add client scope: include roles in userinfo ──────────────────────────

echo ""
echo "[5/7] Configuring client mappers (roles in userinfo)..."

# Create a protocol mapper to include realm roles in the userinfo endpoint
MAPPER_NAME="realm-roles-in-userinfo"
EXISTING_MAPPER=$(kcadm get "clients/$CLIENT_UUID/protocol-mappers/models" -r "$REALM" 2>/dev/null | grep -o "\"$MAPPER_NAME\"" || true)

if [ -n "$EXISTING_MAPPER" ]; then
    echo "  ⓘ Mapper '$MAPPER_NAME' already exists"
else
    kcadm create "clients/$CLIENT_UUID/protocol-mappers/models" -r "$REALM" \
        -s "name=$MAPPER_NAME" \
        -s "protocol=openid-connect" \
        -s "protocolMapper=oidc-usermodel-realm-role-mapper" \
        -s 'config."claim.name"=realm_access.roles' \
        -s 'config."jsonType.label"=String' \
        -s 'config.multivalued=true' \
        -s 'config."userinfo.token.claim"=true' \
        -s 'config."id.token.claim"=true' \
        -s 'config."access.token.claim"=true' \
        2>/dev/null || echo "  ⚠ Mapper creation returned non-zero (may already exist)"
    echo "  ✓ Mapper '$MAPPER_NAME' configured"
fi

# Also add a groups mapper if groups protocol mapper exists
GROUPS_MAPPER="groups-in-userinfo"
EXISTING_GROUPS=$(kcadm get "clients/$CLIENT_UUID/protocol-mappers/models" -r "$REALM" 2>/dev/null | grep -o "\"$GROUPS_MAPPER\"" || true)
if [ -z "$EXISTING_GROUPS" ]; then
    kcadm create "clients/$CLIENT_UUID/protocol-mappers/models" -r "$REALM" \
        -s "name=$GROUPS_MAPPER" \
        -s "protocol=openid-connect" \
        -s "protocolMapper=oidc-group-membership-mapper" \
        -s 'config."claim.name"=groups' \
        -s 'config."full.path"=false' \
        -s 'config."userinfo.token.claim"=true' \
        -s 'config."id.token.claim"=true' \
        -s 'config."access.token.claim"=true' \
        2>/dev/null || echo "  ⚠ Groups mapper not available in this Keycloak version"
    echo "  ✓ Groups mapper configured"
fi

# ── Create test users ────────────────────────────────────────────────────

echo ""
echo "[6/7] Creating test users..."

create_user() {
    local USERNAME="$1"
    local EMAIL="$2"
    local PASSWORD="$3"
    local ROLE="$4"
    local FIRST="$5"
    local LAST="$6"

    # Check if user exists
    EXISTING_USER=$(kcadm get users -r "$REALM" -q "username=$USERNAME" --fields id 2>/dev/null | grep -o '"id" *: *"[^"]*"' | head -1 | grep -o '"[^"]*"$' | tr -d '"' || true)

    if [ -n "$EXISTING_USER" ]; then
        echo "  ⓘ User '$USERNAME' already exists (id=$EXISTING_USER)"
        USER_UUID="$EXISTING_USER"
    else
        USER_UUID=$(kcadm create users -r "$REALM" \
            -s "username=$USERNAME" \
            -s "email=$EMAIL" \
            -s enabled=true \
            -s emailVerified=true \
            -s "firstName=$FIRST" \
            -s "lastName=$LAST" \
            --id 2>/dev/null || true)

        if [ -z "$USER_UUID" ]; then
            USER_UUID=$(kcadm get users -r "$REALM" -q "username=$USERNAME" --fields id 2>/dev/null | grep -o '"id" *: *"[^"]*"' | head -1 | grep -o '"[^"]*"$' | tr -d '"')
        fi

        # Set password
        kcadm set-password -r "$REALM" --username "$USERNAME" --new-password "$PASSWORD" 2>/dev/null
        echo "  ✓ Created user '$USERNAME' (email=$EMAIL, password=$PASSWORD)"
    fi

    # Assign realm role
    kcadm add-roles -r "$REALM" --uusername "$USERNAME" --rolename "$ROLE" 2>/dev/null || true
    echo "    → Assigned role '$ROLE'"
}

create_user "testadmin"   "admin@spiderfoot.test"   "testadmin123"   "sf-admin"   "Test" "Admin"
create_user "testanalyst" "analyst@spiderfoot.test" "testanalyst123" "sf-analyst" "Test" "Analyst"
create_user "testuser"    "user@spiderfoot.test"    "testuser123"    "sf-viewer"  "Test" "User"

# ── Summary ──────────────────────────────────────────────────────────────

echo ""
echo "[7/7] Setup complete!"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Keycloak Realm Configuration Summary"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  OIDC Discovery URL:"
echo "    ${KC_EXTERNAL_URL}/realms/${REALM}/.well-known/openid-configuration"
echo ""
echo "  Client ID:      $CLIENT_ID"
echo "  Client Secret:  $CLIENT_SECRET"
echo ""
echo "  Authorization (external): ${KC_EXTERNAL_URL}/realms/${REALM}/protocol/openid-connect/auth"
echo "  Token URL      (internal): ${KC_HOST}/realms/${REALM}/protocol/openid-connect/token"
echo "  Userinfo URL   (internal): ${KC_HOST}/realms/${REALM}/protocol/openid-connect/userinfo"
echo "  JWKS URI       (internal): ${KC_HOST}/realms/${REALM}/protocol/openid-connect/certs"
echo ""
echo "  Test Users:"
echo "    testadmin   / testadmin123   (sf-admin)"
echo "    testanalyst / testanalyst123 (sf-analyst)"
echo "    testuser    / testuser123    (sf-viewer)"
echo ""
echo "  ── SpiderFoot SSO Provider Config ──"
echo "  In SpiderFoot → Settings → SSO, create an OAuth2 provider:"
echo "    Name:              Keycloak"
echo "    Protocol:          oauth2"
echo "    Client ID:         $CLIENT_ID"
echo "    Client Secret:     $CLIENT_SECRET"
echo "    Authorization URL: ${KC_EXTERNAL_URL}/realms/${REALM}/protocol/openid-connect/auth"
echo "    Token URL:         ${KC_HOST}/realms/${REALM}/protocol/openid-connect/token"
echo "    Userinfo URL:      ${KC_HOST}/realms/${REALM}/protocol/openid-connect/userinfo"
echo "    JWKS URI:          ${KC_HOST}/realms/${REALM}/protocol/openid-connect/certs"
echo "    Scopes:            openid email profile"
echo "    Admin Group:       sf-admin"
echo "    Group Attribute:   realm_access.roles"
echo ""
echo "  NOTE: authorization_url is the EXTERNAL URL (browser-facing)."
echo "        token_url / userinfo_url / jwks_uri are INTERNAL (API→Keycloak)."
echo ""
echo "  ── Group → Role Mapping ──"
echo "    sf-admin   → admin"
echo "    sf-analyst → analyst"
echo "    sf-viewer  → viewer"
echo "  Set attribute_mapping JSON to:"
echo '    {"group_role_map": {"sf-admin": "admin", "sf-analyst": "analyst", "sf-viewer": "viewer"}}'
echo ""
echo "═══════════════════════════════════════════════════════════"
