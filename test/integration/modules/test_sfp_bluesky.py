import pytest
from modules.sfp_bluesky import sfp_bluesky
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_bluesky()

def test_produced_event_type(plugin):
    plugin.setup(None, {"access_token": "token", "username": "user", "max_posts": 10, "output_format": "summary"})
    assert 'BLUESKY_POST' in plugin.producedEvents()

def test_handle_event_stub(plugin):
    plugin.setup(None, {"access_token": "token", "username": "user", "max_posts": 10, "output_format": "summary"})
    event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
    assert plugin.handleEvent(event) is None

def test_setup_requires_access_token(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"access_token": "", "username": "user", "max_posts": 10, "output_format": "summary"})

def test_setup_requires_username(plugin):
    with pytest.raises(Exception):
        plugin.setup(None, {"access_token": "token", "username": "", "max_posts": 10, "output_format": "summary"})
