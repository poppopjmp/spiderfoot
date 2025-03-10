import pytest
import unittest

from spiderfoot import SpiderFootPlugin, SpiderFootEvent, SpiderFootTarget
from sflib import SpiderFoot


@pytest.mark.usefixtures
class TestSpiderFootPlugin(unittest.TestCase):

    default_options = {
        '_debug': False,
        '__logging': True,
        '__outputfilter': None,
        '__blocknotif': False,
        '_fatalerrors': False,
        '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
        '_dnsserver': '',
        '_fetchtimeout': 5,
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '_genericusers': "abuse,admin,billing,compliance,devnull,dns,ftp,hostmaster,inoc,ispfeedback,ispsupport,list-request,list,maildaemon,marketing,noc,no-reply,noreply,null,peering,peering-notify,peering-request,phish,phishing,postmaster,privacy,registrar,registry,root,routing-registry,rr,sales,security,spam,support,sysadmin,tech,undisclosed-recipients,unsubscribe,usenet,uucp,webmaster,www",
        '__version__': '3.0',
        '__database': 'spiderfoot.test.db',
        '_socks1type': '',
        '_socks2addr': '',
        '_socks3port': '',
        '_socks4user': '',
        '_socks5pwd': '',
        '_torctlport': 9051,
        '_password_list': './spiderfoot/dicts/passwords.txt',
    }

    def test_init_should_initialize_attributes(self):
        """
        Test __init__(self)
        """
        plugin = SpiderFootPlugin()
        self.assertEqual(plugin.errorState, False)
        self.assertEqual(plugin.watchedEvents(), [])
        self.assertEqual(plugin.producedEvents(), [])

    def test_setup_should_initialize_attributes(self):
        """
        Test setup(self, sf, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        self.assertIsNotNone(plugin.__name__)
        self.assertIsNotNone(plugin.sf)
        self.assertIsNotNone(plugin.opts)

    def test_enrichTarget_should_return_none_by_default(self):
        """
        Test enrichTarget(self, target)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        
        result = plugin.enrichTarget(target)
        self.assertIsNone(result)

    def test_setTarget_should_set_target_attribute(self):
        """
        Test setTarget(self, target)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        
        plugin.setTarget(target)
        self.assertEqual(plugin.target, target)

    def test_setDbh_should_set_dbh_attribute(self):
        """
        Test setDbh(self, dbh)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        dbh = 'example dbh'
        plugin.setDbh(dbh)
        self.assertEqual(plugin.dbh, dbh)

    def test_setScanId_should_set_scanId_attribute(self):
        """
        Test setScanId(self, scanId)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        scanId = 'example scan id'
        plugin.setScanId(scanId)
        self.assertEqual(plugin.scanId, scanId)

    def test_getScanId_should_return_scanId_attribute(self):
        """
        Test getScanId(self)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        scanId = 'example scan id'
        plugin.setScanId(scanId)
        self.assertEqual(plugin.getScanId(), scanId)

    def test_clearListeners_should_initialize_listeners(self):
        """
        Test clearListeners(self)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        plugin.clearListeners()
        self.assertEqual(plugin._listenerModules, list())
        self.assertEqual(plugin._listener, None)

    def test_setup_should_set_listener_to_none(self):
        """
        Test setup(self, sf, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        self.assertEqual(plugin._listener, None)

    def test_registerListener_should_add_listener(self):
        """
        Test registerListener(self, listener)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        listener = SpiderFootPlugin()
        listener.setup(sf, dict())
        listener.__name__ = 'MODULE_1'
        
        plugin.registerListener(listener)
        self.assertEqual(plugin._listener, listener)

    def test_setOutputFilter_should_initialize_attributes(self):
        """
        Test setOutputFilter(self, types)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        output_filter = ['IP_ADDRESS', 'DOMAIN_NAME']
        plugin.setOutputFilter(output_filter)
        self.assertEqual(plugin.__outputFilter, output_filter)

    def test_tempStorage_should_initialize_attributes(self):
        """
        Test tempStorage(self)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        self.assertIsInstance(plugin.tempStorage(), dict)

    def test_notifyListeners_should_call_handleEvent_on_listeners(self):
        """
        Test notifyListeners(self, sfEvent)
        """
        sf = SpiderFoot(self.default_options)
        plugin = SpiderFootPlugin()
        plugin.setup(sf, dict())
        
        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        
        # Test with no listeners
        plugin._listenerModules = []
        plugin._listener = None
        plugin.notifyListeners(evt)
        
        # Test with a listener
        listener = SpiderFootPlugin()
        listener.setup(sf, dict())
        listener.__name__ = 'MODULE_1'
        
        def handleEvent(event):
            handleEvent.evt = event
        
        handleEvent.evt = None
        listener.handleEvent = handleEvent
        
        plugin._listener = listener
        plugin.notifyListeners(evt)
        self.assertEqual(handleEvent.evt, evt)
