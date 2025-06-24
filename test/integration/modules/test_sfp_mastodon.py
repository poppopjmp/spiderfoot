import pytest
from modules.sfp_mastodon import sfp_mastodon
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    return sfp_mastodon()

def test_produced_event_type(plugin):
    plugin.setup(None, {"access_token": "token", "username": "user", "max_posts": 10, "output_format": "summary"})
    assert 'MASTODON_POST' in plugin.producedEvents()

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
