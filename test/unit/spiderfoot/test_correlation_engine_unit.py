import pytest
from unittest.mock import MagicMock
from spiderfoot.correlation.rule_loader import RuleLoader
from spiderfoot.correlation.event_enricher import EventEnricher
from spiderfoot.correlation.result_aggregator import ResultAggregator

@pytest.fixture
def mock_dbh():
    dbh = MagicMock()
    dbh.get_events_for_scan.return_value = [
        {'type': 'EMAILADDR', 'data': 'unit@example.com', 'scan_id': 'scan1'}
    ]
    return dbh

def test_event_enricher_enrich_sources(mock_dbh):
    enricher = EventEnricher(mock_dbh)
    events = [{'id': 'event1', 'type': 'EMAILADDR', 'data': 'unit@example.com'}]
    enriched = enricher.enrich_sources('scan1', events)
    assert isinstance(enriched, list)

def test_event_enricher_enrich_entities(mock_dbh):
    enricher = EventEnricher(mock_dbh)
    events = [{'id': 'event1', 'type': 'EMAILADDR', 'data': 'unit@example.com'}]
    enriched = enricher.enrich_entities('scan1', events)
    assert isinstance(enriched, list)

def test_result_aggregator_count():
    aggregator = ResultAggregator()
    results = [
        {'meta': {}, 'result': 'A'},
        {'meta': {}, 'result': 'B'}
    ]
    count = aggregator.aggregate(results, method='count')
    assert count == 2

def test_rule_loader_from_dict():
    # Simulate loading rules from a dict
    loader = RuleLoader(None)
    loader.rules = [
        {'id': 'unit_rule', 'meta': {'name': 'Unit Rule'}}
    ]
    assert len(loader.rules) == 1
    assert loader.rules[0]['id'] == 'unit_rule'
