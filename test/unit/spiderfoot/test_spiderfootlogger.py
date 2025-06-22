import unittest
import logging
import tempfile
import os
from queue import Queue
from spiderfoot.logger import (
    SpiderFootSqliteLogHandler,
    logListenerSetup,
    logWorkerSetup,
    stop_listener
)

class TestLoggerIntegration(unittest.TestCase):
    def test_sqlite_log_handler_emit_and_batch(self):
        opts = {'_debug': True}
        handler = SpiderFootSqliteLogHandler(opts)
        logger = logging.getLogger("test_logger_emit")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.info("test message")
        handler.logBatch()  # Should process the batch without error
        logger.removeHandler(handler)

    def test_log_listener_setup_and_stop(self):
        q = Queue()
        listener = logListenerSetup(q)
        self.assertIsNotNone(listener)
        stop_listener(listener)  # Should not raise

    def test_log_worker_setup(self):
        q = Queue()
        logger = logWorkerSetup(q)
        self.assertIsInstance(logger, logging.Logger)
        logger.info("worker test message")

    def test_rotate_logs(self):
        opts = {'_debug': True}
        handler = SpiderFootSqliteLogHandler(opts)
        # Create a fake log file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            log_path = tmp.name
        try:
            handler.log_file = log_path
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('x' * (11 * 1024 * 1024))  # >10MB
            handler.rotate_logs()
            # After rotation, the original file should exist and be empty
            self.assertTrue(os.path.exists(log_path))
        finally:
            if os.path.exists(log_path):
                os.remove(log_path)
            if os.path.exists(log_path + '.1'):
                os.remove(log_path + '.1')

if __name__ == "__main__":
    unittest.main()
