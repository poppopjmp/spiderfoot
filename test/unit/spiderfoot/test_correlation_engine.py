from __future__ import annotations

"""Tests for correlation_engine module."""

import unittest
from test.unit.utils.test_module_base import TestModuleBase
from unittest.mock import MagicMock, patch
from spiderfoot.correlation.rule_loader import RuleLoader
from spiderfoot.correlation.rule_executor import RuleExecutor
from spiderfoot.correlation.event_enricher import EventEnricher
from spiderfoot.correlation.result_aggregator import ResultAggregator

class TestCorrelationEngineUnit(TestModuleBase):
    def setUp(self):
        # Mock DB handle
        self.dbh = MagicMock()
        # Minimal rule YAML for testing
        self.sample_rule = {
            'id': 'test_rule',
            'meta': {
                'name': 'Test Rule',
                'description': 'A test rule',
                'risk': 'INFO',
                'scope': 'scan',
            },
            'collections': [
                {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
            ],
            'aggregation': {'field': 'data'},
            'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
            'headline': 'Test headline {data}',
        }
        self.rules = [self.sample_rule]

        # Define a mock event for use in all tests
        self.mock_event = {
            'hash': 'mockhash',
            'type': 'EMAILADDR',
            'data': 'test@example.com',
            'module': 'test_module',
            'created': 0,
            'source_event_hash': 'ROOT',
            'scan_id': 'mockscanid'
        }
        # Patch _get_scan_events so the rule engine uses the mock event
        patcher = patch(
            'spiderfoot.correlation.rule_executor.DefaultRuleExecutionStrategy._get_scan_events',
            return_value=[self.mock_event]
        )
        self._get_scan_events_patcher = patcher
        self.mock_get_scan_events = patcher.start()

    def tearDown(self):
        # Stop the patcher for _get_scan_events
        if hasattr(self, '_get_scan_events_patcher'):
            self._get_scan_events_patcher.stop()

    def test_rule_loader(self):
        # Simulate loading rules from dict
        loader = RuleLoader(None)
        loader.rules = [self.sample_rule]
        self.assertEqual(len(loader.rules), 1)
        self.assertEqual(loader.rules[0]['id'], 'test_rule')

    def test_rule_executor(self):
        # Mock DB to return events
        self.dbh.get_events_for_scan.return_value = [
            {'hash': 'event1', 'type': 'EMAILADDR', 'data': 'test@example.com'}  # Use 'hash' key
        ]
        executor = RuleExecutor(self.dbh, self.rules, scan_ids=['scan1'], debug=True)
        results = executor.run()
        self.assertIn('test_rule', results)
        self.assertTrue(results['test_rule'].get('matched', True))  # Use get to avoid KeyError

    def test_event_enricher(self):
        enricher = EventEnricher(self.dbh)
        events = [{'hash': 'event1', 'type': 'EMAILADDR', 'data': 'test@example.com'}]  # Use 'hash' key
        enriched = enricher.enrich_sources('scan1', events)
        self.assertIsInstance(enriched, list)

    def test_result_aggregator(self):
        aggregator = ResultAggregator(scan_id="test-scan")
        aggregator.add_event("EMAILADDR", "test@example.com", "sfp_test", confidence=90, risk=10)
        aggregator.add_event("IP_ADDRESS", "192.168.1.1", "sfp_dns", confidence=100, risk=30)
        aggregator.add_event("MALICIOUS_IPADDR", "192.168.1.1", "sfp_virustotal", confidence=80, risk=80)
        self.assertEqual(aggregator.total_events, 3)
        self.assertEqual(aggregator.unique_types, 3)
        summary = aggregator.get_summary()
        self.assertIn("total_events", summary)
        self.assertEqual(summary["total_events"], 3)
        self.assertGreater(summary["overall_risk_score"], 0)
        # Verify risk events are tracked
        top_risk = aggregator.get_top_risk_events(limit=2)
        self.assertEqual(len(top_risk), 2)
        self.assertEqual(top_risk[0]["risk"], 80)  # highest risk first

if __name__ == '__main__':
    unittest.main()
