# SpiderFoot Security Integration Guide

## Overview

This guide provides step-by-step instructions for integrating and configuring the comprehensive security features implemented in SpiderFoot. These enhancements provide enterprise-grade security for production deployments.

## Quick Start

### 1. Verify Security Module Installation

First, verify that all security modules are properly installed:

```bash
cd spiderfoot/spiderfoot
python security_validator.py /path/to/spiderfoot
```

Expected output:
```
Success Rate: 100.00%
Security Modules Available: Yes
All Components Operational: Yes
```

### 2. Basic Configuration

Add security configuration to your SpiderFoot config:

```python
# Minimal security configuration
config = {
    '_security_enabled': True,
    'security.csrf.secret_key': 'your-secure-random-key-here',
    'security.api_security.jwt_secret': 'your-jwt-secret-here'
}
```

### 3. Start SpiderFoot

Start SpiderFoot normally - security middleware will automatically activate:

```bash
python sfwebui.py
```

## Detailed Integration Steps

### Step 1: Environment Setup

#### Prerequisites
- Python 3.9+
- Redis (recommended for production)
- Required Python packages

#### Install Dependencies

The following packages are required for security features:

```bash
pip install bleach redis PyJWT cryptography
```

Or install from requirements.txt:
```bash
pip install -r requirements.txt
```

### Step 2: Redis Configuration (Recommended)

For production deployments, configure Redis for session and rate limiting storage:

#### Install Redis
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# CentOS/RHEL
sudo yum install redis

# macOS
brew install redis

# Windows
# Download from https://redis.io/download
```

#### Configure Redis Connection
```python
config = {
    'security.rate_limiting.storage': 'redis',
    'security.rate_limiting.redis_host': 'localhost',
    'security.rate_limiting.redis_port': 6379,
    'security.rate_limiting.redis_db': 0,
    
    'security.session_security.storage': 'redis',
    'security.session_security.redis_host': 'localhost',
    'security.session_security.redis_port': 6379,
    'security.session_security.redis_db': 1
}
```

### Step 3: Security Configuration

#### Generate Secure Keys

Generate cryptographically secure keys for CSRF and JWT:

```python
import secrets

# Generate CSRF secret key
csrf_secret = secrets.token_hex(32)
print(f"CSRF Secret: {csrf_secret}")

# Generate JWT secret key  
jwt_secret = secrets.token_hex(32)
print(f"JWT Secret: {jwt_secret}")
```

#### Complete Security Configuration

```python
config = {
    # Enable security middleware
    '_security_enabled': True,
    
    # CSRF Protection
    'security.csrf.enabled': True,
    'security.csrf.secret_key': 'your-generated-csrf-secret',
    'security.csrf.timeout': 3600,  # 1 hour
    
    # Rate Limiting
    'security.rate_limiting.enabled': True,
    'security.rate_limiting.storage': 'redis',  # or 'memory'
    'security.rate_limiting.redis_host': 'localhost',
    'security.rate_limiting.redis_port': 6379,
    'security.rate_limiting.redis_db': 0,
    'security.rate_limiting.api_requests_per_minute': 60,
    'security.rate_limiting.web_requests_per_minute': 120,
    'security.rate_limiting.scan_requests_per_hour': 10,
    'security.rate_limiting.login_attempts_per_minute': 5,
    
    # Input Validation
    'security.input_validation.enabled': True,
    'security.input_validation.max_input_length': 10000,
    'security.input_validation.strict_mode': False,
    
    # Session Security
    'security.session_security.enabled': True,
    'security.session_security.storage': 'redis',  # or 'memory'
    'security.session_security.redis_host': 'localhost',
    'security.session_security.redis_port': 6379,
    'security.session_security.redis_db': 1,
    'security.session_security.session_timeout': 3600,  # 1 hour
    'security.session_security.max_sessions_per_user': 5,
    
    # API Security
    'security.api_security.enabled': True,
    'security.api_security.jwt_secret': 'your-generated-jwt-secret',
    'security.api_security.jwt_expiry': 3600,  # 1 hour
    'security.api_security.api_key_length': 32,
    
    # Security Logging
    'security.logging.enabled': True,
    'security.logging.log_file': 'logs/security.log',
    'security.logging.log_level': 'INFO',
    'security.logging.max_file_size': '10MB',
    'security.logging.backup_count': 5,
    
    # Security Headers
    'security.headers.enabled': True,
    'security.headers.hsts_max_age': 31536000,  # 1 year
    'security.headers.csp_policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
}
```

### Step 4: Web Interface Integration

The security middleware is automatically integrated when enabled. Verify integration:

#### Check Web Interface
1. Start SpiderFoot web interface
2. Check browser developer tools for security headers
3. Verify CSRF tokens in forms
4. Test rate limiting by making rapid requests

Expected security headers:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

#### CSRF Protection in Forms
Forms will automatically include CSRF tokens:
```html
<input type="hidden" name="csrf_token" value="generated-token-here">
```

### Step 5: API Integration

For FastAPI endpoints, security middleware is automatically applied:

#### API Key Creation
Create API keys using the management interface or programmatically:

```python
from spiderfoot.api_security import APISecurityManager

