# filepath: spiderfoot/test/unit/modules/test_sfp_tool_gobuster.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_tool_gobuster import sfp_tool_gobuster
import unittest
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleToolGobuster(SpiderFootTestBase):
    """Test Tool Gobuster module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()

        # Create module wrapper class dynamically
        module_attributes = {
            'descr': "Description for sfp_tool_gobuster",
            # Add module-specific options

        }

        self.module_class = self.create_module_wrapper(
            sfp_tool_gobuster,
            module_attributes=module_attributes
        )
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)
        # Register mocks for cleanup during tearDown
        self.register_mock(self.mock_logger)
        # Register patchers for cleanup during tearDown
        if 'patcher1' in locals():
            self.register_patcher(patcher1)

    def test_opts(self):
        """Test the module options."""
        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_gobuster()
        module.setup(sf, dict())
        self.assertIsNotNone(module.opts)
        self.assertTrue(hasattr(module, 'opts'))
        self.assertIsInstance(module.opts, dict)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

    @patch('modules.sfp_tool_gobuster.os.path.isfile', return_value=True)
    @patch('modules.sfp_tool_gobuster.open', create=True)
    @patch('modules.sfp_tool_gobuster.tempfile.NamedTemporaryFile')
    def test_handleEvent_local_success(self, mock_tempfile, mock_open, mock_isfile):
        """Test handleEvent with successful local execution and event emission."""
        module = self.module_class()
        module.sf = MagicMock()
        module.sf.execute.return_value = 0
        module.sf.outputProgress.return_value = True
        module.opts["gobuster_path"] = "/usr/bin/gobuster"  # Use full path to skip 'which' logic
        module.opts["wordlist"] = "/tmp/wordlist.txt"
        module.opts["remote_enabled"] = False
        module.results = {}  # Ensure results is initialized
        # Simulate gobuster output file
        mock_file = MagicMock()
        mock_file.read.return_value = '{"results": [{"path": "/admin/", "status": 200}, {"path": "/index.html", "status": 200}]}'
        mock_open.return_value.__enter__.return_value = mock_file
        mock_tempfile.return_value.name = "/tmp/gobuster_out.json"
        event = SpiderFootEvent("URL", "http://target", "root", None)
        module.notifyListeners = MagicMock()
        module.__name__ = "sfp_tool_gobuster"
        # Patch os.unlink to avoid file deletion errors
        with patch('modules.sfp_tool_gobuster.os.unlink'):
            module.handleEvent(event)
        # Should emit two events: one directory, one file
        self.assertTrue(module.notifyListeners.called)
        self.assertEqual(module.notifyListeners.call_count, 2)

    @patch('modules.sfp_tool_gobuster.paramiko.SSHClient')
    @patch('modules.sfp_tool_gobuster.io.StringIO')
    @patch('modules.sfp_tool_gobuster.paramiko.RSAKey.from_private_key', return_value='pkey')
    def test_run_remote_tool_with_pasted_key(self, mock_rsa, mock_stringio, mock_sshclient):
        """Test remote execution with pasted SSH key data."""
        module = self.module_class()
        module.opts.update({
            "remote_enabled": True,
            "remote_host": "1.2.3.4",
            "remote_user": "user",
            "remote_ssh_key_data": "FAKEKEYDATA",
            "remote_tool_path": "/usr/bin/gobuster",
            "wordlist": "/tmp/wordlist.txt",
            "remote_password": ""
        })
        module.opts["remote_ssh_key"] = ""  # Clear keyfile
        mock_ssh = MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b'{"results": [{"path": "/admin/", "status": 200}]}'
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        result = module.run_remote_tool("http://target")
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        mock_ssh.connect.assert_called_with('1.2.3.4', username='user', pkey='pkey', password="" or None, timeout=10)
        mock_rsa.assert_called()

    @patch('modules.sfp_tool_gobuster.paramiko.SSHClient')
    def test_run_remote_tool_with_keyfile(self, mock_sshclient):
        """Test remote execution with SSH key file path."""
        module = self.module_class()
        module.opts.update({
            "remote_enabled": True,
            "remote_host": "1.2.3.4",
            "remote_user": "user",
            "remote_ssh_key": "/tmp/keyfile",
            "remote_tool_path": "/usr/bin/gobuster",
            "wordlist": "/tmp/wordlist.txt",
            "remote_password": ""
        })
        module.opts["remote_ssh_key_data"] = ""  # Clear pasted key
        mock_ssh = MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b'{"results": [{"path": "/admin/", "status": 200}]}'
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        result = module.run_remote_tool("http://target")
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        mock_ssh.connect.assert_called_with('1.2.3.4', username='user', key_filename='/tmp/keyfile', password="" or None, timeout=10)

    @patch('modules.sfp_tool_gobuster.paramiko.SSHClient')
    def test_run_remote_tool_with_password(self, mock_sshclient):
        """Test remote execution with password only."""
        module = self.module_class()
        module.opts.update({
            "remote_enabled": True,
            "remote_host": "1.2.3.4",
            "remote_user": "user",
            "remote_password": "pw",
            "remote_tool_path": "/usr/bin/gobuster",
            "wordlist": "/tmp/wordlist.txt",
            "remote_ssh_key": "",
            "remote_ssh_key_data": ""
        })
        mock_ssh = MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b'{"results": [{"path": "/admin/", "status": 200}]}'
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b''
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        result = module.run_remote_tool("http://target")
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        mock_ssh.connect.assert_called_with('1.2.3.4', username='user', password='pw', timeout=10)

    @patch('modules.sfp_tool_gobuster.paramiko.SSHClient')
    def test_run_remote_tool_error(self, mock_sshclient):
        """Test remote execution error handling."""
        module = self.module_class()
        module.opts.update({
            "remote_enabled": True,
            "remote_host": "1.2.3.4",
            "remote_user": "user",
            "remote_tool_path": "/usr/bin/gobuster",
            "wordlist": "/tmp/wordlist.txt"
        })
        mock_ssh = MagicMock()
        mock_sshclient.return_value = mock_ssh
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b''
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b'error!'
        mock_ssh.exec_command.return_value = (None, mock_stdout, mock_stderr)
        module.error = MagicMock()
        result = module.run_remote_tool("http://target")
        self.assertIsNone(result)
        module.error.assert_called()

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
