import pytest
from modules.sfp_rocketchat import sfp_rocketchat
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    opts = {"access_token": "token", "room_id": "room", "max_messages": 10, "output_format": "summary"}
    p = sfp_rocketchat()
    p.setup(None, opts)
    return p

def test_meta(plugin):
    assert 'name' in plugin.meta
    assert isinstance(plugin.meta['categories'], list)

def test_opts(plugin):
    for opt in [
        'access_token', 'server_url', 'room_id', 'event_types', 'since', 'max_messages', 'output_format']:
        assert opt in plugin.opts

def test_opts_defaults():
    opts = {"access_token": "token", "room_id": "room", "max_messages": 10, "output_format": "summary"}
    p = sfp_rocketchat()
    p.setup(None, opts)
    assert p.opts['server_url'] == ''
    assert p.opts['event_types'] == 'message,join,leave'
    assert p.opts['output_format'] == 'summary'

def test_produced_events(plugin):
    assert 'ROCKETCHAT_MESSAGE' in plugin.producedEvents()

def test_option_validation():
    p = sfp_rocketchat()
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "", "room_id": "room", "max_messages": 10, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "room_id": "", "max_messages": 10, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "room_id": "room", "max_messages": 0, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "room_id": "room", "max_messages": 10, "output_format": "invalid"})

def test_handle_event_stub(plugin):
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    assert plugin.handleEvent(event) is None
