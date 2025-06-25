import pytest
import unittest
from unittest.mock import patch

from modules.sfp_azureblobstorage import sfp_azureblobstorage
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationazureblobstorage(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({})
        self.module = sfp_azureblobstorage()
        self.module.setup(self.sf, dict())
        self.events = []
        self.module.notifyListeners = lambda evt: self.events.append(evt)

    @patch.object(sfp_azureblobstorage, 'checkForStop', return_value=False)
    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent(self, mock_fetchUrl, mock_checkForStop):
        # Simulate a positive HTTP response for a known Azure blob
        mock_fetchUrl.return_value = {"code": 200}
        test_domain = "spiderfoot-test"
        event = SpiderFootEvent("DOMAIN_NAME", test_domain, "testsrc", None)
        self.module.handleEvent(event)
        # The module should emit at least one CLOUD_STORAGE_BUCKET event
        found = any(evt.eventType == "CLOUD_STORAGE_BUCKET" and \
                   evt.data.startswith("spiderfoot-test") and \
                   evt.data.endswith(".blob.core.windows.net")
                   for evt in self.events)
        self.assertTrue(found, "CLOUD_STORAGE_BUCKET event not emitted for accessible blob")
