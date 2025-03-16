# test_modules.py
import os
import pytest
import unittest

from sflib import SpiderFoot
from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootHelpers
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


@pytest.mark.usefixtures
class TestSpiderFootModuleLoading(unittest.TestCase):
    """Test SpiderFoot module loading."""

    @staticmethod
    def load_modules(sf):
        mod_dir = os.path.dirname(
            os.path.abspath(__file__)) + '/../../modules/'
        return SpiderFootHelpers.loadModulesAsDict(mod_dir, ['sfp_template.py'])

    def test_module_use_cases_are_valid(self):
        sf = SpiderFoot(self.default_options)
        valid_use_cases = ["Footprint", "Passive", "Investigate"]

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for group in m.get('group'):
                self.assertIn(group, valid_use_cases)

    def test_module_labels_are_valid(self):
        sf = SpiderFoot(self.default_options)
        valid_labels = ["errorprone", "tor",
                        "slow", "invasive", "apikey", "tool"]

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for label in m.get('labels'):
                self.assertIn(label, valid_labels)

    def test_module_categories_are_valid(self):
        sf = SpiderFoot(self.default_options)
        valid_categories = ["Content Analysis", "Crawling and Scanning", "DNS",
                            "Leaks, Dumps and Breaches", "Passive DNS",
                            "Public Registries", "Real World", "Reputation Systems",
                            "Search Engines", "Secondary Networks", "Social Media"]

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            self.assertIsInstance(m.get('cats'), list)
            self.assertTrue(len(m.get('cats')) <= 1)

            if module in ["sfp__stor_db", "sfp__stor_stdout"]:
                continue

            for cat in m.get('cats', list()):
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

            meta = m.get('meta')

            self.assertTrue(meta)
            self.assertIsInstance(meta, dict)

            data_source = meta.get('dataSource')

            if not data_source:
                continue

            self.assertIsInstance(data_source, dict)
            model = data_source.get('model')
            self.assertIsInstance(model, str)
            self.assertIn(model, valid_models)

    def test_modules_with_api_key_have_apiKeyInstructions(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            self.assertTrue(m.get('meta'))
            self.assertIsInstance(m.get('meta'), dict)

            meta = m.get('meta')

            if 'apikey' in m.get('labels'):
                self.assertIn('dataSource', meta)
                self.assertIsInstance(
                    meta.get('dataSource').get('apiKeyInstructions'), list)
                self.assertTrue(
                    meta.get('dataSource').get('apiKeyInstructions'))

    def test_modules_with_api_key_options_have_apikey_label(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt in m.get('opts'):
                if "api_key" in opt:
                    self.assertIn("apikey", m.get('labels'))

    def test_modules_with_invasive_flag_are_not_in_passive_use_case(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            if "Passive" in m.get('group'):
                self.assertNotIn("invasive", m.get('labels', list()))

    def test_module_watched_events_are_valid(self):
        sf = SpiderFoot(self.default_options)
        sf.dbh = SpiderFootDb(self.default_options, True)

        valid_events = []
        for event in sf.dbh.eventTypes():
            valid_events.append(event[1])

        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for watched_event in m.get('consumes'):
                if watched_event == '*':
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

            provides = m.get('provides')
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
            if m.get('opts'):
                self.assertEqual(f"{module} opts: {len(m.get('opts').keys())}",
                                 f"{module} opts: {len(m.get('optdescs').keys())}")

    def test_required_module_properties_are_present_and_valid(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            self.assertTrue(m.get('object'))
            self.assertTrue(m.get('name'))
            self.assertTrue(m.get('meta'))
            self.assertTrue(m.get('descr'))
            self.assertTrue(m.get('consumes'))
            self.assertIsInstance(m.get('cats'), list)
            self.assertIsInstance(m.get('labels'), list)
            self.assertIsInstance(m.get('provides'), list)
            self.assertIsInstance(m.get('consumes'), list)
            self.assertIsInstance(m.get('meta'), dict)

            # output modules do not have use cases, categories, produced events, data source, etc
            if module in ["sfp__stor_db", "sfp__stor_stdout"]:
                continue

            self.assertTrue(m.get('cats'))
            self.assertTrue(m.get('group'))
            self.assertTrue(m.get('provides'))

            meta = m.get('meta')

            # not all modules will have a data source (sfp_dnsresolve, sfp_dnscommonsrv, etc)
            if meta.get('dataSource'):
                self.assertIsInstance(meta.get('dataSource'), dict)
                self.assertTrue(meta.get('dataSource').get('website'))
                self.assertTrue(meta.get('dataSource').get('model'))
                # self.assertTrue(meta.get('dataSource').get('favIcon'))
                # self.assertTrue(meta.get('dataSource').get('logo'))
                # self.assertTrue(meta.get('dataSource').get('references'))
                self.assertTrue(meta.get('dataSource').get('description'))

            if module.startswith('sfp_tool_'):
                self.assertIsInstance(meta.get('toolDetails'), dict)
                self.assertTrue(meta.get('toolDetails').get('name'))
                self.assertTrue(meta.get('toolDetails').get('description'))
                self.assertTrue(meta.get('toolDetails').get('website'))
                self.assertTrue(meta.get('toolDetails').get('repository'))

    def test_module_options_have_default_values(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, val in m.get('opts').items():
                self.assertIsNotNone(
                    val, f"Module {module} option {opt} has no default value")

    def test_module_options_have_valid_types(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, val in m.get('opts').items():
                self.assertIsInstance(
                    val, (str, int, bool, list), f"Module {module} option {opt} has invalid type {type(val)}")

    def test_module_options_have_valid_names(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt in m.get('opts').keys():
                self.assertIsInstance(
                    opt, str, f"Module {module} option {opt} has invalid name type {type(opt)}")
                self.assertTrue(
                    opt.isidentifier(), f"Module {module} option {opt} has invalid name")

    def test_module_options_have_valid_descriptions(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, desc in m.get('optdescs').items():
                self.assertIsInstance(
                    desc, str, f"Module {module} option {opt} has invalid description type {type(desc)}")
                self.assertTrue(
                    desc, f"Module {module} option {opt} has empty description")

    def test_module_options_have_valid_labels(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, label in m.get('optlabels').items():
                self.assertIsInstance(
                    label, str, f"Module {module} option {opt} has invalid label type {type(label)}")
                self.assertTrue(
                    label, f"Module {module} option {opt} has empty label")

    def test_module_options_have_valid_values(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, val in m.get('opts').items():
                if isinstance(val, list):
                    for item in val:
                        self.assertIsInstance(
                            item, (str, int, bool), f"Module {module} option {opt} has invalid list item type {type(item)}")
                else:
                    self.assertIsInstance(
                        val, (str, int, bool), f"Module {module} option {opt} has invalid value type {type(val)}")

    def test_module_options_have_valid_defaults(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, val in m.get('opts').items():
                self.assertIsNotNone(
                    val, f"Module {module} option {opt} has no default value")
                self.assertIsInstance(
                    val, (str, int, bool, list), f"Module {module} option {opt} has invalid default value type {type(val)}")

    def test_module_options_have_valid_choices(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, choices in m.get('optchoices').items():
                self.assertIsInstance(
                    choices, list, f"Module {module} option {opt} has invalid choices type {type(choices)}")
                self.assertTrue(
                    choices, f"Module {module} option {opt} has empty choices")
                for choice in choices:
                    self.assertIsInstance(
                        choice, (str, int, bool), f"Module {module} option {opt} has invalid choice type {type(choice)}")

    def test_module_options_have_valid_min_max_values(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, min_val in m.get('optminvals').items():
                self.assertIsInstance(
                    min_val, (int, float), f"Module {module} option {opt} has invalid min value type {type(min_val)}")
                self.assertTrue(
                    min_val >= 0, f"Module {module} option {opt} has invalid min value {min_val}")

            for opt, max_val in m.get('optmaxvals').items():
                self.assertIsInstance(
                    max_val, (int, float), f"Module {module} option {opt} has invalid max value type {type(max_val)}")
                self.assertTrue(
                    max_val >= 0, f"Module {module} option {opt} has invalid max value {max_val}")

    def test_module_options_have_valid_regex(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, regex in m.get('optregex').items():
                self.assertIsInstance(
                    regex, str, f"Module {module} option {opt} has invalid regex type {type(regex)}")
                self.assertTrue(
                    regex, f"Module {module} option {opt} has empty regex")

    def test_module_options_have_valid_tooltips(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, tooltip in m.get('opttooltips').items():
                self.assertIsInstance(
                    tooltip, str, f"Module {module} option {opt} has invalid tooltip type {type(tooltip)}")
                self.assertTrue(
                    tooltip, f"Module {module} option {opt} has empty tooltip")

    def test_module_options_have_valid_order(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, order in m.get('optorder').items():
                self.assertIsInstance(
                    order, int, f"Module {module} option {opt} has invalid order type {type(order)}")
                self.assertTrue(
                    order >= 0, f"Module {module} option {opt} has invalid order {order}")

    def test_module_options_have_valid_sections(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, section in m.get('optsections').items():
                self.assertIsInstance(
                    section, str, f"Module {module} option {opt} has invalid section type {type(section)}")
                self.assertTrue(
                    section, f"Module {module} option {opt} has empty section")

    def test_module_options_have_valid_subsections(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, subsection in m.get('optsubsections').items():
                self.assertIsInstance(
                    subsection, str, f"Module {module} option {opt} has invalid subsection type {type(subsection)}")
                self.assertTrue(
                    subsection, f"Module {module} option {opt} has empty subsection")

    def test_module_options_have_valid_dependencies(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, dependencies in m.get('optdependencies').items():
                self.assertIsInstance(
                    dependencies, list, f"Module {module} option {opt} has invalid dependencies type {type(dependencies)}")
                self.assertTrue(
                    dependencies, f"Module {module} option {opt} has empty dependencies")
                for dependency in dependencies:
                    self.assertIsInstance(
                        dependency, str, f"Module {module} option {opt} has invalid dependency type {type(dependency)}")

    def test_module_options_have_valid_conditions(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, conditions in m.get('optconditions').items():
                self.assertIsInstance(
                    conditions, list, f"Module {module} option {opt} has invalid conditions type {type(conditions)}")
                self.assertTrue(
                    conditions, f"Module {module} option {opt} has empty conditions")
                for condition in conditions:
                    self.assertIsInstance(
                        condition, str, f"Module {module} option {opt} has invalid condition type {type(condition)}")

    def test_module_options_have_valid_visibility(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, visibility in m.get('optvisibility').items():
                self.assertIsInstance(
                    visibility, str, f"Module {module} option {opt} has invalid visibility type {type(visibility)}")
                self.assertTrue(
                    visibility, f"Module {module} option {opt} has empty visibility")

    def test_module_options_have_valid_editability(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, editability in m.get('opteditability').items():
                self.assertIsInstance(
                    editability, str, f"Module {module} option {opt} has invalid editability type {type(editability)}")
                self.assertTrue(
                    editability, f"Module {module} option {opt} has empty editability")

    def test_module_options_have_valid_help(self):
        sf = SpiderFoot(self.default_options)
        sfModules = self.load_modules(sf)
        for module in sfModules:
            m = sfModules[module]

            for opt, help_text in m.get('opthelp').items():
                self.assertIsInstance(
                    help_text, str, f"Module {module} option {opt} has invalid help type {type(help_text)}")
                self.assertTrue(
                    help_text, f"Module {module} option {opt} has empty help")

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
