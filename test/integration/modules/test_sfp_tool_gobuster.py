# filepath: spiderfoot/test/integration/modules/test_sfptool_gobuster.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json

from modules.sfp_tool_gobuster import sfp_tool_gobuster
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationToolGobuster(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
        })
        self.sf.execute = MagicMock(return_value=0)
        self.sf.outputProgress = MagicMock(return_value=True)
        self.module = sfp_tool_gobuster()
        self.module.__name__ = 'sfp_tool_gobuster'
        self.options = {
            'gobuster_path': '/usr/bin/gobuster',
            'wordlist': '/tmp/wordlist.txt',
            'threads': 10,
            'timeout': 30,
            'status_codes': '200,204,301,302,307,401,403',
            'follow_redirects': True,
            'extensions': 'php,asp,aspx,jsp,html,htm,js',
            'use_proxy': False,
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch('os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        'results': [
            {'path': '/admin/', 'status': 200},
            {'path': '/index.html', 'status': 200}
        ]
    }))
    @patch.object(sfp_tool_gobuster, 'execute_command')
    def test_handleEvent_gobuster(self, mock_execute_command, mock_open_file, mock_isfile):
        # Simulate execute_command returning a fake file path
        mock_execute_command.return_value = '/tmp/fake_gobuster_output.json'
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('INTERNET_NAME', 'example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'URL_DIRECTORY' in event_types, 'URL_DIRECTORY event not emitted.'
        assert 'URL_FILE' in event_types, 'URL_FILE event not emitted.'
