import pytest
from modules.sfp_rocketchat import sfp_rocketchat
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_rocketchat()

def test_produced_event_type(plugin):
    plugin.setup(None, {"access_token": "token", "room_id": "room", "max_messages": 10, "output_format": "summary"})
    assert 'ROCKETCHAT_MESSAGE' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {"access_token": "token", "room_id": "room", "max_messages": 10, "output_format": "summary"})
    event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_access_token(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"access_token": "", "room_id": "room", "max_messages": 10, "output_format": "summary"})

def test_setup_requires_room_id(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"access_token": "token", "room_id": "", "max_messages": 10, "output_format": "summary"})
