import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_tool_nuclei import sfp_tool_nuclei
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

NUCLEI_JSON = b'{"matched-at": "1.2.3.4:80", "info": {"name": "test", "severity": "high"}, "template-id": "TID", "matcher-name": "default"}\n'

class TestModuleToolNucleiRemote(SpiderFootTestBase):
    def setUp(self):
        super().setUp()
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_tool_nuclei()
        self.target_value = '1.2.3.4'
        self.target_type = 'IP_ADDRESS'
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        self.event = SpiderFootEvent('ROOT', self.target_value, '', '')
        self.module.setTarget(self.target)

    @patch('modules.sfp_tool_nuclei.sfp_tool_nuclei.notifyListeners')
    @patch('paramiko.SSHClient')
    def test_handleEvent_remote_execution_with_ssh_key_file(self, mock_ssh, mock_notify):
        opts = {
            'remote_enabled': True,
            'remote_host': 'remotehost',
            'remote_user': 'user',
            'remote_ssh_key': '/path/to/key',
            'remote_tool_path': '/usr/bin/nuclei',
            'remote_tool_args': '-u example.com',
            'template_path': '/path/to/templates',
        }
        self.module.setup(self.sf, opts)
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = NUCLEI_JSON
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_stdin = MagicMock()
        mock_stdin.channel.shutdown_write = MagicMock()
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        # Patch paramiko.RSAKey.from_private_key to raise, so code falls through to key_filename logic
        with patch('paramiko.RSAKey.from_private_key', side_effect=Exception('not a valid RSA private key file')):
            self.module.handleEvent(self.event)
        mock_ssh.assert_called_once()
        mock_client.connect.assert_called_with('remotehost', username='user', key_filename='/path/to/key', password=None, timeout=10)
        mock_client.exec_command.assert_called()
        mock_notify.assert_called()

    @patch('modules.sfp_tool_nuclei.sfp_tool_nuclei.notifyListeners')
    @patch('paramiko.SSHClient')
    def test_handleEvent_remote_execution_with_ssh_key_data(self, mock_ssh, mock_notify):
        opts = {
            'remote_enabled': True,
            'remote_host': 'remotehost',
            'remote_user': 'user',
            'remote_ssh_key_data': 'FAKEKEYDATA',
            'remote_tool_path': '/usr/bin/nuclei',
            'remote_tool_args': '-u example.com',
            'template_path': '/path/to/templates',
            'remote_password': '',  # Ensure password is empty so password=None
        }
        self.module.setup(self.sf, opts)
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = NUCLEI_JSON
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_stdin = MagicMock()
        mock_stdin.channel.shutdown_write = MagicMock()
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        with patch('paramiko.RSAKey.from_private_key') as mock_key:
            mock_key.return_value = MagicMock()
            self.module.handleEvent(self.event)
        mock_ssh.assert_called_once()
        mock_client.connect.assert_called_with('remotehost', username='user', pkey=mock_key.return_value, password=None, timeout=10)
        mock_client.exec_command.assert_called()
        mock_notify.assert_called()

    @patch('modules.sfp_tool_nuclei.sfp_tool_nuclei.notifyListeners')
    @patch('paramiko.SSHClient')
    def test_handleEvent_remote_execution_with_password(self, mock_ssh, mock_notify):
        opts = {
            'remote_enabled': True,
            'remote_host': 'remotehost',
            'remote_user': 'user',
            'remote_password': 'pass',
            'remote_tool_path': '/usr/bin/nuclei',
            'remote_tool_args': '-u example.com',
            'template_path': '/path/to/templates',
        }
        self.module.setup(self.sf, opts)
        mock_client = MagicMock()
        mock_ssh.return_value = mock_client
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = NUCLEI_JSON
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_stdin = MagicMock()
        mock_stdin.channel.shutdown_write = MagicMock()
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        self.module.handleEvent(self.event)
        mock_ssh.assert_called_once()
        mock_client.connect.assert_called_with('remotehost', username='user', password='pass', timeout=10)
        mock_client.exec_command.assert_called()
        mock_notify.assert_called()

    @patch('modules.sfp_tool_nuclei.sfp_tool_nuclei.notifyListeners')
    @patch('modules.sfp_tool_nuclei.Popen')
    def test_handleEvent_local_execution(self, mock_popen, mock_notify):
        opts = {
            'remote_enabled': False,
            'nuclei_path': '/usr/bin/nuclei',
            'template_path': '/path/to/templates',
        }
        self.module.setup(self.sf, opts)
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (NUCLEI_JSON, b'')
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc
        self.module.emit = MagicMock()
        with patch('os.path.isfile', return_value=True):
            with patch('spiderfoot.SpiderFootHelpers.sanitiseInput', return_value=True):
                self.module.handleEvent(self.event)
        mock_popen.assert_called()
        mock_notify.assert_called()
