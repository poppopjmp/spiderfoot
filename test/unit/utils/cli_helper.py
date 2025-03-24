"""Utilities for testing command-line interfaces."""

import sys
import io
from contextlib import contextmanager


class CLIHelper:
    """Helper class for testing command-line interfaces."""
    
    @staticmethod
    @contextmanager
    def capture_stdout():
        """Capture stdout during a test.
        
        Yields:
            io.StringIO: Captured stdout
        """
        new_out = io.StringIO()
        old_out = sys.stdout
        try:
            sys.stdout = new_out
            yield new_out
        finally:
            sys.stdout = old_out
    
    @staticmethod
    @contextmanager
    def capture_stderr():
        """Capture stderr during a test.
        
        Yields:
            io.StringIO: Captured stderr
        """
        new_err = io.StringIO()
        old_err = sys.stderr
        try:
            sys.stderr = new_err
            yield new_err
        finally:
            sys.stderr = old_err
    
    @staticmethod
    @contextmanager
    def capture_output():
        """Capture both stdout and stderr during a test.
        
        Yields:
            tuple: (captured stdout, captured stderr)
        """
        new_out = io.StringIO()
        new_err = io.StringIO()
        old_out = sys.stdout
        old_err = sys.stderr
        try:
            sys.stdout = new_out
            sys.stderr = new_err
            yield new_out, new_err
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
    
    @staticmethod
    @contextmanager
    def mock_stdin(input_text):
        """Mock stdin with the provided input.
        
        Args:
            input_text (str): Text to provide as input
            
        Yields:
            None
        """
        new_in = io.StringIO(input_text)
        old_in = sys.stdin
        try:
            sys.stdin = new_in
            yield
        finally:
            sys.stdin = old_in
    
    @staticmethod
    def run_cli_command(command_func, args=None, stdin_input=None):
        """Run a CLI command function with arguments and capture output.
        
        Args:
            command_func (callable): Function to run
            args (list): Arguments to pass
            stdin_input (str): Input to provide via stdin
            
        Returns:
            tuple: (exit_code, stdout, stderr)
        """
        if args is None:
            args = []
            
        old_args = sys.argv
        sys.argv = [old_args[0]] + args
        
        with CLIHelper.capture_output() as (out, err):
            if stdin_input:
                with CLIHelper.mock_stdin(stdin_input):
                    try:
                        exit_code = command_func() or 0
                    except SystemExit as e:
                        exit_code = e.code if isinstance(e.code, int) else 1
            else:
                try:
                    exit_code = command_func() or 0
                except SystemExit as e:
                    exit_code = e.code if isinstance(e.code, int) else 1
                    
        sys.argv = old_args
        return exit_code, out.getvalue(), err.getvalue()
