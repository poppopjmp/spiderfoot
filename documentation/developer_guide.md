# Developer Guide

This guide is for developers who want to contribute to SpiderFoot, build custom modules, or extend its capabilities. Here you'll find resources, best practices, and technical details to help you get started and succeed as a SpiderFoot contributor.

---

## Contributing

We welcome contributions of all kinds! Please read the [Contributing Guide](../docs/contributing.md) for information on submitting issues, feature requests, and pull requests. All contributors must follow the project's code of conduct.

## Security Development

SpiderFoot includes comprehensive security features that developers should understand when contributing or extending the platform.

### Security Architecture

The security system is built on several key components:

- **Security Middleware:** Central security processing layer
- **CSRF Protection:** Cross-site request forgery prevention
- **Input Validation:** Comprehensive input sanitization
- **Rate Limiting:** Request throttling and abuse prevention
- **Session Security:** Secure session management
- **API Security:** JWT tokens and API key management
- **Security Logging:** Structured security event logging

### Security Integration Guidelines

When developing modules or features:

**1. Input Validation**
```python
from spiderfoot.input_validation import InputValidator

# Validate email addresses
if InputValidator.validate_email(email):
    # Process email
    
# Sanitize HTML content
clean_html = InputValidator.sanitize_html(user_content)

# Validate domains
if InputValidator.validate_domain(domain):
    # Process domain
```

**2. Security Logging**
```python
from spiderfoot.security_logging import SecurityLogger, SecurityEventType

logger = SecurityLogger()

# Log security events
logger.log_security_event(
    SecurityEventType.SUSPICIOUS_ACTIVITY,
    "Description of the event",
    {"user_id": "123", "ip": "192.168.1.1"}
)

# Log authentication events
logger.log_login_attempt("username", success=True, ip_address="192.168.1.1")
```

**3. Rate Limiting Integration**
```python
from spiderfoot.rate_limiting import rate_limit

@rate_limit('api')
def api_endpoint():
    # Your API logic here
    pass

@rate_limit('web')  
def web_endpoint():
    # Your web logic here
    pass
```

**4. Session Security**
```python
from spiderfoot.session_security import SessionManager

session_manager = SessionManager()

# Create secure session
session_id = session_manager.create_session(
    user_id="user123",
    user_agent=request.headers.get('User-Agent'),
    ip_address=request.remote_addr
)

# Validate session
session_data = session_manager.validate_session(
    session_id,
    user_agent=request.headers.get('User-Agent'),
    ip_address=request.remote_addr
)
```

### Security Testing

When developing security-related features:

**1. Use the Security Validator**
```bash
cd spiderfoot
python security_validator.py .
```

**2. Write Security Tests**
```python
def test_input_validation():
    # Test XSS prevention
    dirty_input = "<script>alert('xss')</script>"
    clean_input = InputValidator.sanitize_html(dirty_input)
    assert "<script>" not in clean_input
    
    # Test email validation
    assert InputValidator.validate_email("test@example.com")
    assert not InputValidator.validate_email("invalid-email")
```

**3. Performance Testing**
```python
import time

def test_security_performance():
    start = time.time()
    # Test security operation
    end = time.time()
    
    # Ensure minimal performance impact
    assert (end - start) < 0.01  # < 10ms
```

### Security Best Practices for Developers

**1. Input Handling**
- Always validate and sanitize user inputs
- Use parameterized queries for database operations
- Escape output appropriately for the context

**2. Authentication & Authorization**
- Use the built-in session management system
- Implement proper permission checks
- Log authentication events

**3. Error Handling**
- Don't expose sensitive information in error messages
- Log security-relevant errors
- Use structured error responses

**4. Configuration**
- Use secure defaults
- Validate configuration values
- Support environment variable overrides

**5. Dependencies**
- Keep dependencies updated
- Use known-secure libraries
- Validate third-party integrations

### Security Code Review Guidelines

When reviewing code, check for:

- [ ] Input validation on all user inputs
- [ ] Proper error handling without information disclosure
- [ ] Security logging for relevant events
- [ ] Rate limiting on public endpoints
- [ ] Session management for authenticated features
- [ ] CSRF protection for state-changing operations
- [ ] SQL injection prevention
- [ ] XSS prevention in output
- [ ] Secure configuration handling

### Security Documentation

Document security features by:

- Adding security considerations to module documentation
- Including security configuration examples
- Documenting threat models and mitigations
- Providing security testing guidelines

For comprehensive security information, see the [Security Guide](security.md).

## Module Development

SpiderFoot's modular architecture makes it easy to add new functionality. The [Module Development Guide](../docs/developer/module_development.md) explains how to create, test, and document your own modules, including:

- Module structure and naming conventions
- Required and optional methods
- Handling events and results
- Debugging and troubleshooting modules

## API Development

SpiderFoot provides a RESTful API for automation and integration. See the [API Development Guide](../docs/developer/api_development.md) for details on available endpoints, authentication, and usage examples.

## Version Management

Learn how SpiderFoot manages releases, versioning, and changelogs in the [Version Management Guide](../docs/VERSION_MANAGEMENT.md). This is essential for maintaining compatibility and tracking changes.

## Documentation Build

Help keep the documentation up to date! The [Documentation Build Guide](../docs/DOCUMENTATION_BUILD.md) explains how to build, test, and contribute to the docs.

---

Authored by poppopjmp
