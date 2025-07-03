import unittest
from spiderfoot.sfcli import SpiderFootCli
import io
import sys

class TestSpiderFootCliModular(unittest.TestCase):
    def setUp(self):
        self.cli = SpiderFootCli()
        # Use config for all options
        self.cli.config['cli.spool'] = False
        self.cli.config['cli.silent'] = False
        self.cli.config['cli.color'] = False
        self.cli.config['cli.debug'] = False
        self.cli.config['cli.history'] = False

    def test_config_options_affect_behavior(self):
        # Should not print output when silent
        self.cli.config['cli.silent'] = True
        captured = io.StringIO()
        sys.stdout = captured
        self.cli.dprint('Should not print', err=False)
        sys.stdout = sys.__stdout__
        self.assertEqual(captured.getvalue(), '')
        # Should print output when not silent
        self.cli.config['cli.silent'] = False
        captured = io.StringIO()
        sys.stdout = captured
        self.cli.dprint('Should print', err=False)
        sys.stdout = sys.__stdout__
        self.assertIn('Should print', captured.getvalue())

    def test_modular_command_registry(self):
        # All commands should be registered in registry
        commands = self.cli.registry.all_commands()
        for cmd in [
            'ping', 'scans', 'modules', 'types', 'start', 'stop', 'delete',
            'export', 'scaninfo', 'correlations', 'summary', 'find', 'query', 'set', 'help', 'workspaces', 'targets', 'logs', 'data', 'correlationrules'
        ]:
            self.assertIn(cmd, commands)

    def test_modular_command_dispatch(self):
        # Each command should dispatch to a function
        for cmd in self.cli.registry.all_commands():
            entry = self.cli.registry.get(cmd)
            self.assertIsNotNone(entry)
            self.assertIn('func', entry)
            self.assertTrue(callable(entry['func']))

    def test_complete_default_with_config(self):
        self.cli.modules = ['mod1', 'mod2']
        self.cli.types = ['type1', 'type2']
        # Should complete modules
        completions = self.cli.complete_default('mod', 'start -m mod', 10, 13)
        self.assertIn('mod1', completions)
        # Should complete types
        completions = self.cli.complete_default('type', 'start -t type', 10, 14)
        self.assertIn('type1', completions)

    def test_inline_help_available(self):
        # Inline help should be available for registered commands
        for cmd in self.cli.registry.all_commands():
            if cmd in self.cli.inline_help:
                self.assertIsInstance(self.cli.inline_help[cmd], str)
                self.assertTrue(len(self.cli.inline_help[cmd]) > 0)

    def test_error_suggestion_for_unknown_command(self):
        # Should suggest similar commands for typos
        captured = io.StringIO()
        sys.stdout = captured
        self.cli.edprint("[!] Unknown command 'pings'.")
        sys.stdout = sys.__stdout__
        output = captured.getvalue()
        self.assertIn('Did you mean:', output)
        self.assertIn('ping', output)

    def test_pretty_print(self):
        # Should pretty print a list of dicts
        data = [
            {'col1': 'a', 'col2': 'b'},
            {'col1': 'c', 'col2': 'd'}
        ]
        out = self.cli.pretty(data)
        self.assertIn('col1', out)
        self.assertIn('col2', out)
        self.assertIn('a', out)
        self.assertIn('d', out)

if __name__ == '__main__':
    unittest.main()