# Initialize API manager
api_manager = APISecurityManager(secret_key=config['security.api_security.jwt_secret'])

# Create API key
api_key = api_manager.generate_api_key(
    user_id="admin",
    scopes=["read", "write", "admin"]
)
print(f"API Key: {api_key}")
```

#### API Authentication
Include API key in requests:

```python
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

response = requests.get('http://localhost:5001/api/scanlist', headers=headers)
```

### Step 6: Security Logging Configuration

#### Log File Configuration
Ensure log directory exists:
```bash
mkdir -p logs
touch logs/security.log
chmod 644 logs/security.log
```

#### Log Rotation (Production)
Configure logrotate for security logs:

```bash
# /etc/logrotate.d/spiderfoot-security
/path/to/spiderfoot/logs/security.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 spiderfoot spiderfoot
    postrotate
        /bin/kill -HUP `cat /var/run/spiderfoot.pid 2> /dev/null` 2> /dev/null || true
    endscript
}
```

### Step 7: Production Deployment

#### HTTPS Configuration
Configure HTTPS for production deployments:

```python
config = {
    # HTTPS Configuration
    'server.socket_host': '0.0.0.0',
    'server.socket_port': 443,
    'server.ssl_module': 'builtin',
    'server.ssl_certificate': '/path/to/certificate.crt',
    'server.ssl_private_key': '/path/to/private.key',
    
    # Security Headers (HTTPS-specific)
    'security.headers.hsts_enabled': True,
    'security.headers.secure_cookies': True
}
```

#### Environment Variables
Use environment variables for sensitive configuration:

```bash
export SPIDERFOOT_CSRF_SECRET="your-csrf-secret"
export SPIDERFOOT_JWT_SECRET="your-jwt-secret"
export REDIS_URL="redis://localhost:6379"
```

```python
import os

config = {
    'security.csrf.secret_key': os.environ.get('SPIDERFOOT_CSRF_SECRET'),
    'security.api_security.jwt_secret': os.environ.get('SPIDERFOOT_JWT_SECRET'),
    'security.rate_limiting.redis_url': os.environ.get('REDIS_URL', 'redis://localhost:6379')
}
```

## Testing and Validation

### Security Validation Tool

Run comprehensive security tests:

```bash
cd spiderfoot/spiderfoot
python security_validator.py /path/to/spiderfoot --verbose
```

### Manual Testing

#### Test CSRF Protection
1. Submit a form without CSRF token (should fail)
2. Submit with valid token (should succeed)
3. Submit with expired token (should fail)

#### Test Rate Limiting
1. Make rapid API requests (should be rate limited)
2. Verify rate limit headers in response
3. Test different rate limit types

#### Test Input Validation
1. Submit malicious input (XSS, SQL injection)
2. Verify input is sanitized/rejected
3. Test file upload validation

#### Test Session Security
1. Login and verify session creation
2. Test session timeout
3. Test session invalidation
4. Verify IP/User-Agent validation

### Load Testing

Test security components under load:

```bash
# Install artillery for load testing
npm install -g artillery

