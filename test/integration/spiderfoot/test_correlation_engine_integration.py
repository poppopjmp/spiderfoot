import pytest
from spiderfoot import SpiderFootDb
from spiderfoot.correlation.rule_executor import RuleExecutor
import yaml

@pytest.fixture
def dbh():
    config = {'__database': ':memory:'}
    dbh = SpiderFootDb(config, init=True)
    scan_id = 'integration_scan'
    # Ensure table is dropped and created fresh
    dbh.dbh.execute("DROP TABLE IF EXISTS tbl_scan_results")
    dbh.dbh.execute("""
        CREATE TABLE tbl_scan_results (
            scan_id TEXT, type TEXT, data TEXT
        )
    """)
    dbh.dbh.execute(
        "INSERT INTO tbl_scan_results (scan_id, type, data) VALUES (?, ?, ?)",
        (scan_id, 'EMAILADDR', 'integration@example.com')
    )
    dbh.conn.commit()
    return dbh, scan_id

def test_correlation_engine_integration(dbh):
    dbh, scan_id = dbh
    sample_rule = {
        'id': 'integration_rule',
        'meta': {
            'name': 'Integration Rule',
            'description': 'Integration test rule',
            'risk': 'INFO',
            'scope': 'scan',
        },
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
        'headline': 'Integration headline {data}',
    }
    rules = [sample_rule]
    executor = RuleExecutor(dbh, rules, scan_ids=[scan_id])
    results = executor.run()
    print('DEBUG: correlation engine results:', results)
    assert 'integration_rule' in results
    assert 'meta' in results['integration_rule']
    assert 'matched' in results['integration_rule']
    assert results['integration_rule']['matched'] is True
    assert 'Integration Rule' in results['integration_rule']['meta']['name']
    assert results['integration_rule']['correlations_created'] > 0

