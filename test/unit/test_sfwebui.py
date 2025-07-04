import cheroot.test.webtest
cheroot.test.webtest.getchar = lambda: 'I'

import unittest
from unittest.mock import patch, MagicMock
import cherrypy
from sfwebui import SpiderFootWebUi
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion
from cherrypy.test import helper


class TestSpiderFootWebUi(helper.CPWebCase, SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.web_config = self.web_default_options
        self.config = self.default_options.copy()
        
        # Mock the database and logging initialization to avoid real DB operations
        with patch('sfwebui.SpiderFootDb') as mock_db, \
             patch('sfwebui.SpiderFoot') as mock_sf, \
             patch('sfwebui.logListenerSetup'), \
             patch('sfwebui.logWorkerSetup'):
            
            # Configure mocks
            mock_sf.return_value.configUnserialize.return_value = self.config
            mock_db.return_value.configGet.return_value = {}
            
            self.webui = SpiderFootWebUi(self.web_config, self.config)
        
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

        # Always return a valid scan instance for any scanId unless overridden in a test
        self.mock_db = mock_db  # Save the mock for use outside the with block
        self.mock_db.return_value.scanInstanceGet.return_value = ['scan_name', 'target', '', 0, 0, 'status']

    def test_error_page(self):
        with patch('cherrypy.response') as mock_response:
            self.webui.error_page()
            self.assertEqual(mock_response.status, 500)
            self.assertEqual(mock_response.body, b"<html><body>Error</body></html>")

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
            mock_response.headers = {}
            result = self.webui.jsonify_error('404 Not Found', 'Not Found')
            self.assertEqual(mock_response.headers['Content-Type'], 'application/json')
            self.assertEqual(mock_response.status, '404 Not Found')
            self.assertEqual(result, {'error': {'http_status': '404 Not Found', 'message': 'Not Found'}})

    def test_error(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'Error'
            self.webui = SpiderFootWebUi(self.web_config, self.config)
            result = self.webui.error('Error')
            self.assertEqual(result, 'Error')

    def test_cleanUserInput(self):
        result = self.webui.cleanUserInput(['<script>alert("xss")</script>'])
        self.assertEqual(result, ['&lt;script&gt;alert("xss")&lt;/script&gt;'])

    def test_searchBase(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock data with timestamp
            mock_db.return_value.search.return_value = [
                [1627772461, 'data', 'source', 'type', 'ROOT',
                '', '', '', '', '', '', '', '', '', '']
            ]
            result = self.webui.searchBase('id', 'eventType', 'value')
            self.assertEqual(len(result), 1)
            # Check that the timestamp was converted to a string format
            # The timestamp 1627772461 corresponds to 2021-08-01 (UTC)
            # but may vary by timezone, so check for a reasonable date format
            timestamp_str = result[0][0]
            self.assertIsInstance(timestamp_str, str)
            # Check that it contains date-like components
            self.assertTrue(any(year in timestamp_str for year in ['2021']), 
                          f"Expected year 2021 in timestamp string: {timestamp_str}")
            # Verify it has some time format (contains colons for time)
            self.assertTrue(':' in timestamp_str, 
                          f"Expected time format with colons in: {timestamp_str}")

    def test_buildExcel(self):
        with patch('sfwebui.openpyxl.Workbook') as mock_workbook, \
             patch('sfwebui.BytesIO') as mock_bytesio:
            
            # Create mock objects
            mock_worksheet = MagicMock()
            mock_workbook.return_value.active = MagicMock()
            mock_workbook.return_value.create_sheet.return_value = mock_worksheet
            mock_workbook.return_value.__getitem__.side_effect = KeyError  # Always trigger sheet creation
            mock_workbook.return_value.save = MagicMock()
            mock_workbook.return_value._sheets = []
            
            # Mock BytesIO to return bytes when read()
            mock_bytesio_instance = MagicMock()
            mock_bytesio.return_value.__enter__.return_value = mock_bytesio_instance
            mock_bytesio_instance.read.return_value = b'test_excel_data'
            
            # Test with proper data structure
            result = self.webui.buildExcel([['SHEET1', 'data1', 'data2']], ['Sheet', 'Column1', 'Column2'], 0)
            self.assertIsInstance(result, bytes)
            self.assertEqual(result, b'test_excel_data')

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
            mock_db.return_value.scanCorrelations.return_value = [
                ['rule_name', 'correlation', 'risk', 'description']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scancorrelationsexport('id')
                self.assertEqual(result, 'csv_data')

    def test_scancorrelations(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock scanCorrelationList to return correlation data with required 8 fields
            mock_db.return_value.scanCorrelationList.return_value = [
                ['corr_id_1', 'Correlation Title 1', 'rule_name_1', 'HIGH', 'rule_id_1', 'Rule description', 'rule_logic', 5, 'created_time'],
                ['corr_id_2', 'Correlation Title 2', 'rule_name_2', 'MEDIUM', 'rule_id_2', 'Another rule description', 'rule_logic', 3, 'created_time']
            ]
            result = self.webui.scancorrelations('test_scan_id')
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 2)
            # Verify the structure of returned data
            self.assertEqual(result[0][0], 'corr_id_1')  # correlation_id
            self.assertEqual(result[0][1], 'Correlation Title 1')  # correlation title
            self.assertEqual(result[0][3], 'HIGH')  # rule risk

    def test_scaneventresultexport(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock data with all required 15 elements (indices 0-14)
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                '', '', '', '', '', '', '', '', '', '']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scaneventresultexport('id', 'type')
                # Method returns bytes from encode('utf-8')
                self.assertEqual(result, b'csv_data')

    def test_scaneventresultexportmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = ['scan_name']
            # Mock data with all required 15 elements (indices 0-14)
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                '', '', '', '', '', '', '', 'scan_id', '', '']
            ]
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scaneventresultexportmulti('id')
                # Method returns bytes from encode('utf-8')
                self.assertEqual(result, b'csv_data')

    def test_scansearchresultexport(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock searchBase to return properly formatted data with all required elements
            self.webui.searchBase = MagicMock(return_value=[
                ['2021-08-01 00:31:01', 'data', 'source', 'type', '',
                '', '', '', '', '', 'ROOT', '', '', '', '']
            ])
            with patch('sfwebui.StringIO') as mock_stringio:
                mock_stringio.return_value.getvalue.return_value = 'csv_data'
                result = self.webui.scansearchresultexport('id')
                # Method returns bytes from encode('utf-8')
                self.assertEqual(result, b'csv_data')

    def test_scanelementtypediscovery(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock data with all required elements
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                '', '', '', '', '', '', '', '', '', '']
            ]            # Mock scanElementSourcesAll to return data structure with ROOT and other keys
            mock_db.return_value.scanElementSourcesAll.return_value = [
                {'ROOT': {'children': [], 'data': 'root_data'}, 'OTHER': {'children': [], 'data': 'other_data'}},
                {'ROOT': {'children': [], 'data': 'root_data'}, 'OTHER': {'children': [], 'data': 'other_data'}}
            ]
            with patch('sfwebui.SpiderFootHelpers.dataParentChildToTree') as mock_tree:
                mock_tree.return_value = {'OTHER': {'children': []}}
                result = self.webui.scanelementtypediscovery('id', 'type')
                self.assertIsInstance(result, dict)
                self.assertIn('tree', result)
                self.assertIn('data', result)
    def test_scanexportjsonmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = ['scan_name', 'target']
            # Mock data with all required 14 elements
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                 '', '', '', '', '', '', '', '', '']
            ]
            result = self.webui.scanexportjsonmulti('id')
            self.assertIsInstance(result, bytes)

    def test_scanviz(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock data with all required elements
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                 '', '', '', '', '', '', '', '', '']
            ]
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'root']
            with patch('sfwebui.SpiderFootHelpers.buildGraphJson') as mock_graph:
                mock_graph.return_value = 'graph_json'
                result = self.webui.scanviz('id')
                self.assertEqual(result, 'graph_json')

    def test_scanvizmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock data with all required elements
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                 '', '', '', '', '', '', '', '', '']
            ]
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'root']
            with patch('sfwebui.SpiderFootHelpers.buildGraphGexf') as mock_graph:
                mock_graph.return_value = 'gexf_data'
                result = self.webui.scanvizmulti('id')
                self.assertEqual(result, 'gexf_data')

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
            mock_db.return_value.scanInstanceGet.side_effect = [
                ['scan_name', 'example.com'],  # First call for info
                None,  # Second call while waiting for scan to initialize
                ['new_scan']  # Third call when scan is initialized
            ]
            mock_db.return_value.scanConfigGet.return_value = {
                '_modulesenabled': 'module'}
            with patch('sfwebui.mp.Process') as mock_process, \
                 patch('sfwebui.time.sleep'), \
                 patch('sfwebui.SpiderFootHelpers.genScanInstanceId', return_value='new_scan_id'), \
                 patch('sfwebui.SpiderFootHelpers.targetTypeFromString', return_value='INTERNET_NAME'):
                mock_process.return_value.start.return_value = None
                with self.assertRaises(cherrypy.HTTPRedirect):
                    self.webui.rerunscan('id')

    def test_rerunscanmulti(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.side_effect = [
                ['scan_name', 'example.com'],  # First call
                ['new_scan']  # When checking if scan initialized
            ]
            mock_db.return_value.scanConfigGet.return_value = {
                '_modulesenabled': 'module'}
            with patch('sfwebui.mp.Process') as mock_process, \
                 patch('sfwebui.time.sleep'), \
                 patch('sfwebui.SpiderFootHelpers.genScanInstanceId', return_value='new_scan_id'), \
                 patch('sfwebui.SpiderFootHelpers.targetTypeFromString', return_value='INTERNET_NAME'), \
                 patch('sfwebui.Template') as mock_template:
                mock_process.return_value.start.return_value = None
                mock_template.return_value.render.return_value = 'rerunscanmulti'
                result = self.webui.rerunscanmulti('id')
                self.assertEqual(result, 'rerunscanmulti')

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
                'scan_name', 'example.com']
            mock_db.return_value.scanConfigGet.return_value = {
                '_modulesenabled': 'module'}
            mock_db.return_value.eventTypes.return_value = ['type1', 'type2']  # Patch eventTypes
            with patch('sfwebui.Template') as mock_template, \
                 patch('sfwebui.SpiderFootHelpers.targetTypeFromString', return_value='INTERNET_NAME'):
                mock_template.return_value.render.return_value = 'clonescan'
                # Re-instantiate webui inside patch context to ensure patching is effective
                self.webui = SpiderFootWebUi(self.web_config, self.config)
                result = self.webui.clonescan('id')
                self.assertEqual(result, 'clonescan')

    def test_index(self):
        with patch('sfwebui.Template') as mock_template:
            mock_template.return_value.render.return_value = 'index'
            result = self.webui.index()
            self.assertEqual(result, 'index')

    def test_scaninfo(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'status']
            with patch('sfwebui.Template') as mock_template:
                mock_template.return_value.render.return_value = 'scaninfo'
                # Patch any other DB methods if needed (e.g., scanConfigGet, eventTypes)
                self.webui = SpiderFootWebUi(self.web_config, self.config)
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
                'scan_name', 'target', '', 0, 0, 'FINISHED']
            result = self.webui.scandelete('id')
            self.assertEqual(result, '')

    def test_savesettings(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Set up the token properly
            self.webui.token = 'test_token'
            mock_db.return_value.configSet.return_value = None
            with patch('sfwebui.SpiderFoot') as mock_sf:
                mock_sf.return_value.configUnserialize.return_value = self.config
                mock_sf.return_value.configSerialize.return_value = {}
                with self.assertRaises(cherrypy.HTTPRedirect):
                    self.webui.savesettings('{"opt": "value"}', 'test_token')

    def test_savesettingsraw(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Set up the token properly
            self.webui.token = 'test_token'
            mock_db.return_value.configSet.return_value = None
            with patch('sfwebui.SpiderFoot') as mock_sf:
                mock_sf.return_value.configUnserialize.return_value = self.config
                mock_sf.return_value.configSerialize.return_value = {}
                result = self.webui.savesettingsraw('{"opt": "value"}', 'test_token')
                self.assertEqual(result, b'["SUCCESS", ""]')

    def test_reset_settings(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.configClear.return_value = None
            result = self.webui.reset_settings()
            self.assertTrue(result)

    def test_resultsetfp(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock scan to be in FINISHED state
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'FINISHED']
            mock_db.return_value.scanElementSourcesDirect.return_value = []
            mock_db.return_value.scanElementChildrenAll.return_value = []
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
        # Ensure webui has the expected config structure
        self.webui.config = self.webui.config or {}
        self.webui.config['__correlationrules__'] = [
            {'id': 'test_rule', 'name': 'Test Rule', 'risk': 'HIGH', 'description': 'Test rule description'}
        ]
        result = self.webui.correlationrules()
        self.assertIsInstance(result, list)

    def test_ping(self):
        result = self.webui.ping()
        self.assertIsInstance(result, list)

    def test_query(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.dbh.execute.return_value.fetchall.return_value = [
                ['result']]
            mock_db.return_value.dbh.description = [['column1']]
            result = self.webui.query('SELECT 1')
            self.assertIsInstance(result, list)

    def test_startscan(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.side_effect = [
                None,  # First call when waiting
                ['scan_name', 'target', '', 0, 0, 'status']  # Second call when initialized
            ]
            with patch('sfwebui.mp.Process') as mock_process, \
                 patch('sfwebui.time.sleep'), \
                 patch('sfwebui.SpiderFootHelpers.genScanInstanceId', return_value='new_scan_id'), \
                 patch('sfwebui.SpiderFootHelpers.targetTypeFromString', return_value='INTERNET_NAME'):
                mock_process.return_value.start.return_value = None
                with self.assertRaises(cherrypy.HTTPRedirect):
                    self.webui.startscan(
                        'scanname', 'example.com', 'modulelist', 'typelist', 'usecase')

    def test_stopscan(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'RUNNING']
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
                [1627846261000, 'component', 'type', 'event', 'event_id']
            ]
            result = self.webui.scanlog('id')
            self.assertIsInstance(result, list)

    def test_scanerrors(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanErrors.return_value = [
                [1627846261000, 'component', 'error']
            ]
            result = self.webui.scanerrors('id')
            self.assertIsInstance(result, list)

    def test_scanlist(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceList.return_value = [
                ['id', 'name', 'target', 1627846261,
                    1627846261, 1627846261, 'status', 'type']
            ]
            mock_db.return_value.scanCorrelationSummary.return_value = [
                ['HIGH', 1], ['MEDIUM', 2]
            ]
            result = self.webui.scanlist()
            self.assertIsInstance(result, list)

    def test_scanstatus(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', 1627846261, 1627846261, 1627846261, 'status']
            mock_db.return_value.scanCorrelationSummary.return_value = [
                ['HIGH', 1], ['MEDIUM', 2]
            ]
            result = self.webui.scanstatus('id')
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 7)

    def test_scansummary(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.scanResultSummary.return_value = [
                ['type', 'module', 1627846261, 'data', 'source']
            ]
            mock_db.return_value.scanInstanceGet.return_value = [
                'scan_name', 'target', '', 0, 0, 'status']
            result = self.webui.scansummary('id', 'by')
            self.assertIsInstance(result, list)

    def test_scaneventresults(self):
        with patch('sfwebui.SpiderFootDb') as mock_db:
            # Mock data with all required 15 elements (indices 0-14)
            mock_db.return_value.scanResultEvent.return_value = [
                [1627846261, 'data', 'source', 'type', 'ROOT',
                 '', '', '', '', '', '', '', '', '', '']
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
            # Mock data with all required 15 elements
            mock_db.return_value.search.return_value = [
                [1627842461, 'data', 'source', 'type', 'ROOT',
                 '', '', '', '', '', '', '', '', '', '']
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

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

    def test_workspacescanresults_limit_string_conversion(self):
        """Test that workspacescanresults properly converts string limit to int."""
        with patch('sfwebui.SpiderFootWorkspace') as mock_workspace, \
             patch('sfwebui.SpiderFootDb') as mock_db:
            
            # Mock workspace and database
            mock_workspace_instance = MagicMock()
            mock_workspace_instance.scans = [{'scan_id': 'test_scan_1'}]
            mock_workspace.return_value = mock_workspace_instance
            
            mock_db_instance = MagicMock()
            mock_db_instance.scanResultSummary.return_value = {}
            mock_db_instance.scanResultEvent.return_value = [
                ('2025-06-20 12:00:00', 'TEST_EVENT', 'test_data', 'test_module', 'test_source', '', '', '', False)
            ]
            mock_db.return_value = mock_db_instance
            
            # Test with string limit (simulating HTTP GET parameter)
            result = self.webui.workspacescanresults('test_workspace', limit='50')
            
            # Verify it succeeds and doesn't raise the slice error
            self.assertTrue(result['success'])
            self.assertEqual(result['workspace_id'], 'test_workspace')
            self.assertIsInstance(result['results'], list)
            
            # Test with invalid string limit
            result = self.webui.workspacescanresults('test_workspace', limit='invalid')
            self.assertTrue(result['success'])  # Should fall back to default
            
            # Test with negative limit
            result = self.webui.workspacescanresults('test_workspace', limit='-5')
            self.assertTrue(result['success'])  # Should fall back to default

    def test_opts_save_list_index_out_of_range(self):
        """Test that saving options with malformed input triggers a user-friendly error message and does not raise."""
        with patch('sfwebui.SpiderFootDb') as mock_db:
            mock_db.return_value.configSet.side_effect = IndexError('list index out of range')
            self.webui.token = 'test_token'
            with patch('sfwebui.SpiderFoot') as mock_sf:
                mock_sf.return_value.configUnserialize.return_value = self.config
                mock_sf.return_value.configSerialize.return_value = {}
                # The method should return an error message, not raise
                result = self.webui.savesettings('{"opt": "value"}', 'test_token')
                self.assertIn('Processing one or more of your inputs failed', result)
                self.assertIn('list index out of range', result)
