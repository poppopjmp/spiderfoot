"""Convert root-level security files to re-export shims."""

from __future__ import annotations

import os

# Mapping of file to what it exports
FILE_EXPORTS = {
    "auth.py": [
        "AuthMethod",
        "Role",
        "AuthConfig",
        "AuthResult",
        "AuthGuard",
    ],
    "csrf_protection.py": [
        "CSRFProtection",
        "CSRFTool",
        "csrf_protect",
        "csrf_token",
        "init_csrf_protection",
    ],
    "security_compat.py": [
        "RequestContext",
        "get_request_context",
        "json_error_response",
    ],
    "security_integration.py": ["SecurityIntegrator"],
    "security_logging.py": [
        "SecurityEventType",
        "SecurityLogger",
        "ErrorHandler",
        "SecurityMonitor",
        "log_security_event",
        "handle_error",
    ],
    "security_middleware.py": [
        "SecurityConfigDefaults",
        "SpiderFootSecurityMiddleware",
        "CherryPySecurityTool",
        "FastAPISecurityMiddleware",
        "create_security_config",
        "validate_security_config",
        "get_security_status",
        "install_cherrypy_security",
        "install_fastapi_security",
    ],
    "service_auth.py": [
        "TokenValidationResult",
        "ServiceTokenIssuer",
        "ServiceTokenValidator",
        "generate_service_secret",
    ],
}


def make_shim(filename: str, exports: list[str]) -> str:
    """Generate shim content for a file."""
    base = filename.replace(".py", "")
    lines = [
        f'"""Backward-compatibility shim for {filename}.',
        "",
        f"This module re-exports from security/{filename} for backward compatibility.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f"from .security.{base} import (",
    ]
    for exp in exports:
        lines.append(f"    {exp},")
    lines.append(")")
    lines.append("")
    lines.append("__all__ = [")
    for exp in exports:
        lines.append(f'    "{exp}",')
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


# Convert all files
os.chdir("d:/github/spiderfoot/spiderfoot")
for filename, exports in FILE_EXPORTS.items():
    shim = make_shim(filename, exports)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(shim)
    print(f"Converted {filename} to shim ({len(exports)} exports)")

print(f"\nConverted {len(FILE_EXPORTS)} files to shims")
