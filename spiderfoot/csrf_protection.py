# -*- coding: utf-8 -*-
"""
CSRF Protection Module for SpiderFoot Web Interface
Provides Cross-Site Request Forgery protection for all form submissions and API calls.
"""

import hashlib
import hmac
import secrets
import time
from functools import wraps
from flask import session, request, abort, current_app


class CSRFProtection:
    """CSRF Protection implementation for SpiderFoot."""
    
    def __init__(self, app=None, secret_key=None):
        """Initialize CSRF protection.
        
        Args:
            app: Flask application instance
            secret_key: Secret key for CSRF token generation
        """
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_lifetime = 3600  # 1 hour
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize CSRF protection for Flask app."""
        app.csrf = self
        app.before_request(self._check_csrf_token)
        
        # Add CSRF token to template context
        @app.context_processor
        def inject_csrf_token():
            return dict(csrf_token=self.generate_csrf_token())
    
    def generate_csrf_token(self):
        """Generate a new CSRF token for the current session."""
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
            session['csrf_token_time'] = time.time()
        
        # Check if token is expired
        if time.time() - session.get('csrf_token_time', 0) > self.token_lifetime:
            session['csrf_token'] = secrets.token_hex(32)
            session['csrf_token_time'] = time.time()
        
        return session['csrf_token']
    
    def validate_csrf_token(self, token=None):
        """Validate CSRF token.
        
        Args:
            token: Token to validate (if None, gets from request)
            
        Returns:
            bool: True if token is valid
        """
        if token is None:
            token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
        
        if not token:
            return False
        
        session_token = session.get('csrf_token')
        if not session_token:
            return False
        
        # Check token age
        token_time = session.get('csrf_token_time', 0)
        if time.time() - token_time > self.token_lifetime:
            return False
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(token, session_token)
    
    def _check_csrf_token(self):
        """Check CSRF token for POST, PUT, DELETE requests."""
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            # Skip CSRF check for API endpoints with proper authentication
            if request.path.startswith('/api/') and self._has_valid_api_auth():
                return
            
            if not self.validate_csrf_token():
                abort(403, "CSRF token missing or invalid")
    
    def _has_valid_api_auth(self):
        """Check if request has valid API authentication."""
        # Implement your API authentication logic here
        auth_header = request.headers.get('Authorization')
        return auth_header and auth_header.startswith('Bearer ')


def csrf_protect(f):
    """Decorator to enforce CSRF protection on specific routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_app.csrf.validate_csrf_token():
            abort(403, "CSRF token missing or invalid")
        return f(*args, **kwargs)
    return decorated_function


# Template helper function
def csrf_token():
    """Get CSRF token for use in templates."""
    if hasattr(current_app, 'csrf'):
        return current_app.csrf.generate_csrf_token()
    return ''
