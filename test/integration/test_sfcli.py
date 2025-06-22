# test_sfcli.py
import subprocess
import sys
import unittest
import os
import signal
import contextlib


class TestSfcli(unittest.TestCase):
    """Robust integration test for sfcli.py CLI."""

    def execute(self, command, timeout=30, cwd=None):
        """
        Execute command with timeout and robust process cleanup.

        Args:
            command: List of command arguments.
            timeout: Timeout in seconds.
            cwd: Working directory.

        Returns:
            (stdout, stderr, returncode)
        """
        proc = None
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd or os.getcwd(),
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            out, err = proc.communicate(timeout=timeout)
            return out, err, proc.returncode
        except subprocess.TimeoutExpired:
            if proc:
                if hasattr(os, 'killpg'):
                    with contextlib.suppress(Exception):
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    with contextlib.suppress(Exception):
                        proc.terminate()
                with contextlib.suppress(Exception):
                    proc.kill()
                proc.wait()
            return b'', b'TIMEOUT', -1

    def test_help_arg_should_print_help_and_exit(self):
        script_path = os.path.abspath("sfcli.py")
        out, err, code = self.execute([sys.executable, script_path, "-h"])
        help_text = b"show this help message and exit"
        self.assertTrue(help_text in out or help_text in err)
        self.assertEqual(0, code)
