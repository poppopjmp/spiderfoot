import pytest
from modules.sfp_arbitrum import sfp_arbitrum
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_arbitrum()

def test_produced_event_type(plugin):
    plugin.setup(None, {"api_key": "key", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"})
    assert 'ARBITRUM_ADDRESS' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {"api_key": "key", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"})
    event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_api_key(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"api_key": "", "addresses": "0x123", "max_transactions": 10, "output_format": "summary"})

def test_setup_requires_addresses(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"api_key": "key", "addresses": "", "max_transactions": 10, "output_format": "summary"})
