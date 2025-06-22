# test_spiderfootcli.py
import io
import pytest
import sys
import unittest

from sfcli import SpiderFootCli
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestSpiderFootCli(SpiderFootTestBase):
    """Test TestSpiderFootCli."""

    def test_default(self):
        """Test default(self, line)"""
        sfcli = SpiderFootCli()
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.default("")
            output = mock_stdout.getvalue()
        self.assertIn("Unknown command", output)

    def test_default_should_ignore_comments(self):
        """Test default(self, line)"""
        sfcli = SpiderFootCli()
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            result = sfcli.default("# test comment")
            output = mock_stdout.getvalue()
        self.assertEqual(None, result)
        self.assertEqual("", output)

    def test_complete_start_should_return_a_list(self):
        """Test complete_start(self, text, line, startidx, endidx)"""
        sfcli = SpiderFootCli()
        start = sfcli.complete_start(None, None, None, None)
        self.assertIsInstance(start, list)
        self.assertEqual([], start)

    def test_complete_find_should_return_a_list(self):
        """Test complete_find(self, text, line, startidx, endidx)"""
        sfcli = SpiderFootCli()
        find = sfcli.complete_find(None, None, None, None)
        self.assertIsInstance(find, list)
        self.assertEqual([], find)

    def test_complete_data_should_return_a_list(self):
        """Test complete_data(self, text, line, startidx, endidx)"""
        sfcli = SpiderFootCli()
        data = sfcli.complete_data(None, None, None, None)
        self.assertIsInstance(data, list)
        self.assertEqual([], data)

    def test_complete_default(self):
        """Test complete_default(self, text, line, startidx, endidx)"""
        sfcli = SpiderFootCli()
        default = sfcli.complete_default("", "-t -m", None, None)
        self.assertIsInstance(default, list)
        self.assertEqual('TBD', 'TBD')

        default = sfcli.complete_default("", "-m -t", None, None)
        self.assertIsInstance(default, list)
        self.assertEqual('TBD', 'TBD')

    def test_complete_default_invalid_text_should_return_a_string(self):
        """Test complete_default(self, text, line, startidx, endidx)"""
        sfcli = SpiderFootCli()
        default = sfcli.complete_default(None, "example line", None, None)
        self.assertIsInstance(default, list)
        self.assertEqual([], default)

    def test_complete_default_invalid_line_should_return_a_string(self):
        """Test complete_default(self, text, line, startidx, endidx)"""
        sfcli = SpiderFootCli()
        default = sfcli.complete_default("example text", None, None, None)
        self.assertIsInstance(default, list)
        self.assertEqual([], default)

    def test_do_debug_should_toggle_debug(self):
        """Test do_debug(self, line)"""
        sfcli = SpiderFootCli(self.cli_default_options)

        sfcli.do_debug(None)
        initial_debug_state = sfcli.ownopts['cli.debug']
        sfcli.do_debug(None)
        new_debug_state = sfcli.ownopts['cli.debug']

        self.assertNotEqual(initial_debug_state, new_debug_state)

    def test_do_spool_should_toggle_spool(self):
        """Test do_spool(self, line)"""
        sfcli = SpiderFootCli()

        # Use cross-platform null device
        import os
        null_device = os.devnull
        sfcli.ownopts['cli.spool_file'] = null_device

        sfcli.do_spool(None)
        initial_spool_state = sfcli.ownopts['cli.spool']
        sfcli.do_spool(None)
        new_spool_state = sfcli.ownopts['cli.spool']

        self.assertNotEqual(initial_spool_state, new_spool_state)

    def test_do_history_should_toggle_history_option(self):
        """Test do_history(self, line)"""
        sfcli = SpiderFootCli(self.cli_default_options)

        sfcli.do_history("0")
        initial_history_state = sfcli.ownopts['cli.history']
        sfcli.do_history("1")
        new_history_state = sfcli.ownopts['cli.history']

        self.assertNotEqual(initial_history_state, new_history_state)

    def test_precmd_should_return_line(self):
        """Test precmd(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.history'] = False
        sfcli.ownopts['cli.spool'] = False

        line = "example line"

        precmd = sfcli.precmd(line)

        self.assertEqual(line, precmd)

    @unittest.skip("todo")
    def test_precmd_should_print_line_to_history_file(self):
        """Test precmd(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.history'] = True
        sfcli.ownopts['cli.spool'] = False

        line = "example line"

        precmd = sfcli.precmd(line)

        self.assertEqual(line, precmd)

        self.assertEqual('TBD', 'TBD')

    @unittest.skip("todo")
    def test_precmd_should_print_line_to_spool_file(self):
        """Test precmd(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.history'] = False
        sfcli.ownopts['cli.spool'] = True
        # Use cross-platform null device
        import os
        null_device = os.devnull
        sfcli.ownopts['cli.spool_file'] = null_device

        line = "example line"

        precmd = sfcli.precmd(line)

        self.assertEqual(line, precmd)

        self.assertEqual('TBD', 'TBD')

    def test_dprint_should_print_if_debug_option_is_set(self):
        """Test dprint(self, msg, err=False, deb=False, plain=False,
        color=None)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.debug'] = True
        sfcli.ownopts['cli.spool'] = False
        sfcli.ownopts['cli.silent'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.dprint("example output")
            output = mock_stdout.getvalue()
        self.assertIn("example output", output)

    def test_dprint_should_not_print_unless_debug_option_is_set(self):
        """Test dprint(self, msg, err=False, deb=False, plain=False,
        color=None)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.debug'] = False
        sfcli.ownopts['cli.spool'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.dprint("example output", deb=True)
            output = mock_stdout.getvalue()
        self.assertEqual("", output)

    def test_ddprint_should_print_if_debug_option_is_set(self):
        """Test ddprint(self, msg)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.debug'] = True
        sfcli.ownopts['cli.spool'] = False
        sfcli.ownopts['cli.silent'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.ddprint("example debug output")
            output = mock_stdout.getvalue()
        self.assertIn("example debug output", output)

    def test_ddprint_should_not_print_unless_debug_option_is_set(self):
        """Test ddprint(self, msg)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.debug'] = False
        sfcli.ownopts['cli.spool'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.ddprint("example debug output")
            output = mock_stdout.getvalue()
        self.assertEqual("", output)

    def test_edprint_should_print_error_regardless_of_debug_option(self):
        """Test edprint(self, msg)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.debug'] = False
        sfcli.ownopts['cli.spool'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.edprint("example debug output")
            output = mock_stdout.getvalue()
        self.assertIn("example debug output", output)

    def test_pretty_should_return_a_string(self):
        """Test pretty(self, data, titlemap=None)"""
        sfcli = SpiderFootCli()

        invalid_types = [None, "", list(), dict()]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                pretty = sfcli.pretty(invalid_type)
                self.assertEqual("", pretty)

    def test_request_invalid_url_should_return_none(self):
        """Test request(self, url, post=None)"""
        sfcli = SpiderFootCli()

        invalid_types = [None, list(), dict()]
        for invalid_type in invalid_types:
            with self.subTest(invalid_type=invalid_type):
                result = sfcli.request(invalid_type)
                self.assertEqual(None, result)

    def test_emptyline_should_return_none(self):
        """Test emptyline(self)"""
        sfcli = SpiderFootCli()
        emptyline = sfcli.emptyline()
        self.assertEqual(None, emptyline)

    def test_completedefault_should_return_empty_list(self):
        """Test completedefault(self, text, line, begidx, endidx)"""
        sfcli = SpiderFootCli()
        completedefault = sfcli.completedefault(None, None, None, None)
        self.assertIsInstance(completedefault, list)
        self.assertEqual([], completedefault)

    def test_myparseline_should_return_a_list_of_two_lists(self):
        """Test myparseline(self, cmdline, replace=True)"""
        sfcli = SpiderFootCli()
        parsed_line = sfcli.myparseline(None)

        self.assertEqual(len(parsed_line), 2)
        self.assertIsInstance(parsed_line, list)
        self.assertIsInstance(parsed_line[0], list)
        self.assertIsInstance(parsed_line[1], list)

        parsed_line = sfcli.myparseline("")

        self.assertEqual(len(parsed_line), 2)
        self.assertIsInstance(parsed_line, list)
        self.assertIsInstance(parsed_line[0], list)
        self.assertIsInstance(parsed_line[1], list)

    def test_send_output(self):
        """Test send_output(self, data, cmd, titles=None, total=True,
        raw=False)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.silent'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.send_output("{}", "", raw=True)
            output = mock_stdout.getvalue()
        self.assertIn("Total records: 0", output)

    def test_do_query(self):
        """Test do_query(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_query(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_ping(self):
        """Test do_ping(self, line)"""
        from unittest.mock import patch
        
        sfcli = SpiderFootCli()
        
        # Mock the request method to avoid actual HTTP requests
        with patch.object(sfcli, 'request') as mock_request:
            # Return different responses for different calls
            # First call: ping response
            # Second call: modules response 
            # Third call: types response
            mock_request.side_effect = [
                '["SUCCESS", "5.1.0"]',
                '[{"name": "test_module", "descr": "Test module"}]',
                '[["test_type", "Test type description"]]'
            ]
            sfcli.do_ping(None)
            
            # Verify that request was called multiple times
            self.assertEqual(mock_request.call_count, 3)
            # Check that ping URL was called first
            first_call_args = mock_request.call_args_list[0][0]
            self.assertIn("/ping", first_call_args[0])

        self.assertEqual('TBD', 'TBD')

    def test_do_modules(self):
        """Test do_modules(self, line, cacheonly=False)"""
        from unittest.mock import patch, MagicMock
        
        sfcli = SpiderFootCli()
        
        # Mock the request method to avoid actual HTTP requests
        with patch.object(sfcli, 'request') as mock_request:
            # Return non-empty JSON array to avoid "pretty" format issue
            mock_request.return_value = '[{"name": "test_module", "descr": "Test module description"}]'
            sfcli.do_modules(None, None)
            
            # Verify that request was called with the expected URL
            mock_request.assert_called_once()
            call_args = mock_request.call_args[0]
            self.assertIn("/modules", call_args[0])

        self.assertEqual('TBD', 'TBD')

    def test_do_types(self):
        """Test do_types(self, line, cacheonly=False)"""
        from unittest.mock import patch
        
        sfcli = SpiderFootCli()
        
        # Mock the request method to avoid actual HTTP requests
        with patch.object(sfcli, 'request') as mock_request:
            # Return non-empty JSON array to avoid "pretty" format issue
            mock_request.return_value = '[["test_type", "Test type description"]]'
            sfcli.do_types(None, None)
            
            # Verify that request was called with the expected URL
            mock_request.assert_called_once()
            call_args = mock_request.call_args[0]
            self.assertIn("/eventtypes", call_args[0])

        self.assertEqual('TBD', 'TBD')

    def test_do_load(self):
        """Test do_load(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_load(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_scaninfo(self):
        """Test do_scaninfo(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_scaninfo(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_scans(self):
        """Test do_scans(self, line)"""
        from unittest.mock import patch
        
        sfcli = SpiderFootCli()
        
        # Mock the request method to avoid actual HTTP requests
        with patch.object(sfcli, 'request') as mock_request:
            # Return non-empty JSON array to avoid "pretty" format issue
            mock_request.return_value = '[{"id": "test_scan", "name": "Test Scan", "status": "FINISHED"}]'
            sfcli.do_scans(None)
            
            # Verify that request was called with the expected URL
            mock_request.assert_called_once()
            call_args = mock_request.call_args[0]
            self.assertIn("/scanlist", call_args[0])

        self.assertEqual('TBD', 'TBD')

    def test_do_data(self):
        """Test do_data(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_data(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_export(self):
        """Test do_export(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_export(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_logs(self):
        """Test do_logs(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_logs(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_start(self):
        """Test do_start(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_start(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_stop(self):
        """Test do_stop(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_stop(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_search(self):
        """Test do_search(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_search(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_find(self):
        """Test do_find(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_find(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_summary(self):
        """Test do_summary(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_summary(None)

        self.assertEqual('TBD', 'TBD')

    def test_do_delete(self):
        """Test do_delete(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.do_delete(None)

        self.assertEqual('TBD', 'TBD')

    def test_print_topic(self):
        """Test print_topics(self, header, cmds, cmdlen, maxcol)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.silent'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.print_topics(None, "help", None, None)
            output = mock_stdout.getvalue()
        self.assertIn("Command", output)
        self.assertIn("Description", output)

    def test_do_set_should_set_option(self):
        """Test do_set(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.test_opt'] = None

        sfcli.do_set('cli.test_opt = "test value"')
        new_test_opt = sfcli.ownopts['cli.test_opt']

        self.assertEqual(new_test_opt, 'test value')

    def test_do_shell(self):
        """Test do_shell(self, line)"""
        sfcli = SpiderFootCli()
        sfcli.ownopts['cli.silent'] = False
        from unittest.mock import patch
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            sfcli.do_shell("")
            output = mock_stdout.getvalue()
        self.assertIn("Running shell command:", output)

    def test_do_clear(self):
        """Test do_clear(self, line)"""
        sfcli = SpiderFootCli()
        from unittest.mock import patch
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            sfcli.do_clear(None)
            output = mock_stderr.getvalue()
        self.assertEqual("\x1b[2J\x1b[H", output)

    def test_do_exit(self):
        """Test do_exit(self, line)"""
        sfcli = SpiderFootCli()
        do_exit = sfcli.do_exit(None)
        self.assertTrue(do_exit)

    def test_do_eof(self):
        """Test do_EOF(self, line)"""
        sfcli = SpiderFootCli()
        do_eof = sfcli.do_EOF(None)
        self.assertTrue(do_eof)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        # Clean up any CLI instances and their resources
        if hasattr(self, 'sfcli'):
            try:
                # Close any open files or connections
                if hasattr(self.sfcli, 'cleanup'):
                    self.sfcli.cleanup()
                self.sfcli = None
            except:
                pass
        super().tearDown()
