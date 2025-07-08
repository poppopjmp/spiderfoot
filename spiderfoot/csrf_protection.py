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
import cherrypy


class CSRFProtection:
    """CSRF Protection implementation for SpiderFoot with CherryPy."""
    
    def __init__(self, secret_key=None):
        """Initialize CSRF protection.
        
        Args:
            secret_key: Secret key for CSRF token generation
        """
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_lifetime = 3600  # 1 hour
    
    def generate_csrf_token(self):
        """Generate a new CSRF token for the current session.
        
        Returns:
            str: Generated CSRF token
        """
        session = cherrypy.session
        
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
            # Try to get token from form data or headers
            if hasattr(cherrypy.request, 'params'):
                token = cherrypy.request.params.get('csrf_token')
            if not token and hasattr(cherrypy.request, 'headers'):
                token = cherrypy.request.headers.get('X-CSRF-Token')
        
        if not token:
            return False
        
        session = cherrypy.session
        session_token = session.get('csrf_token')
        if not session_token:
            return False
        
        # Check token age
        token_time = session.get('csrf_token_time', 0)
        if time.time() - token_time > self.token_lifetime:
            return False
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(token, session_token)
    
    def check_csrf_token(self):
        """Check CSRF token for POST, PUT, DELETE requests.
        
        Raises:
            cherrypy.HTTPError: If CSRF token is missing or invalid
        """
        method = cherrypy.request.method.upper()
        if method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            # Skip CSRF check for API endpoints with proper authentication
            if cherrypy.request.path_info.startswith('/api/') and self._has_valid_api_auth():
                return
            
            if not self.validate_csrf_token():
                raise cherrypy.HTTPError(403, "CSRF token missing or invalid")
    
    def _has_valid_api_auth(self):
        """Check if request has valid API authentication.
        
        Returns:
            bool: True if request has valid API authentication
        """
        # Implement your API authentication logic here
        auth_header = cherrypy.request.headers.get('Authorization', '')
        return auth_header.startswith('Bearer ')


class CSRFTool(cherrypy.Tool):
    """CherryPy tool for CSRF protection."""
    
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_handler', self.check_csrf)
        self.csrf_protection = CSRFProtection()
    
    def check_csrf(self):
        """Check CSRF token before handling request."""
        self.csrf_protection.check_csrf_token()


# Global CSRF protection instance
csrf_protection = CSRFProtection()

# Register the CSRF tool
cherrypy.tools.csrf = CSRFTool()


def csrf_protect(f):
    """Decorator to enforce CSRF protection on specific routes.
    
    Args:
        f: Function to wrap with CSRF protection
        
    Returns:
        function: Decorated function with CSRF protection
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        csrf_protection.check_csrf_token()
        return f(*args, **kwargs)
    return decorated_function


def csrf_token():
    """Get CSRF token for use in templates.
    
    Returns:
        str: CSRF token for the current session
    """
    return csrf_protection.generate_csrf_token()


def init_csrf_protection(app_config=None):
    """Initialize CSRF protection for CherryPy application.
    
    Args:
        app_config: Optional configuration dictionary
        
    Returns:
        CSRFProtection: The initialized CSRF protection instance
    """
    # Enable sessions
    cherrypy.config.update({
        'tools.sessions.on': True,
        'tools.sessions.timeout': 60,  # Session timeout in minutes
        'tools.csrf.on': True  # Enable CSRF protection by default
    })
    
    # Make csrf_token function available globally
    cherrypy.config.update({
        'tools.staticdir.root': cherrypy.config.get('tools.staticdir.root', ''),
    })
    
    return csrf_protection
