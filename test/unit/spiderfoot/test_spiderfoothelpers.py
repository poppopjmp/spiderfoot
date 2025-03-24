import unittest
from unittest.mock import patch, MagicMock
import spiderfoot.helpers as sfh
from test.unit.utils.test_base import SpiderFootTestBase


class TestSpiderFootHelpers(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        # Setup mock objects
        self.mock_os = patch('spiderfoot.helpers.os').start()
        self.mock_sys = patch('spiderfoot.helpers.sys').start()
        
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def test_dataPath(self):
        """
        Test dataPath
        """
        self.mock_os.path.join.return_value = '/root/path/to/spiderfoot/data'
        result = sfh.dataPath()
        self.assertEqual(result, '/root/path/to/spiderfoot/data')

    def test_cachePath(self):
        """
        Test cachePath
        """
        self.mock_os.path.join.return_value = '/root/path/to/spiderfoot/cache'
        result = sfh.cachePath()
        self.assertEqual(result, '/root/path/to/spiderfoot/cache')

    def test_logPath(self):
        """
        Test logPath
        """
        self.mock_os.path.join.return_value = '/root/path/to/spiderfoot/log'
        result = sfh.logPath()
        self.assertEqual(result, '/root/path/to/spiderfoot/log')

    def test_targetTypeFromString(self):
        """
        Test targetTypeFromString(target)
        """
        result = sfh.targetTypeFromString('127.0.0.1')
        self.assertEqual(result, 'IP_ADDRESS')

        result = sfh.targetTypeFromString('::1')
        self.assertEqual(result, 'IPV6_ADDRESS')

        result = sfh.targetTypeFromString('2001:0DB8:1234:5678::')
        self.assertEqual(result, 'IPV6_ADDRESS')

        result = sfh.targetTypeFromString('example.com')
        self.assertEqual(result, 'DOMAIN_NAME')

        result = sfh.targetTypeFromString('127.0.0.1/24')
        self.assertEqual(result, 'NETBLOCK_OWNER')

        result = sfh.targetTypeFromString('::1/128')
        self.assertEqual(result, 'NETBLOCKV6_OWNER')

        result = sfh.targetTypeFromString('INVALID')
        self.assertEqual(result, 'INTERNET_NAME')

    def test_buildGraphData_empty_data(self):
        """
        Test buildGraphData(data, flt=list()) with empty data
        """
        result = sfh.buildGraphData({}, [])
        self.assertEqual(result, {'nodes': [], 'edges': []})

    def test_buildGraphData_invalid_data_type(self):
        """
        Test buildGraphData(data, flt=list()) with invalid data type
        """
        invalid_data = ['data']
        with self.assertRaises(TypeError):
            sfh.buildGraphData(invalid_data, [])

    def test_buildGraphGexf(self):
        """
        Test buildGraphGexf(root, title, data, flt=[])
        """
        flt = ["ROOT"]
        result = sfh.buildGraphGexf('test_root', 'test_title', {'nodes': [], 'edges': []}, flt)
        self.assertTrue('<gexf xmlns="http://www.gephi.org/gexf"' in result)

    def test_buildGraphJson(self):
        """
        Test buildGraphJson(root, data, flt=list())
        """
        data = {'nodes': [], 'edges': []}
        result = sfh.buildGraphJson('test_root', data, [])
        self.assertEqual(result, '{"nodes": [], "edges": []}')

    def test_extractUrlsFromText(self):
        """
        Test extractUrlsFromText(text)
        """
        urls = sfh.extractUrlsFromText('https://example.com')
        self.assertEqual(urls, ['https://example.com'])

        urls = sfh.extractUrlsFromText('not a url')
        self.assertEqual(urls, [])

    def test_validLEI(self):
        """
        Test validLEI(lei)
        """
        # Valid LEI format (fictitious)
        result = sfh.validLEI('000000LEI0000500000')
        self.assertEqual(result, True)

        # Invalid LEI format
        result = sfh.validLEI('INVALID')
        self.assertEqual(result, False)

    def test_extractEmailsFromText(self):
        """
        Test extractEmailsFromText(text)
        """
        emails = sfh.extractEmailsFromText('user@example.com')
        self.assertEqual(emails, ['user@example.com'])

        emails = sfh.extractEmailsFromText('not an email')
        self.assertEqual(emails, [])

    def test_extractIbansFromText(self):
        """
        Test extractIbansFromText(text)
        """
        ibans = sfh.extractIbansFromText('GB29NWBK60161331926819')
        self.assertEqual(ibans, ['GB29NWBK60161331926819'])

        ibans = sfh.extractIbansFromText('not an IBAN')
        self.assertEqual(ibans, [])

    def test_extractCreditCardsFromText(self):
        """
        Test extractCreditCardsFromText(text)
        """
        cards = sfh.extractCreditCardsFromText('4111111111111111')
        self.assertEqual(cards, ['4111111111111111'])

        cards = sfh.extractCreditCardsFromText('not a credit card')
        self.assertEqual(cards, [])

    def test_extractPgpKeysFromText(self):
        """
        Test extractPgpKeysFromText(text)
        """
        pgp_text = '-----BEGIN PGP PUBLIC KEY BLOCK-----\nVersion: GnuPG v2.0\n\nPUBLIC KEY\n-----END PGP PUBLIC KEY BLOCK-----'
        pgp_keys = sfh.extractPgpKeysFromText(pgp_text)
        self.assertEqual(pgp_keys, [pgp_text])

        pgp_keys = sfh.extractPgpKeysFromText('not a PGP key')
        self.assertEqual(pgp_keys, [])

    def test_validEmail(self):
        """
        Test validEmail(email)
        """
        result = sfh.validEmail('user@example.com')
        self.assertEqual(result, True)

        result = sfh.validEmail('invalid@email@example.com')
        self.assertEqual(result, False)

        result = sfh.validEmail('@example.com')
        self.assertEqual(result, False)

    def test_extractHashesFromText(self):
        """
        Test extractHashesFromText(text)
        """
        md5 = '1f3870be274f6c49b3e31a0c6728957f'  # MD5 of "apple"
        text = f"The hash is {md5}"
        hashes = sfh.extractHashesFromText(text)
        self.assertEqual(hashes, [md5])

        text = "No hashes here"
        hashes = sfh.extractHashesFromText(text)
        self.assertEqual(hashes, [])

    def test_extractLinksFromHtml(self):
        """
        Test extractLinksFromHtml(url, data, domains)
        """
        html = '<a href="https://example.com">Example</a>'

        with patch('spiderfoot.helpers.SpiderFootTarget') as mock_target:
            mock_target.return_value.matches.return_value = True
            links = sfh.extractLinksFromHtml('https://example.org', html, [])
            self.assertIsInstance(links, list)

    def test_extractLinksFromHtml_invalid_data_type(self):
        """
        Test extractLinksFromHtml(url, data, domains) with invalid data type
        """
        with self.assertRaises(TypeError):
            sfh.extractLinksFromHtml('https://example.org', 1, [])

    def test_extractLinksFromHtml_invalid_url_type(self):
        """
        Test extractLinksFromHtml(url, data, domains) with invalid url type
        """
        with self.assertRaises(TypeError):
            sfh.extractLinksFromHtml(1, '..', [])

    def test_urlBaseUrl(self):
        """
        Test urlBaseUrl(url)
        """
        result = sfh.urlBaseUrl('https://example.com/path')
        self.assertEqual(result, 'https://example.com')

    def test_urlBaseDir(self):
        """
        Test urlBaseDir(url)
        """
        result = sfh.urlBaseDir('https://example.com/path/file.txt')
        self.assertEqual(result, 'https://example.com/path')

    def test_urlRelativeToAbsolute(self):
        """
        Test urlRelativeToAbsolute(url)
        """
        result = sfh.urlRelativeToAbsolute('relative/url', 'https://example.com/path')
        self.assertEqual(result, 'https://example.com/path/relative/url')

    def test_sanitiseInput(self):
        """
        Test sanitiseInput(cmd)
        """
        result = sfh.sanitiseInput('input; rm -rf /')
        self.assertEqual(result, 'input rm -rf /')

    def test_extractUrlsFromRobotsTxt(self):
        """
        Test extractUrlsFromRobotsTxt(robotsTxtData)
        """
        data = "User-agent: *\nDisallow: /private\nAllow: /public"
        result = sfh.extractUrlsFromRobotsTxt(data)
        self.assertIsInstance(result, list)

    def test_dictionaryWordsFromWordlists(self):
        """
        Test dictionaryWordsFromWordlists()
        """
        with patch('spiderfoot.helpers.open') as mock_open:
            mock_open.return_value.__enter__.return_value.readlines.return_value = ['word1', 'word2']
            self.mock_os.path.isfile.return_value = True
            
            result = sfh.dictionaryWordsFromWordlists()
            self.assertTrue('word1' in result)
            self.assertTrue('word2' in result)

    def test_humanNamesFromWordlists(self):
        """
        Test humanNamesFromWordlists()
        """
        with patch('spiderfoot.helpers.open') as mock_open:
            mock_open.return_value.__enter__.return_value.readlines.return_value = ['name1', 'name2']
            self.mock_os.path.isfile.return_value = True
            
            result = sfh.humanNamesFromWordlists()
            self.assertTrue('name1' in result)
            self.assertTrue('name2' in result)

    def test_usernamesFromWordlists(self):
        """
        Test usernamesFromWordlists()
        """
        with patch('spiderfoot.helpers.open') as mock_open:
            mock_open.return_value.__enter__.return_value.readlines.return_value = ['username1', 'username2']
            self.mock_os.path.isfile.return_value = True
            
            result = sfh.usernamesFromWordlists()
            self.assertTrue('username1' in result)
            self.assertTrue('username2' in result)

    def test_dataParentChildToTree_empty_data(self):
        """
        Test dataParentChildToTree(data)
        """
        data = []
        result = sfh.dataParentChildToTree(data)
        self.assertEqual(result, [])

    def test_dataParentChildToTree_invalid_data_type(self):
        """
        Test dataParentChildToTree(data)
        """
        data = 'not a list'
        with self.assertRaises(TypeError):
            sfh.dataParentChildToTree(data)

    def test_sslDerToPem(self):
        """
        Test sslDerToPem(der)
        """
        with patch('spiderfoot.helpers.base64') as mock_base64:
            mock_base64.b64encode.return_value.decode.return_value = "ABCDEF"
            result = sfh.sslDerToPem(b'derdata')
            self.assertIn('BEGIN CERTIFICATE', result)

    def test_sslDerToPem_invalid_der_cert_type(self):
        """
        Test sslDerToPem(der)
        """
        with self.assertRaises(TypeError):
            sfh.sslDerToPem('der_data')

    def test_genScanInstanceId(self):
        """
        Test genScanInstanceId()
        """
        result = sfh.genScanInstanceId()
        self.assertTrue(len(result) > 0)

    def test_validPhoneNumber(self):
        """
        Test validPhoneNumber(phone)
        """
        result = sfh.validPhoneNumber('+12125550123')
        self.assertTrue(result)

    def test_loadModulesAsDict(self):
        """
        Test loadModulesAsDict(directory, ignore_files)
        """
        # Mock directory listing
        self.mock_os.listdir.return_value = ['sfp_test.py', '__pycache__', 'sfp_valid.py']
        
        # Mock module file checks
        self.mock_os.path.isfile.return_value = True
        
        # Mock module loading
        with patch('spiderfoot.helpers.importlib') as mock_importlib:
            mock_module = MagicMock()
            mock_module.__name__ = 'sfp_valid'
            mock_module.meta = {'name': 'Valid Module'}
            mock_importlib.import_module.return_value = mock_module
            
            result = sfh.loadModulesAsDict('modules', ['sfp_test.py'])
            self.assertTrue('sfp_valid' in result)

    def test_loadModulesAsDict_invalid_ignore_files_type(self):
        """
        Test loadModulesAsDict(directory, ignore_files) with invalid ignore_files type
        """
        with self.assertRaises(TypeError):
            sfh.loadModulesAsDict('modules', 'not_a_list')

    def test_loadModulesAsDict_invalid_path(self):
        """
        Test loadModulesAsDict(directory, ignore_files) with invalid path
        """
        self.mock_os.path.isdir.return_value = False
        result = sfh.loadModulesAsDict('invalid_path', [])
        self.assertEqual(result, {})

    def test_loadCorrelationRulesRaw(self):
        """
        Test loadCorrelationRulesRaw(directory, ignore_files)
        """
        # Mock directory listing
        self.mock_os.listdir.return_value = ['test_rule.yaml', 'valid_rule.yaml']
        
        # Mock rule file checks
        self.mock_os.path.isfile.return_value = True
        
        # Mock rule file reading
        with patch('spiderfoot.helpers.open') as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "id: test_rule\ndescr: Test Rule"
            
            result = sfh.loadCorrelationRulesRaw('correlations', ['test_rule.yaml'])
            self.assertEqual(len(result), 1)

    def test_loadCorrelationRulesRaw_invalid_ignore_files_type(self):
        """
        Test loadCorrelationRulesRaw(directory, ignore_files) with invalid ignore_files type
        """
        with self.assertRaises(TypeError):
            sfh.loadCorrelationRulesRaw('correlations', 'not_a_list')

    def test_loadCorrelationRulesRaw_invalid_path(self):
        """
        Test loadCorrelationRulesRaw(directory, ignore_files) with invalid path
        """
        self.mock_os.path.isdir.return_value = False
        result = sfh.loadCorrelationRulesRaw('invalid_path', [])
        self.assertEqual(result, [])

    def test_countryCodes(self):
        """
        Test countryCodes()
        """
        result = sfh.countryCodes()
        self.assertIsInstance(result, dict)

    def test_countryNameFromCountryCode(self):
        """
        Test countryNameFromCountryCode(countrycode)
        """
        result = sfh.countryNameFromCountryCode('US')
        self.assertEqual(result, 'United States')

    def test_countryNameFromTld(self):
        """
        Test countryNameFromTld(tld)
        """
        result = sfh.countryNameFromTld('.us')
        self.assertEqual(result, 'United States')

    def reset_mock_objects(self):
        patch.stopall()

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
        patch.stopall()
