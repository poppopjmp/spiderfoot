# -*- coding: utf-8 -*-
"""
Secure Session Management for SpiderFoot Web Interface
Provides secure session handling with proper timeouts and validation.
"""

import time
import secrets
import hashlib
import hmac
from typing import Dict, Optional, Any
from flask import session, request, g
import redis


class SecureSessionManager:
    """Secure session management with Redis backend and security features."""
    
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
            'created_at': int(time.time()),
            'last_activity': int(time.time()),
            'user_agent_hash': self._hash_user_agent(user_agent) if user_agent else None,
            'ip_address': ip_address,
            'csrf_token': secrets.token_hex(32),
            'session_version': 1
        }
        
        # Store session
        self._store_session(session_token, session_data)
        
        # Cleanup old sessions for this user
        self._cleanup_user_sessions(user_id)
        
        return session_token
    
    def validate_session(self, session_token: str, user_agent: str = None, 
                        ip_address: str = None) -> Optional[Dict[str, Any]]:
        """Validate and refresh session.
        
        Args:
            session_token: Session token to validate
            user_agent: Current user agent string
            ip_address: Current client IP address
            
        Returns:
            Session data if valid, None otherwise
        """
        if not session_token:
            return None
        
        # Retrieve session data
        session_data = self._get_session(session_token)
        if not session_data:
            return None
        
        current_time = int(time.time())
        
        # Check session expiry
        if current_time - session_data.get('created_at', 0) > self.session_timeout:
            self._delete_session(session_token)
            return None
        
        # Check idle timeout
        if current_time - session_data.get('last_activity', 0) > self.idle_timeout:
            self._delete_session(session_token)
            return None
        
        # Validate user agent (basic fingerprinting)
        if user_agent and session_data.get('user_agent_hash'):
            current_hash = self._hash_user_agent(user_agent)
            if not hmac.compare_digest(session_data['user_agent_hash'], current_hash):
                self._delete_session(session_token)
                return None
        
        # Validate IP address (optional, can be disabled for mobile users)
        if (ip_address and session_data.get('ip_address') and 
            session_data['ip_address'] != ip_address):
            # Log suspicious activity but don't invalidate session automatically
            # Could implement geo-location validation here
            pass
        
        # Update last activity
        session_data['last_activity'] = current_time
        if ip_address:
            session_data['ip_address'] = ip_address
        
        self._store_session(session_token, session_data)
        
        return session_data
    
    def invalidate_session(self, session_token: str) -> bool:
        """Invalidate a session.
        
        Args:
            session_token: Session token to invalidate
            
        Returns:
            True if session was invalidated
        """
        return self._delete_session(session_token)
    
    def invalidate_user_sessions(self, user_id: str, except_token: str = None) -> int:
        """Invalidate all sessions for a user.
        
        Args:
            user_id: User identifier
            except_token: Session token to exclude from invalidation
            
        Returns:
            Number of sessions invalidated
        """
        if self.redis:
            return self._invalidate_user_sessions_redis(user_id, except_token)
        else:
            return self._invalidate_user_sessions_memory(user_id, except_token)
    
    def get_user_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of session information
        """
        sessions = []
        
        if self.redis:
            # Get all session keys for user
            pattern = f"session:user:{user_id}:*"
            for key in self.redis.scan_iter(match=pattern):
                session_token = key.split(':')[-1]
                session_data = self._get_session(session_token)
                if session_data:
                    sessions.append({
                        'token': session_token,
                        'created_at': session_data.get('created_at'),
                        'last_activity': session_data.get('last_activity'),
                        'ip_address': session_data.get('ip_address')
                    })
        else:
            # Memory-based lookup
            for token, data in self._memory_sessions.items():
                if data.get('user_id') == user_id:
                    sessions.append({
                        'token': token,
                        'created_at': data.get('created_at'),
                        'last_activity': data.get('last_activity'),
                        'ip_address': data.get('ip_address')
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
    
    def _hash_user_agent(self, user_agent: str) -> str:
        """Hash user agent for session validation.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Hashed user agent
        """
        return hashlib.sha256(user_agent.encode()).hexdigest()
    
    def _store_session(self, session_token: str, session_data: Dict[str, Any]) -> None:
        """Store session data.
        
        Args:
            session_token: Session token
            session_data: Session data dictionary
        """
        if self.redis:
            # Store in Redis with expiration
            key = f"session:{session_token}"
            user_key = f"session:user:{session_data['user_id']}:{session_token}"
            
            pipeline = self.redis.pipeline()
            pipeline.hset(key, mapping=session_data)
            pipeline.expire(key, self.session_timeout)
            pipeline.set(user_key, session_token)
            pipeline.expire(user_key, self.session_timeout)
            pipeline.execute()
        else:
            # Store in memory
            self._memory_sessions[session_token] = session_data
    
    def _get_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data.
        
        Args:
            session_token: Session token
            
        Returns:
            Session data or None
        """
        if self.redis:
            try:
                key = f"session:{session_token}"
                session_data = self.redis.hgetall(key)
                
                if session_data:
                    # Convert string values back to appropriate types
                    session_data['created_at'] = int(session_data.get('created_at', 0))
                    session_data['last_activity'] = int(session_data.get('last_activity', 0))
                    session_data['session_version'] = int(session_data.get('session_version', 1))
                    return session_data
            except (redis.ConnectionError, redis.RedisError):
                pass
        else:
            return self._memory_sessions.get(session_token)
        
        return None
    
    def _delete_session(self, session_token: str) -> bool:
        """Delete session data.
        
        Args:
            session_token: Session token
            
        Returns:
            True if session was deleted
        """
        if self.redis:
            try:
                # Get user_id first
                session_data = self._get_session(session_token)
                if session_data:
                    user_id = session_data.get('user_id')
                    
                    # Delete both keys
                    pipeline = self.redis.pipeline()
                    pipeline.delete(f"session:{session_token}")
                    if user_id:
                        pipeline.delete(f"session:user:{user_id}:{session_token}")
                    results = pipeline.execute()
                    return any(results)
            except (redis.ConnectionError, redis.RedisError):
                pass
        else:
            return self._memory_sessions.pop(session_token, None) is not None
        
        return False
    
    def _cleanup_user_sessions(self, user_id: str) -> None:
        """Clean up old sessions for a user to enforce max sessions limit.
        
        Args:
            user_id: User identifier
        """
        sessions = self.get_user_sessions(user_id)
        
        if len(sessions) > self.max_sessions_per_user:
            # Sort by last activity and remove oldest
            sessions.sort(key=lambda x: x.get('last_activity', 0))
            sessions_to_remove = sessions[:-self.max_sessions_per_user]
            
            for session_info in sessions_to_remove:
                self._delete_session(session_info['token'])
    
    def _invalidate_user_sessions_redis(self, user_id: str, except_token: str = None) -> int:
        """Invalidate user sessions in Redis.
        
        Args:
            user_id: User identifier
            except_token: Session token to exclude
            
        Returns:
            Number of sessions invalidated
        """
        count = 0
        pattern = f"session:user:{user_id}:*"
        
        for key in self.redis.scan_iter(match=pattern):
            session_token = key.split(':')[-1]
            if session_token != except_token:
                if self._delete_session(session_token):
                    count += 1
        
        return count
    
    def _invalidate_user_sessions_memory(self, user_id: str, except_token: str = None) -> int:
        """Invalidate user sessions in memory.
        
        Args:
            user_id: User identifier
            except_token: Session token to exclude
            
        Returns:
            Number of sessions invalidated
        """
        count = 0
        tokens_to_remove = []
        
        for token, data in self._memory_sessions.items():
            if data.get('user_id') == user_id and token != except_token:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            if self._delete_session(token):
                count += 1
        
        return count
    
    def _cleanup_expired_sessions_redis(self) -> int:
        """Clean up expired sessions in Redis.
        
        Returns:
            Number of sessions cleaned up
        """
        # Redis automatically expires keys, but we need to clean up user mapping keys
        count = 0
        current_time = int(time.time())
        
        for key in self.redis.scan_iter(match="session:user:*"):
            try:
                session_token = self.redis.get(key)
                if session_token:
                    session_data = self._get_session(session_token)
                    if not session_data or (current_time - session_data.get('created_at', 0) > self.session_timeout):
                        self.redis.delete(key)
                        count += 1
            except (redis.ConnectionError, redis.RedisError):
                pass
        
        return count
    
    def _cleanup_expired_sessions_memory(self) -> int:
        """Clean up expired sessions in memory.
        
        Returns:
            Number of sessions cleaned up
        """
        count = 0
        current_time = int(time.time())
        expired_tokens = []
        
        for token, data in self._memory_sessions.items():
            if current_time - data.get('created_at', 0) > self.session_timeout:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            if self._delete_session(token):
                count += 1
        
        return count

# Alias for backward compatibility and easier imports
SessionManager = SecureSessionManager
