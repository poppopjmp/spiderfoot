"""SpiderFoot logging functionality.

This module provides logging capabilities for SpiderFoot, including:
- Thread-safe logging implementation
- Logging to console, files, and SQLite database
- Centralized logging system using a queue-based approach
- Support for multiple log formats and destinations
"""

import atexit
import logging
import os
import socket
import sqlite3
import sys
import time
from contextlib import suppress
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler, SysLogHandler

from spiderfoot import SpiderFootDb, SpiderFootHelpers


class SafeQueueListener(QueueListener):
    """Thread-safe implementation of QueueListener for handling logs from multiple threads.
    
    This class extends QueueListener to provide thread-safety when processing
    log records from multiple threads through a queue.
    """
    
    def dequeue(self, block):
        """Get a record from the queue.
        
        Args:
            block (bool): Whether to block if queue is empty
            
        Returns:
            LogRecord: A log record from the queue or None
        """
        if self.queue is not None:
            return self.queue.get(block)
        return None

    def _monitor(self):
        """Monitor the queue for records and process them."""
        try:
            while True:
                if self.queue is not None:
                    record = self.dequeue(True)
                    if record is not None:
                        self.handle(record)
                else:
                    break
        except Exception:
            self.handleError(None)

    def enqueue(self, record):
        """Put a record into the queue.
        
        Args:
            record (LogRecord): The log record to queue
        """
        if self.queue is not None:
            self.queue.put_nowait(record)


class SpiderFootSqliteLogHandler(logging.Handler):
    """Handler for logging to SQLite database.

    This ensures all SQLite logging is done from a single
    process and a single database handle to avoid concurrency issues.
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
            level = ("STATUS" if record.levelname == "INFO" else record.levelname)
            self.batch.append((scanId, level, record.getMessage(), component, time.time()))
            if len(self.batch) >= self.batch_size:
                self.logBatch()

    def logBatch(self) -> None:
        """Log a batch of records to the database."""
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

    def makeDbh(self) -> None:
        """Create a new database handle."""
        self.dbh = SpiderFootDb(self.opts)


def logListenerSetup(loggingQueue, opts: dict = None) -> 'logging.handlers.QueueListener':
    """Create and start a SpiderFoot log listener in its own thread.
    
    This function sets up a centralized logging system that safely handles logs
    from multiple threads by using a queue-based approach. All log handlers are
    managed by a single listener thread to avoid file access conflicts.

    Args:
        loggingQueue (Queue): Queue (accepts both normal and multiprocessing queue types)
                              Must be instantiated in the main process.
        opts (dict): SpiderFoot config

    Returns:
        logging.handlers.QueueListener: Log listener
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
    debug_handler = TimedRotatingFileHandler(
        f"{log_dir}/spiderfoot.debug.log",
        when="d",
        interval=1,
        backupCount=30
    )

    # Log error messages to file
    error_handler = TimedRotatingFileHandler(
        f"{log_dir}/spiderfoot.error.log",
        when="d",
        interval=1,
        backupCount=30
    )

    # Get hostname for syslog format
    hostname = socket.gethostname()
    
    # Log to syslog format file
    syslog_handler = logging.FileHandler(f"{log_dir}/spiderfoot.syslog.log")
    syslog_format = logging.Formatter(f"%(asctime)s {hostname} %(name)s: %(message)s")
    syslog_handler.setFormatter(syslog_format)

    # Filter by log level
    console_handler.addFilter(lambda x: x.levelno >= logLevel)
    debug_handler.addFilter(lambda x: x.levelno >= logging.DEBUG)
    error_handler.addFilter(lambda x: x.levelno >= logging.WARN)
    syslog_handler.addFilter(lambda x: x.levelno >= logLevel)

    # Set log format
    log_format = logging.Formatter("%(asctime)s [%(levelname)s] %(module)s : %(message)s")
    debug_format = logging.Formatter("%(asctime)s [%(levelname)s] %(filename)s:%(lineno)s : %(message)s")
    console_handler.setFormatter(log_format)
    debug_handler.setFormatter(debug_format)
    error_handler.setFormatter(debug_format)

    if doLogging:
        handlers = [console_handler, debug_handler, error_handler, syslog_handler]
    else:
        handlers = []

    if doLogging and opts is not None:
        sqlite_handler = SpiderFootSqliteLogHandler(opts)
        sqlite_handler.setLevel(logLevel)
        sqlite_handler.setFormatter(log_format)
        handlers.append(sqlite_handler)
    
    spiderFootLogListener = SafeQueueListener(loggingQueue, *handlers)
    spiderFootLogListener.start()
    atexit.register(stop_listener, spiderFootLogListener)
    return spiderFootLogListener


def logWorkerSetup(loggingQueue) -> 'logging.Logger':
    """Create a thread-safe root SpiderFoot logger.
    
    Creates a thread-safe logger that sends all log records to a queue,
    which is then processed by a single listener thread. This approach ensures
    thread-safety by centralizing all I/O operations to a single thread.

    Args:
        loggingQueue (Queue): Queue for logging events

    Returns:
        logging.Logger: Thread-safe logger
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
        listener (logging.handlers.QueueListener): Log listener
    """
    with suppress(Exception):
        listener.stop()
