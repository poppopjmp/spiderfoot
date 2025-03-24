import os
import sys
import time
import pytest
import logging
import threading
from _pytest.runner import runtestprotocol
from spiderfoot import SpiderFootHelpers
from test.unit.utils.thread_manager import ThreadManager

# Try to import ConnectionMonitor, but don't fail if dependencies are missing
try:
    from test.unit.utils.connection_monitor import ConnectionMonitor
    HAS_CONNECTION_MONITOR = True
except ImportError:
    HAS_CONNECTION_MONITOR = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("pytest-debug.log"),
        logging.StreamHandler()
    ]
)

# Track test execution and find potential issues
@pytest.hookimpl(trylast=True)
def pytest_runtest_protocol(item, nextitem):
    start_time = time.time()
    logging.info(f"Starting test: {item.nodeid}")
    
    # Show active threads at start
    active_threads = threading.enumerate()
    logging.info(f"Active threads before test ({len(active_threads)}): {[t.name for t in active_threads]}")
    
    # Run the test normally
    reports = runtestprotocol(item, nextitem=nextitem)
    
    # Show threads after test completion
    active_threads = threading.enumerate()
    logging.info(f"Active threads after test ({len(active_threads)}): {[t.name for t in active_threads]}")
    
    # Show elapsed time
    elapsed = time.time() - start_time
    logging.info(f"Completed test: {item.nodeid} ({elapsed:.2f}s)")
    
    return True

# Auto-timeout for test session
@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # Create and register the timeout plugin
    config._cleanup.append(start_global_timeout)
    
def start_global_timeout():
    # Create a thread that will terminate the process after a timeout
    def timeout_thread():
        time.sleep(600)  # 10-minute global timeout
        logging.error("Global timeout exceeded. Terminating test run.")
        os._exit(1)
    
    # Explicitly set daemon to True to ensure it doesn't prevent shutdown
    thread = threading.Thread(target=timeout_thread)
    thread.daemon = True  # Setting explicitly in case the keyword arg isn't working
    thread.start()
    
# Detect tests that don't clean up resources
@pytest.fixture(autouse=True)
def check_resource_leaks():
    # Record initial state
    starting_threads = set(threading.enumerate())
    
    # Run the test
    yield
    
    # Give a moment for cleanup
    time.sleep(0.5)
    
    # Check which new threads are lingering
    ending_threads = set(threading.enumerate())
    new_threads = ending_threads - starting_threads
    
    if new_threads:
        thread_names = [t.name for t in new_threads if t.is_alive()]
        if thread_names:  # Only report if threads are still alive
            logging.warning(f"Potential thread leak detected: {thread_names}")

# Add a stronger test isolation mechanism
@pytest.fixture(autouse=True)
def test_isolation():
    """Ensure tests are properly isolated from one another."""
    # Record initial state
    initial_threads = set(threading.enumerate())
    thread_info_before = ThreadManager.get_thread_info()
    logging.info(f"Active threads before test: {thread_info_before['count']}")
    
    # Monitor connections if available
    if HAS_CONNECTION_MONITOR:
        connections_before = len(ConnectionMonitor.get_open_connections())
        logging.info(f"Open connections before test: {connections_before}")
    
    # Let the test run
    yield
    
    # Give threads a moment to clean up
    time.sleep(0.5)
    
    # Close any open connections
    if HAS_CONNECTION_MONITOR:
        closed = ConnectionMonitor.close_all_connections()
        if closed > 0:
            logging.info(f"Closed {closed} connections")
        
        connections_after = len(ConnectionMonitor.get_open_connections())
        logging.info(f"Open connections after test: {connections_after}")
    
    # Try to wait for threads to complete
    ThreadManager.wait_for_threads_completion()
    
    # Check if new threads were created and not cleaned up
    current_threads = set(threading.enumerate())
    new_threads = current_threads - initial_threads
    
    thread_info_after = ThreadManager.get_thread_info()
    logging.info(f"Active threads after test: {thread_info_after['count']}")
    
    if new_threads:
        thread_info = [f"{t.name} (daemon={t.daemon})" for t in new_threads if t.is_alive()]
        if thread_info:  # Only report if threads are still alive
            logging.warning(f"Test left behind {len(thread_info)} thread(s): {', '.join(thread_info)}")
            
            # Try to identify threads that might be hanging
            for thread in new_threads:
                if not thread.daemon and thread.is_alive():
                    logging.warning(f"Non-daemon thread still running: {thread.name}")

@pytest.fixture(autouse=True)
def default_options(request):
    request.cls.default_options = {
        '_debug': False,
        '__logging': True,  # Logging in general
        '__outputfilter': None,  # Event types to filter from modules' output
        # User-Agent to use for HTTP requests
        '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
        '_dnsserver': '',  # Override the default resolver
        '_fetchtimeout': 5,  # number of seconds before giving up on a fetch
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '_genericusers': ",".join(SpiderFootHelpers.usernamesFromWordlists(['generic-usernames'])),
        # note: test database file
        '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.test.db",
        '__modules__': None,  # List of modules. Will be set after start-up.
        # List of correlation rules. Will be set after start-up.
        '__correlationrules__': None,
        '_socks1type': '',
        '_socks2addr': '',
        '_socks3port': '',
        '_socks4user': '',
        '_socks5pwd': '',
        '__logstdout': False
    }

    request.cls.web_default_options = {
        'root': '/'
    }

    request.cls.cli_default_options = {
        "cli.debug": False,
        "cli.silent": False,
        "cli.color": True,
        "cli.output": "pretty",
        "cli.history": True,
        "cli.history_file": "",
        "cli.spool": False,
        "cli.spool_file": "",
        "cli.ssl_verify": True,
        "cli.username": "",
        "cli.password": "",
        "cli.server_baseurl": "http://127.0.0.1:5001"
    }
