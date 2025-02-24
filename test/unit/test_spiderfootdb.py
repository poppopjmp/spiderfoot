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


if __name__ == "__main__":
    unittest.main()
