import unittest
from unittest.mock import MagicMock
from spiderfoot.correlation import SpiderFootCorrelator
from spiderfoot import SpiderFootDb


class TestSpiderFootCorrelator(unittest.TestCase):

    def setUp(self):
        self.dbh = MagicMock(spec=SpiderFootDb)
        self.ruleset = {
            "rule1": """
            meta:
                name: "Test Rule"
                description: "A test rule"
                risk: 1
            collections:
                collect:
                    - field: "type"
                      method: "exact"
                      value: "IP_ADDRESS"
            headline: "Test Rule Headline"
            id: "rule1"
            version: 1
            enabled: true
            rawYaml: ""
            """
        }
        self.scanId = "test_scan"
        self.correlator = SpiderFootCorrelator(self.dbh, self.ruleset, self.scanId)

    def test_init_invalid_ruleset_type(self):
        with self.assertRaises(TypeError):
            SpiderFootCorrelator(self.dbh, "invalid_ruleset")

    def test_init_invalid_dbh_type(self):
        with self.assertRaises(TypeError):
            SpiderFootCorrelator("invalid_dbh", self.ruleset)

    def test_init_invalid_scanId_type(self):
        with self.assertRaises(TypeError):
            SpiderFootCorrelator(self.dbh, self.ruleset, 123)

    def test_get_ruleset(self):
        self.assertEqual(len(self.correlator.get_ruleset()), 1)

    def test_run_correlations_invalid_scanId(self):
        self.dbh.scanInstanceGet.return_value = None
        with self.assertRaises(ValueError):
            self.correlator.run_correlations()

    def test_run_correlations_running_scan(self):
        self.dbh.scanInstanceGet.return_value = [None, None, None, None, None, "RUNNING"]
        with self.assertRaises(ValueError):
            self.correlator.run_correlations()

    def test_build_db_criteria_invalid_matchrule_type(self):
        with self.assertRaises(TypeError):
            self.correlator.build_db_criteria("invalid_matchrule")

    def test_enrich_event_sources_invalid_events_type(self):
        with self.assertRaises(TypeError):
            self.correlator.enrich_event_sources("invalid_events")

    def test_enrich_event_children_invalid_events_type(self):
        with self.assertRaises(TypeError):
            self.correlator.enrich_event_children("invalid_events")

    def test_enrich_event_entities_invalid_events_type(self):
        with self.assertRaises(TypeError):
            self.correlator.enrich_event_entities("invalid_events")

    def test_collect_from_db(self):
        matchrule = {
            "field": "type",
            "method": "exact",
            "value": "IP_ADDRESS"
        }
        self.dbh.scanResultEvent.return_value = [
            [None, "data", None, "module", "type", None, None, None, "id"]
        ]
        events = self.correlator.collect_from_db(matchrule, False, False, False)
        self.assertEqual(len(events), 1)

    def test_event_extract(self):
        event = {
            "field": "value",
            "subfield": [{"field": "subvalue"}]
        }
        result = self.correlator.event_extract(event, "field")
        self.assertEqual(result, ["value"])

    def test_event_keep(self):
        event = {
            "field": "value"
        }
        patterns = ["value"]
        result = self.correlator.event_keep(event, "field", patterns, "exact")
        self.assertTrue(result)

    def test_refine_collection(self):
        matchrule = {
            "field": "type",
            "method": "exact",
            "value": "IP_ADDRESS"
        }
        events = [{"type": "IP_ADDRESS"}]
        self.correlator.refine_collection(matchrule, events)
        self.assertEqual(len(events), 1)

    def test_collect_events(self):
        collection = {
            "collect": [
                {
                    "field": "type",
                    "method": "exact",
                    "value": "IP_ADDRESS"
                }
            ]
        }
        self.dbh.scanResultEvent.return_value = [
            [None, "data", None, "module", "type", None, None, None, "id"]
        ]
        events = self.correlator.collect_events(collection, False, False, False, 0)
        self.assertEqual(len(events), 1)

    def test_aggregate_events(self):
        rule = {
            "id": "rule1",
            "aggregation": {
                "field": "type"
            }
        }
        events = [{"type": "IP_ADDRESS"}]
        buckets = self.correlator.aggregate_events(rule, events)
        self.assertEqual(len(buckets), 1)

    def test_analyze_events(self):
        rule = {
            "method": "threshold",
            "field": "type",
            "minimum": 1,
            "maximum": 10
        }
        buckets = {"bucket1": [{"type": "IP_ADDRESS"}]}
        self.correlator.analyze_events(rule, buckets)
        self.assertEqual(len(buckets), 1)

    def test_build_correlation_title(self):
        rule = {
            "headline": "Test Rule Headline",
            "id": "rule1"
        }
        data = [{"field": "value"}]
        title = self.correlator.build_correlation_title(rule, data)
        self.assertEqual(title, "Test Rule Headline")

    def test_create_correlation(self):
        rule = {
            "id": "rule1",
            "meta": {
                "name": "Test Rule",
                "description": "A test rule",
                "risk": 1
            },
            "rawYaml": ""
        }
        data = [{"id": "event1"}]
        self.dbh.correlationResultCreate.return_value = "correlation_id"
        result = self.correlator.create_correlation(rule, data)
        self.assertTrue(result)

    def test_check_ruleset_validity(self):
        rules = [self.ruleset["rule1"]]
        result = self.correlator.check_ruleset_validity(rules)
        self.assertTrue(result)

    def test_check_rule_validity(self):
        rule = self.ruleset["rule1"]
        result = self.correlator.check_rule_validity(rule)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
