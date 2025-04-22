import atexit
import logging
import os
import sqlite3
import sys
import time
from contextlib import suppress
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler
from queue import Queue

from spiderfoot import SpiderFootDb, SpiderFootHelpers


class SpiderFootSqliteLogHandler(logging.Handler):
    """Handler for logging to SQLite database.

    This handler batches log records and writes them to the SpiderFoot
    SQLite database. It relies on the QueueListener for threading.
    """

    def __init__(self, opts: dict) -> None:
        """Initialize the SQLite log handler.

        Args:
            opts (dict): Configuration options
        """
        super().__init__()
        self.opts = opts
        self.dbh = None
        self.batch = []
        # Make batch size configurable or based on debug status
        self.batch_size = 100 if self.opts.get('_debug', False) else 50
        # Log retention period in days (default: 30 days)
        self.log_retention_days = self.opts.get('__log_retention_days', 30)
        # Initial database connection
        self.makeDbh()
        # Schedule initial log purging
        self.purge_logs()

    def emit(self, record: 'logging.LogRecord') -> None:
        """Format log record and add to batch.

        Args:
            record (logging.LogRecord): Log event record
        """
        scanId = getattr(record, "scanId", None)
        component = getattr(record, "module", None)
        if scanId:
            level = ("STATUS" if record.levelname ==
                     "INFO" else record.levelname)
            # Add formatted log to batch
            self.batch.append(
                (scanId, level, self.format(record), component, time.time())
            )
            # Check batch size and flush if needed
            if len(self.batch) >= self.batch_size:
                self.flush()

    def flush(self) -> None:
        """Process the current batch of log records."""
        if not self.batch:
            return

        # Store the current batch and reset it
        current_batch = self.batch
        self.batch = []

        try:
            if self.dbh is None:
                # Create database handle if it doesn't exist
                self.makeDbh()

            if self.dbh:  # Ensure dbh was created successfully
                logResult = self.dbh.scanLogEvents(current_batch)
                if logResult is False:
                    logging.error("Failed to write log batch to database. Attempting to recreate DB handle.")
                    # Try to recreate database handle if insert failed
                    self.makeDbh()
                    if self.dbh:
                        logResult = self.dbh.scanLogEvents(current_batch)
                        if logResult is False:
                            logging.error("Failed to write log batch to database after recreating handle.")
                    else:
                        logging.error("Failed to recreate database handle for logging.")
            else:
                logging.error("Database handle not available for logging.")

            # Periodically purge old logs (approximately once per 1000 batches)
            if self.dbh and hash(str(time.time())) % 1000 == 0:
                self.purge_logs()

        except Exception as e:
            # Use standard logging for handler errors
            logging.error(f"Exception writing log batch to database: {e}")

    def makeDbh(self) -> None:
        """Create or recreate the database handle."""
        try:
            # Close existing handle first if recreating
            if self.dbh:
                with suppress(Exception):
                    self.dbh.close()
            self.dbh = SpiderFootDb(self.opts)
        except Exception as e:
            logging.error(f"Failed to create/recreate database handle: {e}")
            self.dbh = None  # Ensure dbh is None if creation failed

    def purge_logs(self) -> None:
        """Purge old log records from the database.
        
        Instead of rotating the log file (which can cause database corruption),
        this method removes old log records from within the database,
        keeping the database file intact.
        """
        if not self.dbh:
            return
            
        try:
            # Calculate cutoff timestamp (current time - retention period)
            cutoff_time = time.time() - (self.log_retention_days * 86400)  # 86400 seconds = 1 day
            
            # Execute DELETE query to remove old logs
            result = self.dbh.dbh.execute(
                "DELETE FROM tbl_scan_log WHERE generated < ?", 
                (cutoff_time,)
            )
            self.dbh.dbh.commit()
            
            deleted_count = result.rowcount
            if deleted_count > 0:
                logging.info(f"Purged {deleted_count} log records older than {self.log_retention_days} days")
                
            # Vacuum the database to reclaim space (do this occasionally)
            if deleted_count > 1000:
                self.dbh.dbh.execute("VACUUM")
                logging.info("Database vacuumed after log purge")
                
        except Exception as e:
            logging.error(f"Error purging old logs: {e}")

    def close(self) -> None:
        """Flush any remaining logs and close the database connection."""
        try:
            self.flush()  # Write any remaining items in batch
            if self.dbh:
                self.dbh.close()
                self.dbh = None
        except Exception as e:
            logging.error(f"Exception closing SQLite log handler: {e}")
        finally:
            # Ensure parent close is called
            super().close()


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
    
    # Use respect_handler_level=True to ensure handlers only receive appropriate log levels
    spiderFootLogListener = QueueListener(loggingQueue, *handlers, respect_handler_level=True)
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