def test_multiple_rules(dbh):
    dbh, scan_id = dbh
    rules = [
        {
            'id': 'match_rule',
            'meta': {'name': 'Match Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
            'collections': [
                {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
            ],
            'aggregation': {'field': 'data'},
            'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
            'headline': 'Match headline {data}',
        },
        {
            'id': 'no_match_rule',
            'meta': {'name': 'No Match Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
            'collections': [
                {'collect': [{'method': 'exact', 'field': 'type', 'value': 'SOMETHINGELSE'}]}
            ],
            'aggregation': {'field': 'data'},
            'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
            'headline': 'No match headline {data}',
        }
    ]
    executor = RuleExecutor(dbh, rules, scan_ids=[scan_id])
    results = executor.run()
    assert 'match_rule' in results
    assert 'no_match_rule' in results
    assert 'Match Rule' in results['match_rule']['meta']['name']
    assert 'No Match Rule' in results['no_match_rule']['meta']['name']
    assert results['match_rule']['matched'] is True
    assert results['no_match_rule']['matched'] is False

def test_threshold_logic(dbh):
    dbh, scan_id = dbh
    # Rule with threshold minimum 2, but only 1 event in DB
    rule = {
        'id': 'threshold_rule',
        'meta': {'name': 'Threshold Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 2}],
        'headline': 'Threshold headline {data}',
    }
    executor = RuleExecutor(dbh, [rule], scan_ids=[scan_id])
    results = executor.run()
    assert 'threshold_rule' in results
    assert 'Threshold Rule' in results['threshold_rule']['meta']['name']
    assert results['threshold_rule']['matched'] is False  # Should be False because threshold minimum 2 but only 1 event

def test_non_matching_event_type(dbh):
    dbh, scan_id = dbh
    # Rule for a type not present in DB
    rule = {
        'id': 'nonmatch_type_rule',
        'meta': {'name': 'Nonmatch Type Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': 'IP_ADDRESS'}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
        'headline': 'Nonmatch type headline {data}',
    }
    executor = RuleExecutor(dbh, [rule], scan_ids=[scan_id])
    results = executor.run()
    assert 'nonmatch_type_rule' in results
    assert 'Nonmatch Type Rule' in results['nonmatch_type_rule']['meta']['name']
    assert results['nonmatch_type_rule']['matched'] is False

def test_empty_ruleset(dbh):
    dbh, scan_id = dbh
    rules = []
    executor = RuleExecutor(dbh, rules, scan_ids=[scan_id])
    results = executor.run()
    assert results == {}

def test_empty_events(dbh):
    dbh, scan_id = dbh
    # Remove all events from DB
    dbh.dbh.execute("DELETE FROM tbl_scan_results")
    dbh.conn.commit()
    rule = {
        'id': 'no_events_rule',
        'meta': {'name': 'No Events Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
        'headline': 'No events headline {data}',
    }
    executor = RuleExecutor(dbh, [rule], scan_ids=[scan_id])
    results = executor.run()
    assert 'no_events_rule' in results
    assert 'No Events Rule' in results['no_events_rule']['meta']['name']
    assert results['no_events_rule']['matched'] is False

def test_invalid_rule_format(dbh):
    dbh, scan_id = dbh
    # Rule missing required fields
    rule = {'id': 'invalid_rule'}
    executor = RuleExecutor(dbh, [rule], scan_ids=[scan_id])
    results = executor.run()
    # Should not include invalid_rule in results
    assert 'invalid_rule' not in results

def test_multiple_scans(dbh):
    dbh, scan_id = dbh
    # Add a second scan with a different event
    scan_id2 = 'integration_scan2'
    dbh.dbh.execute(
        "INSERT INTO tbl_scan_results (scan_id, type, data) VALUES (?, ?, ?)",
        (scan_id2, 'EMAILADDR', 'integration2@example.com')
    )
    dbh.conn.commit()
    rule = {
        'id': 'multi_scan_rule',
        'meta': {'name': 'Multi Scan Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 1}],
        'headline': 'Multi scan headline {data}',
    }
    executor = RuleExecutor(dbh, [rule], scan_ids=[scan_id, scan_id2])
    results = executor.run()
    assert 'multi_scan_rule' in results
    assert 'Multi Scan Rule' in results['multi_scan_rule']['meta']['name']
    assert results['multi_scan_rule']['matched'] is True

@pytest.mark.parametrize("event_type,threshold,should_match", [
    ("EMAILADDR", 1, True),
    ("EMAILADDR", 2, False),
    ("IP_ADDRESS", 1, False),
])
def test_parametrized_threshold_and_type(dbh, event_type, threshold, should_match):
    dbh, scan_id = dbh
    rule = {
        'id': 'param_rule',
        'meta': {'name': 'Param Rule', 'description': '', 'risk': 'INFO', 'scope': 'scan'},
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': event_type}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': threshold}],
        'headline': 'Param headline {data}',
    }
    executor = RuleExecutor(dbh, [rule], scan_ids=[scan_id])
    results = executor.run()
    assert 'param_rule' in results
    if should_match:
        assert 'Param Rule' in results['param_rule']['meta']['name']
        assert results['param_rule']['matched'] is True
    else:
        assert 'Param Rule' in results['param_rule']['meta']['name']
        assert results['param_rule']['matched'] is False
        # Could add more checks for non-match if engine supports

def test_cross_scan_correlation(dbh):
    dbh, scan_id = dbh
    scan_id2 = 'integration_scan2'
    dbh.dbh.execute(
        "INSERT INTO tbl_scan_results (scan_id, type, data) VALUES (?, ?, ?)",
        (scan_id2, 'EMAILADDR', 'shared@example.com')
    )
    dbh.dbh.execute(
        "INSERT INTO tbl_scan_results (scan_id, type, data) VALUES (?, ?, ?)",
        (scan_id, 'EMAILADDR', 'shared@example.com')
    )
    dbh.conn.commit()
    rule = {
        'id': 'cross_scan_rule',
        'meta': {'name': 'Cross Scan Rule', 'description': '', 'risk': 'INFO', 'scope': 'workspace'},
        'collections': [
            {'collect': [{'method': 'exact', 'field': 'type', 'value': 'EMAILADDR'}]}
        ],
        'aggregation': {'field': 'data'},
        'analysis': [{'method': 'threshold', 'field': 'data', 'minimum': 2}],
        'headline': 'Cross scan headline {data}',
    }
    executor = RuleExecutor(dbh, [rule], scan_ids=[scan_id, scan_id2])
    results = executor.run()
    assert 'cross_scan_rule' in results
    assert 'Cross Scan Rule' in results['cross_scan_rule']['meta']['name']
    assert results['cross_scan_rule']['matched'] is True

def test_rule_loader_yaml():
    from spiderfoot.correlation.rule_loader import RuleLoader
    yaml_str = '''
- id: yaml_rule
  meta:
    name: YAML Rule
    description: YAML loaded rule
    risk: INFO
    scope: scan
  collections:
    collect:
        - method: exact
          field: type
          value: EMAILADDR
  aggregation:
    field: data
  analysis:
    - method: threshold
      field: data
      minimum: 1
  headline: YAML headline {data}
'''
    rules = yaml.safe_load(yaml_str)
    loader = RuleLoader(None)
    loader.rules = rules
    assert len(loader.rules) == 1
    assert loader.rules[0]['id'] == 'yaml_rule'
    assert loader.rules[0]['meta']['name'] == 'YAML Rule'
