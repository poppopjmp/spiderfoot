import unittest
from unittest.mock import patch, MagicMock
import cherrypy
from sfwebui import SpiderFootWebUi


class TestSpiderFootWebUi(unittest.TestCase):

    def setUp(self):
        self.web_config = {'root': '/'}
        self.config = {'_debug': False}
        self.webui = SpiderFootWebUi(self.web_config, self.config)

    def test_error_page(self):
        with patch('cherrypy.response') as mock_response:
            self.webui.error_page()
            self.assertEqual(mock_response.status, 500)
            self.assertEqual(mock_response.body,
                             b"<html><body>Error</body></html>")

    def test_error_page_401(self):
        result = self.webui.error_page_401(
            '401 Unauthorized', 'Unauthorized', '', '1.0')
        self.assertEqual(result, "")

    def test_error_page_404(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'Not Found'
            result = self.webui.error_page_404(
                '404 Not Found', 'Not Found', '', '1.0')
            self.assertEqual(result, 'Not Found')

    def test_jsonify_error(self):
        with patch('cherrypy.response') as mock_response:
            result = self.webui.jsonify_error('404 Not Found', 'Not Found')
            self.assertEqual(
                mock_response.headers['Content-Type'], 'application/json')
            self.assertEqual(mock_response.status, '404 Not Found')
            self.assertEqual(
                result, {'error': {'http_status': '404 Not Found', 'message': 'Not Found'}})

    def test_error(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'Error'
            result = self.webui.error('Error')
            self.assertEqual(result, 'Error')

    def test_cleanUserInput(self):
        result = self.webui.cleanUserInput(['<script>alert("xss")</script>'])
        self.assertEqual(result, ['&lt;script&gt;alert("xss")&lt;/script&gt;'])

    def test_searchBase(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.search.return_value = [
                [1627846261, 'data', 'source', 'type', '',
                    '', '', '', '', '', 'ROOT', '', '']
            ]
            result = self.webui.searchBase('id', 'eventType', 'value')
            self.assertEqual(result, [
                             ['2021-08-01 00:31:01', 'data', 'source', 'type', '', '', '', '', '', '', 'ROOT', '', '']])

    def test_buildExcel(self):
        with patch('sfwebui.openpyxl.Workbook') as mock_workbook:
            mock_workbook.return_value.active = MagicMock()
            mock_workbook.return_value.save = MagicMock()
            result = self.webui.buildExcel([['data']], ['column'], 0)
            self.assertIsInstance(result, bytes)

    def test_scanexportlogs(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanLogs.return_value = [
                [1627846261, 'component', 'type', 'event', 'event_id']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scanexportlogs('id')
                self.assertEqual(result, b'csv_data')

    def test_scancorrelationsexport(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = ['scan_name']
            mock_db.return_value.scanCorrelationList.return_value = [
                ['rule_name', 'correlation', 'risk', 'description']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scancorrelationsexport('id')
                self.assertEqual(result, 'csv_data')

    def test_scaneventresultexport(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                    '', '', '', '', '', '', '', '', '']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scaneventresultexport('id', 'type')
                self.assertEqual(result, 'csv_data')

    def test_scaneventresultexportmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = ['scan_name']
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                    '', '', '', '', '', '', '', '', '']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scaneventresultexportmulti('id')
                self.assertEqual(result, 'csv_data')

    def test_scansearchresultexport(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.search.return_value = [
                [1627846261, 'data', 'source', 'type', '',
                    '', '', '', '', '', 'ROOT', '', '']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scansearchresultexport('id')
                self.assertEqual(result, 'csv_data')

    def test_scanexportjsonmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = ['scan_name']
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                    '', '', '', '', '', '', '', '', '']
            ]
            result = self.webui.scanexportjsonmulti('id')
            self.assertEqual(result, b'[]')

    def test_scanviz(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                    '', '', '', '', '', '', '', '', '']
            ]
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'root']
            result = self.webui.scanviz('id')
            self.assertIsInstance(result, str)

    def test_scanvizmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                    '', '', '', '', '', '', '', '', '']
            ]
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'root']
            result = self.webui.scanvizmulti('id')
            self.assertIsInstance(result, str)

    def test_scanopts(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'status']
            mock_db.return_value.scanConfigGet.return_value = {
                'config': 'value'}
            result = self.webui.scanopts('id')
            self.assertIsInstance(result, dict)

    def test_rerunscan(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target']
            mock_db.return_value.scanConfigGet.return_value = {
                '_modulesenabled': 'module'}
            with patch('sfwebui.mp.Process') as mock_process:
                mock_process.return_value.start.return_value = None
                with self.assertRaises(cherrypy.HTTPRedirect):
                    self.webui.rerunscan('id')

    def test_rerunscanmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target']
            mock_db.return_value.scanConfigGet.return_value = {
                '_modulesenabled': 'module'}
            with patch('sfwebui.mp.Process') as mock_process:
                mock_process.return_value.start.return_value = None
                result = self.webui.rerunscanmulti('id')
                self.assertIsInstance(result, str)

    def test_newscan(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.eventTypes.return_value = ['type']
            with patch('sfwebui.Template') as mock_template:
                mock_template.return_value.render.return_value = 'newscan'
                result = self.webui.newscan()
                self.assertEqual(result, 'newscan')

    def test_clonescan(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target']
            mock_db.return_value.scanConfigGet.return_value = {
                '_modulesenabled': 'module'}
            with patch('sfwebui.Template') as mock_template:
                mock_template.return_value.render.return_value = 'clonescan'
                result = self.webui.clonescan('id')
                self.assertEqual(result, 'clonescan')

    def test_index(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'index'
            result = self.webui.index()
            self.assertEqual(result, 'index')

    def test_scaninfo(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = ['scan_name']
            with patch('sfwebui.Template') as mock_template:
                mock_template.return_value.render.return_value = 'scaninfo'
                result = self.webui.scaninfo('id')
                self.assertEqual(result, 'scaninfo')

    def test_opts(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'opts'
            result = self.webui.opts()
            self.assertEqual(result, 'opts')

    def test_optsexport(self):
        with patch('sfwebui.SpiderFoot') as mock_spiderfoot:
            mock_spiderfoot.return_value.configSerialize.return_value = {
                'opt': 'value'}
            result = self.webui.optsexport()
            self.assertIsInstance(result, str)

    def test_optsraw(self):
        result = self.webui.optsraw()
        self.assertIsInstance(result, list)

    def test_scandelete(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'status']
            result = self.webui.scandelete('id')
            self.assertEqual(result, '')

    def test_savesettings(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.configSet.return_value = None
            with self.assertRaises(cherrypy.HTTPRedirect):
                self.webui.savesettings('{"opt": "value"}', 'token')

    def test_savesettingsraw(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.configSet.return_value = None
            result = self.webui.savesettingsraw('{"opt": "value"}', 'token')
            self.assertEqual(result, b'["SUCCESS", ""]')

    def test_reset_settings(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.configClear.return_value = None
            result = self.webui.reset_settings()
            self.assertTrue(result)

    def test_resultsetfp(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultsUpdateFP.return_value = True
            result = self.webui.resultsetfp('id', '["resultid"]', '1')
            self.assertEqual(result, b'["SUCCESS", ""]')

    def test_eventtypes(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.eventTypes.return_value = [
                ['type', 'description']]
            result = self.webui.eventtypes()
            self.assertIsInstance(result, list)

    def test_modules(self):
        result = self.webui.modules()
        self.assertIsInstance(result, list)

    def test_correlationrules(self):
        result = self.webui.correlationrules()
        self.assertIsInstance(result, list)

    def test_ping(self):
        result = self.webui.ping()
        self.assertIsInstance(result, list)

    def test_query(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.dbh.execute.return_value.fetchall.return_value = [
                ['result']]
            result = self.webui.query('SELECT 1')
            self.assertIsInstance(result, list)

    def test_startscan(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'status']
            with patch('sfwebui.mp.Process') as mock_process:
                mock_process.return_value.start.return_value = None
                with self.assertRaises(cherrypy.HTTPRedirect):
                    self.webui.startscan(
                        'scanname', 'scantarget', 'modulelist', 'typelist', 'usecase')

    def test_stopscan(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'status']
            result = self.webui.stopscan('id')
            self.assertEqual(result, '')

    def test_vacuum(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.vacuumDB.return_value = True
            result = self.webui.vacuum()
            self.assertEqual(result, b'["SUCCESS", ""]')

    def test_scanlog(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanLogs.return_value = [
                [1627846261, 'component', 'type', 'event', 'event_id']
            ]
            result = self.webui.scanlog('id')
            self.assertIsInstance(result, list)

    def test_scanerrors(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanErrors.return_value = [
                [1627846261, 'component', 'error']
            ]
            result = self.webui.scanerrors('id')
            self.assertIsInstance(result, list)

    def test_scanlist(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceList.return_value = [
                ['id', 'name', 'target', 1627846261,
                    1627846261, 1627846261, 'status', 'type']
            ]
            result = self.webui.scanlist()
            self.assertIsInstance(result, list)

    def test_scanstatus(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'status']
            result = self.webui.scanstatus('id')
            self.assertIsInstance(result, list)

    def test_scansummary(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultSummary.return_value = [
                ['type', 'module', 1627846261, 'data', 'source']
            ]
            result = self.webui.scansummary('id', 'by')
            self.assertIsInstance(result, list)

    def test_scaneventresults(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                    '', '', '', '', '', '', '', '', '']
            ]
            result = self.webui.scaneventresults('id')
            self.assertIsInstance(result, list)

    def test_scaneventresultsunique(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultEventUnique.return_value = [
                ['data', 'type', 'source']
            ]
            result = self.webui.scaneventresultsunique('id', 'type')
            self.assertIsInstance(result, list)

    def test_search(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.search.return_value = [
                [1627846261, 'data', 'source', 'type', '',
                    '', '', '', '', '', 'ROOT', '', '']
            ]
            result = self.webui.search('id', 'eventType', 'value')
            self.assertIsInstance(result, list)

    def test_scanhistory(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultHistory.return_value = [
                ['data', 'type', 'source']
            ]
            result = self.webui.scanhistory('id')
            self.assertIsInstance(result, list)

    def test_scanelementtypediscovery(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                    '', '', '', '', '', '', '', '', '']
            ]
            result = self.webui.scanelementtypediscovery('id', 'type')
            self.assertIsInstance(result, dict)

    def test_active_maintenance_status(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'active_maintenance_status'
            result = self.webui.active_maintenance_status()
            self.assertEqual(result, 'active_maintenance_status')

    def test_footer(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'footer'
            result = self.webui.footer()
            self.assertEqual(result, 'footer')
