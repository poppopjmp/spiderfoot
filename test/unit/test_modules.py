# test_modules.py
import os
import unittest

from sflib import SpiderFoot
from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootHelpers
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


class TestSpiderFootModuleLoading(unittest.TestCase):
    """Test module loading."""

    def setUp(self):
        """Set up test case."""
        # Create mock SpiderFootTarget object
        self.sft = unittest.mock.MagicMock()
        super().setUp()

    @staticmethod
    def load_modules(sf):
        mod_dir = os.path.dirname(
            os.path.abspath(__file__)) + "/../../modules/"
        return SpiderFootHelpers.loadModulesAsDict(mod_dir, ["sfp_template.py"])

    def test_module_use_cases_are_valid(self):
        sf = SpiderFoot(self.default_options)
        valid_use_cases = ["Footprint", "Passive", "Investigate"]

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for group in m.get("group"):
                self.assertIn(group, valid_use_cases)

    def test_module_labels_are_valid(self):
        sf = SpiderFoot(self.default_options)
        valid_labels = ["errorprone", "tor",
                        "slow", "invasive", "apikey", "tool"]

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for label in m.get("labels"):
                self.assertIn(label, valid_labels)

    def test_module_categories_are_valid(self):
        sf = SpiderFoot(self.default_options)
        valid_categories = [
            "Content Analysis",
            "Crawling and Scanning",
            "DNS",
            "Leaks, Dumps and Breaches",
            "Passive DNS",
            "Public Registries",
            "Real World",
            "Reputation Systems",
            "Search Engines",
            "Secondary Networks",
            "Social Media",
        ]

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            self.assertIsInstance(m.get("cats"), list)
            self.assertTrue(len(m.get("cats")) <= 1)

            if module in ["sfp__stor_db", "sfp__stor_stdout"]:
                continue

            for cat in m.get("cats", list()):
                self.assertIn(cat, valid_categories)

    def test_module_model_is_valid(self):
        sf = SpiderFoot(self.default_options)
        valid_models = [
            "COMMERCIAL_ONLY",
            "FREE_AUTH_LIMITED",
            "FREE_AUTH_UNLIMITED",
            "FREE_NOAUTH_LIMITED",
            "FREE_NOAUTH_UNLIMITED",
            "PRIVATE_ONLY",
        ]

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            meta = m.get("meta")

            self.assertTrue(meta)
            self.assertIsInstance(meta, dict)

            data_source = meta.get("dataSource")

            if not data_source:
                continue

            self.assertIsInstance(data_source, dict)
            model = data_source.get("model")
            self.assertIsInstance(model, str)
            self.assertIn(model, valid_models)

    def test_modules_with_api_key_have_apiKeyInstructions(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            self.assertTrue(m.get("meta"))
            self.assertIsInstance(m.get("meta"), dict)

            meta = m.get("meta")

            if "apikey" in m.get("labels"):
                self.assertIn("dataSource", meta)
                self.assertIsInstance(
                    meta.get("dataSource").get("apiKeyInstructions"), list
                )
                self.assertTrue(
                    meta.get("dataSource").get("apiKeyInstructions"))

    def test_modules_with_api_key_options_have_apikey_label(self):
        """
        Test that modules which require API keys have the apikey label.
        """
        sf = SpiderFoot(dict())

        for module in self.sft.modules:
            module_obj = self.sft.modules[module]
            if not module_obj.opts:
                continue

            has_api_option = False
            for opt in module_obj.opts:
                if opt.endswith("_api_key") or opt.endswith("apikey"):
                    has_api_option = True
                    break

            if has_api_option:
                self.assertIn(
                    "apikey",
                    module_obj.meta.get("labels", []),
                    f"Module {module} has API key option but no 'apikey' label",
                )

    def test_modules_with_invasive_flag_are_not_in_passive_use_case(self):
        """
        Test that modules with the 'invasive' flag are excluded from the passive use case.
        """
        sf = SpiderFoot(dict())

        for module in self.sft.modules:
            module_obj = self.sft.modules[module]

            if module_obj.meta.get("flags", []) and "invasive" in module_obj.meta.get(
                "flags", []
            ):
                # Check this module is not in the passive use case
                self.assertNotIn(
                    module,
                    self.sft.use_cases.get("Passive", []),
                    f"Invasive module {module} should not be in passive use case",
                )

    def test_module_watched_events_are_valid(self):
        sf = SpiderFoot(self.default_options)
        sf.dbh = SpiderFootDb(self.default_options, True)

        valid_events = []
        for event in sf.dbh.eventTypes():
            valid_events.append(event[1])

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for watched_event in m.get("consumes"):
                if watched_event == "*":
                    continue
                self.assertIn(watched_event, valid_events)

    def test_module_produced_events_are_valid(self):
        sf = SpiderFoot(self.default_options)
        sf.dbh = SpiderFootDb(self.default_options, True)

        valid_events = []
        for event in sf.dbh.eventTypes():
            valid_events.append(event[1])

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            provides = m.get("provides")
            if not provides:
                continue

            for produced_event in provides:
                self.assertIn(produced_event, valid_events)

    def test_each_module_option_has_a_description(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            if module in ["sfp__stor_db", "sfp__stor_stdout"]:
                continue

            # check len(options) == len(option descriptions)
            if m.get("opts"):
                self.assertEqual(
                    f"{module} opts: {len(m.get('opts').keys())}",
                    f"{module} opts: {len(m.get('optdescs').keys())}",
                )

    def test_required_module_properties_are_present_and_valid(self):
        """
        Test that all modules have the required properties defined.
        """
        sf = SpiderFoot(dict())

        for module in self.sft.modules:
            module_obj = self.sft.modules[module]

            # Check required metadata properties
            self.assertIsInstance(
                module_obj.meta.get("name"),
                str,
                f"Module {module} missing 'name' property",
            )
            self.assertIsInstance(
                module_obj.meta.get("summary"),
                str,
                f"Module {module} missing 'summary' property",
            )
            self.assertIsInstance(
                module_obj.meta.get("flags"),
                list,
                f"Module {module} missing 'flags' property",
            )
            self.assertIsInstance(
                module_obj.meta.get("useCases"),
                list,
                f"Module {module} missing 'useCases' property",
            )
            self.assertIsInstance(
                module_obj.meta.get("categories"),
                list,
                f"Module {module} missing 'categories' property",
            )

            # Check that every module has at least one category and use case
            self.assertGreater(
                len(module_obj.meta.get("categories")),
                0,
                f"Module {module} has no categories",
            )
            self.assertGreater(
                len(module_obj.meta.get("useCases")),
                0,
                f"Module {module} has no use cases",
            )

            # Check that the module has a valid produces or consumes property
            self.assertTrue(
                isinstance(module_obj.producedEvents(), list) or
                isinstance(module_obj.watchedEvents(), list),
                f"Module {module} has no produces or consumes properties",
            )
