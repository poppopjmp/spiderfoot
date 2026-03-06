# SpiderFoot API package
"""SpiderFoot REST API package.

Contains the FastAPI application, routers, middleware, and dependency
injection for the ``/api/v1/`` endpoints.
"""

from __future__ import annotations

from .api_devtools import (
    APIChangelog,
    APIIntrospector,
    ChangeType,
    OpenAPIExampleGenerator,
    SDKStubGenerator,
)

from .openapi_spec import OpenAPIGenerator

from .response_filter import (
    filter_scan_response,
    filter_user_response,
    strip_internal_fields,
)

from .version_negotiation import (
    APIVersion,
    APIVersionManager,
    VersionNegotiator,
    VersionStatus,
    VersionStrategy,
)

__all__: list[str] = [
    # API devtools
    "APIChangelog",
    "APIIntrospector",
    "ChangeType",
    "OpenAPIExampleGenerator",
    "SDKStubGenerator",
    # OpenAPI generator
    "OpenAPIGenerator",
    # Response filtering
    "filter_scan_response",
    "filter_user_response",
    "strip_internal_fields",
    # Version negotiation
    "APIVersion",
    "APIVersionManager",
    "VersionNegotiator",
    "VersionStatus",
    "VersionStrategy",
]
