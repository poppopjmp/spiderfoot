import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

from modules.sfp_tool_nmap import sfp_tool_nmap
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget

class TestModuleIntegrationToolNmap(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
        })
        self.sf.validIP = lambda x: True
        self.sf.validIpNetwork = lambda x: False
        self.module = sfp_tool_nmap()
        self.module.__name__ = 'sfp_tool_nmap'
        self.module.debug = print  # Patch debug to print for test output
        # Cross-platform nmap path
        if sys.platform.startswith('win'):
            nmap_path = r'C:\Program Files (x86)\Nmap\nmap.exe'
        else:
            nmap_path = '/usr/bin/nmap'
        self.options = {
            'nmappath': nmap_path,
            'remote_tool_path': nmap_path,
            'netblockscan': True,
            'netblockscanmax': 24,
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch('os.path.isfile', return_value=True)
    @patch('modules.sfp_tool_nmap.Popen')
    def test_handleEvent_local(self, mock_popen, mock_isfile):
        process_mock = MagicMock()
        # Cross-platform mock output
        if sys.platform.startswith('win'):
            os_details = 'OS details: Microsoft Windows 10 Pro 1909'
        else:
            os_details = 'OS details: Linux 3.2 - 4.9'
        attrs = {'communicate.return_value': (os_details.encode(), b''), 'returncode': 0}
        process_mock.configure_mock(**attrs)
        mock_popen.return_value = process_mock
        target = SpiderFootTarget('1.2.3.4', 'IP_ADDRESS')
        self.module.setTarget(target)
        evt = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test', None)
        self.events.clear()
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        if 'OPERATING_SYSTEM' not in event_types:
            print('DEBUG: Events collected:', self.events)
            print('DEBUG: Event types:', event_types)
            print('DEBUG: errorState:', self.module.errorState)
            print('DEBUG: results:', self.module.results)
        assert 'OPERATING_SYSTEM' in event_types, 'OPERATING_SYSTEM event not emitted (local).'

    @patch('os.path.isfile', return_value=True)
    @patch('modules.sfp_tool_nmap.paramiko.SSHClient')
    @patch('modules.sfp_tool_nmap.io.StringIO')
    @patch('modules.sfp_tool_nmap.paramiko.RSAKey.from_private_key', return_value='pkey')
    def test_handleEvent_remote(self, mock_rsa, mock_stringio, mock_sshclient, mock_isfile):
        self.module.opts.update({
            'remote_enabled': True,
            'remote_host': '1.2.3.4',
            'remote_user': 'user',
            'remote_ssh_key_data': 'FAKEKEYDATA',
            'remote_tool_path': self.options['remote_tool_path'],
            'remote_password': '',
            'remote_ssh_key': ''
        })
        mock_ssh = MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = MagicMock()
        # Cross-platform mock output
        if sys.platform.startswith('win'):
            os_details = 'OS details: Microsoft Windows 10 Pro 1909'
        else:
            os_details = 'OS details: Linux 3.2 - 4.9'
        mock_stdout.read.return_value = os_details.encode()
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        target = SpiderFootTarget('1.2.3.4', 'IP_ADDRESS')
        self.module.setTarget(target)
        evt = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test', None)
        self.events.clear()
        self.module.results.clear()
        self.module.errorState = False
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        if 'OPERATING_SYSTEM' not in event_types:
            print('DEBUG: Events collected:', self.events)
            print('DEBUG: Event types:', event_types)
            print('DEBUG: errorState:', self.module.errorState)
            print('DEBUG: results:', self.module.results)
        assert 'OPERATING_SYSTEM' in event_types, 'OPERATING_SYSTEM event not emitted (remote).'
