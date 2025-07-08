import contextlib
import os
import sys
import time
import pytest
import logging
import threading
from pathlib import Path
from _pytest.runner import runtestprotocol

# Ensure we're in the correct directory for tests
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# Add project root to Python path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import SpiderFootHelpers after path setup
from spiderfoot import SpiderFootHelpers

# Import our test fixtures and utilities
from test.fixtures.database_fixtures import *
from test.fixtures.network_fixtures import *
from test.fixtures.event_fixtures import *
from test.utils import legacy_test_helpers

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
    # Only start timeout if not already configured
    if not hasattr(config, '_timeout_started'):
        config._timeout_started = True
        start_global_timeout()
    
def start_global_timeout():
    # Create a thread that will terminate the process after a timeout
    def timeout_thread():
        time.sleep(1800)  # 30-minute global timeout
        try:
            # Use print instead of logging to avoid closed file issues
            print("Global timeout exceeded. Terminating test run.", file=sys.stderr, flush=True)
        except Exception:
            # If even stderr is closed, just exit
            pass
        finally:
            os._exit(1)
    
    # Explicitly set daemon to True to ensure it doesn't prevent shutdown
    thread = threading.Thread(target=timeout_thread, daemon=True)
    thread.start()
    
# Detect tests that don't clean up resources
@pytest.fixture(autouse=True)
def check_resource_leaks():
    # Record initial state
    starting_threads = set(threading.enumerate())
    
    # Run the test
    yield
    
    # Give a moment for cleanup
    time.sleep(0.1)  # Reduced sleep time
    
    # Check which new threads are lingering
    ending_threads = set(threading.enumerate())
    new_threads = ending_threads - starting_threads
    
    if new_threads:
        thread_names = [t.name for t in new_threads if t.is_alive() and not t.daemon]
        if thread_names:  # Only report non-daemon threads
            logging.warning(f"Potential thread leak detected: {thread_names}")

@pytest.fixture(autouse=True)
def default_options(request):
    # Ensure modules directory exists and is accessible
    modules_dir = PROJECT_ROOT / "modules"
    if not modules_dir.exists():
        pytest.fail(f"Modules directory not found: {modules_dir}")

    # Only set default_options if running in a class context
    if hasattr(request, 'cls') and request.cls is not None:
        request.cls.default_options = {
            '_debug': False,
            '__logging': True,
            '__outputfilter': None,
            '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
            '_dnsserver': '',
            '_fetchtimeout': 5,
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72,
            '_genericusers': ",".join(SpiderFootHelpers.usernamesFromWordlists(['generic-usernames'])),
            '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.test.db",
            '__modules__': None,
            '__correlationrules__': None,
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': '',
            '__logstdout': False,
            '__modulesdir': str(modules_dir)
        }
        request.cls.web_default_options = {'root': '/'}
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
    # For function-based tests, do nothing (or set module-level if needed)
    yield

# Force cleanup of lingering resources
@pytest.fixture(autouse=True, scope="session")
def session_cleanup():
    yield
    # Force cleanup at end of session
    import gc
    import threading
      # Force garbage collection
    gc.collect()
    
    # Clean up threads more safely
    main_thread = threading.main_thread()
    for thread in threading.enumerate():
        if thread != main_thread and thread.is_alive():
            # Only try to set daemon on threads that allow it
            try:
                if not thread.daemon:
                    thread.daemon = True
            except RuntimeError:
                # Thread is already started, cannot change daemon status
                pass
    
    # Use contextlib.suppress to handle potential logging issues during cleanup
    with contextlib.suppress(ValueError, OSError):
        logging.info("Session cleanup completed")


# Add process-level timeout
@pytest.fixture(autouse=True, scope="session")
def process_timeout():
    def timeout_process():
        time.sleep(1800)  # 30-minute absolute timeout
        logging.error("Process timeout exceeded. Force terminating.")
        os._exit(2)
    
    timeout_thread = threading.Thread(target=timeout_process, daemon=True)
    timeout_thread.start()
    yield
