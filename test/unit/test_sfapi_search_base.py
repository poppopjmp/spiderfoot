import pytest
from spiderfoot.api import search_base

def test_search_base_returns_empty_list():
    config = {}
    result = search_base.search_base(config)
    assert isinstance(result, list)
    assert result == []


def test_search_base_accepts_args_kwargs():
    config = {"foo": "bar"}
    result = search_base.search_base(config, 1, 2, key="value")
    assert isinstance(result, list)
    assert result == []


def test_search_base_docstring():
    assert search_base.search_base.__doc__
    assert "Returns empty list" in search_base.search_base.__doc__ or "empty list" in search_base.search_base.__doc__
