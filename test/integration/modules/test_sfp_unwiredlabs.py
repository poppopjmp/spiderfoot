import pytest
from modules.sfp_unwiredlabs import sfp_unwiredlabs
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_unwiredlabs()

def test_produced_event_type(plugin):
    plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': '1.2.3.4', 'max_results': 10, 'output_format': 'summary'})
    assert 'UNWIREDLABS_GEOINFO' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': '1.2.3.4', 'max_results': 10, 'output_format': 'summary'})
    event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_api_key(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': '', 'search_type': 'ip', 'search_value': '1.2.3.4'})

def test_setup_requires_search_value(plugin):
    with pytest.raises(ValueError):
        plugin.setup(None, {'api_key': 'key', 'search_type': 'ip', 'search_value': ''})
