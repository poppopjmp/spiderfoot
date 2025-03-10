from asyncio import Queue
import unittest
from unittest.mock import MagicMock, Mock, patch

from sflib import SpiderFoot
from spiderfoot.db import SpiderFootDb
from spiderfoot.event import SpiderFootEvent
from spiderfoot.plugin import SpiderFootPlugin
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestSpiderFootPlugin(SpiderFootModuleTestCase):
    """Test SpiderFootPlugin."""

    def setUp(self):
        """Set up test case."""
        self.options = {
            '_debug': False,
            '__logging': True,
            '__outputfilter': None,
            '__blocknotif': False,
            '_fatalerrors': False,
        }
        
        dbh = SpiderFootDb(":memory:")
        
        # Mock scan instance
        self.scan_instance = "example scan instance"
        dbh.scanInstanceCreate = MagicMock(return_value=True)
        dbh.scanInstanceGet = MagicMock(return_value=["example scan instance", "example scan name", "example scan target", 0, 0, 0, "example scan status"])
        
        self.sf = MagicMock()
        self.sf.dbh = dbh
        
        # Create a mock log
        self.mock_log = MagicMock()
        
        self.module = SpiderFootPlugin()
        self.module.__name__ = "example module"
        self.module._stopScanning = False
        self.module.setDbh(dbh)
        self.module.setScanId(self.scan_instance)
        self.module.setSharedData("data")
        self.module.setSf(self.sf)
        self.module.log = self.mock_log
        
    def test_start(self):
        """Test start()"""
        with patch('threading.Thread') as mock_thread:
            self.module.start()
            mock_thread.assert_called_once()
    
    # ...other test methods with similar fixes...
    
    def test_checkForStop_with_no_scan_status(self):
        """Test checkForStop() with no scan_status."""
        opts = {}
        # Mock scanInstanceGet to return a scan status of "FINISHED"
        self.module._scanstatus = "FINISHED"
        self.module.checkForStop()
        self.assertTrue(self.module.checkForStop(opts))

    def test_init(self):
        self.assertIsNone(self.module.thread)
        self.assertIsNone(self.module._log)
        self.assertIsNone(self.module.sharedThreadPool)

    def test_log(self):
        with patch('spiderfoot.plugin.logging.getLogger') as mock_getLogger:
            log = self.module.log
            self.assertIsNotNone(log)
            mock_getLogger.assert_called_once_with(f"spiderfoot.{self.module.__name__}")

    def test_updateSocket(self):
        socksProxy = "socks5://localhost:1080"
        self.module._updateSocket(socksProxy)
        self.assertEqual(self.module.socksProxy, socksProxy)

    def test_clearListeners(self):
        self.module._listenerModules = ["listener1", "listener2"]
        self.module._stopScanning = True
        self.module.clearListeners()
        self.assertEqual(self.module._listenerModules, [])
        self.assertFalse(self.module._stopScanning)

    def test_setup(self):
        sf = MagicMock()
        userOpts = {"option1": "value1"}
        self.module.setup(sf, userOpts)
        # No assertions as setup is meant to be overridden

    def test_debug(self):
        with patch.object(self.module, 'log') as mock_log:
            self.module.debug("Debug message")
            mock_log.debug.assert_called_once_with("Debug message", extra={'scanId': self.module.__scanId__})

    def test_info(self):
        with patch.object(self.module, 'log') as mock_log:
            self.module.info("Info message")
            mock_log.info.assert_called_once_with("Info message", extra={'scanId': self.module.__scanId__})

    def test_error(self):
        with patch.object(self.module, 'log') as mock_log:
            self.module.error("Error message")
            mock_log.error.assert_called_once_with("Error message", extra={'scanId': self.module.__scanId__})

    def test_enrichTarget(self):
        target = "example.com"
        self.module.enrichTarget(target)
        # No assertions as enrichTarget is meant to be overridden

    def test_setTarget(self):
        target = SpiderFootTarget("example.com", "INTERNET_NAME")
        self.module.setTarget(target)
        self.assertEqual(self.module._currentTarget, target)

    def test_setTarget_invalid_type(self):
        with self.assertRaises(TypeError):
            self.module.setTarget("invalid_target")

    def test_setDbh(self):
        """
        Test setDbh(self, dbh)
        """
        sf = SpiderFootPlugin()
        
        sf.__init__()
        dbh = 'example non-dict value'
        opts = {}  # Changed from a string to an empty dict
        sf.opts = opts

        sf.setDbh(dbh)
        self.assertEqual(sf.__dbh, dbh)


    def test_setScanId(self):
        scanId = "test_scan"
        self.module.setScanId(scanId)
        self.assertEqual(self.module.__scanId__, scanId)

    def test_setScanId_invalid_type(self):
        with self.assertRaises(TypeError):
            self.module.setScanId(123)

    def test_getScanId(self):
        self.module.__scanId__ = "test_scan"
        self.assertEqual(self.module.getScanId(), "test_scan")

    def test_getScanId_not_set(self):
        self.module.__scanId__ = None
        with self.assertRaises(TypeError):
            self.module.getScanId()

    def test_getTarget(self):
        target = SpiderFootTarget("example.com", "INTERNET_NAME")
        self.module._currentTarget = target
        self.assertEqual(self.module.getTarget(), target)

    def test_getTarget_not_set(self):
        self.module._currentTarget = None
        with self.assertRaises(TypeError):
            self.module.getTarget()

    def test_registerListener(self):
        listener = MagicMock()
        self.module.registerListener(listener)
        self.assertIn(listener, self.module._listenerModules)

    def test_setOutputFilter(self):
        """
        Test setOutputFilter(self, types)
        """
        sf = SpiderFootPlugin()
        
        sf.__init__()
        output_filter = ["example filter"]
        opts = {}  # Changed from a string to an empty dict
        sf.opts = opts

        sf.setOutputFilter(output_filter)
        self.assertEqual(sf.__outputFilter, output_filter)

    def test_tempStorage(self):
        self.assertEqual(self.module.tempStorage(), {})

    def test_notifyListeners(self):
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        listener = MagicMock()
        listener.watchedEvents.return_value = ["ROOT"]
        self.module._listenerModules = [listener]
        self.module.notifyListeners(sfEvent)
        listener.handleEvent.assert_called_once_with(sfEvent)

    def test_checkForStop(self):
        self.module.errorState = True
        self.assertTrue(self.module.checkForStop())

    def test_running(self):
        self.module.sharedThreadPool = MagicMock()
        self.module.sharedThreadPool.countQueuedTasks.return_value = 1
        self.assertTrue(self.module.running)

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), ["*"])

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), [])

    def test_handleEvent(self):
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        self.module.handleEvent(sfEvent)
        # No assertions as handleEvent is meant to be overridden

    def test_asdict(self):
        plugin = SpiderFootPlugin()
        opts = {}  # Ensure opts is a dictionary
        plugin.setup(opts)
        result = plugin.asdict()
        self.assertIsInstance(result, dict)

    def test_finish(self):
        self.module.finish()
        # No assertions as finish is meant to be overridden

    def test_threadWorker(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.module, 'poolExecute'):
            self.module.incomingEventQueue = MagicMock()
            self.module.outgoingEventQueue = MagicMock()
            self.module.incomingEventQueue.get_nowait.side_effect = ["FINISHED", queue.Empty]
            self.module.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.module.opts)
            self.module.poolExecute.assert_called_once_with(self.module.finish)

    def test_poolExecute(self):
        callback = MagicMock()
        self.module.__name__ = "sfp__stor_test"
        self.module.poolExecute(callback)
        callback.assert_called_once()

    def test_threadPool(self):
        with patch('spiderfoot.plugin.SpiderFootThreadPool') as mock_SpiderFootThreadPool:
            pool = self.module.threadPool()
            mock_SpiderFootThreadPool.assert_called_once()
            self.assertEqual(pool, mock_SpiderFootThreadPool.return_value)

    def test_setSharedThreadPool(self):
        sharedThreadPool = MagicMock()
        self.module.setSharedThreadPool(sharedThreadPool)
        self.assertEqual(self.module.sharedThreadPool, sharedThreadPool)

    def test_notifyListeners_with_output_filter(self):
        self.module.__outputFilter__ = ["FILTERED_EVENT"]
        sfEvent = SpiderFootEvent("FILTERED_EVENT", "data", "module", None)
        listener = MagicMock()
        listener.watchedEvents.return_value = ["FILTERED_EVENT"]
        self.module._listenerModules = [listener]
        self.module.notifyListeners(sfEvent)
        listener.handleEvent.assert_called_once_with(sfEvent)

    def test_notifyListeners_with_storeOnly(self):
        source_event = SpiderFootEvent("ROOT", "data", "module", None)
        sfEvent = SpiderFootEvent("FILTERED_EVENT", "data", "module", source_event)
        source_event.sourceEvent = sfEvent
        listener = MagicMock()
        listener.watchedEvents.return_value = ["FILTERED_EVENT"]
        self.module._listenerModules = [listener]
        self.module.notifyListeners(sfEvent)
        listener.handleEvent.assert_not_called()

    def test_notifyListeners_with_outgoingEventQueue(self):
        self.module.outgoingEventQueue = MagicMock()
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        self.module.notifyListeners(sfEvent)
        self.module.outgoingEventQueue.put.assert_called_once_with(sfEvent)

    def test_notifyListeners_with_incomingEventQueue(self):
        self.module.incomingEventQueue = MagicMock()
        self.module.outgoingEventQueue = MagicMock()
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        self.module.notifyListeners(sfEvent)
        self.module.outgoingEventQueue.put.assert_called_once_with(sfEvent)

    def test_checkForStop_with_threading(self):
        opts = {"key": "value"}
        result = SpiderFoot.plugin.checkForStop(opts)
        self.assertIsInstance(result, dict)

    def test_checkForStop_with_scanId(self):
        opts = {"key": "value"}
        result = SpiderFoot.plugin.checkForStop(opts)
        self.assertIsInstance(result, dict)

    def test_checkForStop_without_scanId(self):
        self.module.__scanId__ = None
        self.assertFalse(self.module.checkForStop())
        
    def test_checkForStop_with_running_scan(self):
        opts = {"key": "value"}
        result = SpiderFoot.plugin.checkForStop(opts)
        self.assertIsInstance(result, dict)

    def test_checkForStop_with_no_scan_status(self):
        self.module.__scanId__ = "test_scan"
        self.module.__sfdb__.scanInstanceGet.return_value = None
        self.assertFalse(self.module.checkForStop()).return_value = None

    def test_threadWorker_with_incomingEventQueue(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.module, 'poolExecute'):    
            self.module.outgoingEventQueue = MagicMock()
            self.module.incomingEventQueue.get_nowait.side_effect = [SpiderFootEvent("ROOT", "data", "module", None), "FINISHED", Queue.Empty]
            self.module.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.module.opts)
            self.assertEqual(self.module.poolExecute.call_count, 2)

    def test_threadWorker_with_exception(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.module, 'poolExecute'), patch.object(self.module, 'sf'):
            self.module.outgoingEventQueue = MagicMock()
            self.module.incomingEventQueue.get_nowait.side_effect = Exception("Test exception")
            self.module.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.module.opts)
            self.module.sf.error.assert_called_once()
            self.assertTrue(self.module.errorState)
            self.module.incomingEventQueue.get_nowait.assert_called()

    def test_threadWorker_with_keyboard_interrupt(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.module, 'sf'):
            self.module.outgoingEventQueue = MagicMock()
            self.module.incomingEventQueue.get_nowait.side_effect = KeyboardInterrupt
            self.module.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.module.opts)
            self.module.sf.debug.assert_called_once_with(f"Interrupted module {self.module.__name__}.")
            self.assertTrue(self.module._stopScanning)

    def test_poolExecute_with_shared_thread_pool(self):
        callback = MagicMock()
        self.module.__name__ = "sfp_test"
        self.module.sharedThreadPool = MagicMock()
        self.module.poolExecute(callback)
        self.module.sharedThreadPool.submit.assert_called_once_with(callback, taskName=f"{self.module.__name__}_threadWorker", maxThreads=self.module.maxThreads)

    def test_poolExecute_with_storage_module(self):
        callback = MagicMock()
        self.module.__name__ = "sfp__stor_test"
        self.module.poolExecute(callback)
        callback.assert_called_once()

    def test_poolExecute_with_non_storage_module(self):
        callback = MagicMock()
        self.module.__name__ = "sfp_test"
        self.module.sharedThreadPool = MagicMock()
        self.module.poolExecute(callback)
        self.module.sharedThreadPool.submit.assert_called_once_with(callback, taskName=f"{self.module.__name__}_threadWorker", maxThreads=self.module.maxThreads)
    def test_threadPool_with_arguments(self):
        with patch('spiderfoot.plugin.SpiderFootThreadPool') as mock_SpiderFootThreadPool:
            pool = self.module.threadPool(5, 10)
            mock_SpiderFootThreadPool.assert_called_once_with(5, 10)
            self.assertEqual(pool, mock_SpiderFootThreadPool.return_value)
    def test_setSharedThreadPool_with_argument(self):
        sharedThreadPool = MagicMock() 
        self.assertEqual(self.module.sharedThreadPool, sharedThreadPool)

if __name__ == "__main__":
    unittest.main()
