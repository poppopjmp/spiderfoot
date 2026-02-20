from __future__ import annotations

"""Tests for sfp_haveibeenpwned module."""

import pytest
import unittest
from test.unit.utils.test_module_base import TestModuleBase

from modules.sfp_haveibeenpwned import sfp_haveibeenpwned

class TestModuleIntegrationHaveibeenpwned(TestModuleBase):

    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
