"""
Tests for API Pagination Helpers (Cycle 25).

Covers:
- PaginationParams construction (page-based, offset-based, defaults)
- PaginationParams edge cases (validation, clamping)
- PaginatedResponse serialization
- paginate() utility (full slicing, sorting, edge cases)
- paginate_query() for pre-sliced results
- Sort helpers (dict_sort_key, attr_sort_key)
- Link header generation (RFC 8288)
- make_params() convenience constructor
"""

import pytest


# ===========================================================================
# PaginationParams
# ===========================================================================

class TestPaginationParams:
    """PaginationParams construction and property tests."""

    def test_defaults(self):
        from spiderfoot.api.pagination import make_params
        p = make_params()
        assert p.page == 1
        assert p.page_size == 50
        assert p.offset == 0
        assert p.sort_by is None
        assert p.sort_order == "asc"

    def test_page_based(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page=3, page_size=20)
        assert p.page == 3
        assert p.page_size == 20
        assert p.offset == 40

    def test_page_1(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page=1, page_size=10)
        assert p.offset == 0

    def test_limit_alias(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page_size=25)
        assert p.limit == 25

    def test_is_descending(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(sort_order="desc")
        assert p.is_descending is True
        p2 = make_params(sort_order="asc")
        assert p2.is_descending is False

    def test_repr(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page=2, page_size=10)
        r = repr(p)
        assert "page=2" in r
        assert "page_size=10" in r

    def test_page_clamped_to_1(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page=0)
        assert p.page == 1

    def test_page_size_clamped_max(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page_size=5000)
        assert p.page_size == 1000

    def test_page_size_clamped_min(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page_size=0)
        assert p.page_size == 1


class TestPaginationParamsFastAPI:
    """PaginationParams via direct __init__ (simulating FastAPI injection)."""

    def test_page_mode(self):
        from spiderfoot.api.pagination import PaginationParams
        p = PaginationParams(page=2, page_size=10, offset=None, limit=None)
        assert p.page == 2
        assert p.page_size == 10
        assert p.offset == 10

    def test_offset_mode(self):
        from spiderfoot.api.pagination import PaginationParams
        p = PaginationParams(page=None, page_size=None, offset=20, limit=10)
        assert p.page == 3  # offset 20 / limit 10 = page 3
        assert p.page_size == 10
        assert p.offset == 20

    def test_page_takes_priority(self):
        from spiderfoot.api.pagination import PaginationParams
        p = PaginationParams(page=2, page_size=10, offset=100, limit=5)
        assert p.page == 2
        assert p.page_size == 10
        assert p.offset == 10  # page-based wins

    def test_all_none_defaults(self):
        from spiderfoot.api.pagination import PaginationParams
        p = PaginationParams(page=None, page_size=None, offset=None, limit=None)
        assert p.page == 1
        assert p.page_size == 50
        assert p.offset == 0

    def test_sort_defaults(self):
        from spiderfoot.api.pagination import PaginationParams
        p = PaginationParams(page=None, page_size=None, offset=None, limit=None, sort_by=None, sort_order=None)
        assert p.sort_order == "asc"


# ===========================================================================
# PaginatedResponse
# ===========================================================================

class TestPaginatedResponse:
    """PaginatedResponse dataclass tests."""

    def test_to_dict(self):
        from spiderfoot.api.pagination import PaginatedResponse
        resp = PaginatedResponse(
            items=["a", "b"],
            total=10,
            page=1,
            page_size=5,
            pages=2,
            has_next=True,
            has_previous=False,
        )
        d = resp.to_dict()
        assert d["items"] == ["a", "b"]
        assert d["total"] == 10
        assert d["page"] == 1
        assert d["pages"] == 2
        assert d["has_next"] is True
        assert d["has_previous"] is False

    def test_offset_property(self):
        from spiderfoot.api.pagination import PaginatedResponse
        resp = PaginatedResponse(
            items=[], total=0, page=3, page_size=10, pages=1,
            has_next=False, has_previous=True,
        )
        assert resp.offset == 20

    def test_limit_property(self):
        from spiderfoot.api.pagination import PaginatedResponse
        resp = PaginatedResponse(
            items=[], total=0, page=1, page_size=25, pages=1,
            has_next=False, has_previous=False,
        )
        assert resp.limit == 25


# ===========================================================================
# paginate()
# ===========================================================================

class TestPaginate:
    """paginate() utility tests."""

    def test_basic_pagination(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = list(range(100))
        result = paginate(items, make_params(page=1, page_size=10))
        assert result["items"] == list(range(10))
        assert result["total"] == 100
        assert result["page"] == 1
        assert result["pages"] == 10
        assert result["has_next"] is True
        assert result["has_previous"] is False

    def test_second_page(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = list(range(25))
        result = paginate(items, make_params(page=2, page_size=10))
        assert result["items"] == list(range(10, 20))
        assert result["page"] == 2
        assert result["has_next"] is True
        assert result["has_previous"] is True

    def test_last_page(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = list(range(25))
        result = paginate(items, make_params(page=3, page_size=10))
        assert result["items"] == [20, 21, 22, 23, 24]
        assert result["has_next"] is False
        assert result["has_previous"] is True

    def test_empty_collection(self):
        from spiderfoot.api.pagination import paginate, make_params
        result = paginate([], make_params())
        assert result["items"] == []
        assert result["total"] == 0
        assert result["pages"] == 1
        assert result["has_next"] is False

    def test_single_item(self):
        from spiderfoot.api.pagination import paginate, make_params
        result = paginate(["only"], make_params(page_size=10))
        assert result["items"] == ["only"]
        assert result["total"] == 1
        assert result["pages"] == 1

    def test_exact_page_boundary(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = list(range(20))
        result = paginate(items, make_params(page=2, page_size=10))
        assert result["items"] == list(range(10, 20))
        assert result["pages"] == 2
        assert result["has_next"] is False

    def test_page_beyond_total(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = list(range(5))
        result = paginate(items, make_params(page=100, page_size=10))
        # Page clamped to total_pages
        assert result["items"] == []
        assert result["page"] == 1

    def test_with_total_override(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = list(range(10))
        result = paginate(items, make_params(page=1, page_size=10), total=100)
        assert result["total"] == 100
        assert result["pages"] == 10

    def test_with_sort(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = [{"name": "Charlie"}, {"name": "Alice"}, {"name": "Bob"}]
        params = make_params(page=1, page_size=10, sort_by="name", sort_order="asc")
        result = paginate(items, params, sort_key=lambda x: x.get("name", ""))
        assert result["items"][0]["name"] == "Alice"
        assert result["items"][2]["name"] == "Charlie"

    def test_with_sort_desc(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = [{"val": 1}, {"val": 3}, {"val": 2}]
        params = make_params(sort_by="val", sort_order="desc")
        result = paginate(items, params, sort_key=lambda x: x.get("val", 0))
        assert result["items"][0]["val"] == 3

    def test_sort_without_key_is_noop(self):
        from spiderfoot.api.pagination import paginate, make_params
        items = [3, 1, 2]
        params = make_params(sort_by="field")
        # No sort_key provided — order preserved
        result = paginate(items, params)
        assert result["items"] == [3, 1, 2]


# ===========================================================================
# paginate_query()
# ===========================================================================

class TestPaginateQuery:
    """paginate_query() for pre-sliced DB results."""

    def test_basic(self):
        from spiderfoot.api.pagination import paginate_query, make_params
        # Simulating DB returned page 2 of results
        page_items = ["item11", "item12", "item13"]
        result = paginate_query(
            page_items,
            make_params(page=2, page_size=10),
            total=23,
        )
        assert result["items"] == ["item11", "item12", "item13"]
        assert result["total"] == 23
        assert result["page"] == 2
        assert result["pages"] == 3
        assert result["has_next"] is True
        assert result["has_previous"] is True

    def test_without_total(self):
        from spiderfoot.api.pagination import paginate_query, make_params
        result = paginate_query(["a", "b"], make_params())
        assert result["total"] == 2


# ===========================================================================
# Sort Helpers
# ===========================================================================

class TestSortHelpers:
    """dict_sort_key and attr_sort_key tests."""

    def test_dict_sort_key(self):
        from spiderfoot.api.pagination import dict_sort_key
        items = [{"name": "C"}, {"name": "A"}, {"name": "B"}]
        sorted_items = sorted(items, key=dict_sort_key("name"))
        assert sorted_items[0]["name"] == "A"

    def test_dict_sort_key_missing(self):
        from spiderfoot.api.pagination import dict_sort_key
        items = [{"name": "B"}, {}, {"name": "A"}]
        sorted_items = sorted(items, key=dict_sort_key("name"))
        assert sorted_items[0] == {}  # empty string sorts first

    def test_attr_sort_key(self):
        from spiderfoot.api.pagination import attr_sort_key

        class Obj:
            def __init__(self, val):
                self.val = val

        items = [Obj(3), Obj(1), Obj(2)]
        sorted_items = sorted(items, key=attr_sort_key("val"))
        assert sorted_items[0].val == 1

    def test_attr_sort_key_missing(self):
        from spiderfoot.api.pagination import attr_sort_key

        class Obj:
            pass

        items = [Obj(), Obj()]
        # Should not raise — returns empty string for missing attrs
        sorted(items, key=attr_sort_key("missing"))


# ===========================================================================
# Link Header Generation
# ===========================================================================

class TestLinkHeader:
    """RFC 8288 Link header generation tests."""

    def test_middle_page(self):
        from spiderfoot.api.pagination import generate_link_header
        link = generate_link_header("/api/items", page=2, page_size=10, total_pages=5)
        assert 'rel="next"' in link
        assert 'rel="prev"' in link
        assert 'rel="first"' in link
        assert 'rel="last"' in link
        assert "page=3" in link
        assert "page=1" in link

    def test_first_page(self):
        from spiderfoot.api.pagination import generate_link_header
        link = generate_link_header("/api/items", page=1, page_size=10, total_pages=3)
        assert 'rel="next"' in link
        assert 'rel="prev"' not in link
        assert 'rel="first"' in link

    def test_last_page(self):
        from spiderfoot.api.pagination import generate_link_header
        link = generate_link_header("/api/items", page=3, page_size=10, total_pages=3)
        assert 'rel="next"' not in link
        assert 'rel="prev"' in link
        assert 'rel="last"' in link

    def test_single_page(self):
        from spiderfoot.api.pagination import generate_link_header
        link = generate_link_header("/api/items", page=1, page_size=50, total_pages=1)
        assert 'rel="next"' not in link
        assert 'rel="prev"' not in link
        assert 'rel="first"' in link
        assert 'rel="last"' in link

    def test_base_url_with_query(self):
        from spiderfoot.api.pagination import generate_link_header
        link = generate_link_header("/api/items?status=active", page=1, page_size=10, total_pages=2)
        # Should use & not ? for separator
        assert "&page=" in link


# ===========================================================================
# make_params()
# ===========================================================================

class TestMakeParams:
    """make_params convenience constructor."""

    def test_basic(self):
        from spiderfoot.api.pagination import make_params
        p = make_params(page=3, page_size=25, sort_by="name", sort_order="desc")
        assert p.page == 3
        assert p.page_size == 25
        assert p.offset == 50
        assert p.sort_by == "name"
        assert p.is_descending is True

    def test_defaults(self):
        from spiderfoot.api.pagination import make_params
        p = make_params()
        assert p.page == 1
        assert p.page_size == 50
