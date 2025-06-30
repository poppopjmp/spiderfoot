import pytest
import os
from unittest.mock import patch, MagicMock
from modules.sfp_tool_nuclei import sfp_tool_nuclei
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget

NUCLEI_JSON = b'{"matched-at": "1.2.3.4:80", "info": {"name": "test", "severity": "high"}, "template-id": "TID", "matcher-name": "default"}\n'

def make_event(target_value='1.2.3.4'):
    return SpiderFootEvent('ROOT', target_value, '', '')

def make_target(target_value='1.2.3.4'):
    return SpiderFootTarget(target_value, 'IP_ADDRESS')

@pytest.mark.integration
@patch('modules.sfp_tool_nuclei.sfp_tool_nuclei.notifyListeners')
@patch('paramiko.SSHClient')
def test_integration_remote_execution_with_ssh_key_file(mock_ssh, mock_notify):
    sf = SpiderFoot({})
    module = sfp_tool_nuclei()
    opts = {
        'remote_enabled': True,
        'remote_host': 'remotehost',
        'remote_user': 'user',
        'remote_ssh_key': '/path/to/key',
        'remote_tool_path': '/usr/bin/nuclei',
        'remote_tool_args': '-u example.com',
        'template_path': '/path/to/templates',
    }
    module.setup(sf, opts)
    module.setTarget(make_target())
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
        module.handleEvent(make_event())
    mock_ssh.assert_called_once()
    mock_client.connect.assert_called_with('remotehost', username='user', key_filename='/path/to/key', password=None, timeout=10)
    mock_client.exec_command.assert_called()
    mock_notify.assert_called()

@pytest.mark.integration
@patch('modules.sfp_tool_nuclei.sfp_tool_nuclei.notifyListeners')
@patch('paramiko.SSHClient')
def test_integration_remote_execution_with_password(mock_ssh, mock_notify):
    sf = SpiderFoot({})
    module = sfp_tool_nuclei()
    opts = {
        'remote_enabled': True,
        'remote_host': 'remotehost',
        'remote_user': 'user',
        'remote_password': 'pass',
        'remote_tool_path': '/usr/bin/nuclei',
        'remote_tool_args': '-u example.com',
        'template_path': '/path/to/templates',
    }
    module.setup(sf, opts)
    module.setTarget(make_target())
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = NUCLEI_JSON
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b''
    mock_stdin = MagicMock()
    mock_stdin.channel.shutdown_write = MagicMock()
    mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
    module.handleEvent(make_event())
    mock_ssh.assert_called_once()
    mock_client.connect.assert_called_with('remotehost', username='user', password='pass', timeout=10)
    mock_client.exec_command.assert_called()
    mock_notify.assert_called()

@pytest.mark.integration
@patch('modules.sfp_tool_nuclei.sfp_tool_nuclei.notifyListeners')
@patch('modules.sfp_tool_nuclei.Popen')
def test_integration_local_execution(mock_popen, mock_notify):
    sf = SpiderFoot({})
    module = sfp_tool_nuclei()
    opts = {
        'remote_enabled': False,
        'nuclei_path': '/usr/bin/nuclei',
        'template_path': '/path/to/templates',
    }
    module.setup(sf, opts)
    module.setTarget(make_target())
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (NUCLEI_JSON, b'')
    mock_proc.returncode = 0
    mock_popen.return_value = mock_proc
    module.emit = MagicMock()
    with patch('os.path.isfile', return_value=True):
        with patch('spiderfoot.SpiderFootHelpers.sanitiseInput', return_value=True):
            module.handleEvent(make_event())
    mock_popen.assert_called()
    mock_notify.assert_called()
