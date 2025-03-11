import multiprocessing
import queue

from spiderfoot.logger import logListenerSetup, logWorkerSetup


def setup_logging_in_main_app():
    """How to set up logging in the main SpiderFoot application"""
    # Decide whether to use multiprocessing.Queue or queue.Queue based on your needs
    if your_app_uses_multiprocessing:
        log_queue = multiprocessing.Queue()
    else:
        log_queue = queue.Queue()

    # Set up logging with your app's configuration
    opts = {
        "__logging": True,
        "_debug": False,  # Set to True for development
        # Add other app-specific configuration here
    }

    # Initialize the log listener early in the application startup
    log_listener = logListenerSetup(log_queue, opts)

    # Initialize the main thread logger
    log = logWorkerSetup(log_queue)

    # Log startup message
    log.info("SpiderFoot starting...")

    # Store the log_queue and log_listener in your application state
    app_state = {"log_queue": log_queue,
                 "log_listener": log_listener, "log": log}

    return app_state


def module_initialization(app_state):
    """How modules should initialize logging"""
    # Get the log queue from the application state
    log_queue = app_state["log_queue"]

    # Set up logging for this module/thread
    log = logWorkerSetup(log_queue)

    # Use the logger
    log.info("Module initialized")
    return log


def application_shutdown(app_state):
    """How to properly shut down logging"""
    # Get the log listener from the application state
    log_listener = app_state["log_listener"]
    log = app_state["log"]

    # Log shutdown message
    log.info("SpiderFoot shutting down...")

    # Stop the log listener
    log_listener.stop()
