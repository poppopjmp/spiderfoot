import pytest
from modules.sfp_opendns import sfp_opendns
from sflib import SpiderFoot
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
    m = sfp_opendns()
    m.setup(sf, dict(default_options))
    m.__name__ = "sfp_opendns"
    return m


@pytest.fixture
def target():
    return SpiderFootTarget('van1shland.io', 'INTERNET_NAME')


@pytest.fixture
def root_event():
    return SpiderFootEvent('ROOT', 'example data', '', '')


def test_handleEvent_event_data_safe_internet_name_not_blocked_should_not_return_event(module, sf, target, root_event):
    module.setTarget(target)
    evt = SpiderFootEvent('INTERNET_NAME', 'opendns.com', 'example module', root_event)
    events = []
    with patch.object(module, 'queryAddr', return_value=['8.8.8.8']):
        with patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
    assert events == []


def test_handleEvent_event_data_adult_internet_name_blocked_should_return_event(module, sf, target, root_event):
    module.setTarget(target)
    evt = SpiderFootEvent('INTERNET_NAME', 'pornhub.com', 'example module', root_event)
    events = []
    # OpenDNS Adult block IP: 146.112.61.106
    with patch.object(module, 'queryAddr', return_value=['146.112.61.106']):
        with patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
    assert any(e.eventType == 'BLACKLISTED_INTERNET_NAME' for e in events)
    blocked_event = next((e for e in events if e.eventType == 'BLACKLISTED_INTERNET_NAME'), None)
    assert blocked_event is not None
    assert blocked_event.data == 'OpenDNS - Adult [pornhub.com]'
