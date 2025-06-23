import pytest
from modules.sfp_unwiredlabs import sfp_unwiredlabs
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_unwiredlabs()

def test_meta(plugin):
    assert 'name' in plugin.meta
    assert 'dataSource' in plugin.meta
    assert isinstance(plugin.meta['categories'], list)
    assert len(plugin.meta['categories']) == 1

def test_opts(plugin):
    for opt in [
        'api_key', 'search_type', 'search_value', 'country', 'city', 'max_results', 'output_format']:
        assert opt in plugin.opts

def test_opts_defaults(plugin):
    assert plugin.opts['country'] == ''
    assert plugin.opts['city'] == ''
    assert plugin.opts['max_results'] == 50
    assert plugin.opts['output_format'] == 'summary'

def test_produced_events(plugin):
    assert 'UNWIREDLABS_GEOINFO' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': '1.2.3.4'})
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_api_key(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': '', 'search_type': 'ip', 'search_value': '1.2.3.4'})

def test_setup_requires_search_value(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': ''})

def test_setup_invalid_search_type(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': 'key', 'search_type': 'invalid', 'search_value': 'foo'})

def test_setup_invalid_max_results(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': 'foo', 'max_results': 0})
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': 'foo', 'max_results': -1})
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': 'foo', 'max_results': 'foo'})

def test_setup_invalid_output_format(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': 'foo', 'output_format': 'invalid'})
