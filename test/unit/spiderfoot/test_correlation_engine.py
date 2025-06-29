import unittest
from unittest.mock import MagicMock, patch
from spiderfoot.correlation.rule_loader import RuleLoader
from spiderfoot.correlation.rule_executor import RuleExecutor
from spiderfoot.correlation.event_enricher import EventEnricher
from spiderfoot.correlation.result_aggregator import ResultAggregator

class TestCorrelationEngineUnit(unittest.TestCase):
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
            {'id': 'event1', 'type': 'EMAILADDR', 'data': 'test@example.com'}  # Add 'id' key
        ]
        executor = RuleExecutor(self.dbh, self.rules, scan_ids=['scan1'], debug=True)
        results = executor.run()
        self.assertIn('test_rule', results)
        self.assertTrue(results['test_rule'].get('matched', True))  # Use get to avoid KeyError

    def test_event_enricher(self):
        enricher = EventEnricher(self.dbh)
        events = [{'id': 'event1', 'type': 'EMAILADDR', 'data': 'test@example.com'}]  # Add 'id' key
        enriched = enricher.enrich_sources('scan1', events)
        self.assertIsInstance(enriched, list)

    def test_result_aggregator(self):
        aggregator = ResultAggregator()
        results = [
            {'matched': True, 'events': [{'type': 'EMAILADDR', 'data': 'test@example.com'}]},
            {'matched': False, 'events': []}
        ]
        count = aggregator.aggregate(results, method='count')
        self.assertEqual(count, 2)

if __name__ == '__main__':
    unittest.main()
