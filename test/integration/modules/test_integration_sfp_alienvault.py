# filepath: /mnt/c/Users/van1sh/Documents/GitHub/spiderfoot/test/integration/modules/test_integration_sfp_alienvault.py
import pytest
import os

from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_alienvault import sfp_alienvault

# This test requires credentials for the Alienvault service
# To run this test, set the environment variables:
# - SF_SFP_ALIENVAULT_API_KEY


@pytest.mark.skipif(
    not all(os.environ.get(env_var)
            for env_var in ["SF_SFP_ALIENVAULT_API_KEY"]),
    reason="Integration test - requires Alienvault credentials",
)
class TestModuleIntegrationAlienvault:
    """Integration testing for the Alienvault module."""

    @pytest.fixture
    def module(self):
        """Return a Alienvault module."""
        sf = SpiderFoot(
            {
                "_debug": True,
                "__logging": True,
                "__outputfilter": None,
                "api_key": os.environ.get("SF_API_KEY", ""),
                "checkaffiliates": True,
            }
        )
        module = sfp_alienvault()
        module.setup(
            sf,
            {
                "_debug": True,
                "__logging": True,
                "__outputfilter": None,
                "api_key": os.environ.get("SF_API_KEY", ""),
                "checkaffiliates": True,
            },
        )
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
            assert event.get("type") is not None
            assert event.get("data") is not None
