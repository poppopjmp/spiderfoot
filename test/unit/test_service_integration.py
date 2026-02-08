"""
Tests for the service integration wiring.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.service_integration import (
    integrate_services,
    wire_scan_services,
    wire_module_services,
    complete_scan_services,
)


class TestIntegrateServices(unittest.TestCase):
    """Test global service initialization."""

    @patch("spiderfoot.service_integration.log")
    def test_initializes_registry(self, mock_log):
        result = integrate_services({"_cache_backend": "memory"})
        self.assertTrue(result)
        mock_log.info.assert_called()

    @patch("spiderfoot.service_integration.log")
    def test_handles_empty_config(self, mock_log):
        result = integrate_services({})
        self.assertTrue(result)


class TestWireScanServices(unittest.TestCase):
    """Test per-scan wiring."""

    def test_does_not_raise(self):
        scanner = MagicMock()
        wire_scan_services(scanner, "test-scan-123")

    @patch("spiderfoot.service_integration._wire_scan_metrics")
    def test_calls_metrics(self, mock_metrics):
        wire_scan_services(MagicMock(), "s1")
        mock_metrics.assert_called_once_with("s1")


class TestWireModuleServices(unittest.TestCase):
    """Test per-module wiring."""

    def test_legacy_module_no_crash(self):
        mod = MagicMock()
        mod.__name__ = "sfp_test"
        wire_module_services(mod, {})


class TestCompleteScanServices(unittest.TestCase):
    """Test scan completion recording."""

    def test_does_not_raise(self):
        complete_scan_services("scan-1", "FINISHED", 120.0)

    def test_error_status(self):
        complete_scan_services("scan-1", "ERROR", 10.0)


if __name__ == "__main__":
    unittest.main()
