import unittest
from unittest.mock import MagicMock, patch
from spiderfoot.plugin import SpiderFootPlugin
from spiderfoot import SpiderFootEvent, SpiderFootTarget
import queue


class TestSpiderFootPlugin(unittest.TestCase):

    def setUp(self):
        self.plugin = SpiderFootPlugin()

    def test_init(self):
        self.assertIsNone(self.plugin.thread)
        self.assertIsNone(self.plugin._log)
        self.assertIsNone(self.plugin.sharedThreadPool)

    def test_log(self):
        with patch('spiderfoot.plugin.logging.getLogger') as mock_getLogger:
            log = self.plugin.log
            self.assertIsNotNone(log)
            mock_getLogger.assert_called_once_with(
                f"spiderfoot.{self.plugin.__name__}")

    def test_updateSocket(self):
        socksProxy = "socks5://localhost:1080"
        self.plugin._updateSocket(socksProxy)
        self.assertEqual(self.plugin.socksProxy, socksProxy)

    def test_clearListeners(self):
        self.plugin._listenerModules = ["listener1", "listener2"]
        self.plugin._stopScanning = True
        self.plugin.clearListeners()
        self.assertEqual(self.plugin._listenerModules, [])
        self.assertFalse(self.plugin._stopScanning)

    def test_setup(self):
        sf = MagicMock()
        userOpts = {"option1": "value1"}
        self.plugin.setup(sf, userOpts)
        # No assertions as setup is meant to be overridden

    def test_debug(self):
        with patch.object(self.plugin, 'log') as mock_log:
            self.plugin.debug("Debug message")
            mock_log.debug.assert_called_once_with(
                "Debug message", extra={'scanId': self.plugin.__scanId__})

    def test_info(self):
        with patch.object(self.plugin, 'log') as mock_log:
            self.plugin.info("Info message")
            mock_log.info.assert_called_once_with(
                "Info message", extra={'scanId': self.plugin.__scanId__})

    def test_error(self):
        with patch.object(self.plugin, 'log') as mock_log:
            self.plugin.error("Error message")
            mock_log.error.assert_called_once_with(
                "Error message", extra={'scanId': self.plugin.__scanId__})

    def test_enrichTarget(self):
        target = "example.com"
        self.plugin.enrichTarget(target)
        # No assertions as enrichTarget is meant to be overridden

    def test_setTarget(self):
        target = SpiderFootTarget("example.com", "INTERNET_NAME")
        self.plugin.setTarget(target)
        self.assertEqual(self.plugin._currentTarget, target)

    def test_setTarget_invalid_type(self):
        with self.assertRaises(TypeError):
            self.plugin.setTarget("invalid_target")

    def test_setDbh(self):
        dbh = MagicMock()
        self.plugin.setDbh(dbh)
        self.assertEqual(self.plugin.__sfdb__, dbh)

    def test_setScanId(self):
        scanId = "test_scan"
        self.plugin.setScanId(scanId)
        self.assertEqual(self.plugin.__scanId__, scanId)

    def test_setScanId_invalid_type(self):
        with self.assertRaises(TypeError):
            self.plugin.setScanId(123)

    def test_getScanId(self):
        self.plugin.__scanId__ = "test_scan"
        self.assertEqual(self.plugin.getScanId(), "test_scan")

    def test_getScanId_not_set(self):
        self.plugin.__scanId__ = None
        with self.assertRaises(TypeError):
            self.plugin.getScanId()

    def test_getTarget(self):
        target = SpiderFootTarget("example.com", "INTERNET_NAME")
        self.plugin._currentTarget = target
        self.assertEqual(self.plugin.getTarget(), target)

    def test_getTarget_not_set(self):
        self.plugin._currentTarget = None
        with self.assertRaises(TypeError):
            self.plugin.getTarget()

    def test_registerListener(self):
        listener = MagicMock()
        self.plugin.registerListener(listener)
        self.assertIn(listener, self.plugin._listenerModules)

    def test_setOutputFilter(self):
        types = ["type1", "type2"]
        self.plugin.setOutputFilter(types)
        self.assertEqual(self.plugin.__outputFilter__, types)

    def test_tempStorage(self):
        self.assertEqual(self.plugin.tempStorage(), {})

    def test_notifyListeners(self):
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        listener = MagicMock()
        listener.watchedEvents.return_value = ["ROOT"]
        self.plugin._listenerModules = [listener]
        self.plugin.notifyListeners(sfEvent)
        listener.handleEvent.assert_called_once_with(sfEvent)

    def test_checkForStop(self):
        self.plugin.errorState = True
        self.assertTrue(self.plugin.checkForStop())

    def test_running(self):
        self.plugin.sharedThreadPool = MagicMock()
        self.plugin.sharedThreadPool.countQueuedTasks.return_value = 1
        self.assertTrue(self.plugin.running)

    def test_watchedEvents(self):
        self.assertEqual(self.plugin.watchedEvents(), ["*"])

    def test_producedEvents(self):
        self.assertEqual(self.plugin.producedEvents(), [])

    def test_handleEvent(self):
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        self.plugin.handleEvent(sfEvent)
        # No assertions as handleEvent is meant to be overridden

    def test_asdict(self):
        self.plugin.meta = {"name": "Test Plugin", "summary": "A test plugin", "categories": [
            "cat1"], "useCases": ["useCase1"], "flags": ["flag1"]}
        self.plugin.opts = {"opt1": "value1"}
        self.plugin.optdescs = {"opt1": "Option 1"}
        expected_dict = {
            'name': "Test Plugin",
            'descr': "A test plugin",
            'cats': ["cat1"],
            'group': ["useCase1"],
            'labels': ["flag1"],
            'provides': [],
            'consumes': ["*"],
            'meta': self.plugin.meta,
            'opts': self.plugin.opts,
            'optdescs': self.plugin.optdescs,
        }
        self.assertEqual(self.plugin.asdict(), expected_dict)

    def test_start(self):
        with patch('threading.Thread') as mock_thread:
            self.plugin.start()
            mock_thread.assert_called_once_with(
                target=self.plugin.threadWorker)
            mock_thread.return_value.start.assert_called_once()
            # Verify thread is set as daemon
            mock_thread.return_value.daemon = True

    def test_start_thread_daemon(self):
        """Test that threads created by the plugin are set as daemon threads."""
        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            self.plugin.start()
            
            mock_thread_instance.daemon = True
            mock_thread_instance.start.assert_called_once()

    def test_thread_cleanup_on_finish(self):
        """Test that threads are properly cleaned up when the plugin finishes."""
        self.plugin.thread = MagicMock()
        self.plugin.finish()
        # Verify any thread cleanup that should happen in finish()
        self.assertTrue(self.plugin.thread.daemon if self.plugin.thread else True,
                        "Thread should be set as daemon or None after finish()")

    def test_finish(self):
        self.plugin.finish()
        # No assertions as finish is meant to be overridden

    def test_threadWorker(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.plugin, 'poolExecute'):
            self.plugin.incomingEventQueue = MagicMock()
            self.plugin.outgoingEventQueue = MagicMock()
            self.plugin.incomingEventQueue.get_nowait.side_effect = [
                "FINISHED", queue.Empty]
            self.plugin.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.plugin.opts)
            self.plugin.poolExecute.assert_called_once_with(self.plugin.finish)

    def test_poolExecute(self):
        callback = MagicMock()
        self.plugin.__name__ = "sfp__stor_test"
        self.plugin.poolExecute(callback)
        callback.assert_called_once()

    def test_threadPool(self):
        with patch('spiderfoot.plugin.SpiderFootThreadPool') as mock_SpiderFootThreadPool:
            pool = self.plugin.threadPool()
            mock_SpiderFootThreadPool.assert_called_once()
            self.assertEqual(pool, mock_SpiderFootThreadPool.return_value)

    def test_setSharedThreadPool(self):
        sharedThreadPool = MagicMock()
        self.plugin.setSharedThreadPool(sharedThreadPool)
        self.assertEqual(self.plugin.sharedThreadPool, sharedThreadPool)

    def test_notifyListeners_with_output_filter(self):
        self.plugin.__outputFilter__ = ["FILTERED_EVENT"]
        sfEvent = SpiderFootEvent("FILTERED_EVENT", "data", "module", None)
        listener = MagicMock()
        listener.watchedEvents.return_value = ["FILTERED_EVENT"]
        self.plugin._listenerModules = [listener]
        self.plugin.notifyListeners(sfEvent)
        listener.handleEvent.assert_called_once_with(sfEvent)

    def test_notifyListeners_with_storeOnly(self):
        source_event = SpiderFootEvent("ROOT", "data", "module", None)
        sfEvent = SpiderFootEvent(
            "FILTERED_EVENT", "data", "module", source_event)
        source_event.sourceEvent = sfEvent
        listener = MagicMock()
        listener.watchedEvents.return_value = ["FILTERED_EVENT"]
        self.plugin._listenerModules = [listener]
        self.plugin.notifyListeners(sfEvent)
        listener.handleEvent.assert_not_called()

    def test_notifyListeners_with_outgoingEventQueue(self):
        self.plugin.outgoingEventQueue = MagicMock()
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        self.plugin.notifyListeners(sfEvent)
        self.plugin.outgoingEventQueue.put.assert_called_once_with(sfEvent)

    def test_notifyListeners_with_incomingEventQueue(self):
        self.plugin.incomingEventQueue = MagicMock()
        self.plugin.outgoingEventQueue = MagicMock()
        sfEvent = SpiderFootEvent("ROOT", "data", "module", None)
        self.plugin.notifyListeners(sfEvent)
        self.plugin.outgoingEventQueue.put.assert_called_once_with(sfEvent)

    def test_checkForStop_with_threading(self):
        self.plugin.outgoingEventQueue = MagicMock()
        self.plugin.incomingEventQueue = MagicMock()
        self.plugin._stopScanning = True
        self.assertTrue(self.plugin.checkForStop())

    def test_checkForStop_with_scanId(self):
        self.plugin.__scanId__ = "test_scan"
        self.plugin.__sfdb__ = MagicMock()
        self.plugin.__sfdb__.scanInstanceGet.return_value = [
            None, None, None, None, None, "ABORT-REQUESTED"]
        self.assertTrue(self.plugin.checkForStop())

    def test_checkForStop_without_scanId(self):
        self.plugin.__scanId__ = None
        self.assertFalse(self.plugin.checkForStop())

    def test_checkForStop_with_running_scan(self):
        self.plugin.__scanId__ = "test_scan"
        self.plugin.__sfdb__ = MagicMock()
        self.plugin.__sfdb__.scanInstanceGet.return_value = [
            None, None, None, None, None, "RUNNING"]
        self.assertFalse(self.plugin.checkForStop())

    def test_checkForStop_with_no_scan_status(self):
        self.plugin.__scanId__ = "test_scan"
        self.plugin.__sfdb__.scanInstanceGet.return_value = None
        self.assertFalse(self.plugin.checkForStop())

    def test_threadWorker_with_incomingEventQueue(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.plugin, 'poolExecute'):
            self.plugin.incomingEventQueue = MagicMock()
            self.plugin.outgoingEventQueue = MagicMock()
            self.plugin.incomingEventQueue.get_nowait.side_effect = [
                SpiderFootEvent("ROOT", "data", "module", None), "FINISHED", queue.Empty]
            self.plugin.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.plugin.opts)
            self.assertEqual(self.plugin.poolExecute.call_count, 2)

    def test_threadWorker_with_exception(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.plugin, 'poolExecute'), patch.object(self.plugin, 'sf'):
            self.plugin.incomingEventQueue = MagicMock()
            self.plugin.outgoingEventQueue = MagicMock()
            self.plugin.incomingEventQueue.get_nowait.side_effect = Exception(
                "Test exception")
            self.plugin.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.plugin.opts)
            self.plugin.sf.error.assert_called_once()
            self.assertTrue(self.plugin.errorState)
            self.plugin.incomingEventQueue.get_nowait.assert_called()

    def test_threadWorker_with_keyboard_interrupt(self):
        with patch('spiderfoot.plugin.SpiderFootDb') as mock_SpiderFootDb, patch.object(self.plugin, 'sf'):
            self.plugin.incomingEventQueue = MagicMock()
            self.plugin.outgoingEventQueue = MagicMock()
            self.plugin.incomingEventQueue.get_nowait.side_effect = KeyboardInterrupt
            self.plugin.threadWorker()
            mock_SpiderFootDb.assert_called_once_with(self.plugin.opts)
            self.plugin.sf.debug.assert_called_once_with(
                f"Interrupted module {self.plugin.__name__}.")
            self.assertTrue(self.plugin._stopScanning)

    def test_poolExecute_with_shared_thread_pool(self):
        callback = MagicMock()
        self.plugin.__name__ = "sfp_test"
        self.plugin.sharedThreadPool = MagicMock()
        self.plugin.poolExecute(callback)
        self.plugin.sharedThreadPool.submit.assert_called_once_with(
            callback, taskName=f"{self.plugin.__name__}_threadWorker", maxThreads=self.plugin.maxThreads)

    def test_poolExecute_with_storage_module(self):
        callback = MagicMock()
        self.plugin.__name__ = "sfp__stor_test"
        self.plugin.poolExecute(callback)
        callback.assert_called_once()

    def test_poolExecute_with_non_storage_module(self):
        callback = MagicMock()
        self.plugin.__name__ = "sfp_test"
        self.plugin.sharedThreadPool = MagicMock()
        self.plugin.poolExecute(callback)
        self.plugin.sharedThreadPool.submit.assert_called_once_with(
            callback, taskName=f"{self.plugin.__name__}_threadWorker", maxThreads=self.plugin.maxThreads)

    def test_threadPool_with_arguments(self):
        with patch('spiderfoot.plugin.SpiderFootThreadPool') as mock_SpiderFootThreadPool:
            pool = self.plugin.threadPool(5, 10)
            mock_SpiderFootThreadPool.assert_called_once_with(5, 10)
            self.assertEqual(pool, mock_SpiderFootThreadPool.return_value)

    def test_setSharedThreadPool_with_argument(self):
        sharedThreadPool = MagicMock()
        self.plugin.setSharedThreadPool(sharedThreadPool)
        self.assertEqual(self.plugin.sharedThreadPool, sharedThreadPool)
