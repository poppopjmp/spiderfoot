# -*- coding: utf-8 -*-
"""
API Security Module for SpiderFoot
Provides comprehensive API security including authentication, authorization, and request validation for FastAPI.
"""

import time
import hmac
import hashlib
import secrets
import jwt
from typing import Dict, List, Optional, Any, Tuple
from functools import wraps
from fastapi import HTTPException, Depends, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from datetime import datetime, timedelta


class APISecurityManager:
    """Comprehensive API security management for FastAPI."""
    
    def __init__(self, secret_key: str = None, token_expiry: int = 3600):
        """Initialize API security manager.
        
        Args:
            secret_key: Secret key for JWT signing
            token_expiry: JWT token expiry time in seconds
        """
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_expiry = token_expiry
        self.algorithm = 'HS256'
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # API permissions and scopes
        self.scopes = {
            'read': ['scan:read', 'config:read', 'results:read'],
            'write': ['scan:write', 'config:write'],
            'admin': ['user:manage', 'system:admin', 'audit:read'],
            'scan': ['scan:create', 'scan:start', 'scan:stop', 'scan:delete'],
            'module': ['module:enable', 'module:disable', 'module:configure']
        }
        
        # Rate limiting per scope
        self.scope_limits = {
            'read': {'requests': 1000, 'window': 3600},
            'write': {'requests': 100, 'window': 3600},
            'scan': {'requests': 50, 'window': 3600},
            'admin': {'requests': 200, 'window': 3600}
        }
    
    def generate_jwt_token(self, user_id: str, scopes: List[str] = None, 
                          expires_in: int = None) -> str:
        """Generate JWT token for API authentication.
        
        Args:
            user_id: User identifier
            scopes: List of permission scopes
            expires_in: Token expiry time in seconds
            
        Returns:
            JWT token string
        """
        expires_in = expires_in or self.token_expiry
        expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        
        payload = {
            'user_id': user_id,
            'scopes': scopes or [],
            'exp': expiry,
            'iat': datetime.utcnow(),
            'iss': 'spiderfoot-api'
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate JWT token.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Token claims if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
                return None
            
            return payload
        except jwt.InvalidTokenError:
            return None
    
    def generate_api_key(self, user_id: str, scopes: List[str] = None, 
                        expires_in: int = None) -> str:
        """Generate API key (same as JWT for now).
        
        Args:
            user_id: User identifier
            scopes: List of permission scopes
            expires_in: Token expiry time in seconds
            
        Returns:
            API key string
        """
        return self.generate_jwt_token(user_id, scopes, expires_in)
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key.
        
        Args:
            api_key: API key to validate
            
        Returns:
            Key claims if valid, None otherwise
        """
        return self.validate_jwt_token(api_key)
    
    def check_permission(self, claims: Dict[str, Any], required_scope: str) -> bool:
        """Check if user has required permission.
        
        Args:
            claims: Token/key claims
            required_scope: Required permission scope
            
        Returns:
            True if user has permission
        """
        user_scopes = claims.get('scopes', [])
        
        # Check direct scope match
        if required_scope in user_scopes:
            return True
        
        # Check if user has admin scope (admin can do everything)
        if 'system:admin' in user_scopes:
            return True
        
        # Check scope hierarchy
        for scope_group, group_scopes in self.scopes.items():
            if required_scope in group_scopes and scope_group in user_scopes:
                return True
        
        return False
    
    def create_signature(self, method: str, url: str, payload: str = '', 
                        timestamp: str = None, api_key: str = None) -> str:
        """Create request signature for additional security.
        
        Args:
            method: HTTP method
            url: Request URL
            payload: Request payload
            timestamp: Request timestamp
            api_key: API key
            
        Returns:
            Request signature
        """
        timestamp = timestamp or str(int(time.time()))
        string_to_sign = f"{method}\n{url}\n{payload}\n{timestamp}"
        
        signature = hmac.new(
            self.secret_key.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def validate_signature(self, signature: str, method: str, url: str, 
                          payload: str = '', timestamp: str = None,
                          api_key: str = None, tolerance: int = 300) -> bool:
        """Validate request signature.
        
        Args:
            signature: Provided signature
            method: HTTP method
            url: Request URL
            payload: Request payload
            timestamp: Request timestamp
            api_key: API key
            tolerance: Time tolerance in seconds
            
        Returns:
            True if signature is valid
        """
        if not timestamp:
            return False
        
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            
            # Check timestamp tolerance
            if abs(current_time - request_time) > tolerance:
                return False
            
            expected_signature = self.create_signature(method, url, payload, timestamp, api_key)
            return hmac.compare_digest(signature, expected_signature)
        except (ValueError, TypeError):
            return False
    
    def get_api_limits(self, scopes: List[str]) -> Dict[str, int]:
        """Get API rate limits based on user scopes.
        
        Args:
            scopes: User permission scopes
            
        Returns:
            Rate limit configuration
        """
        # Default limits
        limits = {'requests': 100, 'window': 3600}
        
        # Find the highest limit the user is entitled to
        for scope in scopes:
            for scope_group, scope_list in self.scopes.items():
                if scope in scope_list and scope_group in self.scope_limits:
                    scope_limits = self.scope_limits[scope_group]
                    if scope_limits['requests'] > limits['requests']:
                        limits = scope_limits
        
        return limits


class APIKeyManager:
    """API key management with database storage for FastAPI."""
    
    def __init__(self, db_instance):
        """Initialize API key manager.
        
        Args:
            db_instance: Database instance for storing API keys
        """
        self.db = db_instance
        self._ensure_api_keys_table()
    
    def _ensure_api_keys_table(self) -> None:
        """Ensure API keys table exists."""
        if not self.db:
            return
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT UNIQUE NOT NULL,
            key_hash TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT,
            description TEXT,
            scopes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            last_used TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
        """
        
        try:
            self.db.execute(create_table_sql)
        except Exception as e:
            # Log error but don't fail initialization
            pass
    
    def create_api_key(self, user_id: str, scopes: List[str], name: str = None,
                      description: str = None, expires_in: int = None) -> Tuple[str, str]:
        """Create new API key.
        
        Args:
            user_id: User identifier
            scopes: Permission scopes
            name: Key name
            description: Key description
            expires_in: Expiry time in seconds
            
        Returns:
            Tuple of (key_id, api_key)
        """
        key_id = secrets.token_urlsafe(16)
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        if self.db:
            try:
                self.db.execute("""
                    INSERT INTO api_keys (key_id, key_hash, user_id, name, description, scopes, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [key_id, key_hash, user_id, name, description, ','.join(scopes), expires_at])
            except Exception as e:
                raise Exception(f"Failed to create API key: {e}")
        
        return key_id, api_key
    
    def revoke_api_key(self, key_id: str, user_id: str = None) -> bool:
        """Revoke API key.
        
        Args:
            key_id: Key identifier
            user_id: User identifier (for authorization)
            
        Returns:
            True if revoked successfully
        """
        if not self.db:
            return False
        
        try:
            where_clause = "key_id = ?"
            params = [key_id]
            
            if user_id:
                where_clause += " AND user_id = ?"
                params.append(user_id)
            
            result = self.db.execute(f"""
                UPDATE api_keys SET is_active = 0 WHERE {where_clause}
            """, params)
            
            return result.rowcount > 0
        except Exception as e:
            return False
    
    def update_last_used(self, key_hash: str) -> None:
        """Update last used timestamp for API key.
        
        Args:
            key_hash: Hashed API key
        """
        if not self.db:
            return
        
        try:
            self.db.execute("""
                UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE key_hash = ?
            """, [key_hash])
        except Exception:
            pass
    
    def list_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """List API keys for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of API key information
        """
        if not self.db:
            return []
        
        try:
            result = self.db.execute("""
                SELECT key_id, name, description, scopes, created_at, expires_at, last_used, is_active
                FROM api_keys WHERE user_id = ? ORDER BY created_at DESC
            """, [user_id])
            
            keys = []
            for row in result.fetchall():
                keys.append({
                    'key_id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'scopes': row[3].split(',') if row[3] else [],
                    'created_at': row[4],
                    'expires_at': row[5],
                    'last_used': row[6],
                    'is_active': bool(row[7])
                })
            
            return keys
        except Exception as e:
            return []


# FastAPI Security Dependencies
security_scheme = HTTPBearer()

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    api_security: APISecurityManager = Depends()
) -> Dict[str, Any]:
    """Get current authenticated user from JWT token.
    
    Args:
        request: FastAPI request
        credentials: HTTP Bearer credentials
        api_security: API security manager
        
    Returns:
        User claims from token
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    claims = api_security.validate_jwt_token(credentials.credentials)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return claims


def require_scopes(required_scopes: List[str]):
    """Dependency to require specific scopes.
    
    Args:
        required_scopes: List of required permission scopes
        
    Returns:
        FastAPI dependency function
    """
    def check_scopes(
        current_user: Dict[str, Any] = Depends(get_current_user),
        api_security: APISecurityManager = Depends()
    ) -> Dict[str, Any]:
        """Check if user has required scopes."""
        user_scopes = current_user.get('scopes', [])
        
        for required_scope in required_scopes:
            if not api_security.check_permission(current_user, required_scope):
                raise HTTPException(
                    status_code=403, 
                    detail=f"Permission '{required_scope}' required"
                )
        
        return current_user
    
    return check_scopes


def require_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    api_security: APISecurityManager = Depends()
) -> Dict[str, Any]:
    """Dependency to require API key authentication.
    
    Args:
        request: FastAPI request
        x_api_key: API key from header
        api_security: API security manager
        
    Returns:
        API key claims
        
    Raises:
        HTTPException: If API key is invalid
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    claims = api_security.validate_api_key(x_api_key)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return claims


# Convenience dependencies for common scopes
def require_read_access(current_user: Dict[str, Any] = Depends(require_scopes(['scan:read']))):
    """Require read access."""
    return current_user


def require_write_access(current_user: Dict[str, Any] = Depends(require_scopes(['scan:write']))):
    """Require write access."""
    return current_user


def require_admin_access(current_user: Dict[str, Any] = Depends(require_scopes(['system:admin']))):
    """Require admin access."""
    return current_user


# Aliases for easier imports and backward compatibility
JWTManager = APISecurityManager  # JWT functionality is in APISecurityManager
