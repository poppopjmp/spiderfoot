"""
API Pagination Helpers for SpiderFoot FastAPI.

Provides standardized pagination across all API list endpoints with
consistent request parameters and response envelopes.

Features:
  - ``PaginationParams`` as FastAPI ``Depends()`` for query extraction
  - ``PaginatedResponse`` generic envelope with navigation metadata
  - ``paginate()`` utility for in-memory slicing
  - Sort parameter support (``sort_by`` / ``sort_order``)
  - Backward-compatible ``offset``/``limit`` query params mapped to pages
  - RFC 8288 ``Link`` header generation

Usage in a router::

    from spiderfoot.api.pagination import PaginationParams, paginate

    @router.get("/items")
    def list_items(params: PaginationParams = Depends()):
        items = get_all_items()
        return paginate(items, params)

"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from fastapi import Query


# -----------------------------------------------------------------------
# Pagination Parameters (FastAPI Depends-compatible)
# -----------------------------------------------------------------------

class PaginationParams:
    """Query parameter extractor for paginated endpoints.

    Supports two input modes:
      1. **Page-based**: ``page`` + ``page_size``
      2. **Offset-based**: ``offset`` + ``limit`` (backward compat)

    When both are provided, page-based takes priority.
    """

    # Configurable constraints
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 1000
    MIN_PAGE_SIZE = 1

    def __init__(
        self,
        page: Optional[int] = Query(None, ge=1, description="Page number (1-based)"),
        page_size: Optional[int] = Query(None, ge=1, le=1000, description="Items per page"),
        offset: Optional[int] = Query(None, ge=0, description="Offset (backward compat)"),
        limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit (backward compat)"),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
        sort_order: Optional[str] = Query(
            "asc",
            regex="^(asc|desc)$",
            description="Sort order: asc or desc",
        ),
    ):
        # Resolve page_size/limit
        if page_size is not None:
            self._page_size = min(max(page_size, self.MIN_PAGE_SIZE), self.MAX_PAGE_SIZE)
        elif limit is not None:
            self._page_size = min(max(limit, self.MIN_PAGE_SIZE), self.MAX_PAGE_SIZE)
        else:
            self._page_size = self.DEFAULT_PAGE_SIZE

        # Resolve page/offset
        if page is not None:
            self._page = max(page, 1)
            self._offset = (self._page - 1) * self._page_size
        elif offset is not None:
            self._offset = max(offset, 0)
            self._page = (self._offset // self._page_size) + 1
        else:
            self._page = 1
            self._offset = 0

        self.sort_by = sort_by
        self.sort_order = sort_order or "asc"

    @property
    def page(self) -> int:
        """Current page number (1-based)."""
        return self._page

    @property
    def page_size(self) -> int:
        """Items per page."""
        return self._page_size

    @property
    def offset(self) -> int:
        """Computed offset."""
        return self._offset

    @property
    def limit(self) -> int:
        """Alias for page_size (backward compat)."""
        return self._page_size

    @property
    def is_descending(self) -> bool:
        """Whether sort order is descending."""
        return self.sort_order == "desc"

    def __repr__(self) -> str:
        return (
            f"PaginationParams(page={self.page}, page_size={self.page_size}, "
            f"offset={self.offset}, sort_by={self.sort_by}, sort_order={self.sort_order})"
        )


# -----------------------------------------------------------------------
# Paginated Response Envelope
# -----------------------------------------------------------------------

@dataclass
class PaginatedResponse:
    """Standardized paginated response envelope.

    JSON shape::

        {
            "items": [...],
            "total": 150,
            "page": 2,
            "page_size": 50,
            "pages": 3,
            "has_next": true,
            "has_previous": true
        }
    """

    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_previous: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "pages": self.pages,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
        }

    @property
    def offset(self) -> int:
        """Backward-compatible offset."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Backward-compatible limit."""
        return self.page_size


# -----------------------------------------------------------------------
# paginate() — main utility
# -----------------------------------------------------------------------

