import pytest
from unittest.mock import patch, MagicMock
from modules.sfp_bluesky import sfp_bluesky
from spiderfoot import SpiderFootEvent

@pytest.fixture
def plugin():
    opts = {"access_token": "token", "username": "user", "max_posts": 2, "output_format": "summary"}
    p = sfp_bluesky()
    p.setup(None, opts)
    p.notifyListeners = MagicMock()
    return p

def test_meta(plugin):
    assert 'name' in plugin.meta
    assert isinstance(plugin.meta['categories'], list)

def test_opts(plugin):
    for opt in [
        'access_token', 'username', 'event_types', 'since', 'max_posts', 'output_format']:
        assert opt in plugin.opts

def test_opts_defaults():
    opts = {"access_token": "token", "username": "user", "max_posts": 10, "output_format": "summary"}
    p = sfp_bluesky()
    p.setup(None, opts)
    assert p.opts['event_types'] == 'post,reply,like'
    assert p.opts['output_format'] == 'summary'

def test_produced_events(plugin):
    assert 'BLUESKY_POST' in plugin.producedEvents()

def test_option_validation():
    p = sfp_bluesky()
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "", "username": "user", "max_posts": 10, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "username": "", "max_posts": 10, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "username": "user", "max_posts": 0, "output_format": "summary"})
    with pytest.raises(ValueError):
        p.setup(None, {"access_token": "token", "username": "user", "max_posts": 10, "output_format": "invalid"})

@patch('modules.sfp_bluesky.requests.get')
def test_handle_event_emits_events(mock_get, plugin):
    # Mock Bluesky API response with 2 posts
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "feed": [
            {"post": {"uri": "uri1", "text": "text1", "createdAt": "2024-01-01", "author": {"handle": "user"}}},
            {"post": {"uri": "uri2", "text": "text2", "createdAt": "2024-01-02", "author": {"handle": "user"}}}
        ]
    }
    event = SpiderFootEvent('post', 'test', 'test', None)  # Use 'post' to match allowed_types
    plugin.handleEvent(event)
    assert plugin.notifyListeners.call_count == 2
    args, _ = plugin.notifyListeners.call_args
    evt = args[0]
    assert evt.eventType == 'BLUESKY_POST'
    assert 'uri' in evt.data
    assert 'text' in evt.data

@patch('modules.sfp_bluesky.requests.get')
def test_handle_event_no_posts(mock_get, plugin):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"feed": []}
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    plugin.handleEvent(event)
    plugin.notifyListeners.assert_not_called()

@patch('modules.sfp_bluesky.requests.get')
def test_handle_event_api_error(mock_get, plugin):
    mock_get.return_value.status_code = 500
    mock_get.return_value.text = 'Internal Server Error'
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    plugin.handleEvent(event)
    plugin.notifyListeners.assert_not_called()

@patch('modules.sfp_bluesky.requests.get')
def test_handle_event_invalid_token(mock_get, plugin):
    mock_get.return_value.status_code = 401
    mock_get.return_value.text = 'Unauthorized'
    event = SpiderFootEvent('ROOT', 'test', 'test', None)
    plugin.handleEvent(event)
    plugin.notifyListeners.assert_not_called()
