#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Web Security Module for SpiderFoot
==========================================

This module provides enhanced security features for the SpiderFoot web interface,
integrating with the new security framework while maintaining backward compatibility.

Author: SpiderFoot Security Team
"""

import cherrypy
import logging
from typing import Dict, Any, Optional

try:
    import secure
    SECURE_AVAILABLE = True
except ImportError:
    SECURE_AVAILABLE = False

# Import security modules if available
try:
    from spiderfoot.security_middleware import install_cherrypy_security
    from spiderfoot.secure_config import SecureConfigManager
    SECURITY_MODULES_AVAILABLE = True
except ImportError:
    SECURITY_MODULES_AVAILABLE = False


def setup_security_headers():
    """Legacy security headers setup function for backward compatibility."""
    if not SECURE_AVAILABLE:
        logging.getLogger(__name__).warning("secure module not available, skipping security headers")
        return
        
    csp = (
        secure.ContentSecurityPolicy()
            .default_src("'self'")
            .script_src("'self'", "'unsafe-inline'", "blob:")
            .style_src("'self'", "'unsafe-inline'")
            .base_uri("'self'")
            .connect_src("'self'", "data:")
            .frame_src("'self'", 'data:')
            .img_src("'self'", "data:")
    )
    secure_headers = secure.Secure(
        server=secure.Server().set("server"),
        cache=secure.CacheControl().must_revalidate(),
        csp=csp,
        referrer=secure.ReferrerPolicy().no_referrer(),
    )
    cherrypy.config.update({
        "tools.response_headers.on": True,
        "tools.response_headers.headers": secure_headers.framework.cherrypy()
    })


def setup_enhanced_security(config: Dict[str, Any]) -> Optional[Any]:
    """
    Set up enhanced security with the new security framework.
    
    Args:
        config: SpiderFoot configuration dictionary
        
    Returns:
        Security middleware instance or None if not available
    """
    log = logging.getLogger(__name__)
    
    if not SECURITY_MODULES_AVAILABLE:
        log.warning("Enhanced security modules not available, falling back to basic security")
        setup_security_headers()
        return None
    
    try:
        # Install enhanced security middleware
        security_middleware = install_cherrypy_security(config)
        log.info("Enhanced security middleware installed successfully")
        return security_middleware
        
    except Exception as e:
        log.error(f"Failed to install enhanced security middleware: {e}")
        log.info("Falling back to basic security headers")
        setup_security_headers()
        return None


def get_security_status() -> Dict[str, Any]:
    """
    Get current security status and capabilities.
    
    Returns:
        Security status information
    """
    return {
        'secure_module_available': SECURE_AVAILABLE,
        'enhanced_security_available': SECURITY_MODULES_AVAILABLE,
        'security_headers_enabled': True,
        'enhanced_middleware_enabled': SECURITY_MODULES_AVAILABLE
    }


# Backward compatibility
def setup_security():
    """Backward compatibility function."""
    setup_security_headers()


# Export for backward compatibility
__all__ = ['setup_security_headers', 'setup_enhanced_security', 'get_security_status', 'setup_security']
