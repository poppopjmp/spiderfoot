import pytest
from unittest.mock import MagicMock
from spiderfoot.correlation.rule_executor import RuleExecutor
import time

@pytest.fixture
def dbh():
    dbh = MagicMock()
    # Simulate 10,000 EMAILADDR events for performance
    dbh.get_events_for_scan.return_value = [
        {'type': 'EMAILADDR', 'data': f'user{i}@example.com', 'scan_id': 'scan1'} for i in range(10000)
    ]
    return dbh

def test_rule_executor_performance(dbh):
    rule = {
        'id': 'perf_rule',
        'meta': {'name': 'Perf Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 10000}],
        'headline': 'Perf headline {data}',
    }
    rules = [rule]
    executor = RuleExecutor(dbh, rules, scan_ids=['scan1'])
    start = time.time()
    results = executor.run()
    elapsed = time.time() - start
    assert 'perf_rule' in results
    assert 'Perf Rule' in results['perf_rule']['meta']['name']
    # Should complete in under 2 seconds for 10,000 events
    assert elapsed < 2, f"Engine too slow: {elapsed:.2f}s for 10,000 events"

def test_rule_executor_many_rules(dbh):
    # 100 rules, each matching all events
    rules = [
        {
            'id': f'rule_{i}',
            'meta': {'name': f'Rule {i}', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
            'collections': [
                {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
            ],
            'aggregation': {'field': 'data'},
            'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
            'headline': f'Rule {i} headline {{data}}',
        } for i in range(100)
    ]
    executor = RuleExecutor(dbh, rules, scan_ids=['scan1'])
    start = time.time()
    results = executor.run()
    elapsed = time.time() - start
    assert len(results) == 100
    assert all(f'rule_{i}' in results for i in range(100))
    assert elapsed < 2, f"Engine too slow: {elapsed:.2f}s for 100 rules"
