"""Tests for spiderfoot.api_versioning."""

import unittest

from spiderfoot.api_versioning import (
    APIVersion,
    APIVersionManager,
    VersionedRoute,
    VersionNegotiator,
    VersionStatus,
    VersionStrategy,
)


class TestAPIVersion(unittest.TestCase):
    """Tests for APIVersion."""

    def test_basic(self):
        v = APIVersion("v1", status=VersionStatus.CURRENT)
        self.assertEqual(v.version, "v1")
        self.assertTrue(v.is_available)
        self.assertFalse(v.is_deprecated)

    def test_deprecated(self):
        v = APIVersion("v1", status=VersionStatus.DEPRECATED)
        self.assertTrue(v.is_deprecated)
        self.assertTrue(v.is_available)

    def test_sunset(self):
        v = APIVersion("v1", status=VersionStatus.SUNSET)
        self.assertFalse(v.is_available)
        self.assertTrue(v.is_deprecated)

    def test_numeric(self):
        self.assertEqual(APIVersion("v1").numeric, 1)
        self.assertEqual(APIVersion("v23").numeric, 23)

    def test_to_dict(self):
        v = APIVersion("v2", status=VersionStatus.CURRENT, released="2024-01-01")
        d = v.to_dict()
        self.assertEqual(d["version"], "v2")
        self.assertEqual(d["status"], "current")
        self.assertTrue(d["is_available"])


class TestVersionedRoute(unittest.TestCase):
    """Tests for VersionedRoute."""

    def test_full_path(self):
        r = VersionedRoute("/scans", "GET", "v1")
        self.assertEqual(r.full_path, "/api/v1/scans")

    def test_to_dict(self):
        r = VersionedRoute("/scans", "POST", "v2",
                          handler_name="createScan",
                          description="Create scan")
        d = r.to_dict()
        self.assertEqual(d["method"], "POST")
        self.assertEqual(d["handler_name"], "createScan")


class TestVersionNegotiator(unittest.TestCase):
    """Tests for VersionNegotiator."""

    def test_url_prefix(self):
        n = VersionNegotiator(strategies=[VersionStrategy.URL_PREFIX])
        v = n.negotiate(path="/api/v2/scans")
        self.assertEqual(v, "v2")

    def test_url_prefix_no_match(self):
        n = VersionNegotiator(
            strategies=[VersionStrategy.URL_PREFIX],
            default_version="v1",
        )
        v = n.negotiate(path="/api/scans")
        self.assertEqual(v, "v1")

    def test_header(self):
        n = VersionNegotiator(strategies=[VersionStrategy.HEADER])
        v = n.negotiate(headers={"X-API-Version": "v3"})
        self.assertEqual(v, "v3")

    def test_query(self):
        n = VersionNegotiator(strategies=[VersionStrategy.QUERY])
        v = n.negotiate(query_params={"version": "v2"})
        self.assertEqual(v, "v2")

    def test_accept_header(self):
        n = VersionNegotiator(strategies=[VersionStrategy.ACCEPT])
        v = n.negotiate(
            headers={"Accept": "application/vnd.spiderfoot.v2+json"}
        )
        self.assertEqual(v, "v2")

    def test_multiple_strategies_priority(self):
        n = VersionNegotiator(
            strategies=[VersionStrategy.URL_PREFIX, VersionStrategy.HEADER],
            default_version="v1",
        )
        # URL should win
        v = n.negotiate(
            path="/api/v2/scans",
            headers={"X-API-Version": "v3"},
        )
        self.assertEqual(v, "v2")

    def test_fallback_to_default(self):
        n = VersionNegotiator(
            strategies=[VersionStrategy.HEADER],
            default_version="v1",
        )
        v = n.negotiate(headers={})
        self.assertEqual(v, "v1")


