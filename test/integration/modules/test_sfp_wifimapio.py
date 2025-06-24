import pytest
from modules.sfp_wifimapio import sfp_wifimapio
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_wifimapio()

def test_produced_event_type(plugin):
    plugin.setup(None, {'search_term': 'cafe', 'max_results': 10, 'output_format': 'summary'})
    assert 'WIFIMAPIO_HOTSPOT' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {'search_term': 'cafe', 'max_results': 10, 'output_format': 'summary'})
    event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_search_term(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'search_term': '', 'max_results': 10})
