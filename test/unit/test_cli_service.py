"""Unit tests for spiderfoot.cli_service."""
from __future__ import annotations

import io
import sys
import unittest
from unittest.mock import patch

from spiderfoot.cli_service import (
    _print_table,
    build_parser,
    cmd_version,
    main,
)


class TestPrintTable(unittest.TestCase):

    def test_empty_rows(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            _print_table([], ["a", "b"])
        self.assertIn("no data", out.getvalue())

    def test_simple_table(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            _print_table(
                [{"name": "alice", "age": "30"},
                 {"name": "bob", "age": "25"}],
                ["name", "age"],
            )
        output = out.getvalue()
        self.assertIn("alice", output)
        self.assertIn("bob", output)
        self.assertIn("name", output)


class TestBuildParser(unittest.TestCase):

    def test_parser_creates(self):
        parser = build_parser()
        self.assertIsNotNone(parser)

    def test_version_command(self):
        parser = build_parser()
        args = parser.parse_args(["version"])
        self.assertEqual(args.command, "version")

    def test_status_command(self):
        parser = build_parser()
        args = parser.parse_args(["status"])
        self.assertEqual(args.command, "status")

    def test_metrics_command(self):
        parser = build_parser()
        args = parser.parse_args(["metrics", "--format", "json"])
        self.assertEqual(args.command, "metrics")
        self.assertEqual(args.format, "json")

    def test_scan_submit_command(self):
        parser = build_parser()
        args = parser.parse_args([
            "scan", "submit", "--target", "example.com",
            "--priority", "high",
        ])
        self.assertEqual(args.command, "scan")
        self.assertEqual(args.scan_cmd, "submit")
        self.assertEqual(args.target, "example.com")
        self.assertEqual(args.priority, "high")

    def test_correlate_command(self):
        parser = build_parser()
        args = parser.parse_args(["correlate", "scan-123"])
        self.assertEqual(args.command, "correlate")
        self.assertEqual(args.scan_id, "scan-123")

    def test_modules_command(self):
        parser = build_parser()
        args = parser.parse_args(["modules", "--json"])
        self.assertEqual(args.command, "modules")

    def test_config_get(self):
        parser = build_parser()
        args = parser.parse_args(["config", "get", "_fetchtimeout"])
        self.assertEqual(args.command, "config")
        self.assertEqual(args.config_cmd, "get")
        self.assertEqual(args.key, "_fetchtimeout")


class TestCmdVersion(unittest.TestCase):

    def test_prints_version(self):
        out = io.StringIO()
        with patch("sys.stdout", out):
            cmd_version(build_parser().parse_args(["version"]))
        output = out.getvalue()
        self.assertIn("SpiderFoot", output)
        self.assertIn("Python", output)


class TestMainNoArgs(unittest.TestCase):

    def test_no_args_prints_help(self):
        with self.assertRaises(SystemExit) as ctx:
            main([])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
