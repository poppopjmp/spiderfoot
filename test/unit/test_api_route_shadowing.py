"""Guard against parameterized routes shadowing literal sibling routes.

Starlette matches routes in declaration order. If a parameterized route such as
``GET /scans/{scan_id}`` is declared before a literal sibling such as
``GET /scans/compare``, the literal endpoint becomes unreachable (the path
param swallows it) and returns the param handler's response in production.

This regression test assembles the full application and, for every literal
GET route, asserts that the route actually matched is the literal one — not a
parameterized sibling that precedes it. It permanently closes the bug class
fixed across the SARIF/notification-rules/report-templates/scan/health/etc.
routers.
"""
from __future__ import annotations

import re

import pytest

pytest.importorskip("fastapi")
from starlette.routing import Match


def _assembled_app():
    import spiderfoot.api.main as main
    return main.app


def _literal_get_paths(app):
    """All GET routes whose path has no `{param}` segment."""
    out = []
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path and "{" not in path:
            out.append(path)
    return out


def test_no_literal_get_route_is_shadowed():
    app = _assembled_app()
    shadowed = []
    for path in _literal_get_paths(app):
        # Find the first route (declaration order) that fully matches this path
        # for a GET request — that is the handler Starlette will dispatch to.
        for route in app.routes:
            try:
                match, _ = route.matches(
                    {"type": "http", "method": "GET", "path": path,
                     "path_params": {}}
                )
            except Exception:
                continue
            if match == Match.FULL:
                matched_path = getattr(route, "path", "")
                if "{" in matched_path:
                    shadowed.append((path, matched_path))
                break

    assert not shadowed, (
        "Literal GET routes shadowed by a parameterized sibling declared "
        "earlier (move the literal route before the {param} route):\n"
        + "\n".join(f"  {lit}  ->  shadowed by  {par}" for lit, par in shadowed)
    )
