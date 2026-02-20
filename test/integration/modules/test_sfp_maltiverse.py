from __future__ import annotations

"""Tests for sfp_maltiverse module."""

import pytest
import unittest
from test.unit.utils.test_module_base import TestModuleBase

from modules.sfp_maltiverse import sfp_maltiverse

class TestModuleIntegrationMaltiverse(TestModuleBase):

    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
