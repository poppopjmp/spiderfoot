# filepath: spiderfoot/test/integration/modules/test_sfptool_gobuster.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile

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
        # Use a platform-independent temp file path
        temp_output = tempfile.NamedTemporaryFile(delete=False)
        temp_output.close()
        mock_execute_command.return_value = temp_output.name
        # Use a valid target type for SpiderFootTarget
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('URL', 'http://example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        if 'URL_DIRECTORY' not in event_types:
            print('DEBUG: Events collected:', self.events)
            print('DEBUG: Event types:', event_types)
        assert 'URL_DIRECTORY' in event_types, 'URL_DIRECTORY event not emitted.'
        assert 'URL_FILE' in event_types, 'URL_FILE event not emitted.'

    @patch('os.path.isfile', return_value=True)
    @patch('modules.sfp_tool_gobuster.paramiko.SSHClient')
    @patch('modules.sfp_tool_gobuster.io.StringIO')
    @patch('modules.sfp_tool_gobuster.paramiko.RSAKey.from_private_key', return_value='pkey')
    def test_handleEvent_remote(self, mock_rsa, mock_stringio, mock_sshclient, mock_isfile):
        # Set remote options
        self.module.opts.update({
            'remote_enabled': True,
            'remote_host': '1.2.3.4',
            'remote_user': 'user',
            'remote_ssh_key_data': 'FAKEKEYDATA',
            'remote_tool_path': '/usr/bin/gobuster',
            'wordlist': '/tmp/wordlist.txt',
            'remote_password': '',
            'remote_ssh_key': ''
        })
        # Mock SSH client and output
        mock_ssh = MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b'{"results": [{"path": "/admin/", "status": 200}, {"path": "/index.html", "status": 200}]}'
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('URL', 'http://example.com', 'test', parent_evt)
        self.events.clear()
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'URL_DIRECTORY' in event_types, 'URL_DIRECTORY event not emitted (remote).'
        assert 'URL_FILE' in event_types, 'URL_FILE event not emitted (remote).'
