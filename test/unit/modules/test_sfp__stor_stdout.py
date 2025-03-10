from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp__stor_stdout import sfp__stor_stdout
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleStor_stdout(SpiderFootModuleTestCase):
    """Test stdout storage module."""

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp__stor_stdout()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        module = sfp__stor_stdout()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp__stor_stdout()
        self.assertIsInstance(module.producedEvents(), list)
