import pytest
from unittest.mock import patch, MagicMock
from modules.sfp_tool_wappalyzer import sfp_tool_wappalyzer
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget

@pytest.mark.integration
def test_integration_wappalyzer_api_success():
    sf = SpiderFoot({})
    module = sfp_tool_wappalyzer()
    opts = {
        'wappalyzer_api_key': 'FAKEKEY',
        'wappalyzer_api_url': 'https://api.wappalyzer.com/v2/lookup/'
    }
    module.setup(sf, opts)
    target_value = 'example.com'
    target = SpiderFootTarget(target_value, 'INTERNET_NAME')
    module.setTarget(target)
    event = SpiderFootEvent('INTERNET_NAME', target_value, 'sfp_tool_wappalyzer', None)
    with patch('modules.sfp_tool_wappalyzer.requests.get') as mock_get, \
         patch('modules.sfp_tool_wappalyzer.sfp_tool_wappalyzer.notifyListeners') as mock_notify:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            'technologies': [
                {'name': 'Apache', 'categories': [{'name': 'Web servers'}]},
                {'name': 'Linux', 'categories': [{'name': 'Operating systems'}]},
                {'name': 'jQuery', 'categories': [{'name': 'JavaScript frameworks'}]}
            ]
        }]
        mock_get.return_value = mock_resp
        module.handleEvent(event)
        calls = [call[0][0].eventType for call in mock_notify.call_args_list]
        assert 'WEBSERVER_TECHNOLOGY' in calls
        assert 'OPERATING_SYSTEM' in calls
        assert 'SOFTWARE_USED' in calls

@pytest.mark.integration
def test_integration_wappalyzer_api_error():
    sf = SpiderFoot({})
    module = sfp_tool_wappalyzer()
    opts = {
        'wappalyzer_api_key': 'FAKEKEY',
        'wappalyzer_api_url': 'https://api.wappalyzer.com/v2/lookup/'
    }
    module.setup(sf, opts)
    target_value = 'example.com'
    target = SpiderFootTarget(target_value, 'INTERNET_NAME')
    module.setTarget(target)
    event = SpiderFootEvent('INTERNET_NAME', target_value, 'sfp_tool_wappalyzer', None)
    with patch('modules.sfp_tool_wappalyzer.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = 'Forbidden'
        mock_get.return_value = mock_resp
        module.handleEvent(event)
        assert module.errorState or not module.results[target_value]

@pytest.mark.integration
def test_integration_wappalyzer_api_no_technologies():
    sf = SpiderFoot({})
    module = sfp_tool_wappalyzer()
    opts = {
        'wappalyzer_api_key': 'FAKEKEY',
        'wappalyzer_api_url': 'https://api.wappalyzer.com/v2/lookup/'
    }
    module.setup(sf, opts)
    target_value = 'example.com'
    target = SpiderFootTarget(target_value, 'INTERNET_NAME')
    module.setTarget(target)
    event = SpiderFootEvent('INTERNET_NAME', target_value, 'sfp_tool_wappalyzer', None)
    with patch('modules.sfp_tool_wappalyzer.requests.get') as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{}]
        mock_get.return_value = mock_resp
        module.handleEvent(event)
        assert not module.errorState

# End of integration tests