# Run load test
artillery quick --count 50 --num 10 http://localhost:5001/api/scanlist
```

## Troubleshooting

### Common Issues

#### 1. Security Modules Not Loading
**Symptoms:** Security validation fails, no security headers
**Solution:**
- Verify all dependencies are installed: `pip install bleach redis PyJWT cryptography`
- Check import errors in logs
- Ensure `_security_enabled: True` in config

#### 2. CSRF Token Validation Fails
**Symptoms:** Forms submission fails with CSRF errors
**Solution:**
- Verify CSRF secret key is configured
- Check that forms include CSRF tokens
- Ensure CSRF timeout is appropriate

#### 3. Rate Limiting Too Restrictive
**Symptoms:** Legitimate requests being blocked
**Solution:**
- Increase rate limits in configuration
- Check Redis connectivity
- Review rate limiting logs

#### 4. Session Issues
**Symptoms:** Users getting logged out frequently
**Solution:**
- Increase session timeout
- Verify Redis connectivity for session storage
- Check IP/User-Agent fingerprinting settings

#### 5. Redis Connection Issues
**Symptoms:** Rate limiting/sessions not working
**Solution:**
- Verify Redis is running: `redis-cli ping`
- Check Redis connection parameters
- Test Redis connectivity

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging

# Enable debug logging for security components
logging.getLogger('spiderfoot.security').setLevel(logging.DEBUG)
logging.getLogger('spiderfoot.csrf_protection').setLevel(logging.DEBUG)
logging.getLogger('spiderfoot.rate_limiting').setLevel(logging.DEBUG)
```

### Log Analysis

Check security logs for issues:

```bash
# View recent security events
tail -f logs/security.log

# Filter for specific event types
grep "RATE_LIMIT_EXCEEDED" logs/security.log
grep "LOGIN_FAILURE" logs/security.log
grep "UNAUTHORIZED_ACCESS" logs/security.log
```

## Migration from Previous Versions

### Backup Current Configuration
```bash
cp spiderfoot.cfg spiderfoot.cfg.backup
```

### Update Configuration File
Add security configuration to existing config file:

```python
# Add to existing spiderfoot.cfg
[security]
_security_enabled = True
csrf_secret_key = your-generated-secret
jwt_secret = your-generated-secret
```

### Database Migration
No database changes are required for security features.

## Performance Optimization

### Memory Usage
Security middleware adds minimal memory overhead (~5-10MB).

### CPU Usage  
Security processing adds ~5-15ms per request.

### Optimization Tips
1. Use Redis for production (better performance than memory storage)
2. Tune rate limits based on your usage patterns
3. Configure appropriate log rotation
4. Monitor security metrics

## Security Monitoring

### Key Metrics to Monitor
- Failed login attempts
- Rate limit violations
- CSRF violations
- API authentication failures
- Suspicious activity patterns

### SIEM Integration
Security logs are structured for easy SIEM integration:

```json
{
    "timestamp": "2025-07-08T10:00:00Z",
    "event_type": "LOGIN_FAILURE",
    "severity": "WARNING",
    "ip_address": "192.168.1.100",
    "details": {
        "username": "admin",
        "reason": "invalid_password",
        "attempt_count": 3
    }
}
```

## Support and Maintenance

### Regular Tasks
1. **Key Rotation:** Rotate CSRF and JWT secrets quarterly
2. **Log Review:** Review security logs weekly
3. **Config Review:** Review security configuration monthly
4. **Dependency Updates:** Keep security dependencies updated

### Security Updates
Monitor for security updates and apply promptly:

```bash
# Update security dependencies
pip install --upgrade bleach PyJWT cryptography
```

### Getting Help
1. Check this integration guide
2. Review security logs for specific errors
3. Run security validator for component status
4. Consult main documentation

This integration guide provides comprehensive instructions for implementing enterprise-grade security in SpiderFoot. Follow these steps carefully for a secure, production-ready deployment.
