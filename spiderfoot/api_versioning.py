#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# Name:         api_versioning
# Purpose:      API versioning framework for SpiderFoot REST endpoints.
#               Supports URL-prefix, header-based, and query-parameter
#               version negotiation with deprecation lifecycle management.
#
# Author:       SpiderFoot Team
# Created:      2025-07-08
# Copyright:    (c) SpiderFoot Team 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

"""
SpiderFoot API Versioning

Provides version negotiation, route registration, and deprecation
lifecycle management for the REST API::

    from spiderfoot.api_versioning import APIVersionManager, APIVersion

    vm = APIVersionManager(default_version="v2")
    vm.register_version(APIVersion("v1", deprecated=True, sunset="2025-12-01"))
    vm.register_version(APIVersion("v2", current=True))
    vm.register_version(APIVersion("v3", beta=True))

    # Route resolution
    handler = vm.resolve("/api/v1/scans", "GET")
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger("spiderfoot.api_versioning")

__all__ = [
    "VersionStrategy",
    "VersionStatus",
    "APIVersion",
    "VersionedRoute",
    "APIVersionManager",
    "VersionNegotiator",
]


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class VersionStrategy(Enum):
    """How version is communicated in requests."""
    URL_PREFIX = "url_prefix"  # /api/v1/scans
    HEADER = "header"          # X-API-Version: v1
    QUERY = "query"            # /api/scans?version=v1
    ACCEPT = "accept"          # Accept: application/vnd.spiderfoot.v1+json


class VersionStatus(Enum):
    """Version lifecycle status."""
    BETA = "beta"
    CURRENT = "current"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"          # no longer available


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class APIVersion:
    """Describes an API version and its lifecycle."""

    version: str                # e.g., "v1", "v2"
    status: VersionStatus = VersionStatus.CURRENT
    released: str = ""          # ISO date "2024-01-15"
    deprecated_at: str = ""     # ISO date when deprecated
    sunset_at: str = ""         # ISO date when removed
    changelog: str = ""         # description of changes
    breaking_changes: list[str] = field(default_factory=list)

    @property
    def is_available(self) -> bool:
        return self.status != VersionStatus.SUNSET

    @property
    def is_deprecated(self) -> bool:
        return self.status in (VersionStatus.DEPRECATED, VersionStatus.SUNSET)

    @property
    def numeric(self) -> int:
        """Extract numeric portion for comparison: v2 -> 2."""
        m = re.search(r"(\d+)", self.version)
        return int(m.group(1)) if m else 0

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "status": self.status.value,
            "released": self.released,
            "deprecated_at": self.deprecated_at,
            "sunset_at": self.sunset_at,
            "changelog": self.changelog,
            "breaking_changes": self.breaking_changes,
            "is_available": self.is_available,
        }


@dataclass
class VersionedRoute:
    """A route registered for a specific API version."""

    path: str               # e.g., "/scans"
    method: str             # GET, POST, etc.
    version: str            # e.g., "v1"
    handler_name: str = ""  # function/handler name
    added_in: str = ""      # version when added
    deprecated_in: str = "" # version when deprecated
    removed_in: str = ""    # version when removed
    description: str = ""
    response_schema: dict | None = None
    transforms: list[Callable] = field(default_factory=list)

    @property
    def full_path(self) -> str:
        return f"/api/{self.version}{self.path}"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "full_path": self.full_path,
            "method": self.method,
            "version": self.version,
            "handler_name": self.handler_name,
            "added_in": self.added_in,
            "deprecated_in": self.deprecated_in,
            "removed_in": self.removed_in,
            "description": self.description,
        }


# ------------------------------------------------------------------
# Version Negotiator
# ------------------------------------------------------------------

class VersionNegotiator:
    """Extracts the requested API version from a request."""

    def __init__(self, *,
                 strategies: list[VersionStrategy] | None = None,
                 default_version: str = "v1",
                 header_name: str = "X-API-Version",
                 query_param: str = "version",
                 vendor_type: str = "application/vnd.spiderfoot"):
        self._strategies = strategies or [VersionStrategy.URL_PREFIX]
        self._default = default_version
        self._header_name = header_name
        self._query_param = query_param
        self._vendor_type = vendor_type

    def negotiate(self, *,
                  path: str = "",
                  headers: dict[str, str] | None = None,
                  query_params: dict[str, str] | None = None) -> str:
        """Determine the version from the request context.

        Tries each strategy in order and returns the first match.
        """
        headers = headers or {}
        query_params = query_params or {}

        for strategy in self._strategies:
            version = None

            if strategy == VersionStrategy.URL_PREFIX:
                version = self._from_url(path)
            elif strategy == VersionStrategy.HEADER:
                version = headers.get(self._header_name)
            elif strategy == VersionStrategy.QUERY:
                version = query_params.get(self._query_param)
            elif strategy == VersionStrategy.ACCEPT:
                version = self._from_accept(headers.get("Accept", ""))

            if version:
                return version

        return self._default

    def _from_url(self, path: str) -> str | None:
        m = re.match(r"/api/(v\d+)/", path)
        return m.group(1) if m else None

    def _from_accept(self, accept: str) -> str | None:
        # application/vnd.spiderfoot.v2+json
        m = re.search(
            rf"{re.escape(self._vendor_type)}\.(v\d+)",
            accept,
        )
        return m.group(1) if m else None


# ------------------------------------------------------------------
# Version Manager
# ------------------------------------------------------------------

class APIVersionManager:
    """Manages API versions, routes, and lifecycle transitions."""

    def __init__(self, *,
                 default_version: str = "v1",
                 strategies: list[VersionStrategy] | None = None):
        self._versions: dict[str, APIVersion] = {}
        self._routes: dict[str, list[VersionedRoute]] = {}  # version -> routes
        self._default = default_version
        self._negotiator = VersionNegotiator(
            default_version=default_version,
            strategies=strategies or [VersionStrategy.URL_PREFIX],
        )
        self._transforms: dict[tuple[str, str], list[Callable]] = {}
        # (from_version, to_version) -> transform chain

    # --- Version CRUD ---

    def register_version(self, version: APIVersion) -> None:
        """Register an API version."""
        self._versions[version.version] = version
        if version.version not in self._routes:
            self._routes[version.version] = []
        log.info("Registered API version %s (%s)",
                 version.version, version.status.value)

    def get_version(self, version: str) -> APIVersion | None:
        return self._versions.get(version)

    def list_versions(self, *, include_sunset: bool = False) -> list[APIVersion]:
        versions = list(self._versions.values())
        if not include_sunset:
            versions = [v for v in versions if v.is_available]
        return sorted(versions, key=lambda v: v.numeric)

    def current_version(self) -> APIVersion | None:
        for v in self._versions.values():
            if v.status == VersionStatus.CURRENT:
                return v
        return None

    def deprecate_version(self, version: str,
                          sunset_at: str = "") -> bool:
        """Mark a version as deprecated."""
        v = self._versions.get(version)
        if v is None:
            return False
        v.status = VersionStatus.DEPRECATED
        v.deprecated_at = sunset_at or time.strftime("%Y-%m-%d")
        if sunset_at:
            v.sunset_at = sunset_at
        log.info("Deprecated API version %s", version)
        return True

    def sunset_version(self, version: str) -> bool:
        """Fully remove a version."""
        v = self._versions.get(version)
        if v is None:
            return False
        v.status = VersionStatus.SUNSET
        log.info("Sunset API version %s", version)
        return True

    # --- Route management ---

    def add_route(self, route: VersionedRoute) -> None:
        """Register a route for a specific version."""
        if route.version not in self._routes:
            self._routes[route.version] = []
        self._routes[route.version].append(route)

    def add_routes(self, routes: list[VersionedRoute]) -> None:
        for r in routes:
            self.add_route(r)

    def get_routes(self, version: str) -> list[VersionedRoute]:
        """Get all routes for a version."""
        return list(self._routes.get(version, []))

    def find_route(self, version: str, path: str,
                   method: str) -> VersionedRoute | None:
        """Find a specific route."""
        method_upper = method.upper()
        for r in self._routes.get(version, []):
            if r.path == path and r.method == method_upper:
                return r
        return None

    def copy_routes(self, from_version: str, to_version: str,
                    *, exclude: set[str] | None = None) -> int:
        """Copy all routes from one version to another.

        Returns count of copied routes.
        """
        exclude = exclude or set()
        source = self._routes.get(from_version, [])
        count = 0
        for r in source:
            if r.path in exclude:
                continue
            new_route = VersionedRoute(
                path=r.path,
                method=r.method,
                version=to_version,
                handler_name=r.handler_name,
                added_in=r.added_in or from_version,
                description=r.description,
            )
            self.add_route(new_route)
            count += 1
        return count

    # --- Response transforms ---

    def register_transform(self, from_version: str, to_version: str,
                           transform: Callable[[dict], dict]) -> None:
        """Register a response transform between versions.

        Transforms modify response bodies when a client requests
        an older version but the backend returns the current format.
        """
        key = (from_version, to_version)
        if key not in self._transforms:
            self._transforms[key] = []
        self._transforms[key].append(transform)

    def apply_transforms(self, response: dict,
                         from_version: str,
                         to_version: str) -> dict:
        """Apply registered transforms from one version to another."""
        key = (from_version, to_version)
        transforms = self._transforms.get(key, [])
        result = response
        for t in transforms:
            result = t(result)
        return result

    # --- Negotiation ---

    def negotiate(self, *, path: str = "",
                  headers: dict[str, str] | None = None,
                  query_params: dict[str, str] | None = None) -> str:
        """Determine the requested API version."""
        version = self._negotiator.negotiate(
            path=path, headers=headers, query_params=query_params
        )
        # Validate it exists and is available
        v = self._versions.get(version)
        if v is None or not v.is_available:
            return self._default
        return version

    # --- Deprecation headers ---

    def deprecation_headers(self, version: str) -> dict[str, str]:
        """Generate deprecation-related HTTP headers."""
        v = self._versions.get(version)
        if v is None or not v.is_deprecated:
            return {}
        headers = {"Deprecation": "true"}
        if v.sunset_at:
            headers["Sunset"] = v.sunset_at
        current = self.current_version()
        if current:
            headers["Link"] = (
                f'</api/{current.version}/>; rel="successor-version"'
            )
        return headers

    # --- Compatibility check ---

    def is_compatible(self, requested: str, minimum: str) -> bool:
        """Check if the requested version meets the minimum."""
        req = self._versions.get(requested)
        min_v = self._versions.get(minimum)
        if req is None or min_v is None:
            return False
        return req.numeric >= min_v.numeric

    # --- Stats ---

    def stats(self) -> dict:
        total_routes = sum(len(r) for r in self._routes.values())
        return {
            "total_versions": len(self._versions),
            "available_versions": len([
                v for v in self._versions.values() if v.is_available
            ]),
            "deprecated_versions": len([
                v for v in self._versions.values() if v.is_deprecated
            ]),
            "total_routes": total_routes,
            "default_version": self._default,
            "current_version": (
                self.current_version().version
                if self.current_version() else None
            ),
        }