def paginate(
    items: Sequence[Any],
    params: PaginationParams,
    *,
    total: Optional[int] = None,
    sort_key: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Paginate a sequence of items using the given parameters.

    Args:
        items: Full collection to paginate.
        params: Pagination parameters (from request).
        total: Override total count (e.g. from DB COUNT query).
        sort_key: Optional callable for sorting (like ``key=`` in sorted()).
                  Uses ``params.sort_by`` and ``params.sort_order``.

    Returns:
        Dict matching ``PaginatedResponse`` shape.
    """
    all_items = list(items)

    # Sort if requested
    if params.sort_by and sort_key is not None:
        try:
            all_items = sorted(
                all_items,
                key=sort_key,
                reverse=params.is_descending,
            )
        except (TypeError, KeyError):
            pass  # Skip sort on error

    total_count = total if total is not None else len(all_items)
    total_pages = max(1, math.ceil(total_count / params.page_size))
    page = min(params.page, total_pages)

    # Slice
    start = params.offset
    end = start + params.page_size
    page_items = all_items[start:end]

    return PaginatedResponse(
        items=page_items,
        total=total_count,
        page=page,
        page_size=params.page_size,
        pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    ).to_dict()


def paginate_query(
    items: Sequence[Any],
    params: PaginationParams,
    *,
    total: Optional[int] = None,
) -> Dict[str, Any]:
    """Paginate pre-sliced query results (DB already applied LIMIT/OFFSET).

    Use when the database handles pagination and you only have
    the current page's items plus a total count.

    Args:
        items: Items for the current page (already sliced).
        params: Pagination parameters.
        total: Total count from DB (required for accurate metadata).

    Returns:
        Dict matching ``PaginatedResponse`` shape.
    """
    total_count = total if total is not None else len(items)
    total_pages = max(1, math.ceil(total_count / params.page_size))
    page = min(params.page, total_pages)

    return PaginatedResponse(
        items=list(items),
        total=total_count,
        page=page,
        page_size=params.page_size,
        pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    ).to_dict()


# -----------------------------------------------------------------------
# Sort helpers
# -----------------------------------------------------------------------

def dict_sort_key(sort_by: str) -> Callable:
    """Create a sort key function for dicts.

    Usage::

        result = paginate(items, params, sort_key=dict_sort_key(params.sort_by))
    """
    def _key(item):
        if isinstance(item, dict):
            return item.get(sort_by, "")
        return getattr(item, sort_by, "")
    return _key


def attr_sort_key(sort_by: str) -> Callable:
    """Create a sort key function for objects with attributes."""
    def _key(item):
        return getattr(item, sort_by, "")
    return _key


# -----------------------------------------------------------------------
# Link header generation (RFC 8288)
# -----------------------------------------------------------------------

def generate_link_header(
    base_url: str,
    page: int,
    page_size: int,
    total_pages: int,
) -> str:
    """Generate RFC 8288 Link header for pagination.

    Args:
        base_url: Request URL without pagination parameters.
        page: Current page number.
        page_size: Items per page.
        total_pages: Total number of pages.

    Returns:
        Link header value string.
    """
    separator = "&" if "?" in base_url else "?"
    links = []

    if page < total_pages:
        links.append(
            f'<{base_url}{separator}page={page + 1}&page_size={page_size}>; rel="next"'
        )
    if page > 1:
        links.append(
            f'<{base_url}{separator}page={page - 1}&page_size={page_size}>; rel="prev"'
        )
    links.append(
        f'<{base_url}{separator}page=1&page_size={page_size}>; rel="first"'
    )
    links.append(
        f'<{base_url}{separator}page={total_pages}&page_size={page_size}>; rel="last"'
    )

    return ", ".join(links)


# -----------------------------------------------------------------------
# Convenience: create params without FastAPI Depends
# -----------------------------------------------------------------------

def make_params(
    page: int = 1,
    page_size: int = 50,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
) -> PaginationParams:
    """Create ``PaginationParams`` programmatically (for internal use / testing)."""
    p = object.__new__(PaginationParams)
    p._page = max(page, 1)
    p._page_size = min(max(page_size, 1), 1000)
    p._offset = (p._page - 1) * p._page_size
    p.sort_by = sort_by
    p.sort_order = sort_order
    return p
