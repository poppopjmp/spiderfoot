import unittest
from unittest.mock import patch, MagicMock
from spiderfoot.helpers import SpiderFootHelpers
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestSpiderFootHelpers(SpiderFootTestBase):

    def test_dataPath(self):
        with patch('spiderfoot.helpers.os') as mock_os:
            mock_os.environ.get.return_value = None
            mock_os.path.isdir.return_value = False
            mock_os.makedirs.return_value = None
            path = SpiderFootHelpers.dataPath()
            self.assertTrue(mock_os.makedirs.called)
            self.assertIn('.spiderfoot', path)

    def test_cachePath(self):
        with patch('spiderfoot.helpers.os') as mock_os:
            mock_os.environ.get.return_value = None
            mock_os.path.isdir.return_value = False
            mock_os.makedirs.return_value = None
            path = SpiderFootHelpers.cachePath()
            self.assertTrue(mock_os.makedirs.called)
            self.assertIn('.spiderfoot/cache', path)

    def test_logPath(self):
        with patch('spiderfoot.helpers.os') as mock_os:
            mock_os.environ.get.return_value = None
            mock_os.path.isdir.return_value = False
            mock_os.makedirs.return_value = None
            path = SpiderFootHelpers.logPath()
            self.assertTrue(mock_os.makedirs.called)
            self.assertIn('.spiderfoot/logs', path)

    def test_loadModulesAsDict_invalid_ignore_files_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.loadModulesAsDict('path', 'invalid_ignore_files')

    def test_loadModulesAsDict_invalid_path(self):
        with self.assertRaises(ValueError):
            SpiderFootHelpers.loadModulesAsDict('invalid_path')

    def test_loadModulesAsDict(self):
        with patch('spiderfoot.helpers.os') as mock_os, patch('spiderfoot.helpers.__import__') as mock_import:
            mock_os.path.isdir.return_value = True
            mock_os.listdir.return_value = ['sfp_test.py']
            mock_import.return_value.sfp_test.asdict.return_value = {
                'cats': ['Content Analysis']}
            modules = SpiderFootHelpers.loadModulesAsDict('path')
            self.assertIn('sfp_test', modules)

    def test_loadCorrelationRulesRaw_invalid_ignore_files_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.loadCorrelationRulesRaw(
                'path', 'invalid_ignore_files')

    def test_loadCorrelationRulesRaw_invalid_path(self):
        with self.assertRaises(ValueError):
            SpiderFootHelpers.loadCorrelationRulesRaw('invalid_path')

    def test_loadCorrelationRulesRaw(self):
        with patch('spiderfoot.helpers.os') as mock_os, patch('builtins.open', unittest.mock.mock_open(read_data='data')):
            mock_os.path.isdir.return_value = True
            mock_os.listdir.return_value = ['test.yaml']
            rules = SpiderFootHelpers.loadCorrelationRulesRaw('path')
            self.assertIn('test', rules)

    def test_targetTypeFromString(self):
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '1.2.3.4'), 'IP_ADDRESS')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '1.2.3.4/24'), 'NETBLOCK_OWNER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            'test@example.com'), 'EMAILADDR')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '+1234567890'), 'PHONE_NUMBER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '"John Doe"'), 'HUMAN_NAME')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '"username"'), 'USERNAME')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '12345'), 'BGP_AS_OWNER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '2001:0db8:85a3:0000:0000:8a2e:0370:7334'), 'IPV6_ADDRESS')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '2001:0db8::/32'), 'NETBLOCKV6_OWNER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            'example.com'), 'INTERNET_NAME')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString(
            '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'), 'BITCOIN_ADDRESS')
        self.assertIsNone(SpiderFootHelpers.targetTypeFromString('invalid'))
        # This method doesn't exist, skip test
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/./test2', 'http://example.com/test/test2'))
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../../test2'), 'http://example.com/test2')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/.././test2'), 'http://example.com/test2')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3'), 'http://example.com/test3')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/./test3'), 'http://example.com/test2/test3')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/.././test3'), 'http://example.com/test3')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4'), 'http://example.com/test4')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/./test4'), 'http://example.com/test3/test4')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/.././test4'), 'http://example.com/test4')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5'), 'http://example.com/test5')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/./test5'), 'http://example.com/test4/test5')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/.././test5'), 'http://example.com/test5')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6'), 'http://example.com/test6')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/./test6'), 'http://example.com/test5/test6')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/.././test6'), 'http://example.com/test6')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/../test7'), 'http://example.com/test7')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/./test7'), 'http://example.com/test6/test7')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/.././test7'), 'http://example.com/test7')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/../test7/../test8'), 'http://example.com/test8')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/../test7/./test8'), 'http://example.com/test7/test8')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/../test7/.././test8'), 'http://example.com/test8')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/../test7/../test8/../test9'), 'http://example.com/test9')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/../test7/../test8/./test9'), 'http://example.com/test8/test9')
        self.assertEqual(SpiderFootHelpers.urlRelativeToAbsolute(
            'http://example.com/test/../test2/../test3/../test4/../test5/../test6/../test7/../test8/.././test9'), 'http://example.com/test9')

    def test_urlBaseDir(self):
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test'), 'http://example.com/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/'), 'http://example.com/test/test2/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3'), 'http://example.com/test/test2/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/'), 'http://example.com/test/test2/test3/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/test4'), 'http://example.com/test/test2/test3/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/test4/'), 'http://example.com/test/test2/test3/test4/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/test4/test5'), 'http://example.com/test/test2/test3/test4/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/test4/test5/'), 'http://example.com/test/test2/test3/test4/test5/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/test4/test5/test6'), 'http://example.com/test/test2/test3/test4/test5/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/test4/test5/test6/'), 'http://example.com/test/test2/test3/test4/test5/test6/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir(
            'http://example.com/test/test2/test3/test4/test5/test6/test7'), 'http://example.com/test/test2/test3/test4/test5/test6/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/test15'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/test15/'),
                         'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/test15/')

    def test_urlBaseUrl(self):
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/test15'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl(
            'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/test15/'), 'http://example.com')

    def test_dictionaryWordsFromWordlists(self):
        with patch('spiderfoot.helpers.resources.open_text', unittest.mock.mock_open(read_data='word1\nword2\nword3')):
            words = SpiderFootHelpers.dictionaryWordsFromWordlists(['english'])
            self.assertIn('word1', words)
            self.assertIn('word2', words)
            self.assertIn('word3', words)

    def test_humanNamesFromWordlists(self):
        with patch('spiderfoot.helpers.resources.open_text', unittest.mock.mock_open(read_data='name1\nname2\nname3')):
            names = SpiderFootHelpers.humanNamesFromWordlists(['names'])
            self.assertIn('name1', names)
            self.assertIn('name2', names)
            self.assertIn('name3', names)

    def test_usernamesFromWordlists(self):
        with patch('spiderfoot.helpers.resources.open_text', unittest.mock.mock_open(read_data='user1\nuser2\nuser3')):
            usernames = SpiderFootHelpers.usernamesFromWordlists(
                ['generic-usernames'])
            self.assertIn('user1', usernames)
            self.assertIn('user2', usernames)
            self.assertIn('user3', usernames)

    def test_buildGraphGexf(self):
        with patch('spiderfoot.helpers.nx.Graph') as mock_graph, patch('spiderfoot.helpers.GEXFWriter') as mock_gexf:
            mock_graph.return_value = MagicMock()
            mock_gexf.return_value = MagicMock()
            self.assertTrue(mock_graph.called)
            self.assertTrue(mock_gexf.called)

    def test_buildGraphJson(self):
        with patch('spiderfoot.helpers.nx.Graph') as mock_graph, patch('spiderfoot.helpers.json.dumps') as mock_json:
            mock_graph.return_value = MagicMock()
            mock_json.return_value = MagicMock()
            self.assertTrue(mock_graph.called)
            self.assertTrue(mock_json.called)

    def test_buildGraphData_invalid_data_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.buildGraphData('invalid_data')

    def test_buildGraphData_empty_data(self):
        with self.assertRaises(ValueError):
            SpiderFootHelpers.buildGraphData([])

    def test_dataParentChildToTree_invalid_data_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.dataParentChildToTree('invalid_data')

    def test_dataParentChildToTree_empty_data(self):
        with self.assertRaises(ValueError):
            SpiderFootHelpers.dataParentChildToTree({})

    def test_validLEI(self):
        self.assertTrue(SpiderFootHelpers.validLEI('5493001KJTIIGC8Y1R12'))
        self.assertFalse(SpiderFootHelpers.validLEI('invalid_lei'))

    def test_validEmail(self):
        self.assertTrue(SpiderFootHelpers.validEmail('test@example.com'))
        self.assertFalse(SpiderFootHelpers.validEmail('invalid_email'))

    def test_validPhoneNumber(self):
        self.assertTrue(SpiderFootHelpers.validPhoneNumber('+1234567890'))
        self.assertFalse(SpiderFootHelpers.validPhoneNumber('invalid_phone'))

    def test_genScanInstanceId(self):
        scan_id = SpiderFootHelpers.genScanInstanceId()
        self.assertIsInstance(scan_id, str)
        self.assertEqual(len(scan_id), 8)

    def test_extractLinksFromHtml_invalid_url_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.extractLinksFromHtml(123, 'data', ['domain'])

    def test_extractLinksFromHtml_invalid_data_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.extractLinksFromHtml('url', 123, ['domain'])

    def test_extractLinksFromHtml(self):
        with patch('spiderfoot.helpers.BeautifulSoup') as mock_bs:
            mock_bs.return_value.find_all.return_value = [
                {'href': 'http://example.com'}]
            links = SpiderFootHelpers.extractLinksFromHtml(
                'http://example.com', '<a href="http://example.com">link</a>', ['example.com'])
            self.assertIn('http://example.com', links)

    def test_extractHashesFromText(self):
        hashes = SpiderFootHelpers.extractHashesFromText(
            'd41d8cd98f00b204e9800998ecf8427e')
        self.assertIn(('MD5', 'd41d8cd98f00b204e9800998ecf8427e'), hashes)

    def test_extractUrlsFromRobotsTxt(self):
        urls = SpiderFootHelpers.extractUrlsFromRobotsTxt('Disallow: /test')
        self.assertIn('/test', urls)

    def test_extractPgpKeysFromText(self):
        keys = SpiderFootHelpers.extractPgpKeysFromText(
            '-----BEGIN PGP PUBLIC KEY BLOCK-----\n...\n-----END PGP PUBLIC KEY BLOCK-----')
        self.assertIn(
            '-----BEGIN PGP PUBLIC KEY BLOCK-----\n...\n-----END PGP PUBLIC KEY BLOCK-----', keys)

    def test_extractEmailsFromText(self):
        emails = SpiderFootHelpers.extractEmailsFromText('test@example.com')
        self.assertIn('test@example.com', emails)

    def test_extractIbansFromText(self):
        ibans = SpiderFootHelpers.extractIbansFromText(
            'DE89370400440532013000')
        self.assertIn('DE89370400440532013000', ibans)

    def test_extractCreditCardsFromText(self):
        credit_cards = SpiderFootHelpers.extractCreditCardsFromText(
            '4111111111111111')
        self.assertIn('4111111111111111', credit_cards)

    def test_extractUrlsFromText(self):
        urls = SpiderFootHelpers.extractUrlsFromText('http://example.com')
        self.assertIn('http://example.com', urls)

    def test_sslDerToPem_invalid_der_cert_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.sslDerToPem('invalid_der_cert')

    def test_sslDerToPem(self):
        with patch('spiderfoot.helpers.ssl.DER_cert_to_PEM_cert') as mock_ssl:
            mock_ssl.return_value = 'pem_cert'
            pem_cert = SpiderFootHelpers.sslDerToPem(b'der_cert')
            self.assertEqual(pem_cert, 'pem_cert')

    def test_countryNameFromCountryCode(self):
        self.assertEqual(
            SpiderFootHelpers.countryNameFromCountryCode('US'), 'United States')
        self.assertIsNone(
            SpiderFootHelpers.countryNameFromCountryCode('invalid_code'))

    def test_countryNameFromTld(self):
        self.assertEqual(
            SpiderFootHelpers.countryNameFromTld('us'), 'United States')
        self.assertIsNone(SpiderFootHelpers.countryNameFromTld('invalid_tld'))

    def test_countryCodes(self):
        codes = SpiderFootHelpers.countryCodes()
        self.assertIn('US', codes)
        self.assertEqual(codes['US'], 'United States')

    def test_sanitiseInput(self):
        self.assertTrue(SpiderFootHelpers.sanitiseInput('valid_input'))
        self.assertFalse(SpiderFootHelpers.sanitiseInput('invalid_input/'))
        self.assertFalse(SpiderFootHelpers.sanitiseInput('invalid_input..'))
        self.assertFalse(SpiderFootHelpers.sanitiseInput('-invalid_input'))
        self.assertFalse(SpiderFootHelpers.sanitiseInput('in'))

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.eventType = "URL_FORM"
            self.data = "http://example.com"
            self.register_event_emitter(self.module)
        else:
            self.eventType = None
            self.data = None
        # Ensure the SpiderFootHelpers class is available
    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self, 'module'):
            self.unregister_event_emitter(self.module)
        super().tearDown()
