import pytest
from modules.sfp_wifimapio import sfp_wifimapio
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_wifimapio()

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
    assert 'WIFIMAPIO_HOTSPOT' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {'search_term': 'cafe'})
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_search_term(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'search_term': ''})

def test_setup_invalid_max_results(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'search_term': 'cafe', 'max_results': 0})
    with pytest.raises(ValueError):
        plugin.setup(None, {'search_term': 'cafe', 'max_results': -1})
    with pytest.raises(ValueError):
        plugin.setup(None, {'search_term': 'cafe', 'max_results': 'foo'})

def test_setup_invalid_output_format(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'search_term': 'cafe', 'output_format': 'invalid'})
