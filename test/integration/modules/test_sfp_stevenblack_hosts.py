import pytest
from modules.sfp_stevenblack_hosts import sfp_stevenblack_hosts
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
    m = sfp_stevenblack_hosts()
    m.setup(sf, dict(default_options))
    m.__name__ = "sfp_stevenblack_hosts"
    return m


@pytest.fixture
def target():
    return SpiderFootTarget('van1shland.io', 'INTERNET_NAME')


@pytest.fixture
def root_event():
    return SpiderFootEvent('ROOT', 'example data', '', '')


def test_handleEvent_event_data_affiliate_internet_name_matching_ad_server_should_return_event(module, sf, target, root_event):
    module.setTarget(target)
    evt = SpiderFootEvent('AFFILIATE_INTERNET_NAME', 'ads.google.com', 'example module', root_event)
    events = []
    hosts_content = '0.0.0.0 ads.google.com\n127.0.0.1 localhost\n'
    with patch.object(sf, 'fetchUrl', return_value={'content': hosts_content, 'code': '200'}):
        with patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
    assert any(e.eventType == 'MALICIOUS_AFFILIATE_INTERNET_NAME' for e in events)
    blocked_event = next((e for e in events if e.eventType == 'MALICIOUS_AFFILIATE_INTERNET_NAME'), None)
    assert blocked_event is not None
    assert 'Steven Black Hosts Blocklist' in blocked_event.data


def test_handleEvent_event_data_affiliate_internet_name_not_matching_ad_server_should_not_return_event(module, sf, target, root_event):
    module.setTarget(target)
    evt = SpiderFootEvent('AFFILIATE_INTERNET_NAME', 'notanadserver.com', 'example module', root_event)
    events = []
    hosts_content = '0.0.0.0 ads.google.com\n127.0.0.1 localhost\n'
    with patch.object(sf, 'fetchUrl', return_value={'content': hosts_content, 'code': '200'}):
        with patch.object(module, 'notifyListeners', side_effect=events.append):
            module.handleEvent(evt)
    assert not any(e.eventType == 'MALICIOUS_AFFILIATE_INTERNET_NAME' for e in events)
