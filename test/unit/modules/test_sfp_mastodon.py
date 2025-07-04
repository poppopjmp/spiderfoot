import pytest
from modules.sfp_mastodon import sfp_mastodon
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    opts = {"access_token": "token", "username": "user", "instance_url": "https://mastodon.social", "max_posts": 10, "output_format": "summary"}
    p = sfp_mastodon()
    p.setup(None, opts)
    return p

def test_meta(plugin):
    assert 'name' in plugin.meta
    assert isinstance(plugin.meta['categories'], list)

def test_opts(plugin):
    for opt in [
        'access_token', 'instance_url', 'username', 'event_types', 'since', 'max_posts', 'output_format']:
        assert opt in plugin.opts

def test_opts_defaults():
    opts = {"access_token": "token", "username": "user", "instance_url": "https://mastodon.social", "max_posts": 10, "output_format": "summary"}
    p = sfp_mastodon()
    p.setup(None, opts)
    assert p.opts['event_types'] == 'post,reply,boost'
    assert p.opts['output_format'] == 'summary'

def test_produced_events(plugin):
    assert 'MASTODON_POST' in plugin.producedEvents()

def test_option_validation():
    p = sfp_mastodon()
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "", "username": "user", "instance_url": "https://mastodon.social", "max_posts": 10, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "username": "", "instance_url": "https://mastodon.social", "max_posts": 10, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "username": "user", "instance_url": "https://mastodon.social", "max_posts": 0, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "username": "user", "instance_url": "https://mastodon.social", "max_posts": 10, "output_format": "invalid"})

def test_handle_event_stub(plugin):
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    assert plugin.handleEvent(event) is None
