"""
CORS (Cross-Origin Resource Sharing) configuration for the SpiderFoot API.

Configurable via environment variables:
    SF_API_CORS_ORIGINS    — Comma-separated allowed origins (default: *)
    SF_API_CORS_METHODS    — Comma-separated allowed methods (default: *)
    SF_API_CORS_HEADERS    — Comma-separated allowed headers (default: *)
    SF_API_CORS_CREDENTIALS — Allow credentials (default: false)
    SF_API_CORS_MAX_AGE    — Preflight cache max age in seconds (default: 600)

Usage::

    from spiderfoot.api.cors_config import install_cors
    install_cors(app)
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger("spiderfoot.api.cors")


def _parse_list(env_var: str, default: str = "*") -> list[str]:
    """Parse a comma-separated env var into a list."""
    value = os.environ.get(env_var, default).strip()
    if value == "*":
        return ["*"]
    return [v.strip() for v in value.split(",") if v.strip()]


def install_cors(app: Any) -> None:
    """Install CORS middleware on a FastAPI/Starlette app.

    Reads configuration from environment variables so that
    production deployments can restrict origins without code changes.
    """
    from starlette.middleware.cors import CORSMiddleware

    origins = _parse_list("SF_API_CORS_ORIGINS")
    methods = _parse_list("SF_API_CORS_METHODS")
    headers = _parse_list("SF_API_CORS_HEADERS")
    credentials = os.environ.get("SF_API_CORS_CREDENTIALS", "false").lower() in ("1", "true", "yes")
    max_age = int(os.environ.get("SF_API_CORS_MAX_AGE", "600"))

    # When allowing all origins, credentials cannot be true (browser security)
    if "*" in origins and credentials:
        log.warning(
            "CORS: Cannot use allow_credentials=True with allow_origins=['*']. "
            "Disabling credentials. Set SF_API_CORS_ORIGINS to specific origins."
        )
        credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=credentials,
        allow_methods=methods,
        allow_headers=headers,
        max_age=max_age,
    )

    log.info(
        "CORS middleware installed: origins=%s, credentials=%s, max_age=%ds",
        origins[:3] if len(origins) > 3 else origins,
        credentials,
        max_age,
    )
