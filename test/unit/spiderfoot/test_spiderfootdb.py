import unittest
from unittest.mock import patch, MagicMock
from spiderfoot.db import SpiderFootDb


class TestSpiderFootDb(unittest.TestCase):

    def setUp(self):
        self.opts = {
            '__database': 'test.db',
            '__dbtype': 'sqlite'
        }
        self.db = SpiderFootDb(self.opts)

    def test_init_invalid_opts_type(self):
        with self.assertRaises(TypeError):
            SpiderFootDb("invalid_opts")

    def test_init_empty_opts(self):
        with self.assertRaises(ValueError):
            SpiderFootDb({})

    def test_init_missing_database_key(self):
        with self.assertRaises(ValueError):
            SpiderFootDb({'__dbtype': 'sqlite'})

    def test_create(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.db.create()
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_close(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.close.return_value = None
            self.db.close()
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.close.called)

    def test_vacuumDB(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.db.vacuumDB()
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_search_invalid_criteria_type(self):
        with self.assertRaises(TypeError):
            self.db.search("invalid_criteria")

    def test_search_empty_criteria(self):
        with self.assertRaises(ValueError):
            self.db.search({})

    def test_search_single_criteria(self):
        with self.assertRaises(ValueError):
            self.db.search({'scan_id': 'test_scan'})

    def test_eventTypes(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('event_descr', 'event', 'event_raw', 'event_type')
            ]
            result = self.db.eventTypes()
            self.assertEqual(result, [('event_descr', 'event', 'event_raw', 'event_type')])

    def test_scanLogEvents_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanLogEvents([123, 'classification', 'message', 'component', 1234567890])

    def test_scanLogEvent_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanLogEvent(123, 'classification', 'message')

    def test_scanInstanceCreate_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanInstanceCreate(123, 'scanName', 'scanTarget')

    def test_scanInstanceSet_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanInstanceSet(123)

    def test_scanInstanceGet_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanInstanceGet(123)

    def test_scanResultSummary_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanResultSummary(123)

    def test_scanCorrelationSummary_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanCorrelationSummary(123)

    def test_scanCorrelationList_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanCorrelationList(123)

    def test_scanResultEvent_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanResultEvent(123)

    def test_scanResultEventUnique_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanResultEventUnique(123)

    def test_scanLogs_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanLogs(123)

    def test_scanErrors_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanErrors(123)

    def test_scanInstanceDelete_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanInstanceDelete(123)

    def test_scanResultsUpdateFP_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanResultsUpdateFP(123, ['resultHash'], 1)

    def test_configSet_invalid_optMap_type(self):
        with self.assertRaises(TypeError):
            self.db.configSet("invalid_optMap")

    def test_configSet_empty_optMap(self):
        with self.assertRaises(ValueError):
            self.db.configSet({})

    def test_configGet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('GLOBAL', 'opt', 'val')
            ]
            result = self.db.configGet()
            self.assertEqual(result, {'opt': 'val'})

    def test_configClear(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.db.configClear()
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanConfigSet_invalid_optMap_type(self):
        with self.assertRaises(TypeError):
            self.db.scanConfigSet('scan_id', "invalid_optMap")

    def test_scanConfigSet_empty_optMap(self):
        with self.assertRaises(ValueError):
            self.db.scanConfigSet('scan_id', {})

    def test_scanConfigGet_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanConfigGet(123)

    def test_scanEventStore_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanEventStore(123, MagicMock())

    def test_scanInstanceList(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('guid', 'name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status', 0)
            ]
            result = self.db.scanInstanceList()
            self.assertEqual(result, [('guid', 'name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status', 0)])

    def test_scanResultHistory_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanResultHistory(123)

    def test_scanElementSourcesDirect_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanElementSourcesDirect(123, ['elementId'])

    def test_scanElementChildrenDirect_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanElementChildrenDirect(123, ['elementId'])

    def test_scanElementSourcesAll_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanElementSourcesAll(123, ['childData'])

    def test_scanElementChildrenAll_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.scanElementChildrenAll(123, ['parentIds'])

    def test_correlationResultCreate_invalid_instanceId_type(self):
        with self.assertRaises(TypeError):
            self.db.correlationResultCreate(123, 'ruleId', 'ruleName', 'ruleDescr', 'ruleRisk', 'ruleYaml', 'correlationTitle', ['eventHash'])

    def test_scanLogEvents(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.executemany.return_value = None
            batch = [
                ('instanceId', 'classification', 'message', 'component', 1234567890)
            ]
            result = self.db.scanLogEvents(batch)
            self.assertTrue(result)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.executemany.called)

    def test_scanLogEvent(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.db.scanLogEvent('instanceId', 'classification', 'message')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanInstanceCreate(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.db.scanInstanceCreate('instanceId', 'scanName', 'scanTarget')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanInstanceSet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.db.scanInstanceSet('instanceId', started='started', ended='ended', status='status')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanInstanceGet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchone.return_value = [
                'name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status'
            ]
            result = self.db.scanInstanceGet('instanceId')
            self.assertEqual(result, ['name', 'seed_target', 1234567890, 1234567890, 1234567890, 'status'])

    def test_scanResultSummary(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('type', 'event_descr', 1234567890, 1, 1)
            ]
            result = self.db.scanResultSummary('instanceId')
            self.assertEqual(result, [('type', 'event_descr', 1234567890, 1, 1)])

    def test_scanCorrelationSummary(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('rule_risk', 1)
            ]
            result = self.db.scanCorrelationSummary('instanceId')
            self.assertEqual(result, [('rule_risk', 1)])

    def test_scanCorrelationList(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('id', 'title', 'rule_id', 'rule_risk', 'rule_name', 'rule_descr', 'rule_logic', 1)
            ]
            result = self.db.scanCorrelationList('instanceId')
            self.assertEqual(result, [('id', 'title', 'rule_id', 'rule_risk', 'rule_name', 'rule_descr', 'rule_logic', 1)])

    def test_scanResultEvent(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)
            ]
            result = self.db.scanResultEvent('instanceId')
            self.assertEqual(result, [(1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)])

    def test_scanResultEventUnique(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('data', 'type', 1)
            ]
            result = self.db.scanResultEventUnique('instanceId')
            self.assertEqual(result, [('data', 'type', 1)])

    def test_scanLogs(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'component', 'type', 'message', 1)
            ]
            result = self.db.scanLogs('instanceId')
            self.assertEqual(result, [(1234567890, 'component', 'type', 'message', 1)])

    def test_scanErrors(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'component', 'message')
            ]
            result = self.db.scanErrors('instanceId')
            self.assertEqual(result, [(1234567890, 'component', 'message')])

    def test_scanInstanceDelete(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            result = self.db.scanInstanceDelete('instanceId')
            self.assertTrue(result)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanResultsUpdateFP(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            result = self.db.scanResultsUpdateFP('instanceId', ['resultHash'], 1)
            self.assertTrue(result)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanConfigSet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            self.db.scanConfigSet('scan_id', {'opt': 'val'})
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanConfigGet(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                ('component', 'opt', 'val')
            ]
            result = self.db.scanConfigGet('instanceId')
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
            self.db.scanEventStore('instanceId', sfEvent)
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)

    def test_scanElementSourcesDirect(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')
            ]
            result = self.db.scanElementSourcesDirect('instanceId', ['elementId'])
            self.assertEqual(result, [(1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')])

    def test_scanElementChildrenDirect(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)
            ]
            result = self.db.scanElementChildrenDirect('instanceId', ['elementId'])
            self.assertEqual(result, [(1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)])

    def test_scanElementSourcesAll(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')
            ]
            result = self.db.scanElementSourcesAll('instanceId', ['childData'])
            self.assertEqual(result, [{'hash': (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0, 'type', 'module', 'source_entity_type')}, {'source_event_hash': ['hash']}])

    def test_scanElementChildrenAll(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value.fetchall.return_value = [
                (1234567890, 'data', 'source_data', 'module', 'type', 100, 100, 0, 'hash', 'source_event_hash', 'event_descr', 'event_type', 'scan_instance_id', 0, 0)
            ]
            result = self.db.scanElementChildrenAll('instanceId', ['parentIds'])
            self.assertEqual(result, ['hash'])

    def test_correlationResultCreate(self):
        with patch('spiderfoot.db.sqlite3') as mock_sqlite3:
            mock_sqlite3.connect.return_value.cursor.return_value.execute.return_value = None
            result = self.db.correlationResultCreate('instanceId', 'ruleId', 'ruleName', 'ruleDescr', 'ruleRisk', 'ruleYaml', 'correlationTitle', ['eventHash'])
            self.assertEqual(result, 'correlation_id')
            self.assertTrue(mock_sqlite3.connect.return_value.cursor.return_value.execute.called)


if __name__ == "__main__":
    unittest.main()
