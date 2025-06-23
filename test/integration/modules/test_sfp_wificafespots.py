import pytest
from modules.sfp_wificafespots import sfp_wificafespots
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_wificafespots()

def test_produced_event_type(plugin):
    plugin.setup(None, {'search_term': 'cafe'})
    assert 'WIFICAFESPOTS_HOTSPOT' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {'search_term': 'cafe'})
    event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_search_term(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'search_term': ''})
