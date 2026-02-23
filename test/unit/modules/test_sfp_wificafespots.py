from __future__ import annotations

"""Tests for sfp_wificafespots module."""

import pytest
from modules.sfp_wificafespots import sfp_wificafespots
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_wificafespots()

def test_meta(plugin):
    assert 'name' in plugin.meta
    assert 'dataSource' in plugin.meta
    assert isinstance(plugin.meta['categories'], list)
    assert len(plugin.meta['categories']) == 1

def test_opts(plugin):
    for opt in [
        'search_term', 'country', 'city', 'max_results', 'output_format']:
        assert opt in plugin.opts

def test_opts_defaults(plugin):
    assert plugin.opts['country'] == ''
    assert plugin.opts['city'] == ''
    assert plugin.opts['max_results'] == 50
    assert plugin.opts['output_format'] == 'summary'

def test_produced_events(plugin):
    assert 'WIFICAFESPOTS_HOTSPOT' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {'search_term': 'cafe'})
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_search_term():
    p = sfp_wificafespots()
    p.setup(None, {'search_term': ''})
    assert p.errorState

def test_setup_invalid_max_results():
    p = sfp_wificafespots()
    p.setup(None, {'search_term': 'cafe', 'max_results': 0})
    assert p.errorState
    p = sfp_wificafespots()
    p.setup(None, {'search_term': 'cafe', 'max_results': -1})
    assert p.errorState
    p = sfp_wificafespots()
    p.setup(None, {'search_term': 'cafe', 'max_results': 'foo'})
    assert p.errorState

def test_setup_invalid_output_format():
    p = sfp_wificafespots()
    p.setup(None, {'search_term': 'cafe', 'output_format': 'invalid'})
    assert p.errorState
