import multiprocessing
import threading
import time
import queue

from spiderfoot.logger import logListenerSetup, logWorkerSetup


def example_basic_logging():
    """Example of basic logging setup in the main thread"""
    # Step 1: Create a queue for log messages
    log_queue = queue.Queue()

    # Step 2: Set up the log listener in the main thread
    opts = {"__logging": True, "_debug": True}
    log_listener = logListenerSetup(log_queue, opts)

    # Step 3: Set up the worker logger that will send messages to the queue
    log = logWorkerSetup(log_queue)

    # Step 4: Use the logger
    log.info("This is an informational message")
    log.debug("This is a debug message")
    log.warning("This is a warning message")
    log.error("This is an error message")
    log.critical("This is a critical message")

    # Step 5: Ensure the listener is stopped when done
    log_listener.stop()


def worker_function(log_queue):
    """Example worker function using the logger"""
    # Set up the logger in this thread
    log = logWorkerSetup(log_queue)

    # Use the logger
    log.info("Worker thread starting")
    time.sleep(1)
    log.debug("Worker thread processing")
    time.sleep(1)
    log.info("Worker thread finished")


def example_multithreading():
    """Example of using the logger in multiple threads"""
    # Create a queue for log messages (shared between threads)
    log_queue = queue.Queue()

    # Set up the log listener in the main thread
    opts = {"__logging": True, "_debug": True}
    log_listener = logListenerSetup(log_queue, opts)

    # Set up the logger for the main thread
    log = logWorkerSetup(log_queue)

    # Create and start worker threads
    log.info("Starting worker threads")
    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker_function, args=(log_queue,))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    log.info("All worker threads have finished")

    # Stop the log listener
    log_listener.stop()


def scan_worker(log_queue, scan_id):
    """Example worker function with scan ID"""
    # Set up the logger in this thread
    log = logWorkerSetup(log_queue)

    # Add scan_id as an extra attribute to log records
    extra = {"scanId": scan_id}

    # Log using extra to include scan_id
    log.info(f"Scan {scan_id} starting", extra=extra)
    time.sleep(1)
    log.debug(f"Scan {scan_id} processing", extra=extra)
    time.sleep(1)
    log.info(f"Scan {scan_id} finished", extra=extra)


def example_multiprocessing():
    """Example of using the logger with multiple processes"""
    # Create a multiprocessing queue for log messages (shared between processes)
    log_queue = multiprocessing.Queue()

    # Set up the log listener in the main process
    opts = {"__logging": True, "_debug": True}
    log_listener = logListenerSetup(log_queue, opts)

    # Set up the logger for the main process
    log = logWorkerSetup(log_queue)

    # Create and start worker processes
    log.info("Starting worker processes")
    processes = []
    for i in range(3):
        scan_id = f"SCAN_{i}"
        process = multiprocessing.Process(
            target=scan_worker, args=(log_queue, scan_id))
        process.start()
        processes.append(process)

    # Wait for all processes to finish
    for process in processes:
        process.join()

    log.info("All worker processes have finished")

    # Stop the log listener
    log_listener.stop()


def module_specific_logging(log_queue):
    """Example of module-specific logging"""
    # Create a module-specific logger (inherits from root logger)
    logger = logging.getLogger("spiderfoot.modules.mymodule")

    # No need to add handlers - they're inherited from the root logger
    # Just start logging
    logger.info("This is a module-specific log message")
    logger.debug("This is a module-specific debug message")


if __name__ == "__main__":
    print("Basic logging example:")
    example_basic_logging()

    print("\nMultithreading example:")
    example_multithreading()

    print("\nMultiprocessing example:")
    example_multiprocessing()
