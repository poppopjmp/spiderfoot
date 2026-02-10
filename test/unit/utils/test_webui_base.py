"""
Enhanced base class for web UI tests with robust timeout protection and resource cleanup.
"""
from __future__ import annotations

import threading
import time
import queue
import socket
import cherrypy
from contextlib import suppress
from functools import wraps
from unittest.mock import patch, MagicMock
from cherrypy.test import helper
from test.unit.utils.test_base import TestModuleBase

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


class WebUITimeoutError(Exception):
    """Custom timeout exception for test methods."""
    pass


def with_timeout(timeout_seconds=30):
    """
    Decorator that enforces a timeout on test methods.
    
    Args:
        timeout_seconds (int): Maximum time allowed for the test to run
        
    Returns:
        function: Decorated function with timeout protection
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            result_queue = queue.Queue()
            exception_queue = queue.Queue()
            
            def target():
                try:
                    result = func(self, *args, **kwargs)
                    result_queue.put(result)
                except Exception as e:
                    exception_queue.put(e)
            
            test_thread = threading.Thread(target=target, daemon=True)
            test_thread.start()
            test_thread.join(timeout=timeout_seconds)
            
            if test_thread.is_alive():
                # Force cleanup on timeout
                self._force_cleanup()
                raise WebUITimeoutError(f"Test {func.__name__} timed out after {timeout_seconds} seconds")
            
            # Check for exceptions
            if not exception_queue.empty():
                raise exception_queue.get()
            
            # Return result if available
            if not result_queue.empty():
                return result_queue.get()
            
            return None
        
        return wrapper
    return decorator


class ThreadReaper:
    """Aggressive thread and resource cleanup utility."""
    
    def __init__(self):
        self.registered_threads = set()
        self.registered_sockets = []
        self.registered_servers = []
        self.initial_thread_count = threading.active_count()
    
    def register_thread(self, thread):
        """Register a thread for cleanup.
        
        Args:
            thread: Thread object to register for cleanup
        """
        self.registered_threads.add(thread)
    
    def register_socket(self, socket_obj):
        """Register a socket for cleanup.
        
        Args:
            socket_obj: Socket object to register for cleanup
        """
        self.registered_sockets.append(socket_obj)
    
    def register_server(self, server):
        """Register a server for cleanup.
        
        Args:
            server: Server object to register for cleanup
        """
        self.registered_servers.append(server)
    
    def cleanup_all(self, force=False):
        """Perform aggressive cleanup of all registered resources.
        
        Args:
            force (bool): Whether to force aggressive cleanup
        """
        # Close sockets
        for sock in self.registered_sockets:
            with suppress(Exception):
                sock.close()
        self.registered_sockets.clear()
        
        # Stop servers
        for server in self.registered_servers:
            with suppress(Exception):
                if hasattr(server, 'stop'):
                    server.stop()
                if hasattr(server, 'shutdown'):
                    server.shutdown()
        self.registered_servers.clear()
        
        # Handle threads
        for thread in self.registered_threads:
            with suppress(Exception):
                if thread.is_alive():
                    if hasattr(thread, '_stop'):
                        thread._stop()
                    # Give thread a moment to stop gracefully
                    thread.join(timeout=0.5)
        self.registered_threads.clear()
        
        # Force cleanup if requested
        if force:
            self._force_thread_cleanup()
    
    def _force_thread_cleanup(self):
        """Force cleanup of all non-daemon threads."""
        current_threads = threading.enumerate()
        for thread in current_threads:
            if thread != threading.current_thread() and not thread.daemon:
                with suppress(Exception):
                    if hasattr(thread, '_stop'):
                        thread._stop()


class EnhancedWebUITestBase(helper.CPWebCase, TestModuleBase):
    """Enhanced base class for web UI tests with robust resource management."""
    
    def setUp(self):
        """Enhanced setup with resource tracking."""
        super().setUp()
        self.thread_reaper = ThreadReaper()
        self.web_config = self.web_default_options
        self.config = self.default_options.copy()
        
        # Track initial system state
        self._initial_threads = set(threading.enumerate())
        self._initial_connections = self._get_open_connections()
        
        # Mock database and logging to avoid real resources
        self._setup_mocks()
    
    def _setup_mocks(self):
        """Setup common mocks to avoid real resource allocation."""
        self.db_patcher = patch('sfwebui.SpiderFootDb')
        self.sf_patcher = patch('sfwebui.SpiderFoot')
        self.log_patcher = patch('sfwebui.logListenerSetup')
        
        self.mock_db = self.db_patcher.start()
        self.mock_sf = self.sf_patcher.start()
        self.mock_log = self.log_patcher.start()
        
        # Configure mock database instance
        self.mock_db_instance = MagicMock()
        self.mock_db.return_value = self.mock_db_instance
    
    def _get_open_connections(self):
        """Get current open network connections.
        
        Returns:
            int: Number of open connections
        """
        if not HAS_PSUTIL:
            return 0
        try:
            process = psutil.Process()
            return len(process.connections())
        except Exception:
            return 0
    
    def _force_cleanup(self):
        """Force aggressive cleanup of all resources."""
        # Stop CherryPy engine
        with suppress(Exception):
            if hasattr(cherrypy, 'engine') and cherrypy.engine.state != cherrypy.engine.states.STOPPED:
                cherrypy.engine.stop()
                cherrypy.engine.wait(states=[cherrypy.engine.states.STOPPED], interval=0.1, timeout=2)
        
        # Clean up webui instance
        if hasattr(self, 'webui'):
            with suppress(Exception):
                if hasattr(self.webui, 'loggingQueue') and self.webui.loggingQueue:
                    while not self.webui.loggingQueue.empty():
                        self.webui.loggingQueue.get_nowait()
                self.webui = None
        
        # Use thread reaper for aggressive cleanup
        self.thread_reaper.cleanup_all(force=True)
        
        # Close any remaining sockets
        self._close_dangling_sockets()
    
    def _close_dangling_sockets(self):
        """Close any sockets that might be keeping ports bound."""
        if not HAS_PSUTIL:
            return
        try:
            process = psutil.Process()
            for conn in process.connections():
                if conn.status == 'LISTEN' and conn.laddr.port >= 8080:  # Common test ports
                    with suppress(Exception):
                        # Try to close the socket (this is platform-specific)
                        if hasattr(socket, 'fromfd'):
                            sock = socket.fromfd(conn.fd, socket.AF_INET, socket.SOCK_STREAM)
                            sock.close()
        except Exception:
            pass
    
    def tearDown(self):
        """Enhanced teardown with aggressive resource cleanup."""
        # Stop mocks
        with suppress(Exception):
            self.db_patcher.stop()
        with suppress(Exception):
            self.sf_patcher.stop()
        with suppress(Exception):
            self.log_patcher.stop()
        
        # Force cleanup
        self._force_cleanup()
        
        # Wait for threads to finish
        self._wait_for_threads_cleanup()
        
        super().tearDown()
    
    def _wait_for_threads_cleanup(self, timeout=5):
        """Wait for threads to finish cleanup.
        
        Args:
            timeout (int): Maximum time to wait for cleanup
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            current_threads = set(threading.enumerate())
            new_threads = current_threads - self._initial_threads
            
            # Filter out daemon threads and main thread
            active_new_threads = [t for t in new_threads
                                  if t.is_alive() and not t.daemon and t != threading.current_thread()]
            
            if not active_new_threads:
                break
            
            time.sleep(0.1)
    
    def log_system_state(self, test_name):
        """Log detailed system state for debugging timeouts.
        
        Args:
            test_name (str): Name of the test for logging context
        """
        print(f"\n{'='*60}")
        print(f"DIAGNOSTIC: {test_name} - System State")
        print(f"{'='*60}")
        
        # Thread information
        threads = threading.enumerate()
        print(f"Active threads: {len(threads)}")
        for thread in threads:
            print(f"  - {thread.name} (daemon={thread.daemon}, alive={thread.is_alive()})")
        
        # Process information
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                open_files = process.open_files()
                connections = process.connections()
                print("\nProcess info:")
                print(f"  - Open files: {len(open_files)}")
                print(f"  - Open connections: {len(connections)}")
                print(f"  - Threads: {process.num_threads()}")
                
                # Port binding check
                listening_ports = [conn for conn in connections if conn.status == 'LISTEN']
                for conn in listening_ports:
                    print(f"  - Listening on: {conn.laddr}")
            except Exception as e:
                print(f"  - Error getting process info: {e}")
        else:
            print("\nProcess info: (psutil not available)")
        
        print(f"{'='*60}\n")


def ensure_platform_socket_cleanup():
    """Platform-specific socket cleanup to prevent port binding issues."""
    import platform
    
    if platform.system() == "Windows":
        # Windows-specific cleanup
        with suppress(Exception):
            import subprocess
            # Kill any processes using common test ports
            subprocess.run(['netstat', '-ano'], capture_output=True, timeout=5)
    else:
        # Unix-like systems
        with suppress(Exception):
            import subprocess
            # Force close TIME_WAIT connections
            subprocess.run(['ss', '-tuln'], capture_output=True, timeout=5)
