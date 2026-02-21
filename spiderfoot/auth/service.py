# -*- coding: utf-8 -*-
"""
Core authentication service for SpiderFoot.

Handles:
- User CRUD (PostgreSQL-backed)
- Password hashing (bcrypt via passlib)
- JWT token issuance and validation
- Session management
- SSO provider CRUD
- Account lockout
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
import uuid
from typing import Any, Optional

import jwt
from passlib.hash import bcrypt

from spiderfoot.auth.models import (
    AccountStatus,
    ApiKey,
    AuthConfig,
    AuthMethod,
    Session,
    SSOProvider,
    User,
)
from spiderfoot.rbac import Role, UserContext, has_permission, parse_role

log = logging.getLogger("spiderfoot.auth")

# Module-level singleton
_auth_service: Optional["AuthService"] = None


def get_auth_service() -> "AuthService":
    """Return the global AuthService singleton, creating it if needed."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def reset_auth_service() -> None:
    """Reset the singleton (for testing)."""
    global _auth_service
    _auth_service = None


class AuthService:
    """Central auth service managing users, tokens, and sessions."""

    def __init__(self, config: AuthConfig | None = None) -> None:
        self.config = config or AuthConfig()
        self._db_conn = None
        self._db_type = "postgresql"
        self._initialized = False

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _get_conn(self):
        """Get or create a database connection."""
        if self._db_conn is not None:
            return self._db_conn

        pg_dsn = os.environ.get("SF_POSTGRES_DSN", "")
        if not pg_dsn:
            raise RuntimeError("SF_POSTGRES_DSN environment variable is required")

        import psycopg2
        self._db_conn = psycopg2.connect(pg_dsn)
        self._db_conn.autocommit = False
        self._db_type = "postgresql"

        return self._db_conn

    def _ph(self, idx: int = 1) -> str:
        """Return the PostgreSQL parameter placeholder."""
        return "%s"

    def _phs(self, count: int) -> str:
        """Return comma-separated placeholders."""
        return ", ".join([self._ph()] * count)

    def initialize(self) -> None:
        """Create auth tables and seed default admin if needed."""
        if self._initialized:
            return

        conn = self._get_conn()
        cur = conn.cursor()

        # Create tables
        for sql in self._get_schema():
            try:
                cur.execute(sql)
            except Exception as e:
                log.debug("Schema statement skipped: %s", e)

        conn.commit()

        # Seed default admin user if none exists
        self._seed_default_admin(cur, conn)
        self._initialized = True
        log.info("Auth service initialized (db=%s)", self._db_type)

    def _get_schema(self) -> list[str]:
        """Return CREATE TABLE statements for auth tables."""
        return [
                """CREATE TABLE IF NOT EXISTS tbl_users (
                    id VARCHAR(64) NOT NULL PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL DEFAULT '',
                    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
                    display_name VARCHAR(255) NOT NULL DEFAULT '',
                    auth_method VARCHAR(50) NOT NULL DEFAULT 'local',
                    status VARCHAR(50) NOT NULL DEFAULT 'active',
                    created_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    last_login DOUBLE PRECISION NOT NULL DEFAULT 0,
                    failed_logins INT NOT NULL DEFAULT 0,
                    locked_until DOUBLE PRECISION NOT NULL DEFAULT 0,
                    sso_provider_id VARCHAR(64) NOT NULL DEFAULT '',
                    sso_subject VARCHAR(255) NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )""",
                """CREATE TABLE IF NOT EXISTS tbl_sessions (
                    id VARCHAR(64) NOT NULL PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL REFERENCES tbl_users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    expires_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    ip_address VARCHAR(45) NOT NULL DEFAULT '',
                    user_agent TEXT NOT NULL DEFAULT '',
                    auth_method VARCHAR(50) NOT NULL DEFAULT 'local',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                )""",
                """CREATE TABLE IF NOT EXISTS tbl_sso_providers (
                    id VARCHAR(64) NOT NULL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    protocol VARCHAR(50) NOT NULL,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    client_id VARCHAR(255) NOT NULL DEFAULT '',
                    client_secret TEXT NOT NULL DEFAULT '',
                    authorization_url TEXT NOT NULL DEFAULT '',
                    token_url TEXT NOT NULL DEFAULT '',
                    userinfo_url TEXT NOT NULL DEFAULT '',
                    jwks_uri TEXT NOT NULL DEFAULT '',
                    scopes VARCHAR(500) NOT NULL DEFAULT 'openid email profile',
                    idp_entity_id TEXT NOT NULL DEFAULT '',
                    idp_sso_url TEXT NOT NULL DEFAULT '',
                    idp_slo_url TEXT NOT NULL DEFAULT '',
                    idp_certificate TEXT NOT NULL DEFAULT '',
                    sp_entity_id TEXT NOT NULL DEFAULT '',
                    sp_acs_url TEXT NOT NULL DEFAULT '',
                    ldap_url TEXT NOT NULL DEFAULT '',
                    ldap_bind_dn TEXT NOT NULL DEFAULT '',
                    ldap_bind_password TEXT NOT NULL DEFAULT '',
                    ldap_base_dn TEXT NOT NULL DEFAULT '',
                    ldap_user_filter VARCHAR(500) NOT NULL DEFAULT '(uid={username})',
                    ldap_group_filter VARCHAR(500) NOT NULL DEFAULT '(member={dn})',
                    ldap_tls BOOLEAN NOT NULL DEFAULT TRUE,
                    default_role VARCHAR(50) NOT NULL DEFAULT 'viewer',
                    allowed_domains TEXT NOT NULL DEFAULT '',
                    auto_create_users BOOLEAN NOT NULL DEFAULT TRUE,
                    attribute_mapping TEXT NOT NULL DEFAULT '{}',
                    group_attribute VARCHAR(255) NOT NULL DEFAULT 'groups',
                    admin_group VARCHAR(500) NOT NULL DEFAULT '',
                    created_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at DOUBLE PRECISION NOT NULL DEFAULT 0
                )""",
                """CREATE TABLE IF NOT EXISTS tbl_api_keys (
                    id VARCHAR(64) NOT NULL PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL REFERENCES tbl_users(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    key_prefix VARCHAR(16) NOT NULL,
                    key_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
                    status VARCHAR(50) NOT NULL DEFAULT 'active',
                    expires_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    allowed_modules TEXT NOT NULL DEFAULT '',
                    allowed_endpoints TEXT NOT NULL DEFAULT '',
                    rate_limit INT NOT NULL DEFAULT 0,
                    last_used DOUBLE PRECISION NOT NULL DEFAULT 0,
                    created_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at DOUBLE PRECISION NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )""",
                "CREATE INDEX IF NOT EXISTS idx_sessions_user ON tbl_sessions (user_id)",
                "CREATE INDEX IF NOT EXISTS idx_sessions_token ON tbl_sessions (token_hash)",
                "CREATE INDEX IF NOT EXISTS idx_sessions_active ON tbl_sessions (is_active, expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_users_email ON tbl_users (email)",
                "CREATE INDEX IF NOT EXISTS idx_users_sso ON tbl_users (sso_provider_id, sso_subject)",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_user ON tbl_api_keys (user_id)",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON tbl_api_keys (key_prefix)",
            ]

    def _seed_default_admin(self, cur, conn) -> None:
        """Create the default admin user if no users exist."""
        ph = self._ph()
        cur.execute("SELECT COUNT(*) FROM tbl_users")
        count = cur.fetchone()[0]
        if count > 0:
            return

        now = time.time()
        admin_id = str(uuid.uuid4())
        password = self.config.default_admin_password or "admin"
        pw_hash = bcrypt.hash(password)

        try:
            cur.execute(
                f"""INSERT INTO tbl_users
                    (id, username, email, password_hash, role, display_name,
                     auth_method, status, created_at, updated_at)
                    VALUES ({self._phs(10)})""",
                (
                    admin_id,
                    self.config.default_admin_username,
                    self.config.default_admin_email,
                    pw_hash,
                    "admin",
                    "Administrator",
                    "local",
                    "active",
                    now,
                    now,
                ),
            )
            conn.commit()
            log.info(
                "Created default admin user: %s (password: %s)",
                self.config.default_admin_username,
                "****" if self.config.default_admin_password else "admin",
            )
        except Exception:
            # Another worker may have already seeded the admin
            conn.rollback()
            log.debug("Default admin already exists (concurrent init)")

    # ------------------------------------------------------------------
    # Password hashing
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hash(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            return bcrypt.verify(password, password_hash)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # JWT tokens
    # ------------------------------------------------------------------

    def create_access_token(
        self, user: User, extra_claims: dict | None = None
    ) -> str:
        """Create a JWT access token for a user."""
        now = time.time()
        payload = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "iat": int(now),
            "exp": int(now + self.config.jwt_expiry_hours * 3600),
            "type": "access",
        }
        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(
            payload,
            self.config.jwt_secret,
            algorithm=self.config.jwt_algorithm,
        )

    def create_refresh_token(self, user: User) -> str:
        """Create a JWT refresh token for a user."""
        now = time.time()
        payload = {
            "sub": user.id,
            "type": "refresh",
            "iat": int(now),
            "exp": int(now + self.config.jwt_refresh_expiry_days * 86400),
            "jti": secrets.token_hex(16),
        }
        return jwt.encode(
            payload,
            self.config.jwt_secret,
            algorithm=self.config.jwt_algorithm,
        )

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate and decode a JWT token.

        Returns:
            Decoded payload dict.

        Raises:
            jwt.ExpiredSignatureError: Token expired.
            jwt.InvalidTokenError: Invalid token.
        """
        return jwt.decode(
            token,
            self.config.jwt_secret,
            algorithms=[self.config.jwt_algorithm],
        )

    def token_to_user_context(self, token: str) -> UserContext:
        """Decode a JWT and return a UserContext."""
        payload = self.validate_token(token)
        role = parse_role(payload.get("role", "viewer"))
        return UserContext(
            user_id=payload.get("sub", ""),
            username=payload.get("username", ""),
            email=payload.get("email", ""),
            role=role,
        )

    # ------------------------------------------------------------------
    # User CRUD
    # ------------------------------------------------------------------

    def _row_to_user(self, row: tuple) -> User:
        """Convert a database row to a User object."""
        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            password_hash=row[3],
            role=row[4],
            display_name=row[5],
            auth_method=row[6],
            status=row[7],
            created_at=row[8],
            updated_at=row[9],
            last_login=row[10],
            failed_logins=row[11],
            locked_until=row[12],
            sso_provider_id=row[13],
            sso_subject=row[14],
        )

    _USER_COLS = (
        "id, username, email, password_hash, role, display_name, "
        "auth_method, status, created_at, updated_at, last_login, "
        "failed_logins, locked_until, sso_provider_id, sso_subject"
    )

    def get_user_by_id(self, user_id: str) -> User | None:
        """Fetch a user by ID."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._USER_COLS} FROM tbl_users WHERE id = {self._ph()}",
            (user_id,),
        )
        row = cur.fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_username(self, username: str) -> User | None:
        """Fetch a user by username."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._USER_COLS} FROM tbl_users WHERE username = {self._ph()}",
            (username,),
        )
        row = cur.fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_email(self, email: str) -> User | None:
        """Fetch a user by email."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._USER_COLS} FROM tbl_users WHERE email = {self._ph()}",
            (email,),
        )
        row = cur.fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_sso(self, provider_id: str, subject: str) -> User | None:
        """Fetch a user by SSO provider and subject."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._USER_COLS} FROM tbl_users "
            f"WHERE sso_provider_id = {self._ph()} AND sso_subject = {self._ph()}",
            (provider_id, subject),
        )
        row = cur.fetchone()
        return self._row_to_user(row) if row else None

    def list_users(self, limit: int = 100, offset: int = 0) -> list[User]:
        """List all users."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._USER_COLS} FROM tbl_users "
            f"ORDER BY created_at DESC LIMIT {self._ph()} OFFSET {self._ph()}",
            (limit, offset),
        )
        return [self._row_to_user(row) for row in cur.fetchall()]

    def count_users(self) -> int:
        """Return total user count."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tbl_users")
        return cur.fetchone()[0]

    def create_user(
        self,
        username: str,
        email: str,
        password: str = "",
        role: str = "viewer",
        display_name: str = "",
        auth_method: str = "local",
        sso_provider_id: str = "",
        sso_subject: str = "",
        status: str = "active",
    ) -> User:
        """Create a new user account.

        Raises:
            ValueError: If username already exists or password too short.
        """
        # Validate role
        parse_role(role)

        # Check uniqueness
        if self.get_user_by_username(username):
            raise ValueError(f"Username '{username}' already exists")

        # Validate password for local auth
        if auth_method == "local" and password:
            if len(password) < self.config.min_password_length:
                raise ValueError(
                    f"Password must be at least {self.config.min_password_length} characters"
                )

        now = time.time()
        user_id = str(uuid.uuid4())
        pw_hash = self.hash_password(password) if password else ""

        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO tbl_users
                (id, username, email, password_hash, role, display_name,
                 auth_method, status, created_at, updated_at,
                 sso_provider_id, sso_subject)
                VALUES ({self._phs(12)})""",
            (
                user_id,
                username,
                email,
                pw_hash,
                role,
                display_name or username,
                auth_method,
                status,
                now,
                now,
                sso_provider_id,
                sso_subject,
            ),
        )
        conn.commit()

        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=pw_hash,
            role=role,
            display_name=display_name or username,
            auth_method=auth_method,
            status=status,
            created_at=now,
            updated_at=now,
            sso_provider_id=sso_provider_id,
            sso_subject=sso_subject,
        )
        log.info("Created user: %s (role=%s, method=%s)", username, role, auth_method)
        return user

    def update_user(self, user_id: str, updates: dict[str, Any]) -> User | None:
        """Update a user's fields.

        Allowed fields: email, role, display_name, status.
        """
        allowed = {"email", "role", "display_name", "status"}
        valid = {k: v for k, v in updates.items() if k in allowed}
        if not valid:
            return self.get_user_by_id(user_id)

        if "role" in valid:
            parse_role(valid["role"])

        valid["updated_at"] = time.time()

        conn = self._get_conn()
        cur = conn.cursor()
        set_clause = ", ".join(f"{k} = {self._ph()}" for k in valid)
        values = list(valid.values()) + [user_id]
        cur.execute(
            f"UPDATE tbl_users SET {set_clause} WHERE id = {self._ph()}",
            values,
        )
        conn.commit()
        return self.get_user_by_id(user_id)

    def delete_user(self, user_id: str) -> bool:
        """Delete a user and their sessions."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM tbl_sessions WHERE user_id = {self._ph()}", (user_id,)
        )
        cur.execute(
            f"DELETE FROM tbl_users WHERE id = {self._ph()}", (user_id,)
        )
        conn.commit()
        return cur.rowcount > 0

    def change_password(self, user_id: str, new_password: str) -> bool:
        """Change a user's password."""
        if len(new_password) < self.config.min_password_length:
            raise ValueError(
                f"Password must be at least {self.config.min_password_length} characters"
            )

        pw_hash = self.hash_password(new_password)
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tbl_users SET password_hash = {self._ph()}, "
            f"updated_at = {self._ph()} WHERE id = {self._ph()}",
            (pw_hash, time.time(), user_id),
        )
        conn.commit()
        return True

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate_local(self, username: str, password: str) -> User:
        """Authenticate a user with username/password.

        Raises:
            ValueError: If credentials are invalid or account is locked.
        """
        user = self.get_user_by_username(username)
        if not user:
            raise ValueError("Invalid username or password")

        if user.is_locked():
            raise ValueError("Account is locked. Try again later.")

        if user.status != AccountStatus.ACTIVE.value:
            raise ValueError("Account is not active")

        if not self.verify_password(password, user.password_hash):
            self._record_failed_login(user)
            raise ValueError("Invalid username or password")

        # Reset failed login counter on success
        self._record_successful_login(user)
        return user

    def _record_failed_login(self, user: User) -> None:
        """Increment failed login counter and lock if needed."""
        conn = self._get_conn()
        cur = conn.cursor()
        new_count = user.failed_logins + 1
        locked_until = 0.0

        if new_count >= self.config.max_failed_logins:
            locked_until = time.time() + self.config.lockout_duration_minutes * 60
            cur.execute(
                f"UPDATE tbl_users SET failed_logins = {self._ph()}, "
                f"locked_until = {self._ph()}, status = {self._ph()} "
                f"WHERE id = {self._ph()}",
                (new_count, locked_until, AccountStatus.LOCKED.value, user.id),
            )
            log.warning("User %s locked after %d failed logins", user.username, new_count)
        else:
            cur.execute(
                f"UPDATE tbl_users SET failed_logins = {self._ph()} WHERE id = {self._ph()}",
                (new_count, user.id),
            )
        conn.commit()

    def _record_successful_login(self, user: User) -> None:
        """Reset failed login counter and update last_login."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tbl_users SET failed_logins = 0, locked_until = 0, "
            f"status = {self._ph()}, last_login = {self._ph()} "
            f"WHERE id = {self._ph()}",
            (AccountStatus.ACTIVE.value, time.time(), user.id),
        )
        conn.commit()

    def login(
        self,
        username: str,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict[str, Any]:
        """Full login flow: authenticate + issue tokens + create session.

        Returns:
            Dict with access_token, refresh_token, token_type, expires_in, user.
        """
        user = self.authenticate_local(username, password)
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)

        # Create session record
        session = self._create_session(
            user, access_token, ip_address, user_agent, "local"
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.config.jwt_expiry_hours * 3600,
            "user": user.to_dict(),
        }

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Issue a new access token from a refresh token.

        Returns:
            Dict with access_token, token_type, expires_in.
        """
        payload = self.validate_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")

        user = self.get_user_by_id(payload["sub"])
        if not user or not user.is_active():
            raise ValueError("User not found or inactive")

        access_token = self.create_access_token(user)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": self.config.jwt_expiry_hours * 3600,
        }

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def _create_session(
        self,
        user: User,
        token: str,
        ip_address: str,
        user_agent: str,
        auth_method: str,
    ) -> Session:
        """Create a session record in the database."""
        now = time.time()
        session_id = str(uuid.uuid4())
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = now + self.config.session_ttl_hours * 3600

        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO tbl_sessions
                (id, user_id, token_hash, created_at, expires_at,
                 ip_address, user_agent, auth_method, is_active)
                VALUES ({self._phs(9)})""",
            (
                session_id,
                user.id,
                token_hash,
                now,
                expires_at,
                ip_address,
                user_agent,
                auth_method,
                True,
            ),
        )
        conn.commit()
        return Session(
            id=session_id,
            user_id=user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            auth_method=auth_method,
            is_active=True,
        )

    def get_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """List active sessions for a user."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, user_id, created_at, expires_at, ip_address, "
            f"user_agent, auth_method, is_active "
            f"FROM tbl_sessions WHERE user_id = {self._ph()} "
            f"AND is_active = {self._ph()} ORDER BY created_at DESC",
            (user_id, True),
        )
        return [
            {
                "id": r[0],
                "user_id": r[1],
                "created_at": r[2],
                "expires_at": r[3],
                "ip_address": r[4],
                "user_agent": r[5],
                "auth_method": r[6],
                "is_active": r[7],
            }
            for r in cur.fetchall()
        ]

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tbl_sessions SET is_active = {self._ph()} WHERE id = {self._ph()}",
            (False, session_id),
        )
        conn.commit()
        return cur.rowcount > 0

    def revoke_all_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tbl_sessions SET is_active = {self._ph()} "
            f"WHERE user_id = {self._ph()} AND is_active = {self._ph()}",
            (False, user_id, True),
        )
        conn.commit()
        return cur.rowcount

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions from the database."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM tbl_sessions WHERE expires_at < {self._ph()}",
            (time.time(),),
        )
        conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # SSO Provider CRUD
    # ------------------------------------------------------------------

    _SSO_COLS = (
        "id, name, protocol, enabled, client_id, client_secret, "
        "authorization_url, token_url, userinfo_url, jwks_uri, scopes, "
        "idp_entity_id, idp_sso_url, idp_slo_url, idp_certificate, "
        "sp_entity_id, sp_acs_url, ldap_url, ldap_bind_dn, ldap_bind_password, "
        "ldap_base_dn, ldap_user_filter, ldap_group_filter, ldap_tls, "
        "default_role, allowed_domains, auto_create_users, attribute_mapping, "
        "group_attribute, admin_group, "
        "created_at, updated_at"
    )

    def _row_to_sso_provider(self, row: tuple) -> SSOProvider:
        return SSOProvider(
            id=row[0], name=row[1], protocol=row[2], enabled=bool(row[3]),
            client_id=row[4], client_secret=row[5],
            authorization_url=row[6], token_url=row[7],
            userinfo_url=row[8], jwks_uri=row[9], scopes=row[10],
            idp_entity_id=row[11], idp_sso_url=row[12], idp_slo_url=row[13],
            idp_certificate=row[14], sp_entity_id=row[15], sp_acs_url=row[16],
            ldap_url=row[17], ldap_bind_dn=row[18], ldap_bind_password=row[19],
            ldap_base_dn=row[20], ldap_user_filter=row[21],
            ldap_group_filter=row[22], ldap_tls=bool(row[23]),
            default_role=row[24], allowed_domains=row[25],
            auto_create_users=bool(row[26]), attribute_mapping=row[27],
            group_attribute=row[28] if len(row) > 30 else "groups",
            admin_group=row[29] if len(row) > 30 else "",
            created_at=row[30] if len(row) > 30 else row[28],
            updated_at=row[31] if len(row) > 30 else row[29],
        )

    def list_sso_providers(self) -> list[SSOProvider]:
        """List all SSO providers."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT {self._SSO_COLS} FROM tbl_sso_providers ORDER BY name")
        return [self._row_to_sso_provider(r) for r in cur.fetchall()]

    def get_sso_provider(self, provider_id: str) -> SSOProvider | None:
        """Fetch an SSO provider by ID."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._SSO_COLS} FROM tbl_sso_providers WHERE id = {self._ph()}",
            (provider_id,),
        )
        row = cur.fetchone()
        return self._row_to_sso_provider(row) if row else None

    def create_sso_provider(self, data: dict[str, Any]) -> SSOProvider:
        """Create an SSO provider."""
        now = time.time()
        provider_id = str(uuid.uuid4())
        data["id"] = provider_id
        data["created_at"] = now
        data["updated_at"] = now

        # Build insert
        cols = [
            "id", "name", "protocol", "enabled", "client_id", "client_secret",
            "authorization_url", "token_url", "userinfo_url", "jwks_uri", "scopes",
            "idp_entity_id", "idp_sso_url", "idp_slo_url", "idp_certificate",
            "sp_entity_id", "sp_acs_url", "ldap_url", "ldap_bind_dn",
            "ldap_bind_password", "ldap_base_dn", "ldap_user_filter",
            "ldap_group_filter", "ldap_tls", "default_role", "allowed_domains",
            "auto_create_users", "attribute_mapping",
            "group_attribute", "admin_group",
            "created_at", "updated_at",
        ]
        defaults = {
            "enabled": True, "client_id": "", "client_secret": "",
            "authorization_url": "", "token_url": "", "userinfo_url": "",
            "jwks_uri": "", "scopes": "openid email profile",
            "idp_entity_id": "", "idp_sso_url": "", "idp_slo_url": "",
            "idp_certificate": "", "sp_entity_id": "", "sp_acs_url": "",
            "ldap_url": "", "ldap_bind_dn": "", "ldap_bind_password": "",
            "ldap_base_dn": "", "ldap_user_filter": "(uid={username})",
            "ldap_group_filter": "(member={dn})", "ldap_tls": True,
            "default_role": "viewer", "allowed_domains": "",
            "auto_create_users": True, "attribute_mapping": "{}",
            "group_attribute": "groups", "admin_group": "",
        }

        values = [data.get(c, defaults.get(c, "")) for c in cols]

        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO tbl_sso_providers ({', '.join(cols)}) VALUES ({self._phs(len(cols))})",
            values,
        )
        conn.commit()
        return self.get_sso_provider(provider_id)

    def update_sso_provider(self, provider_id: str, updates: dict[str, Any]) -> SSOProvider | None:
        """Update an SSO provider."""
        blocked = {"id", "created_at"}
        valid = {k: v for k, v in updates.items() if k not in blocked}
        if not valid:
            return self.get_sso_provider(provider_id)

        valid["updated_at"] = time.time()
        conn = self._get_conn()
        cur = conn.cursor()
        set_clause = ", ".join(f"{k} = {self._ph()}" for k in valid)
        values = list(valid.values()) + [provider_id]
        cur.execute(
            f"UPDATE tbl_sso_providers SET {set_clause} WHERE id = {self._ph()}",
            values,
        )
        conn.commit()
        return self.get_sso_provider(provider_id)

    def delete_sso_provider(self, provider_id: str) -> bool:
        """Delete an SSO provider."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM tbl_sso_providers WHERE id = {self._ph()}",
            (provider_id,),
        )
        conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # SSO: OAuth2/OIDC flow helpers
    # ------------------------------------------------------------------

    def get_oauth2_login_url(self, provider: SSOProvider, redirect_uri: str, state: str) -> str:
        """Build the OAuth2 authorization URL."""
        import urllib.parse
        params = {
            "client_id": provider.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": provider.scopes,
            "state": state,
        }
        return f"{provider.authorization_url}?{urllib.parse.urlencode(params)}"

    async def exchange_oauth2_code(
        self, provider: SSOProvider, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Exchange an OAuth2 authorization code for tokens and user info."""
        import httpx

        # Exchange code for token
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                provider.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": provider.client_id,
                    "client_secret": provider.client_secret,
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            # Fetch user info
            access_token = token_data.get("access_token", "")
            userinfo_resp = await client.get(
                provider.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()

        return {
            "access_token": access_token,
            "id_token": token_data.get("id_token", ""),
            "userinfo": userinfo,
        }

    def process_oauth2_userinfo(
        self, provider: SSOProvider, userinfo: dict
    ) -> User:
        """Find or create a user from OAuth2 userinfo.

        Supports Keycloak/Azure AD group→role mapping via provider's
        group_attribute and admin_group fields, plus attribute_mapping
        JSON with a group_role_map key.
        """
        import json
        attr_map = json.loads(provider.attribute_mapping or "{}")

        email = userinfo.get(attr_map.get("email", "email"), "")
        name = userinfo.get(attr_map.get("name", "name"), "")
        subject = userinfo.get("sub", userinfo.get("id", email))

        # Check domain restriction
        if provider.allowed_domains:
            allowed = [d.strip() for d in provider.allowed_domains.split(",")]
            domain = email.split("@")[-1] if "@" in email else ""
            if domain not in allowed:
                raise ValueError(f"Email domain '{domain}' not allowed")

        # Determine role from SSO groups
        role = self._map_oauth2_groups_to_role(provider, userinfo, attr_map)

        # Find existing user by SSO binding
        user = self.get_user_by_sso(provider.id, str(subject))
        if user:
            # Update role from group mapping if it changed
            if role != provider.default_role and user.role != role:
                self.update_user(user.id, {"role": role})
                user.role = role
            self._record_successful_login(user)
            return user

        # Find by email
        user = self.get_user_by_email(email)
        if user:
            # Bind SSO to existing user
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                f"UPDATE tbl_users SET sso_provider_id = {self._ph()}, "
                f"sso_subject = {self._ph()} WHERE id = {self._ph()}",
                (provider.id, str(subject), user.id),
            )
            conn.commit()
            # Update role from groups
            if role != provider.default_role and user.role != role:
                self.update_user(user.id, {"role": role})
                user.role = role
            return user

        # Auto-create user
        if not provider.auto_create_users:
            raise ValueError("User not found and auto-creation is disabled")

        username = email.split("@")[0] if email else f"sso_{subject}"
        # Ensure unique username
        if self.get_user_by_username(username):
            username = f"{username}_{secrets.token_hex(4)}"

        return self.create_user(
            username=username,
            email=email,
            role=role,
            display_name=name or username,
            auth_method="oauth2",
            sso_provider_id=provider.id,
            sso_subject=str(subject),
        )

    def _map_oauth2_groups_to_role(
        self, provider: SSOProvider, userinfo: dict, attr_map: dict
    ) -> str:
        """Map OAuth2/OIDC groups (Keycloak, Azure AD) to a SpiderFoot role.

        Uses three mechanisms (highest priority first):
        1. provider.admin_group — if user is in this group, role = admin
        2. attribute_mapping.group_role_map — explicit group→role mapping
        3. Falls back to provider.default_role
        """
        # Get groups from userinfo
        group_attr = provider.group_attribute or "groups"
        groups = userinfo.get(group_attr, [])
        if isinstance(groups, str):
            groups = [groups]
        if not groups:
            # Try Keycloak realm_access.roles
            realm_access = userinfo.get("realm_access", {})
            if isinstance(realm_access, dict):
                groups = realm_access.get("roles", [])

        if not groups:
            return provider.default_role

        # Check admin_group directly
        if provider.admin_group:
            admin_groups = [g.strip() for g in provider.admin_group.split(",")]
            for g in groups:
                if g in admin_groups or g.lower() in [ag.lower() for ag in admin_groups]:
                    return "admin"

        # Check group_role_map from attribute_mapping
        group_map = attr_map.get("group_role_map", {})
        if group_map:
            best_role = provider.default_role
            best_level = 0
            for group in groups:
                group_lower = group.lower()
                for pattern, role_name in group_map.items():
                    if pattern.lower() in group_lower or group_lower == pattern.lower():
                        try:
                            r = parse_role(role_name)
                            if r.level > best_level:
                                best_level = r.level
                                best_role = role_name
                        except ValueError:
                            pass
            return best_role

        return provider.default_role

    # ------------------------------------------------------------------
    # SSO: LDAP authentication
    # ------------------------------------------------------------------

    def authenticate_ldap(
        self,
        provider: SSOProvider,
        username: str,
        password: str,
    ) -> User:
        """Authenticate a user via LDAP bind.

        Raises:
            ValueError: If authentication fails.
            ImportError: If python-ldap is not installed.
        """
        try:
            import ldap3
        except ImportError:
            raise ImportError(
                "ldap3 package required for LDAP auth. "
                "Install with: pip install ldap3"
            )

        # Build user filter
        user_filter = provider.ldap_user_filter.replace("{username}", username)

        server = ldap3.Server(
            provider.ldap_url,
            use_ssl=provider.ldap_tls,
            get_info=ldap3.ALL,
        )

        # First, search for the user DN using the service account
        try:
            conn = ldap3.Connection(
                server,
                user=provider.ldap_bind_dn,
                password=provider.ldap_bind_password,
                auto_bind=True,
            )
            conn.search(
                provider.ldap_base_dn,
                user_filter,
                attributes=["uid", "mail", "cn", "displayName", "memberOf"],
            )

            if not conn.entries:
                raise ValueError("User not found in LDAP directory")

            entry = conn.entries[0]
            user_dn = entry.entry_dn
            user_email = str(entry.mail) if hasattr(entry, "mail") else ""
            user_display = str(entry.displayName) if hasattr(entry, "displayName") else str(entry.cn) if hasattr(entry, "cn") else username
            groups = [str(g) for g in entry.memberOf] if hasattr(entry, "memberOf") else []
            conn.unbind()
        except ldap3.core.exceptions.LDAPException as e:
            raise ValueError(f"LDAP search failed: {e}")

        # Bind as the user to verify password
        try:
            user_conn = ldap3.Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
            )
            user_conn.unbind()
        except ldap3.core.exceptions.LDAPException:
            raise ValueError("Invalid LDAP credentials")

        # Map LDAP groups to role
        role = self._map_ldap_groups_to_role(provider, groups)

        # Find or create user
        user = self.get_user_by_sso(provider.id, username)
        if user:
            # Update role from LDAP groups
            if user.role != role:
                self.update_user(user.id, {"role": role})
                user.role = role
            self._record_successful_login(user)
            return user

        # Auto-create
        if not provider.auto_create_users:
            raise ValueError("User not found and auto-creation is disabled")

        return self.create_user(
            username=username,
            email=user_email,
            role=role,
            display_name=user_display,
            auth_method="ldap",
            sso_provider_id=provider.id,
            sso_subject=username,
        )

    def _map_ldap_groups_to_role(
        self, provider: SSOProvider, groups: list[str]
    ) -> str:
        """Map LDAP group memberships to a SpiderFoot role.

        Uses the attribute_mapping field with a 'group_role_map' key:
        {"group_role_map": {"CN=admins,DC=...": "admin", "CN=analysts,DC=...": "analyst"}}
        """
        import json
        try:
            mapping = json.loads(provider.attribute_mapping or "{}")
        except json.JSONDecodeError:
            return provider.default_role

        group_map = mapping.get("group_role_map", {})
        if not group_map:
            return provider.default_role

        # Return the highest-privilege matching role
        best_role = provider.default_role
        best_level = 0
        for group in groups:
            group_lower = group.lower()
            for pattern, role_name in group_map.items():
                if pattern.lower() in group_lower:
                    try:
                        r = parse_role(role_name)
                        if r.level > best_level:
                            best_level = r.level
                            best_role = role_name
                    except ValueError:
                        pass

        return best_role

    def ldap_login(
        self,
        provider_id: str,
        username: str,
        password: str,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict[str, Any]:
        """Full LDAP login flow: LDAP auth + issue tokens + create session."""
        provider = self.get_sso_provider(provider_id)
        if not provider:
            raise ValueError("SSO provider not found")
        if not provider.enabled:
            raise ValueError("SSO provider is disabled")
        if provider.protocol != "ldap":
            raise ValueError("Provider is not an LDAP provider")

        user = self.authenticate_ldap(provider, username, password)
        access_token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)
        self._create_session(user, access_token, ip_address, user_agent, "ldap")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.config.jwt_expiry_hours * 3600,
            "user": user.to_dict(),
        }

    # ------------------------------------------------------------------
    # SSO: SAML helpers
    # ------------------------------------------------------------------

    def get_saml_login_url(self, provider: SSOProvider, acs_url: str = "") -> str:
        """Build the SAML SSO redirect URL with a proper AuthnRequest.

        Generates a deflate-encoded, base64-encoded SAML 2.0 AuthnRequest
        per the HTTP-Redirect binding spec (SAMLBindings §3.4.4).
        """
        import base64
        import urllib.parse
        import zlib

        issuer = provider.sp_entity_id or "spiderfoot"
        if not acs_url:
            acs_url = provider.sp_acs_url or ""

        request_id = f"_sf_{uuid.uuid4().hex}"
        issue_instant = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        authn_request = (
            f'<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
            f' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
            f' ID="{request_id}"'
            f' Version="2.0"'
            f' IssueInstant="{issue_instant}"'
            f' Destination="{provider.idp_sso_url}"'
            f' AssertionConsumerServiceURL="{acs_url}"'
            f' ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
            f'<saml:Issuer>{issuer}</saml:Issuer>'
            f'<samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"'
            f' AllowCreate="true"/>'
            f'</samlp:AuthnRequest>'
        )

        # Deflate → base64 encode (HTTP-Redirect binding)
        deflated = zlib.compress(authn_request.encode("utf-8"))[2:-4]  # raw deflate
        encoded = base64.b64encode(deflated).decode("ascii")

        params = {
            "SAMLRequest": encoded,
            "RelayState": provider.id,
        }
        return f"{provider.idp_sso_url}?{urllib.parse.urlencode(params)}"

    def process_saml_response(
        self, provider: SSOProvider, saml_response: str
    ) -> dict[str, str]:
        """Process a SAML response and extract user attributes.

        In production, this would validate the XML signature using
        the IdP certificate and extract the NameID and attributes.
        For now, it decodes the base64 response and extracts basic attributes.
        """
        import base64
        import xml.etree.ElementTree as ET

        try:
            decoded = base64.b64decode(saml_response)
            root = ET.fromstring(decoded)
            # Extract NameID (simplified - real impl would validate signature)
            namespaces = {
                "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
                "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            }
            name_id = root.find(".//saml:NameID", namespaces)
            attributes = {}
            for attr in root.findall(".//saml:Attribute", namespaces):
                attr_name = attr.get("Name", "")
                value_elem = attr.find("saml:AttributeValue", namespaces)
                if attr_name and value_elem is not None and value_elem.text:
                    attributes[attr_name] = value_elem.text

            email = attributes.get("email", attributes.get("mail", ""))
            name = attributes.get("displayName", attributes.get("cn", ""))
            subject = name_id.text if name_id is not None else email

            return {
                "subject": subject,
                "email": email,
                "name": name,
                "attributes": str(attributes),
            }
        except Exception as e:
            log.error("SAML response processing failed: %s", e)
            raise ValueError(f"Invalid SAML response: {e}")

    # ------------------------------------------------------------------
    # API Key management
    # ------------------------------------------------------------------

    _API_KEY_COLS = (
        "id, user_id, name, key_prefix, key_hash, role, status, "
        "expires_at, allowed_modules, allowed_endpoints, rate_limit, "
        "last_used, created_at, updated_at"
    )

    def _row_to_api_key(self, row: tuple) -> ApiKey:
        return ApiKey(
            id=row[0], user_id=row[1], name=row[2],
            key_prefix=row[3], key_hash=row[4],
            role=row[5], status=row[6],
            expires_at=row[7],
            allowed_modules=row[8], allowed_endpoints=row[9],
            rate_limit=row[10], last_used=row[11],
            created_at=row[12], updated_at=row[13],
        )

    def create_api_key(
        self,
        user_id: str,
        name: str,
        role: str = "viewer",
        expires_at: float = 0.0,
        allowed_modules: str = "",
        allowed_endpoints: str = "",
        rate_limit: int = 0,
    ) -> tuple[ApiKey, str]:
        """Create a new API key for a user.

        Returns:
            Tuple of (ApiKey object, raw key string).
            The raw key is only available at creation time.
        """
        parse_role(role)  # validate

        # Check user exists
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Generate key: sf_<prefix>_<random>
        raw_key = f"sf_{secrets.token_hex(4)}_{secrets.token_hex(24)}"
        key_prefix = raw_key[:12]
        key_hash = bcrypt.hash(raw_key)

        now = time.time()
        key_id = str(uuid.uuid4())

        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO tbl_api_keys
                (id, user_id, name, key_prefix, key_hash, role, status,
                 expires_at, allowed_modules, allowed_endpoints, rate_limit,
                 last_used, created_at, updated_at)
                VALUES ({self._phs(14)})""",
            (
                key_id, user_id, name, key_prefix, key_hash, role, "active",
                expires_at, allowed_modules, allowed_endpoints, rate_limit,
                0.0, now, now,
            ),
        )
        conn.commit()

        api_key = ApiKey(
            id=key_id, user_id=user_id, name=name,
            key_prefix=key_prefix, key_hash=key_hash,
            role=role, status="active",
            expires_at=expires_at,
            allowed_modules=allowed_modules,
            allowed_endpoints=allowed_endpoints,
            rate_limit=rate_limit,
            created_at=now, updated_at=now,
        )
        log.info("Created API key '%s' for user %s (role=%s)", name, user_id, role)
        return api_key, raw_key

    def validate_api_key(self, raw_key: str) -> ApiKey | None:
        """Validate an API key and return its metadata if valid."""
        prefix = raw_key[:12] if len(raw_key) >= 12 else raw_key
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._API_KEY_COLS} FROM tbl_api_keys WHERE key_prefix = {self._ph()}",
            (prefix,),
        )
        rows = cur.fetchall()
        for row in rows:
            api_key = self._row_to_api_key(row)
            if not api_key.is_active():
                continue
            try:
                if bcrypt.verify(raw_key, api_key.key_hash):
                    # Update last_used
                    cur.execute(
                        f"UPDATE tbl_api_keys SET last_used = {self._ph()} WHERE id = {self._ph()}",
                        (time.time(), api_key.id),
                    )
                    conn.commit()
                    return api_key
            except Exception:
                continue
        return None

    def api_key_to_user_context(self, raw_key: str) -> UserContext:
        """Validate an API key and return a UserContext."""
        api_key = self.validate_api_key(raw_key)
        if not api_key:
            raise ValueError("Invalid or expired API key")

        user = self.get_user_by_id(api_key.user_id)
        if not user or not user.is_active():
            raise ValueError("API key owner account is inactive")

        role = parse_role(api_key.role)
        return UserContext(
            user_id=user.id,
            username=user.username,
            email=user.email,
            role=role,
            api_key_id=api_key.id,
            metadata={
                "allowed_modules": api_key.allowed_modules,
                "allowed_endpoints": api_key.allowed_endpoints,
                "rate_limit": api_key.rate_limit,
            },
        )

    def list_api_keys(self, user_id: str | None = None) -> list[ApiKey]:
        """List API keys, optionally filtered by user."""
        conn = self._get_conn()
        cur = conn.cursor()
        if user_id:
            cur.execute(
                f"SELECT {self._API_KEY_COLS} FROM tbl_api_keys "
                f"WHERE user_id = {self._ph()} ORDER BY created_at DESC",
                (user_id,),
            )
        else:
            cur.execute(
                f"SELECT {self._API_KEY_COLS} FROM tbl_api_keys ORDER BY created_at DESC"
            )
        return [self._row_to_api_key(row) for row in cur.fetchall()]

    def get_api_key(self, key_id: str) -> ApiKey | None:
        """Fetch an API key by ID."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"SELECT {self._API_KEY_COLS} FROM tbl_api_keys WHERE id = {self._ph()}",
            (key_id,),
        )
        row = cur.fetchone()
        return self._row_to_api_key(row) if row else None

    def update_api_key(self, key_id: str, updates: dict[str, Any]) -> ApiKey | None:
        """Update an API key's fields."""
        allowed = {"name", "role", "status", "expires_at", "allowed_modules",
                    "allowed_endpoints", "rate_limit"}
        valid = {k: v for k, v in updates.items() if k in allowed}
        if not valid:
            return self.get_api_key(key_id)
        if "role" in valid:
            parse_role(valid["role"])
        valid["updated_at"] = time.time()

        conn = self._get_conn()
        cur = conn.cursor()
        set_clause = ", ".join(f"{k} = {self._ph()}" for k in valid)
        values = list(valid.values()) + [key_id]
        cur.execute(
            f"UPDATE tbl_api_keys SET {set_clause} WHERE id = {self._ph()}",
            values,
        )
        conn.commit()
        return self.get_api_key(key_id)

    def delete_api_key(self, key_id: str) -> bool:
        """Delete an API key."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM tbl_api_keys WHERE id = {self._ph()}",
            (key_id,),
        )
        conn.commit()
        return cur.rowcount > 0

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key (set status to 'revoked')."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE tbl_api_keys SET status = 'revoked', updated_at = {self._ph()} "
            f"WHERE id = {self._ph()}",
            (time.time(), key_id),
        )
        conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Auth info / status
    # ------------------------------------------------------------------

    def get_auth_status(self) -> dict[str, Any]:
        """Return the current auth system status."""
        providers = self.list_sso_providers()
        return {
            "auth_required": self.config.auth_required,
            "rbac_enforced": self.config.rbac_enforce,
            "jwt_expiry_hours": self.config.jwt_expiry_hours,
            "session_ttl_hours": self.config.session_ttl_hours,
            "user_count": self.count_users(),
            "sso_providers": [
                {"id": p.id, "name": p.name, "protocol": p.protocol, "enabled": p.enabled}
                for p in providers
            ],
            "supported_methods": ["local", "ldap", "oauth2", "saml"],
        }
