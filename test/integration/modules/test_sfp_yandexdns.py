import pytest
from modules.sfp_yandexdns import sfp_yandexdns
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from unittest.mock import patch


@pytest.fixture
def default_options():
    return {
        '_fetchtimeout': 15,
        '_useragent': 'SpiderFoot',
        '_internettlds': 'com,net,org,info,biz,us,uk',
        '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        '_socks1type': '',
        '_socks1addr': '',
        '_socks1port': '',
        '_socks1user': '',
        '_socks1pwd': '',
        '__logging': False,
    }


@pytest.fixture
def sf(default_options):
    return SpiderFoot(default_options)


@pytest.fixture
def module(sf, default_options):
    m = sfp_yandexdns()
    m.setup(sf, dict(default_options))
    m.__name__ = "sfp_yandexdns"
    return m


@pytest.fixture
def target():
    return SpiderFootTarget('van1shland.io', 'INTERNET_NAME')


@pytest.fixture
def root_event():
    return SpiderFootEvent('ROOT', 'example data', '', '')


def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(module, sf, target):
    module.setTarget(target)
    with patch.object(module, 'queryAddr', return_value=['8.8.8.8']):
        result = module.handleEvent(SpiderFootEvent('INTERNET_NAME', 'yandex.com', 'example module', None))
        assert result is None


def test_handleEvent_event_data_adult_internet_name_blocked_should_return_event(module, sf, target, root_event):
    module.setTarget(target)
    evt = SpiderFootEvent('INTERNET_NAME', 'pornhub.com', 'example module', root_event)
    events = []
    # Yandex Adult block IP: 93.158.134.250
    with patch.object(module, 'queryAddr', return_value=['93.158.134.250']):
        with patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
    assert any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events)
    blocked_event = next((e for e in events if e.eventType == 'BLACKLISTED_INTERNET_NAME'), None)
    assert blocked_event is not None
    assert blocked_event.data == 'Yandex - Adult [pornhub.com]'
