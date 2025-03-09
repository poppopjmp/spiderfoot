import unittest
from unittest.mock import MagicMock, Mock, patch

from spiderfoot.db import SpiderFootDb


class TestSpiderFootDb(SpiderFootModuleTestCase):
    """Test SpiderFootDb."""

    def setUp(self):
        """Set up test case."""
        self.dbh = SpiderFootDb(":memory:")
        self.sf_event = MagicMock()
        self.sf_event.return_value.__class__.__name__ = "SpiderFootEvent"
        self.sf_event.data = "test data"
        self.sf_event.module = "test module"
        self.sf_event.eventType = "test event type"
        self.sf_event.confidence = 100
        self.sf_event.visibility = 100
        self.sf_event.risk = 0
        self.sf_event.hash = "test hash"
        self.sf_event.sourceEventHash = "test source event hash"

    def test_create(self):
        """Test create()"""
        result = self.dbh.create()
        self.assertTrue(result)

    def test_close(self):
        """Test close()"""
        result = self.dbh.close()
        self.assertTrue(result)

    def test_configGet(self):
        """Test configGet()"""
        # Set up a test config
        self.dbh.configSet('opt', 'val')
        config = self.dbh.configGet()
        self.assertEqual(config, {'opt': 'val'})

    def test_configClear(self):
        """Test configClear()"""
        result = self.dbh.configClear()
        self.assertTrue(result)

    def test_init_invalid_opts_type(self):
        with self.assertRaises(TypeError):
            SpiderFootDb("invalid_opts")

    def test_init_empty_opts(self):
        with self.assertRaises(ValueError):
            SpiderFootDb({})

    def test_init_missing_database_key(self):
        with self.assertRaises(ValueError):
            SpiderFootDb({'__dbtype': 'sqlite'})

    def test_vacuumDB(self):
        """
        Test vacuumDB
        """
        opts = {}  # Make sure opts is a dict, not a string
        result = self.sf.vacuumDB(opts)
        self.assertIsNone(result)

    def test_search_invalid_criteria_type(self):
        with self.assertRaises(TypeError):
            self.dbh.search("invalid_criteria")

    def test_search_empty_criteria(self):
        with self.assertRaises(ValueError):
            self.dbh.search({})

    def test_search_single_criteria(self):
        """
        Test search with single criteria
        """
        modules_data = self.sf.modulesData()
        module = modules_data[0]
        if isinstance(module, str):
            module = {'module': module}  # Convert string to dict if needed
        result = self.sf.search([module])
        self.assertIsInstance(result, list)

    def test_eventTypes(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('event_descr', 'event', 'event_raw', 'event_type')
            ]
            result = self.dbh.eventTypes()
            self.assertEqual(result, [('event_descr', 'event', 'event_raw', 'event_type')])

    def test_scanLogEvents_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanLogEvents([123, 'classification', 'message', 'component', 1234567890])

    def test_scanLogEvent_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanLogEvent(123, 'classification', 'message')

    def test_scanInstanceCreate_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanInstanceCreate(123, 'scanName', 'scanTarget')

    def test_scanInstanceSet_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanInstanceSet(123)

    def test_scanInstanceGet_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanInstanceGet(123)

    def test_scanResultSummary_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanResultSummary(123)

    def test_scanCorrelationSummary_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanCorrelationSummary(123)

    def test_scanCorrelationList_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanCorrelationList(123)

    def test_scanResultEvent_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanResultEvent(123)

    def test_scanResultEventUnique_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanResultEventUnique(123)

    def test_scanLogs_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanLogs(123)

    def test_scanErrors_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanErrors(123)

    def test_scanInstanceDelete_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanInstanceDelete(123)

    def test_scanResultsUpdateFP_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanResultsUpdateFP(123, ['resultHash'], 1)

    def test_configSet_invalid_optMap_type(self):
        with self.assertRaises(TypeError):
            self.dbh.configSet("invalid_optMap")

    def test_configSet_empty_optMap(self):
        with self.assertRaises(ValueError):
            self.dbh.configSet({})

    def test_scanConfigSet_invalid_optMap_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanConfigSet('scan_id', "invalid_optMap")

    def test_scanConfigSet_empty_optMap(self):
        with self.assertRaises(ValueError):
            self.dbh.scanConfigSet('scan_id', {})

    def test_scanConfigGet_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanConfigGet(123)

    def test_scanEventStore_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanEventStore(123, MagicMock())

    def test_scanInstanceList(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('guid', 'name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status', 0)
            ]
            result = self.dbh.scanInstanceList()
            self.assertEqual(result, [('guid', 'name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status', 0)])

    def test_scanResultHistory_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanResultHistory(123)

    def test_scanElementSourcesDirect_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanElementSourcesDirect(123, ['elementId'])

    def test_scanElementChildrenDirect_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanElementChildrenDirect(123, ['elementId'])

    def test_scanElementSourcesAll_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanElementSourcesAll(123, ['childData'])

    def test_scanElementChildrenAll_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.scanElementChildrenAll(123, ['parentIds'])

    def test_correlationResultCreate_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.dbh.correlationResultCreate(123, 'ruleId', 'ruleName', 'ruleDescr', 'ruleRisk', 'ruleYaml', 'correlationTitle', ['eventHash'])

    def test_scanLogEvents(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.executemany.return_value = None
            batch = [
                ('instanceId', 'classification', 'message', 'component', 1234567890)
            ]
            result = self.dbh.scanLogEvents(batch)
            self.assertTrue(result)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.executemany.called)

    def test_scanLogEvent(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.dbh.scanLogEvent('instanceId', 'classification', 'message')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanInstanceCreate(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.dbh.scanInstanceCreate('instanceId', 'scanName', 'scanTarget')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanInstanceSet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.dbh.scanInstanceSet('instanceId', started='started', ended='ended', status='status')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanInstanceGet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchone.return_value = [
                'name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status'
            ]
            result = self.dbh.scanInstanceGet('instanceId')
            self.assertEqual(result, ['name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status'])

    def test_scanResultSummary(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('type', 'event_descr', 1234567890, 1, 1)
            ]
            result = self.dbh.scanResultSummary('instanceId')
            self.assertEqual(result, [('type', 'event_descr', 1234567890, 1, 1)])

    def test_scanCorrelationSummary(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('rule_risk', 1)
            ]
            result = self.dbh.scanCorrelationSummary('instanceId')
            self.assertEqual(result, [('rule_risk', 1)])

    def test_scanCorrelationList(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('id', 'title', 'rule_id', 'rule_risk', 'rule_name', 'rule_descr', 'rule_logic', 1)
            ]
            result = self.dbh.scanCorrelationList('instanceId')
            self.assertEqual(result, [('id', 'title', 'rule_id', 'rule_risk', 'rule_name', 'rule_descr', 'rule_logic', 1)])

    def test_scanResultEvent(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)
            ]
            result = self.dbh.scanResultEvent('instanceId')
            self.assertEqual(result, [(1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)])

    def test_scanResultEventUnique(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('data', 'type', 1)
            ]
            result = self.dbh.scanResultEventUnique('instanceId')
            self.assertEqual(result, [('data', 'type', 1)])

    def test_scanLogs(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'component', 'type', 'message', 1)
            ]
            result = self.dbh.scanLogs('instanceId')
            self.assertEqual(result, [(1234567890, 'component', 'type', 'message', 1)])

    def test_scanErrors(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'component', 'message')
            ]
            result = self.dbh.scanErrors('instanceId')
            self.assertEqual(result, [(1234567890, 'component', 'message')])

    def test_scanInstanceDelete(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            result = self.dbh.scanInstanceDelete('instanceId')
            self.assertTrue(result)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanResultsUpdateFP(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            result = self.dbh.scanResultsUpdateFP('instanceId', ['resultHash'], 1)
            self.assertTrue(result)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanConfigSet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.dbh.scanConfigSet('scan_id', {'opt': 'val'})
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanConfigGet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('component', 'opt', 'val')
            ]
            result = self.dbh.scanConfigGet('instanceId')
            self.assertEqual(result, {'opt': 'val'})

    def test_scanEventStore(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            sfEvent = MagicMock()
            sfEvent.generated = 1234567890.0
            sfEvent.eventType = 'type'
            sfEvent.data = 'data'
            sfEvent.module = 'module'
            sfEvent.confidence = 100
            sfEvent.visibility = 100
            sfEvent.risk = 0
            sfEvent.sourceEvent = MagicMock()
            sfEvent.sourceEventHash = 'source_event_hash'
            sfEvent.hash = 'hash'
            self.dbh.scanEventStore('instanceId', sfEvent)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanElementSourcesDirect(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')
            ]
            result = self.dbh.scanElementSourcesDirect('instanceId', ['elementId'])
            self.assertEqual(result, [(1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')])

    def test_scanElementChildrenDirect(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)
            ]
            result = self.dbh.scanElementChildrenDirect('instanceId', ['elementId'])
            self.assertEqual(result, [(1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)])

    def test_scanElementSourcesAll(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')
            ]
            result = self.dbh.scanElementSourcesAll('instanceId', ['childData'])
            self.assertEqual(result, [{'hash': (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')}, {'source_event_hash': ['hash']}])

    def test_scanElementChildrenAll(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)
            ]
            result = self.dbh.scanElementChildrenAll('instanceId', ['parentIds'])
            self.assertEqual(result, ['hash'])

    def test_correlationResultCreate(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            result = self.dbh.correlationResultCreate('instanceId', 'ruleId', 'ruleName', 'ruleDescr', 'ruleRisk', 'ruleYaml', 'correlationTitle', ['eventHash'])
            self.assertEqual(result, 'correlation_id')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)


if __name__ == "__main__":
    unittest.main()