class TestAPIVersionManager(unittest.TestCase):
    """Tests for APIVersionManager."""

    def setUp(self):
        self.vm = APIVersionManager(default_version="v1")
        self.vm.register_version(APIVersion("v1", VersionStatus.DEPRECATED))
        self.vm.register_version(APIVersion("v2", VersionStatus.CURRENT))
        self.vm.register_version(APIVersion("v3", VersionStatus.BETA))

    def test_register_version(self):
        self.assertEqual(len(self.vm.list_versions()), 3)

    def test_get_version(self):
        v = self.vm.get_version("v2")
        self.assertIsNotNone(v)
        self.assertEqual(v.status, VersionStatus.CURRENT)

    def test_get_version_missing(self):
        self.assertIsNone(self.vm.get_version("v99"))

    def test_list_versions_sorted(self):
        versions = self.vm.list_versions()
        nums = [v.numeric for v in versions]
        self.assertEqual(nums, sorted(nums))

    def test_list_versions_exclude_sunset(self):
        self.vm.sunset_version("v1")
        versions = self.vm.list_versions(include_sunset=False)
        self.assertFalse(any(v.version == "v1" for v in versions))

    def test_current_version(self):
        c = self.vm.current_version()
        self.assertEqual(c.version, "v2")

    def test_deprecate_version(self):
        self.assertTrue(self.vm.deprecate_version("v2"))
        v = self.vm.get_version("v2")
        self.assertEqual(v.status, VersionStatus.DEPRECATED)

    def test_deprecate_nonexistent(self):
        self.assertFalse(self.vm.deprecate_version("v99"))

    def test_sunset_version(self):
        self.assertTrue(self.vm.sunset_version("v1"))
        v = self.vm.get_version("v1")
        self.assertEqual(v.status, VersionStatus.SUNSET)

    def test_add_route(self):
        r = VersionedRoute("/scans", "GET", "v2", handler_name="listScans")
        self.vm.add_route(r)
        routes = self.vm.get_routes("v2")
        self.assertEqual(len(routes), 1)

    def test_find_route(self):
        self.vm.add_route(VersionedRoute("/scans", "GET", "v2"))
        self.vm.add_route(VersionedRoute("/scans", "POST", "v2"))
        r = self.vm.find_route("v2", "/scans", "POST")
        self.assertIsNotNone(r)
        self.assertEqual(r.method, "POST")

    def test_find_route_missing(self):
        self.assertIsNone(self.vm.find_route("v2", "/missing", "GET"))

    def test_copy_routes(self):
        self.vm.add_route(VersionedRoute("/scans", "GET", "v2"))
        self.vm.add_route(VersionedRoute("/scans", "POST", "v2"))
        self.vm.add_route(VersionedRoute("/config", "GET", "v2"))
        count = self.vm.copy_routes("v2", "v3")
        self.assertEqual(count, 3)
        self.assertEqual(len(self.vm.get_routes("v3")), 3)

    def test_copy_routes_exclude(self):
        self.vm.add_route(VersionedRoute("/scans", "GET", "v2"))
        self.vm.add_route(VersionedRoute("/old", "GET", "v2"))
        count = self.vm.copy_routes("v2", "v3", exclude={"/old"})
        self.assertEqual(count, 1)

    def test_negotiate_url(self):
        v = self.vm.negotiate(path="/api/v2/scans")
        self.assertEqual(v, "v2")

    def test_negotiate_sunset_fallback(self):
        self.vm.sunset_version("v1")
        v = self.vm.negotiate(path="/api/v1/scans")
        self.assertEqual(v, "v1")  # default fallback

    def test_deprecation_headers(self):
        h = self.vm.deprecation_headers("v1")
        self.assertEqual(h["Deprecation"], "true")
        self.assertIn("Link", h)

    def test_deprecation_headers_not_deprecated(self):
        h = self.vm.deprecation_headers("v2")
        self.assertEqual(h, {})

    def test_response_transform(self):
        def add_legacy_field(resp):
            resp["legacy_id"] = resp.get("id", "")
            return resp

        self.vm.register_transform("v2", "v1", add_legacy_field)
        response = {"id": "scan123", "name": "test"}
        transformed = self.vm.apply_transforms(response, "v2", "v1")
        self.assertEqual(transformed["legacy_id"], "scan123")

    def test_is_compatible(self):
        self.assertTrue(self.vm.is_compatible("v2", "v1"))
        self.assertTrue(self.vm.is_compatible("v2", "v2"))
        self.assertFalse(self.vm.is_compatible("v1", "v2"))

    def test_is_compatible_missing(self):
        self.assertFalse(self.vm.is_compatible("v99", "v1"))

    def test_stats(self):
        self.vm.add_route(VersionedRoute("/scans", "GET", "v2"))
        s = self.vm.stats()
        self.assertEqual(s["total_versions"], 3)
        self.assertEqual(s["total_routes"], 1)
        self.assertEqual(s["current_version"], "v2")
        self.assertEqual(s["default_version"], "v1")

    def test_add_routes_batch(self):
        routes = [
            VersionedRoute("/scans", "GET", "v2"),
            VersionedRoute("/scans", "POST", "v2"),
        ]
        self.vm.add_routes(routes)
        self.assertEqual(len(self.vm.get_routes("v2")), 2)


if __name__ == "__main__":
    unittest.main()
