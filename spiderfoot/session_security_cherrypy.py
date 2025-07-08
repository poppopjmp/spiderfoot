# -*- coding: utf-8 -*-
"""
Secure Session Management for SpiderFoot Web Interface
Provides secure session handling with proper timeouts and validation for CherryPy.
"""

import time
import secrets
import hashlib
import hmac
from typing import Dict, Optional, Any
import redis
import cherrypy


class SecureSessionManager:
    """Secure session management with Redis backend and security features for CherryPy."""
    
    def __init__(self, redis_client=None, redis_host='localhost', redis_port=6379):
        """Initialize secure session manager.
        
        Args:
            redis_client: Existing Redis client instance
            redis_host: Redis server host
            redis_port: Redis server port
        """
        if redis_client:
            self.redis = redis_client
        else:
            try:
                self.redis = redis.Redis(
                    host=redis_host, 
                    port=redis_port, 
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                self.redis.ping()
            except (redis.ConnectionError, redis.RedisError):
                self.redis = None
                self._memory_sessions = {}
        
        # Session configuration
        self.session_timeout = 3600  # 1 hour
        self.idle_timeout = 1800     # 30 minutes
        self.max_sessions_per_user = 5
        self.secure_cookie = True
        self.httponly_cookie = True
        self.samesite_cookie = 'Strict'
    
    def create_session(self, user_id: str, user_agent: str = None, ip_address: str = None) -> str:
        """Create a new secure session.
        
        Args:
            user_id: User identifier
            user_agent: User agent string
            ip_address: Client IP address
            
        Returns:
            Session token
        """
        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        
        # Create session data
        session_data = {
            'user_id': user_id,
            'created_at': time.time(),
            'last_activity': time.time(),
            'ip_address': ip_address or self._get_client_ip(),
            'user_agent_hash': self._hash_user_agent(user_agent or '') if user_agent else None,
            'is_active': True
        }
        
        # Store session
        self._store_session(session_token, session_data)
        
        # Cleanup old sessions for this user
        self._cleanup_user_sessions(user_id)
        
        # Set CherryPy session
        cherrypy.session['session_token'] = session_token
        cherrypy.session['user_id'] = user_id
        cherrypy.session['authenticated'] = True
        
        return session_token
    
    def validate_session(self, session_token: str, user_agent: str = None, 
                        ip_address: str = None) -> Optional[Dict[str, Any]]:
        """Validate session token and update activity.
        
        Args:
            session_token: Session token to validate
            user_agent: User agent string for verification
            ip_address: Client IP address for verification
            
        Returns:
            Session data if valid, None otherwise
        """
        if not session_token:
            return None
        
        # Get session data
        session_data = self._get_session(session_token)
        if not session_data:
            return None
        
        current_time = time.time()
        
        # Check if session is active
        if not session_data.get('is_active', False):
            return None
        
        # Check session timeout
        if current_time - session_data.get('created_at', 0) > self.session_timeout:
            self.invalidate_session(session_token)
            return None
        
        # Check idle timeout
        if current_time - session_data.get('last_activity', 0) > self.idle_timeout:
            self.invalidate_session(session_token)
            return None
        
        # Verify IP address (optional, can be disabled for mobile users)
        stored_ip = session_data.get('ip_address')
        current_ip = ip_address or self._get_client_ip()
        if stored_ip and stored_ip != current_ip:
            # Log suspicious activity but don't immediately invalidate
            # This can be configurable based on security requirements
            cherrypy.log(f"IP address mismatch for session {session_token}: {stored_ip} vs {current_ip}", severity=30)
        
        # Verify user agent hash (helps detect session hijacking)
        stored_ua_hash = session_data.get('user_agent_hash')
        if stored_ua_hash and user_agent:
            current_ua_hash = self._hash_user_agent(user_agent)
            if stored_ua_hash != current_ua_hash:
                cherrypy.log(f"User agent mismatch for session {session_token}", severity=30)
                # Optionally invalidate session on user agent mismatch
                # self.invalidate_session(session_token)
                # return None
        
        # Update last activity
        session_data['last_activity'] = current_time
        self._store_session(session_token, session_data)
        
        return session_data
    
    def invalidate_session(self, session_token: str) -> bool:
        """Invalidate a specific session.
        
        Args:
            session_token: Session token to invalidate
            
        Returns:
            True if session was invalidated
        """
        success = self._delete_session(session_token)
        
        # Clear CherryPy session if it matches
        if cherrypy.session.get('session_token') == session_token:
            cherrypy.session.clear()
        
        return success
    
    def invalidate_user_sessions(self, user_id: str, except_token: str = None) -> int:
        """Invalidate all sessions for a user.
        
        Args:
            user_id: User identifier
            except_token: Session token to keep active
            
        Returns:
            Number of sessions invalidated
        """
        if self.redis:
            return self._invalidate_user_sessions_redis(user_id, except_token)
        else:
            return self._invalidate_user_sessions_memory(user_id, except_token)
    
    def get_user_sessions(self, user_id: str) -> list:
        """Get active sessions for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of session information
        """
        sessions = []
        
        if self.redis:
            try:
                # Get all session keys for user
                pattern = f"session:{user_id}:*"
                keys = self.redis.keys(pattern)
                
                for key in keys:
                    session_data = self.redis.hgetall(key)
                    if session_data and session_data.get('is_active') == 'True':
                        session_token = key.split(':')[-1]
                        sessions.append({
                            'token': session_token,
                            'created_at': float(session_data.get('created_at', 0)),
                            'last_activity': float(session_data.get('last_activity', 0)),
                            'ip_address': session_data.get('ip_address', 'unknown')
                        })
            except Exception:
                pass
        else:
            for token, data in self._memory_sessions.items():
                if data.get('user_id') == user_id and data.get('is_active', False):
                    sessions.append({
                        'token': token,
                        'created_at': data.get('created_at', 0),
                        'last_activity': data.get('last_activity', 0),
                        'ip_address': data.get('ip_address', 'unknown')
                    })
        
        return sessions
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        if self.redis:
            return self._cleanup_expired_sessions_redis()
        else:
            return self._cleanup_expired_sessions_memory()
    
    def _get_client_ip(self) -> str:
        """Get client IP address from CherryPy request."""
        try:
            # Check for forwarded headers first
            ip = cherrypy.request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            if not ip:
                ip = cherrypy.request.headers.get('X-Real-IP', '')
            if not ip:
                ip = getattr(cherrypy.request, 'remote', {}).get('ip', 'unknown')
            return ip
        except AttributeError:
            return 'unknown'
    
    def _hash_user_agent(self, user_agent: str) -> str:
        """Hash user agent string for privacy and storage efficiency.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Hashed user agent
        """
        return hashlib.sha256(user_agent.encode()).hexdigest()[:16]  # First 16 chars for efficiency
    
    def _store_session(self, session_token: str, session_data: Dict[str, Any]) -> None:
        """Store session data.
        
        Args:
            session_token: Session token
            session_data: Session data to store
        """
        if self.redis:
            try:
                user_id = session_data['user_id']
                key = f"session:{user_id}:{session_token}"
                
                # Convert data for Redis storage
                redis_data = {}
                for k, v in session_data.items():
                    if isinstance(v, bool):
                        redis_data[k] = str(v)
                    else:
                        redis_data[k] = v
                
                self.redis.hset(key, mapping=redis_data)
                self.redis.expire(key, self.session_timeout)
                
                # Also store in user index for easy cleanup
                user_key = f"user_sessions:{user_id}"
                self.redis.sadd(user_key, session_token)
                self.redis.expire(user_key, self.session_timeout)
            except Exception:
                # Fall back to memory storage
                self._memory_sessions[session_token] = session_data
        else:
            self._memory_sessions[session_token] = session_data
    
    def _get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data.
        
        Args:
            session_token: Session token
            
        Returns:
            Session data if exists
        """
        if self.redis:
            try:
                # We need to find the session by scanning user sessions
                # This is less efficient but necessary without knowing user_id
                pattern = f"session:*:{session_token}"
                keys = self.redis.keys(pattern)
                
                if keys:
                    session_data = self.redis.hgetall(keys[0])
                    if session_data:
                        # Convert back from Redis storage
                        data = {}
                        for k, v in session_data.items():
                            if k == 'is_active':
                                data[k] = v == 'True'
                            elif k in ['created_at', 'last_activity']:
                                data[k] = float(v)
                            else:
                                data[k] = v
                        return data
                return None
            except Exception:
                # Fall back to memory storage
                return self._memory_sessions.get(session_token)
        else:
            return self._memory_sessions.get(session_token)
    
    def _delete_session(self, session_token: str) -> bool:
        """Delete session data.
        
        Args:
            session_token: Session token
            
        Returns:
            True if deleted successfully
        """
        if self.redis:
            try:
                # Find and delete the session
                pattern = f"session:*:{session_token}"
                keys = self.redis.keys(pattern)
                
                if keys:
                    key = keys[0]
                    session_data = self.redis.hgetall(key)
                    user_id = session_data.get('user_id')
                    
                    # Delete session
                    self.redis.delete(key)
                    
                    # Remove from user index
                    if user_id:
                        user_key = f"user_sessions:{user_id}"
                        self.redis.srem(user_key, session_token)
                    
                    return True
                return False
            except Exception:
                # Fall back to memory storage
                return self._memory_sessions.pop(session_token, None) is not None
        else:
            return self._memory_sessions.pop(session_token, None) is not None
    
    def _cleanup_user_sessions(self, user_id: str) -> None:
        """Clean up old sessions for user, keeping only the most recent ones.
        
        Args:
            user_id: User identifier
        """
        sessions = self.get_user_sessions(user_id)
        
        if len(sessions) > self.max_sessions_per_user:
            # Sort by last activity and keep the most recent ones
            sessions.sort(key=lambda x: x['last_activity'], reverse=True)
            sessions_to_remove = sessions[self.max_sessions_per_user:]
            
            for session in sessions_to_remove:
                self.invalidate_session(session['token'])
    
    def _invalidate_user_sessions_redis(self, user_id: str, except_token: str = None) -> int:
        """Invalidate user sessions in Redis.
        
        Args:
            user_id: User identifier
            except_token: Session token to keep active
            
        Returns:
            Number of sessions invalidated
        """
        try:
            user_key = f"user_sessions:{user_id}"
            session_tokens = self.redis.smembers(user_key)
            
            invalidated = 0
            for token in session_tokens:
                if token != except_token:
                    if self._delete_session(token):
                        invalidated += 1
            
            return invalidated
        except Exception:
            return 0
    
    def _invalidate_user_sessions_memory(self, user_id: str, except_token: str = None) -> int:
        """Invalidate user sessions in memory.
        
        Args:
            user_id: User identifier
            except_token: Session token to keep active
            
        Returns:
            Number of sessions invalidated
        """
        tokens_to_remove = []
        for token, data in self._memory_sessions.items():
            if data.get('user_id') == user_id and token != except_token:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self._memory_sessions[token]
        
        return len(tokens_to_remove)
    
    def _cleanup_expired_sessions_redis(self) -> int:
        """Clean up expired sessions in Redis.
        
        Returns:
            Number of sessions cleaned up
        """
        try:
            current_time = time.time()
            cleaned = 0
            
            # Get all session keys
            pattern = "session:*"
            keys = self.redis.keys(pattern)
            
            for key in keys:
                session_data = self.redis.hgetall(key)
                if session_data:
                    created_at = float(session_data.get('created_at', 0))
                    last_activity = float(session_data.get('last_activity', 0))
                    
                    # Check if session is expired
                    if (current_time - created_at > self.session_timeout or 
                        current_time - last_activity > self.idle_timeout):
                        
                        # Extract session token and user_id
                        parts = key.split(':')
                        if len(parts) >= 3:
                            user_id = parts[1]
                            session_token = parts[2]
                            
                            # Delete session
                            self.redis.delete(key)
                            
                            # Remove from user index
                            user_key = f"user_sessions:{user_id}"
                            self.redis.srem(user_key, session_token)
                            
                            cleaned += 1
            
            return cleaned
        except Exception:
            return 0
    
    def _cleanup_expired_sessions_memory(self) -> int:
        """Clean up expired sessions in memory.
        
        Returns:
            Number of sessions cleaned up
        """
        current_time = time.time()
        tokens_to_remove = []
        
        for token, data in self._memory_sessions.items():
            created_at = data.get('created_at', 0)
            last_activity = data.get('last_activity', 0)
            
            # Check if session is expired
            if (current_time - created_at > self.session_timeout or 
                current_time - last_activity > self.idle_timeout):
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self._memory_sessions[token]
        
        return len(tokens_to_remove)


# Alias for backward compatibility and easier imports
SessionManager = SecureSessionManager


# CherryPy tool for session management
class SessionTool(cherrypy.Tool):
    """CherryPy tool for secure session management."""
    
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_handler', self.setup_session)
        self.session_manager = SecureSessionManager()
    
    def setup_session(self):
        """Setup secure session for request."""
        # Validate existing session
        session_token = cherrypy.session.get('session_token')
        if session_token:
            user_agent = cherrypy.request.headers.get('User-Agent', '')
            session_data = self.session_manager.validate_session(session_token, user_agent)
            
            if not session_data:
                # Session is invalid, clear it
                cherrypy.session.clear()


# Register the session tool
cherrypy.tools.secure_session = SessionTool()
