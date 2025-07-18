# -*- coding: utf-8 -*-
"""
API Security Module for SpiderFoot
Provides comprehensive API security including authentication, authorization, and request validation.
"""

import time
import hmac
import hashlib
import secrets
import jwt
from typing import Dict, List, Optional, Any, Tuple
from functools import wraps
from flask import request, jsonify, g
from werkzeug.security import check_password_hash, generate_password_hash


class APISecurityManager:
    """Comprehensive API security management."""
    
    def __init__(self, secret_key: str = None, token_expiry: int = 3600):
        """Initialize API security manager.
        
        Args:
            secret_key: Secret key for JWT signing
            token_expiry: JWT token expiry time in seconds
        """
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_expiry = token_expiry
        self.algorithm = 'HS256'
        
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
    
    def generate_api_key(self, user_id: str, scopes: List[str] = None, 
                        expires_in: int = None) -> str:
        """Generate API key with JWT.
        
        Args:
            user_id: User identifier
            scopes: List of allowed scopes
            expires_in: Expiry time in seconds (overrides default)
            
        Returns:
            JWT API key
        """
        scopes = scopes or ['read']
        expires_in = expires_in or self.token_expiry
        
        payload = {
            'user_id': user_id,
            'scopes': scopes,
            'iat': int(time.time()),
            'exp': int(time.time()) + expires_in,
            'type': 'api_key',
            'jti': secrets.token_hex(16)  # Unique token ID
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate API key and extract claims.
        
        Args:
            api_key: JWT API key to validate
            
        Returns:
            Token claims if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                api_key, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={'verify_exp': True}
            )
            
            # Verify token type
            if payload.get('type') != 'api_key':
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def check_permission(self, claims: Dict[str, Any], required_scope: str) -> bool:
        """Check if user has required permission.
        
        Args:
            claims: JWT token claims
            required_scope: Required scope (e.g., 'scan:read')
            
        Returns:
            True if user has permission
        """
        user_scopes = claims.get('scopes', [])
        
        # Check direct scope match
        if required_scope in user_scopes:
            return True
        
        # Check if user has broader scope that includes required scope
        for user_scope in user_scopes:
            if user_scope in self.scopes:
                if required_scope in self.scopes[user_scope]:
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
            HMAC signature
        """
        timestamp = timestamp or str(int(time.time()))
        
        # Create string to sign
        string_to_sign = f"{method}\n{url}\n{payload}\n{timestamp}"
        
        # Use API key as HMAC key if provided, otherwise use secret
        key = api_key.encode() if api_key else self.secret_key.encode()
        
        signature = hmac.new(
            key,
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
        
        # Check timestamp tolerance
        current_time = int(time.time())
        request_time = int(timestamp)
        
        if abs(current_time - request_time) > tolerance:
            return False
        
        # Generate expected signature
        expected_signature = self.create_signature(
            method, url, payload, timestamp, api_key
        )
        
        # Constant-time comparison
        return hmac.compare_digest(signature, expected_signature)
    
    def get_api_limits(self, scopes: List[str]) -> Dict[str, int]:
        """Get rate limits for given scopes.
        
        Args:
            scopes: List of user scopes
            
        Returns:
            Rate limit configuration
        """
        max_requests = 0
        window = 3600  # Default 1 hour
        
        for scope in scopes:
            if scope in self.scope_limits:
                scope_limit = self.scope_limits[scope]
                max_requests = max(max_requests, scope_limit['requests'])
                window = max(window, scope_limit['window'])
        
        return {'requests': max_requests, 'window': window}


class APIKeyManager:
    """API key management with database storage."""
    
    def __init__(self, config):
        """Initialize API key manager.
        
        Args:
            config: SpiderFoot configuration dictionary
        """
        # Import here to avoid circular imports
        from spiderfoot import SpiderFootDb
        
        try:
            self.db = SpiderFootDb(config, init=True)
            self._ensure_api_keys_table()
        except Exception as e:
            print(f"Failed to initialize APIKeyManager database: {e}")
            self.db = None
    
    def _ensure_api_keys_table(self) -> None:
        """Ensure API keys table exists."""
        if not self.db:
            return
            
        try:
            with self.db.dbhLock:
                if self.db.db_type == 'sqlite':
                    qry = """CREATE TABLE IF NOT EXISTS tbl_api_keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_id VARCHAR(32) UNIQUE NOT NULL,
                        user_id VARCHAR(50) NOT NULL,
                        key_hash VARCHAR(64) NOT NULL,
                        scopes TEXT NOT NULL,
                        created_at BIGINT NOT NULL,
                        expires_at BIGINT,
                        last_used BIGINT,
                        is_active BOOLEAN DEFAULT TRUE,
                        name VARCHAR(100),
                        description TEXT
                    )"""
                else:  # postgresql
                    qry = """CREATE TABLE IF NOT EXISTS tbl_api_keys (
                        id SERIAL PRIMARY KEY,
                        key_id VARCHAR(32) UNIQUE NOT NULL,
                        user_id VARCHAR(50) NOT NULL,
                        key_hash VARCHAR(64) NOT NULL,
                        scopes TEXT NOT NULL,
                        created_at BIGINT NOT NULL,
                        expires_at BIGINT,
                        last_used BIGINT,
                        is_active BOOLEAN DEFAULT TRUE,
                        name VARCHAR(100),
                        description TEXT
                    )"""
                
                self.db.dbh.execute(qry)
                self.db.conn.commit()
        except Exception as e:
            print(f"Failed to create API keys table: {e}")
    
    def create_api_key(self, user_id: str, scopes: List[str], name: str = None,
                      description: str = None, expires_in: int = None) -> Tuple[str, str]:
        """Create and store API key.
        
        Args:
            user_id: User identifier
            scopes: List of scopes
            name: API key name
            description: API key description
            expires_in: Expiry time in seconds
            
        Returns:
            Tuple of (key_id, api_key)
        """
        if not self.db:
            raise RuntimeError("Database not available for API key management")
            
        # Generate API key
        security_manager = APISecurityManager()
        api_key = security_manager.generate_api_key(user_id, scopes, expires_in)
        
        # Generate key ID and hash
        key_id = secrets.token_hex(16)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Store in database
        current_time = int(time.time())
        expires_at = current_time + expires_in if expires_in else None
        
        try:
            with self.db.dbhLock:
                if self.db.db_type == 'sqlite':
                    qry = """INSERT INTO tbl_api_keys 
                           (key_id, user_id, key_hash, scopes, created_at, expires_at, name, description)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
                    params = (key_id, user_id, key_hash, ','.join(scopes), 
                             current_time, expires_at, name, description)
                else:  # postgresql
                    qry = """INSERT INTO tbl_api_keys 
                           (key_id, user_id, key_hash, scopes, created_at, expires_at, name, description)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                    params = (key_id, user_id, key_hash, ','.join(scopes),
                             current_time, expires_at, name, description)
                
                self.db.dbh.execute(qry, params)
                self.db.conn.commit()
                
                return key_id, api_key
                
        except Exception as e:
            raise RuntimeError(f"Failed to store API key: {e}")
    
    def revoke_api_key(self, key_id: str, user_id: str = None) -> bool:
        """Revoke API key.
        
        Args:
            key_id: API key ID
            user_id: User ID (for additional validation)
            
        Returns:
            True if key was revoked
        """
        if not self.db:
            return False
            
        try:
            with self.db.dbhLock:
                if self.db.db_type == 'sqlite':
                    if user_id:
                        qry = "UPDATE tbl_api_keys SET is_active = 0 WHERE key_id = ? AND user_id = ?"
                        params = (key_id, user_id)
                    else:
                        qry = "UPDATE tbl_api_keys SET is_active = 0 WHERE key_id = ?"
                        params = (key_id,)
                else:  # postgresql
                    if user_id:
                        qry = "UPDATE tbl_api_keys SET is_active = FALSE WHERE key_id = %s AND user_id = %s"
                        params = (key_id, user_id)
                    else:
                        qry = "UPDATE tbl_api_keys SET is_active = FALSE WHERE key_id = %s"
                        params = (key_id,)
                
                cursor = self.db.dbh.execute(qry, params)
                self.db.conn.commit()
                
                return cursor.rowcount > 0
                
        except Exception:
            return False
    
    def update_last_used(self, key_hash: str) -> None:
        """Update last used timestamp for API key.
        
        Args:
            key_hash: Hash of the API key
        """
        if not self.db:
            return
            
        try:
            with self.db.dbhLock:
                current_time = int(time.time())
                
                if self.db.db_type == 'sqlite':
                    qry = "UPDATE tbl_api_keys SET last_used = ? WHERE key_hash = ?"
                    params = (current_time, key_hash)
                else:  # postgresql
                    qry = "UPDATE tbl_api_keys SET last_used = %s WHERE key_hash = %s"
                    params = (current_time, key_hash)
                
                self.db.dbh.execute(qry, params)
                self.db.conn.commit()
                
        except Exception:
            pass  # Don't fail request if we can't update timestamp
    
    def list_user_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """List API keys for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of API key information
        """
        if not self.db:
            return []
            
        try:
            with self.db.dbhLock:
                if self.db.db_type == 'sqlite':
                    qry = """SELECT key_id, scopes, created_at, expires_at, last_used, 
                           is_active, name, description FROM tbl_api_keys WHERE user_id = ?"""
                    params = (user_id,)
                else:  # postgresql
                    qry = """SELECT key_id, scopes, created_at, expires_at, last_used,
                           is_active, name, description FROM tbl_api_keys WHERE user_id = %s"""
                    params = (user_id,)
                
                self.db.dbh.execute(qry, params)
                rows = self.db.dbh.fetchall()
                
                keys = []
                for row in rows:
                    keys.append({
                        'key_id': row[0],
                        'scopes': row[1].split(',') if row[1] else [],
                        'created_at': row[2],
                        'expires_at': row[3],
                        'last_used': row[4],
                        'is_active': bool(row[5]),
                        'name': row[6],
                        'description': row[7]
                    })
                
                return keys
                
        except Exception:
            return []


def require_api_auth(required_scope: str = None):
    """Decorator to require API authentication and authorization.
    
    Args:
        required_scope: Required scope for the endpoint
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get API key from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing or invalid authorization header'}), 401
            
            api_key = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Validate API key
            security_manager = APISecurityManager()
            claims = security_manager.validate_api_key(api_key)
            
            if not claims:
                return jsonify({'error': 'Invalid or expired API key'}), 401
            
            # Check required scope
            if required_scope and not security_manager.check_permission(claims, required_scope):
                return jsonify({'error': f'Insufficient permissions. Required: {required_scope}'}), 403
            
            # Store user info in g for use in the route
            g.user_id = claims.get('user_id')
            g.api_scopes = claims.get('scopes', [])
            g.api_claims = claims
            
            # Update API key usage
            try:
                from flask import current_app
                if hasattr(current_app, 'api_key_manager'):
                    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    current_app.api_key_manager.update_last_used(key_hash)
            except Exception:
                pass
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Convenience decorators for common scopes
def require_read_access(f):
    """Require read access."""
    return require_api_auth('scan:read')(f)


def require_write_access(f):
    """Require write access."""
    return require_api_auth('scan:write')(f)


def require_admin_access(f):
    """Require admin access."""
    return require_api_auth('system:admin')(f)


# Aliases for easier imports and backward compatibility
JWTManager = APISecurityManager  # JWT functionality is in APISecurityManager
