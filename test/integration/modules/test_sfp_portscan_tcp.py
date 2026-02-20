from __future__ import annotations

"""Tests for sfp_portscan_tcp module."""

import pytest
import unittest
from test.unit.utils.test_module_base import TestModuleBase

from modules.sfp_portscan_tcp import sfp_portscan_tcp

class TestModuleIntegrationPortscanTcp(TestModuleBase):

    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
