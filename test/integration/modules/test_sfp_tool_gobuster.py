# filepath: spiderfoot/test/integration/modules/test_sfptool_gobuster.py
import pytest
from unittest.mock import patch, MagicMock
import os

from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_tool_gobuster import sfp_tool_gobuster

# This test requires credentials for the Tool Gobuster service
# To run this test, set the environment variables:
# - SF_SFP_TOOL_GOBUSTER_API_KEY


@pytest.mark.skipif(
    not all(os.environ.get(env_var)
            for env_var in ['SF_SFP_TOOL_GOBUSTER_API_KEY']),
    reason="Integration test - requires Tool Gobuster credentials"
)
class TestModuleIntegrationToolGobuster:
    """Integration testing for the Tool Gobuster module."""

    @pytest.fixture
    def module(self):
        """Return a Tool Gobuster module."""
        sf = SpiderFoot({
            '_debug': True,
            '__logging': True,
            '__outputfilter': None,
            'api_key': os.environ.get('SF_API_KEY', ''),
            'checkaffiliates': True,
        })
        module = sfp_tool_gobuster()
        module.setup(sf, {
            '_debug': True,
            '__logging': True,
            '__outputfilter': None,
            'api_key': os.environ.get('SF_API_KEY', ''),
            'checkaffiliates': True,
        })
        return module

    def test_module_produces_events(self, module):
        """Test whether the module produces events when given input data."""
        target_value = "example.com"
        target_type = "DOMAIN_NAME"
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = "DOMAIN_NAME"
        event_data = "example.com"
        event_module = "test"
        source_event = SpiderFootEvent("ROOT", "", "", "")
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        # We're using a direct call to handleEvent, bypassing the framework's logic
        # for calling it in order to test it directly.
        result = module.handleEvent(evt)

        # Assert that the module produced events
        assert len(module.sf.events) > 0

        # Each event should be a dict with certain required fields
        for event in module.sf.events:
            assert event.get('type') is not None
            assert event.get('data') is not None
