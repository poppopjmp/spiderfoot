import pytest
from modules.sfp_openwifimap import sfp_openwifimap
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    opts = {"search_term": "wifi", "max_results": 10, "output_format": "summary"}
    p = sfp_openwifimap()
    p.setup(None, opts)
    return p

def test_meta(plugin):
    assert 'name' in plugin.meta
    assert isinstance(plugin.meta['categories'], list)

def test_opts(plugin):
    for opt in [
        'search_term', 'country', 'city', 'max_results', 'output_format']:
        assert opt in plugin.opts

def test_opts_defaults():
    opts = {"search_term": "wifi", "max_results": 10, "output_format": "summary"}
    p = sfp_openwifimap()
    p.setup(None, opts)
    assert p.opts['country'] == ''
    assert p.opts['city'] == ''
    assert p.opts['output_format'] == 'summary'

def test_produced_events(plugin):
    assert 'OPENWIFIMAP_HOTSPOT' in plugin.producedEvents()

def test_option_validation():
    p = sfp_openwifimap()
    with pytest.raises(ValueError):
        p.setup(None, {"search_term": "", "max_results": 10, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"search_term": "wifi", "max_results": 0, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"search_term": "wifi", "max_results": 10, "output_format": "invalid"})

def test_handle_event_stub(plugin):
    event = SpiderFootEvent('INTERNET_NAME', 'test', 'test', None)
    assert plugin.handleEvent(event) is None
