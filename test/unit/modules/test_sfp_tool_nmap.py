import pytest
import unittest

from modules.sfp_tool_nmap import sfp_tool_nmap
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleToolNmap(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_tool_nmap()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_nmap()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_nmap()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_nmap()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_tool_nmap()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    @unittest.mock.patch('modules.sfp_tool_nmap.os.path.isfile', return_value=True)
    @unittest.mock.patch('modules.sfp_tool_nmap.Popen')
    def test_handleEvent_local_success(self, mock_popen, mock_isfile):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_nmap()
        module.setup(sf, {'nmappath': '/usr/bin/nmap'})
        module.__name__ = 'sfp_tool_nmap'
        module.sf.validIP = lambda x: True
        module.sf.validIpNetwork = lambda x: False
        # Mock Popen to simulate nmap output
        process_mock = unittest.mock.MagicMock()
        attrs = {'communicate.return_value': (b'OS details: Linux 3.2 - 4.9', b''), 'returncode': 0}
        process_mock.configure_mock(**attrs)
        mock_popen.return_value = process_mock
        module.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test', None)
        module.handleEvent(event)
        self.assertTrue(module.notifyListeners.called)
        self.assertEqual(module.notifyListeners.call_args[0][0].eventType, 'OPERATING_SYSTEM')

    @unittest.mock.patch('modules.sfp_tool_nmap.paramiko.SSHClient')
    @unittest.mock.patch('modules.sfp_tool_nmap.io.StringIO')
    @unittest.mock.patch('modules.sfp_tool_nmap.paramiko.RSAKey.from_private_key', return_value='pkey')
    def test_handleEvent_remote_with_pasted_key(self, mock_rsa, mock_stringio, mock_sshclient):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_nmap()
        module.setup(sf, {
            'remote_enabled': True,
            'remote_host': '1.2.3.4',
            'remote_user': 'user',
            'remote_ssh_key_data': 'FAKEKEYDATA',
            'remote_tool_path': '/usr/bin/nmap',
            'nmappath': '/usr/bin/nmap',
        })
        module.__name__ = 'sfp_tool_nmap'
        module.sf.validIP = lambda x: True
        module.sf.validIpNetwork = lambda x: False
        mock_ssh = unittest.mock.MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = unittest.mock.MagicMock()
        mock_stdout.read.return_value = b'OS details: Linux 3.2 - 4.9'
        mock_stderr = unittest.mock.MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        module.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test', None)
        module.handleEvent(event)
        self.assertTrue(module.notifyListeners.called)
        self.assertEqual(module.notifyListeners.call_args[0][0].eventType, 'OPERATING_SYSTEM')
        mock_ssh.connect.assert_called_with('1.2.3.4', username='user', pkey='pkey', password=None, timeout=10)

    @unittest.mock.patch('modules.sfp_tool_nmap.paramiko.SSHClient')
    def test_handleEvent_remote_with_keyfile(self, mock_sshclient):
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_nmap()
        module.setup(sf, {
            'remote_enabled': True,
            'remote_host': '1.2.3.4',
            'remote_user': 'user',
            'remote_ssh_key': '/tmp/keyfile',
            'remote_tool_path': '/usr/bin/nmap',
            'nmappath': '/usr/bin/nmap',
        })
        module.__name__ = 'sfp_tool_nmap'
        module.sf.validIP = lambda x: True
        module.sf.validIpNetwork = lambda x: False
        mock_ssh = unittest.mock.MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = unittest.mock.MagicMock()
        mock_stdout.read.return_value = b'OS details: Linux 3.2 - 4.9'
        mock_stderr = unittest.mock.MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        module.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test', None)
        module.handleEvent(event)
        self.assertTrue(module.notifyListeners.called)
        self.assertEqual(module.notifyListeners.call_args[0][0].eventType, 'OPERATING_SYSTEM')
        mock_ssh.connect.assert_called_with('1.2.3.4', username='user', key_filename='/tmp/keyfile', password=None, timeout=10)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
