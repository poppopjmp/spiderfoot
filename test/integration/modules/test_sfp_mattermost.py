import pytest
from modules.sfp_mattermost import sfp_mattermost
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_mattermost()

def test_produced_event_type(plugin):
    plugin.setup(None, {"access_token": "token", "channel_id": "chan", "max_messages": 10, "output_format": "summary"})
    assert 'MATTERMOST_MESSAGE' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {"access_token": "token", "channel_id": "chan", "max_messages": 10, "output_format": "summary"})
    event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_access_token(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"access_token": "", "channel_id": "chan", "max_messages": 10, "output_format": "summary"})

def test_setup_requires_channel_id(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"access_token": "token", "channel_id": "", "max_messages": 10, "output_format": "summary"})
