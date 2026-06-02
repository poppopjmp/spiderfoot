"""Tests for the correlation rule executor's collection-filter matching.

_apply_collection_filter is the per-event matching core of the correlation
engine. Correlation rules (and their regex patterns) are loaded from YAML, so a
malformed pattern must not abort the whole correlation run — a regression that
previously raised re.error and crashed _apply_collection_filter.
"""
from __future__ import annotations

import pytest

from spiderfoot.correlation.rule_executor import DefaultRuleExecutionStrategy


@pytest.fixture
def strategy():
    return DefaultRuleExecutionStrategy()


EVENTS = [{"data": "abc", "type": "X"}, {"data": "def", "type": "X"},
          {"data": "xyz", "type": "Y"}]


class TestExactFilter:
    def test_exact_match(self, strategy):
        out = strategy._apply_collection_filter(
            EVENTS, {"method": "exact", "field": "data", "value": "abc"})
        assert len(out) == 1 and out[0]["data"] == "abc"

    def test_exact_no_match(self, strategy):
        out = strategy._apply_collection_filter(
            EVENTS, {"method": "exact", "field": "data", "value": "nope"})
        assert out == []


class TestRegexFilter:
    def test_regex_match(self, strategy):
        out = strategy._apply_collection_filter(
            EVENTS, {"method": "regex", "field": "data", "value": "a.c"})
        assert len(out) == 1

    def test_regex_list_of_patterns(self, strategy):
        out = strategy._apply_collection_filter(
            EVENTS, {"method": "regex", "field": "data", "value": ["a.c", "x.z"]})
        assert len(out) == 2

    def test_invalid_regex_does_not_crash(self, strategy):
        # Regression: a malformed pattern raised re.error and aborted the run.
        out = strategy._apply_collection_filter(
            EVENTS, {"method": "regex", "field": "data", "value": "a(bc"})
        assert out == []

    def test_invalid_pattern_skipped_valid_still_applies(self, strategy):
        out = strategy._apply_collection_filter(
            EVENTS, {"method": "regex", "field": "data", "value": ["a(bc", "d.f"]})
        assert len(out) == 1 and out[0]["data"] == "def"


class TestUnknownMethod:
    def test_unknown_method_returns_all(self, strategy):
        # Unknown filter method degrades to no-filter (all events) rather than
        # raising.
        out = strategy._apply_collection_filter(
            EVENTS, {"method": "bogus", "field": "data", "value": "x"})
        assert len(out) == len(EVENTS)
