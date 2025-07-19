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

# Set up logging with error suppression for distributed testing


class SafeHandler(logging.StreamHandler):
    """A logging handler that suppresses BrokenPipeError and similar issues during xdist termination."""
    
    def emit(self, record):
        with contextlib.suppress(OSError, ValueError):
            super().emit(record)


class SafeFileHandler(logging.FileHandler):
    """A file handler that suppresses errors during xdist termination."""
    
    def emit(self, record):
        with contextlib.suppress(OSError, ValueError):
            super().emit(record)


# Configure logging with safe handlers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        SafeFileHandler("pytest-debug.log"),
        SafeHandler()
    ]
)

# Track test execution and find potential issues


@pytest.hookimpl(trylast=True)
def pytest_runtest_protocol(item, nextitem):
    start_time = time.time()
    
    # Use safe logging
    with contextlib.suppress(OSError, ValueError):
        logging.info(f"Starting test: {item.nodeid}")
        
        # Show active threads at start
        active_threads = threading.enumerate()
        logging.info(f"Active threads before test ({len(active_threads)}): {[t.name for t in active_threads]}")
    
    # Run the test normally
    runtestprotocol(item, nextitem=nextitem)
    
    # Use safe logging for completion
    with contextlib.suppress(OSError, ValueError):
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
    # Only start timeout if not already configured and not in xdist worker
    if not hasattr(config, '_timeout_started') and not hasattr(config, 'workerinput'):
        config._timeout_started = True
        start_global_timeout()


def start_global_timeout():
    """Create a global timeout thread with safe error handling."""
    def timeout_thread():
        time.sleep(1800)  # 30-minute global timeout
        with contextlib.suppress(Exception):
            # Use print instead of logging to avoid closed file issues
            print("Global timeout exceeded. Terminating test run.", file=sys.stderr, flush=True)
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
    # Force cleanup at end of session - suppress all logging errors for xdist compatibility
    import gc
    import threading
    
    # Force garbage collection
    gc.collect()
    
    # Clean up threads safely with proper error handling
    main_thread = threading.main_thread()
    from contextlib import suppress
    
    for thread in threading.enumerate():
        if thread != main_thread and thread.is_alive():
            # FIXED: Don't try to set daemon on active threads - this causes RuntimeError
            # Instead, attempt to join threads safely with timeout
            with suppress(RuntimeError, OSError):
                # Only join threads that are SpiderFoot-related or our test threads
                if (hasattr(thread, '_target') and thread._target
                        and ('SpiderFoot' in str(thread._target) or 'test' in str(thread._target))):
                    thread.join(timeout=1.0)
    
    # Use contextlib.suppress to handle potential logging issues during cleanup
    # This is essential for xdist compatibility
    with contextlib.suppress(ValueError, OSError, BrokenPipeError):
        logging.info("Session cleanup completed")
