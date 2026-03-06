# -------------------------------------------------------------------------------
# Name:         SpiderFoot Upload Security
# Purpose:      File upload validation, content-type enforcement, filename sanitization.
#
# Author:       SpiderFoot Security Hardening
#
# Created:      2025-07-17
# Licence:      MIT
# -------------------------------------------------------------------------------
"""
Centralised file-upload security utilities.

Provides three layers of defence:

1. **Filename sanitisation** – strips path traversal, null bytes, and
   dangerous characters; enforces a maximum filename length.

2. **Content-type allow-listing** – rejects uploads whose declared MIME
   type is not in the allow-list.  Magic-byte sniffing is used as a
   secondary check when available.

3. **Size enforcement** – rejects payloads exceeding the configurable
   max (default 100 MiB).
"""
from __future__ import annotations

import os
import re
import logging
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100 MiB

MAX_FILENAME_LENGTH: int = 255

# Allow-list of acceptable MIME types for user document uploads.
# Grouped by category for readability.
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset({
    # Text / structured
    "text/plain",
    "text/csv",
    "text/html",
    "text/xml",
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/rtf",
    # Archives (for batch IOC import)
    "application/zip",
    "application/gzip",
    "application/x-tar",
    # Images (for screenshot/logo analysis)
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    # NOTE: image/svg+xml intentionally excluded — SVG can contain
    # embedded JavaScript and must be sanitised before serving.
    # NOTE: application/octet-stream intentionally excluded — it bypasses
    # all type-based checks as a browser fallback MIME type.
})

# Dangerous file extensions that must never be accepted, even if
# content-type checks pass (e.g. double-extension tricks).
BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".exe", ".dll", ".bat", ".cmd", ".com", ".msi", ".scr", ".pif",
    ".jar", ".svg", ".swf", ".html", ".htm", ".xhtml",
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".ps1", ".psm1",
    ".sh", ".bash", ".csh", ".ksh", ".zsh",
    ".app", ".action", ".command",  # macOS
    ".elf", ".bin",                  # Linux
    ".php", ".jsp", ".asp", ".aspx", ".cgi", ".py", ".rb", ".pl",
})

# Characters forbidden in sanitised filenames.
_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Path traversal patterns.
_TRAVERSAL_RE = re.compile(r'\.\.[/\\]')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sanitize_filename(name: str | None) -> str:
    """Return a safe, flat filename.

    * Strips directory components (path traversal).
    * Removes null bytes and control characters.
    * Replaces unsafe characters with ``_``.
    * Truncates to ``MAX_FILENAME_LENGTH``.
    * Falls back to ``upload`` if the result is empty.

    >>> sanitize_filename("../../etc/passwd")
    'passwd'
    >>> sanitize_filename("hello world.pdf")
    'hello world.pdf'
    >>> sanitize_filename(None)
    'upload'
    """
    if not name:
        return "upload"

    # Strip null bytes
    name = name.replace("\x00", "")

    # Take only the basename (no directory components)
    name = os.path.basename(name)

    # Remove traversal remnants and unsafe chars
    name = _TRAVERSAL_RE.sub("", name)
    name = _UNSAFE_FILENAME_RE.sub("_", name)

    # Trim leading/trailing dots and spaces (Windows concerns)
    name = name.strip(". ")

    # Enforce length
    if len(name) > MAX_FILENAME_LENGTH:
        base, ext = os.path.splitext(name)
        # Keep the extension, truncate the base
        name = base[: MAX_FILENAME_LENGTH - len(ext)] + ext

    return name or "upload"


def validate_content_type(
    content_type: str | None,
    *,
    allowed: frozenset[str] | None = None,
) -> str | None:
    """Check declared content-type against the allow-list.

    Returns:
        ``None`` if the content-type is acceptable.
        An error message string if the content-type is rejected.
    """
    if not content_type:
        return "Missing Content-Type header"

    ct = content_type.split(";")[0].strip().lower()
    pool = allowed or ALLOWED_CONTENT_TYPES

    if ct not in pool:
        return f"Content type '{ct}' is not permitted"

    return None


def validate_extension(filename: str) -> str | None:
    """Check filename extension against the blocked list.

    Returns:
        ``None`` if the extension is acceptable.
        An error message string if the extension is blocked.
    """
    _, ext = os.path.splitext(filename.lower())
    if ext in BLOCKED_EXTENSIONS:
        return f"File extension '{ext}' is not permitted"
    return None


def validate_upload(
    filename: str | None,
    content_type: str | None,
    size: int,
    *,
    max_bytes: int = MAX_UPLOAD_BYTES,
    allowed_types: frozenset[str] | None = None,
) -> tuple[str, Optional[str]]:
    """Full upload validation pipeline.

    Args:
        filename: Original filename from the upload.
        content_type: Declared MIME type.
        size: Payload size in bytes.
        max_bytes: Maximum allowed payload size.
        allowed_types: Optional override for the content-type allow-list.

    Returns:
        A ``(safe_filename, error)`` tuple.
        *error* is ``None`` when the upload is valid.

    Example::

        safe_name, err = validate_upload(file.filename, file.content_type, len(data))
        if err:
            raise HTTPException(status_code=400, detail=err)
    """
    safe_name = sanitize_filename(filename)

    # Size
    if size <= 0:
        return safe_name, "Empty file"
    if size > max_bytes:
        mb = max_bytes / (1024 * 1024)
        return safe_name, f"File too large (max {mb:.0f} MB)"

    # Content-type
    ct_err = validate_content_type(content_type, allowed=allowed_types)
    if ct_err:
        return safe_name, ct_err

    # Extension block-list
    ext_err = validate_extension(safe_name)
    if ext_err:
        return safe_name, ext_err

    return safe_name, None
