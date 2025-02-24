import unittest
import logging
import sys
from logging.handlers import QueueHandler, QueueListener
from unittest.mock import MagicMock, patch
from spiderfoot.logger import SpiderFootSqliteLogHandler, logListenerSetup, logWorkerSetup, stop_listener


class TestSpiderFootSqliteLogHandler(unittest.TestCase):

    def setUp(self):
        self.opts = {'_debug': True}
        self.handler = SpiderFootSqliteLogHandler(self.opts)

    def test_init(self):
        self.assertEqual(self.handler.opts, self.opts)
        self.assertIsNone(self.handler.dbh)
        self.assertEqual(self.handler.batch, [])
        self.assertEqual(self.handler.batch_size, 100)
        self.assertFalse(self.handler.shutdown_hook)

    def test_emit(self):
        record = MagicMock()
        record.levelname = "INFO"
        record.getMessage.return_value = "Test message"
        record.scanId = "test_scan"
        record.module = "test_module"

        with patch.object(self.handler, 'logBatch') as mock_logBatch:
            self.handler.emit(record)
            self.assertEqual(len(self.handler.batch), 1)
            self.assertTrue(self.handler.shutdown_hook)
            mock_logBatch.assert_not_called()

    def test_logBatch(self):
        self.handler.batch = [("test_scan", "INFO", "Test message", "test_module", 1234567890)]
        self.handler.dbh = MagicMock()
        self.handler.dbh.scanLogEvents.return_value = True

        self.handler.logBatch()
        self.assertEqual(self.handler.batch, [])
        self.handler.dbh.scanLogEvents.assert_called_once()

    def test_makeDbh(self):
        with patch('spiderfoot.logger.SpiderFootDb') as mock_SpiderFootDb:
            self.handler.makeDbh()
            mock_SpiderFootDb.assert_called_once_with(self.opts)


class TestLogListenerSetup(unittest.TestCase):

    @patch('spiderfoot.logger.SpiderFootHelpers.logPath', return_value='/tmp')
    @patch('spiderfoot.logger.logging.StreamHandler')
    @patch('spiderfoot.logger.logging.handlers.TimedRotatingFileHandler')
    def test_logListenerSetup(self, mock_TimedRotatingFileHandler, mock_StreamHandler, mock_logPath):
        loggingQueue = MagicMock()
        opts = {'__logging': True, '_debug': True}

        listener = logListenerSetup(loggingQueue, opts)
        self.assertIsInstance(listener, QueueListener)
        self.assertTrue(listener._queue is loggingQueue)
        self.assertEqual(len(listener.handlers), 4)


class TestLogWorkerSetup(unittest.TestCase):

    def test_logWorkerSetup(self):
        loggingQueue = MagicMock()
        log = logWorkerSetup(loggingQueue)
        self.assertIsInstance(log, logging.Logger)
        self.assertEqual(log.name, "spiderfoot")
        self.assertEqual(len(log.handlers), 1)
        self.assertIsInstance(log.handlers[0], QueueHandler)


class TestStopListener(unittest.TestCase):

    def test_stop_listener(self):
        listener = MagicMock()
        stop_listener(listener)
        listener.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
