import atexit
import logging
import os
import sqlite3
import sys
import time
from contextlib import suppress
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from queue import Queue
from threading import Thread

from spiderfoot import SpiderFootDb, SpiderFootHelpers


class SpiderFootSqliteLogHandler(logging.Handler):
    """Handler for logging to SQLite database.

    This ensure all sqlite logging is done from a single process and a
    single database handle.
    """

    def __init__(self, opts: dict) -> None:
        """Initialize the SQLite log handler.

        Args:
            opts (dict): Configuration options
        """
        self.opts = opts
        self.dbh = None
        self.batch = []
        if self.opts.get('_debug', False):
            self.batch_size = 100
        else:
            self.batch_size = 5
        self.shutdown_hook = False
        self.log_file = os.path.join(SpiderFootHelpers.logPath(), "spiderfoot.sqlite.log")
        self.backup_count = 30
        self.rotate_logs()
        self.log_queue = Queue()
        self.logging_thread = Thread(target=self.process_log_queue)
        self.logging_thread.start()
        super().__init__()

    def emit(self, record: 'logging.LogRecord') -> None:
        """Emit a log record.

        Args:
            record (logging.LogRecord): Log event record
        """
        if not self.shutdown_hook:
            atexit.register(self.logBatch)
            self.shutdown_hook = True
        scanId = getattr(record, "scanId", None)
        component = getattr(record, "module", None)
        if scanId:
            level = ("STATUS" if record.levelname ==
                     "INFO" else record.levelname)
            self.batch.append(
                (scanId, level, record.getMessage(), component, time.time()))
            if len(self.batch) >= self.batch_size:
                self.logBatch()


    def logBatch(self):
        """Log a batch of records to the database."""
        while not self.log_queue.empty():
            self.batch.append(self.log_queue.get())
            if len(self.batch) >= self.batch_size:
                self.process_log_batch()

    def process_log_batch(self):
        """Process a batch of log records."""
        batch = self.batch
        self.batch = []
        if self.dbh is None:
            # Create a new database handle when the first log batch is processed
            self.makeDbh()
        logResult = self.dbh.scanLogEvents(batch)
        if logResult is False:
            # Try to recreate database handle if insert failed
            self.makeDbh()
            self.dbh.scanLogEvents(batch)
        self.rotate_logs()

    def makeDbh(self) -> None:
        """Create a new database handle."""
        self.dbh = SpiderFootDb(self.opts)

    def rotate_logs(self) -> None:
        """Rotate and archive SQLite logs."""
        if os.path.exists(self.log_file):
            if os.path.getsize(self.log_file) > 10 * 1024 * 1024:  # 10 MB
                for i in range(self.backup_count - 1, 0, -1):
                    sfn = f"{self.log_file}.{i}"
                    dfn = f"{self.log_file}.{i + 1}"
                    if os.path.exists(sfn):
                        os.rename(sfn, dfn)
                dfn = self.log_file + ".1"
                os.rename(self.log_file, dfn)
                open(self.log_file, 'w').close()

    def filter(self, record: 'logging.LogRecord') -> bool:
        """Filter log records based on log levels.

        Args:
            record (logging.LogRecord): Log event record

        Returns:
            bool: Whether the record should be logged
        """
        return record.levelno >= self.level

    def format(self, record: 'logging.LogRecord') -> str:
        """Format log records.

        Args:
            record (logging.LogRecord): Log event record

        Returns:
            str: Formatted log message
        """
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(module)s : %(message)s")
        return formatter.format(record)

    def process_log_queue(self):
        """Process log records from the queue."""
        while True:
            self.logBatch()


def logListenerSetup(loggingQueue, opts: dict = None) -> 'logging.handlers.QueueListener':
    """Create and start a SpiderFoot log listener in its own thread.

    This function should be called as soon as possible in the main
    process, or whichever process is attached to stdin/stdout.

    Args:
        loggingQueue (Queue): Queue (accepts both normal and multiprocessing queue types)
                              Must be instantiated in the main process.
        opts (dict): SpiderFoot config

    Returns:
        spiderFootLogListener (logging.handlers.QueueListener): Log listener
    """
    if opts is None:
        opts = dict()
    doLogging = opts.get("__logging", True)
    debug = opts.get("_debug", False)
    logLevel = (logging.DEBUG if debug else logging.INFO)

    # Log to terminal
    console_handler = logging.StreamHandler(sys.stderr)

    # Log debug messages to file
    log_dir = SpiderFootHelpers.logPath()
    debug_handler = logging.handlers.TimedRotatingFileHandler(
        f"{log_dir}/spiderfoot.debug.log",
        when="d",
        interval=1,
        backupCount=30
    )

    # Log error messages to file
    error_handler = logging.handlers.TimedRotatingFileHandler(
        f"{log_dir}/spiderfoot.error.log",
        when="d",
        interval=1,
        backupCount=30
    )

    # Filter by log level
    console_handler.addFilter(lambda x: x.levelno >= logLevel)
    debug_handler.addFilter(lambda x: x.levelno >= logging.DEBUG)
    error_handler.addFilter(lambda x: x.levelno >= logging.WARN)

    # Set log format
    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(module)s : %(message)s")
    debug_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(filename)s:%(lineno)s : %(message)s")
    console_handler.setFormatter(log_format)
    debug_handler.setFormatter(debug_format)
    error_handler.setFormatter(debug_format)

    if doLogging:
        handlers = [console_handler, debug_handler, error_handler]
    else:
        handlers = []

    if doLogging and opts is not None:
        sqlite_handler = SpiderFootSqliteLogHandler(opts)
        sqlite_handler.setLevel(logLevel)
        sqlite_handler.setFormatter(log_format)
        handlers.append(sqlite_handler)
    spiderFootLogListener = QueueListener(loggingQueue, *handlers)
    spiderFootLogListener.start()
    atexit.register(stop_listener, spiderFootLogListener)
    return spiderFootLogListener


def logWorkerSetup(loggingQueue) -> 'logging.Logger':
    """Root SpiderFoot logger.

    Args:
        loggingQueue (Queue): Queue for logging events

    Returns:
        logging.Logger: Logger
    """
    log = logging.getLogger("spiderfoot")
    # Don't do this more than once
    if len(log.handlers) == 0:
        log.setLevel(logging.DEBUG)
        queue_handler = QueueHandler(loggingQueue)
        log.addHandler(queue_handler)
    return log


def stop_listener(listener: 'logging.handlers.QueueListener') -> None:
    """Stop the log listener.

    Args:
        listener: (logging.handlers.QueueListener): Log listener
    """
    with suppress(Exception):
        listener.stop()
