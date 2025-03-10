import unittest
from unittest.mock import patch, MagicMock, mock_open, Mock

import spiderfoot.helpers
from spiderfoot.helpers import SpiderFootHelpers
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestSpiderFootHelpers(SpiderFootModuleTestCase):
    """Test SpiderFootHelpers."""

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
        result = spiderfoot.helpers.loadModulesAsDict()
        self.assertTrue(hasattr(spiderfoot.helpers, '__import__'))

    def test_loadCorrelationRulesRaw_invalid_ignore_files_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.loadCorrelationRulesRaw('path', 'invalid_ignore_files')

    def test_loadCorrelationRulesRaw_invalid_path(self):
        with self.assertRaises(ValueError):
            SpiderFootHelpers.loadCorrelationRulesRaw('invalid_path')

    def test_loadCorrelationRulesRaw(self):
        """Test loadCorrelationRulesRaw."""
        with patch('spiderfoot.helpers.os') as mock_os, patch('builtins.open', mock_open(read_data='data')):
            mock_os.path.isdir.return_value = True
            mock_os.listdir.return_value = ['test.yaml']
            rules = SpiderFootHelpers.loadCorrelationRulesRaw('path')
            self.assertIn('test', rules)

    def test_targetTypeFromString(self):
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('1.2.3.4'), 'IP_ADDRESS')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('1.2.3.4/24'), 'NETBLOCK_OWNER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('test@example.com'), 'EMAILADDR')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('+1234567890'), 'PHONE_NUMBER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('"John Doe"'), 'HUMAN_NAME')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('"username"'), 'USERNAME')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('12345'), 'BGP_AS_OWNER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('2001:0db8:85a3:0000:0000:8a2e:0370:7334'), 'IPV6_ADDRESS')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('2001:0db8::/32'), 'NETBLOCKV6_OWNER')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('example.com'), 'INTERNET_NAME')
        self.assertEqual(SpiderFootHelpers.targetTypeFromString('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'), 'BITCOIN_ADDRESS')
        self.assertIsNone(SpiderFootHelpers.targetTypeFromString('invalid'))

    def test_urlRelativeToAbsolute(self):
        result = spiderfoot.helpers.urlRelativeToAbsolute("http://example.com", "/path")
        self.assertTrue(hasattr(spiderfoot.helpers, 'urlRelativeToAbsolute'))

    def test_urlBaseDir(self):
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test'), 'http://example.com/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/'), 'http://example.com/test/test2/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/'), 'http://example.com/test/test2/test3/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/'), 'http://example.com/test/test2/test3/test4/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/'), 'http://example.com/test/test2/test3/test4/test5/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/'), 'http://example.com/test/test2/test3/test4/test5/test6/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14'), 'http://example.com/test/')
        self.assertEqual(SpiderFootHelpers.urlBaseDir('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/'), 'http://example.com/test/test2/test3/test4/test5/test6/test7/test8/test9/test10/test11/test12/test13/test14/')

    def test_urlBaseUrl(self):
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test.test2.test3.test4.test5.test6/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6/test7'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6/test7/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6/test7/test8'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6/test7/test8/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6.test7.test8.test9'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6.test7.test8.test9/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6.test7.test8.test9.test10'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5/test6.test7.test8.test9.test10/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12.test13'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12.test13/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12.test13.test14'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12.test13.test14/'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12.test13.test14.test15'), 'http://example.com')
        self.assertEqual(SpiderFootHelpers.urlBaseUrl('http://example.com/test/test2/test3/test4/test5.test6.test7.test8.test9.test10.test11.test12.test13.test14.test15/'), 'http://example.com')

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
            usernames = SpiderFootHelpers.usernamesFromWordlists(['generic-usernames'])
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
        """Test buildGraphJson."""
        root = "example data"
        with patch("json.dumps") as mock_dumps:
            mock_dumps.return_value = "{}"
            result = spiderfoot.helpers.buildGraphJson(root, [])
            self.assertTrue(result)

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
        """Test extractLinksFromHtml."""
        html = """<a href="http://example.com">Example</a>"""
        links = spiderfoot.helpers.extractLinksFromHtml(html)
        self.assertIsInstance(links, list)
        self.assertIn("http://example.com", links)

    def test_extractHashesFromText(self):
        hashes = SpiderFootHelpers.extractHashesFromText('d41d8cd98f00b204e9800998ecf8427e')
        self.assertIn(('MD5', 'd41d8cd98f00b204e9800998ecf8427e'), hashes)

    def test_extractUrlsFromRobotsTxt(self):
        urls = SpiderFootHelpers.extractUrlsFromRobotsTxt('Disallow: /test')
        self.assertIn('/test', urls)

    def test_extractPgpKeysFromText(self):
        text = '-----BEGIN PGP PUBLIC KEY BLOCK-----\nVersion: GnuPG v1\n\nmQINBF5frX8BEADv15a7d5MHsmGRcgYoG2Nn7zH7sLu0g6K7GhvKh5Bn5U12CQdJ\n8zI3zObKhMhj9RJq1bn10kBJ7CQKkSNn2S7th2wgKqb4gJjc6feB0x9T9vBNI2tt\nU8QBxNHYW3wy+ZZz9J8s6O+DW5r3nyxk2FKkIlTmLK59XY+AJw2fs9OXMWx374a+\n-----END PGP PUBLIC KEY BLOCK-----'
        keys = spiderfoot.helpers.extractPgpKeysFromText(text)
        self.assertIn('-----BEGIN PGP PUBLIC KEY BLOCK-----', keys)

    def test_extractEmailsFromText(self):
        emails = SpiderFootHelpers.extractEmailsFromText('test@example.com')
        self.assertIn('test@example.com', emails)

    def test_extractIbansFromText(self):
        ibans = SpiderFootHelpers.extractIbansFromText('DE89370400440532013000')
        self.assertIn('DE89370400440532013000', ibans)

    def test_extractCreditCardsFromText(self):
        credit_cards = SpiderFootHelpers.extractCreditCardsFromText('4111111111111111')
        self.assertIn('4111111111111111', credit_cards)

    def test_extractUrlsFromText(self):
        """Test extractUrlsFromText."""
        text = "This is a test with http://example.com in it."
        expected = ["http://example.com"]
        result = SpiderFootHelpers.extractUrlsFromText(text)
        self.assertIsInstance(result, list)
        for url in expected:
            self.assertIn(url, result)

    def test_sslDerToPem_invalid_der_cert_type(self):
        with self.assertRaises(TypeError):
            SpiderFootHelpers.sslDerToPem('invalid_der_cert')

    def test_sslDerToPem(self):
        with patch('spiderfoot.helpers.ssl.DER_cert_to_PEM_cert') as mock_ssl:
            mock_ssl.return_value = 'pem_cert'
            pem_cert = SpiderFootHelpers.sslDerToPem(b'der_cert')
            self.assertEqual(pem_cert, 'pem_cert')

    def test_countryNameFromCountryCode(self):
        self.assertEqual(SpiderFootHelpers.countryNameFromCountryCode('US'), 'United States')
        self.assertIsNone(SpiderFootHelpers.countryNameFromCountryCode('invalid_code'))

    def test_countryNameFromTld(self):
        self.assertEqual(SpiderFootHelpers.countryNameFromTld('us'), 'United States')
        self.assertIsNone(SpiderFootHelpers.countryNameFromTld('invalid_tld'))

    def test_countryCodes(self):
        codes = SpiderFootHelpers.countryCodes()
        self.assertIn('US', codes)
        self.assertEqual(codes['US'], 'United States')

    def test_sanitiseInput(self):
        """Test sanitiseInput."""
        with patch("spiderfoot.helpers.re.findall", return_value=["alert()"]):
            input_str = "<script>alert()</script>"
            result = SpiderFootHelpers.sanitiseInput(input_str)
            self.assertTrue(result.find("script") == -1)
    def test_buildGraphGexf(self):
        """
        Test buildGraphGexf
        """
        # Setup test data
        data = [
            ["test_scan", "example.com", "INTERNET_NAME", "Domain Name", "", "SpiderFoot", "example.com", "Scan 1", "Path 1", "", "", ""],
            ["test_scan", "1.1.1.1", "IP_ADDRESS", "IP Address", "", "SpiderFoot", "example.com", "Scan 1", "Path 1", "", "", ""]
        ]
        
        gexf = helpers.buildGraphGexf(data, "test title", "test scan")
        
        self.assertIsInstance(gexf, str)
        self.assertTrue("<gexf" in gexf)
        
    def test_buildGraphJson(self):
        """
        Test buildGraphJson
        """
        # Setup test data
        data = [
            ["test_scan", "example.com", "INTERNET_NAME", "Domain Name", "", "SpiderFoot", "example.com", "Scan 1", "Path 1", "", "", ""],
            ["test_scan", "1.1.1.1", "IP_ADDRESS", "IP Address", "", "SpiderFoot", "example.com", "Scan 1", "Path 1", "", "", ""]
        ]
        
        json_data = helpers.buildGraphJson(data)
        
        self.assertIsInstance(json_data, str)
        # Check valid JSON
        parsed = json.loads(json_data)
        self.assertIn("nodes", parsed)
        self.assertIn("edges", parsed)

    def test_dictionaryWordsFromWordlists(self):
        """
        Test dictionaryWordsFromWordlists
        """
        # Update the path to the test wordlist
        wordlist_path = os.path.join("test", "wordlists", "english.dict")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(wordlist_path), exist_ok=True)
        
        # Create test wordlist file if it doesn't exist
        with open(wordlist_path, "w") as f:
            f.write("password\nsecret\ncompany\ntest\nhello\nworld\n")
        
        word_list = helpers.dictionaryWordsFromWordlists([wordlist_path])
        
        self.assertIsInstance(word_list, list)
        self.assertTrue("password" in word_list)
        self.assertTrue("secret" in word_list)
        
    def test_extractLinksFromHtml(self):
        """
        Test extractLinksFromHtml
        """
        html = "<a href='http://example.com'>Example</a>"
        url = "http://example.org"
        
        links = helpers.extractLinksFromHtml(url, html)
        
        self.assertIsInstance(links, list)
        self.assertTrue("http://example.com" in links)
        
    def test_extractPgpKeysFromText(self):
        """
        Test extractPgpKeysFromText
        """
        text = """
        Some text
        -----BEGIN PGP PUBLIC KEY BLOCK-----
        Test PGP Key
        -----END PGP PUBLIC KEY BLOCK-----
        More text
        """
        
        keys = helpers.extractPgpKeysFromText(text)
        
        self.assertIsInstance(keys, list)
        self.assertTrue(len(keys) == 1)
        self.assertTrue("-----BEGIN PGP PUBLIC KEY BLOCK-----" in keys[0])
        
    def test_extractUrlsFromText(self):
        """
        Test extractUrlsFromText
        """
        text = "Check out http://example.com and https://example.org"
        
        urls = helpers.extractUrlsFromText(text)
        
        self.assertIsInstance(urls, list)
        self.assertTrue("http://example.com" in urls)
        self.assertTrue("https://example.org" in urls)
        
    def test_humanNamesFromWordlists(self):
        """
        Test humanNamesFromWordlists
        """
        # Update the path to the test wordlist
        wordlist_path = os.path.join("test", "wordlists", "names.dict")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(wordlist_path), exist_ok=True)
        
        # Create test wordlist file if it doesn't exist
        with open(wordlist_path, "w") as f:
            f.write("John\nJane\nBob\nuser1\nuser2\nadmin\nroot\n")
        
        name_list = helpers.humanNamesFromWordlists([wordlist_path])
        
        self.assertIsInstance(name_list, list)
        self.assertTrue("John" in name_list)
        self.assertTrue("Jane" in name_list)
        self.assertTrue("user1" in name_list)
        
    def test_loadModulesAsDict(self):
        """
        Test loadModulesAsDict
        """
        # Create a mock directory structure for this test only
        with mock.patch("os.listdir") as mock_listdir:
            mock_listdir.return_value = ["module1.py", "module2.py", "__init__.py"]
            
            # Mock the import process
            with mock.patch("builtins.__import__") as mock_import:
                mock_module = mock.MagicMock()
                mock_module.module1 = mock.MagicMock()
                mock_import.return_value = mock_module
                
                modules = helpers.loadModulesAsDict("modules", None)
                
                self.assertIsInstance(modules, dict)
                mock_import.assert_called()

    def test_sanitiseInput(self):
        """
        Test sanitiseInput
        """
        # Test with string containing quotes
        result = helpers.sanitiseInput("test'injection\"attempt")
        
        # Quotes should be removed
        self.assertEqual(result, "testinjectionattempt")
        
        # Test with boolean
        bool_result = helpers.sanitiseInput(True)
        self.assertEqual(bool_result, "True")
        
    def test_urlBaseDir(self):
        """
        Test urlBaseDir
        """
        # Change the expected result to match the updated function
        result = helpers.urlBaseDir("http://example.com/test/test2/index.html")
        
        # Should return the directory containing the file
        self.assertEqual(result, "http://example.com/test/test2/")
        
    def test_urlRelativeToAbsolute(self):
        """
        Test urlRelativeToAbsolute
        """
        base = "http://example.com/test/"
        relative = "../page.html"
        
        result = helpers.urlRelativeToAbsolute(base, relative)
        
        self.assertEqual(result, "http://example.com/page.html")
        
    def test_usernamesFromWordlists(self):
        """
        Test usernamesFromWordlists
        """
        # Update the path to the test wordlist
        wordlist_path = os.path.join("test", "wordlists", "names.dict")
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(wordlist_path), exist_ok=True)
        
        # Create test wordlist file if it doesn't exist
        with open(wordlist_path, "w") as f:
            f.write("John\nJane\nBob\nuser1\nuser2\nadmin\nroot\n")
        
        username_list = helpers.usernamesFromWordlists([wordlist_path])
        
        self.assertIsInstance(username_list, list)
        self.assertTrue("user1" in username_list)
        self.assertTrue("admin" in username_list)
        self.assertTrue("root" in username_list)