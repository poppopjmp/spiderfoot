#!/usr/bin/env python3
"""
Platform-Specific Utilities for SpiderFoot Tests
===============================================

Cross-platform compatibility layer for thread management,
process control, and resource cleanup.
"""

import sys
import os
import threading
import time
import signal
from contextlib import suppress
from typing import Any, Optional, List, Dict


class PlatformUtils:
    """Platform-specific utilities for cross-platform compatibility."""
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows."""
        return sys.platform == 'win32'
    
    @staticmethod
    def is_linux() -> bool:
        """Check if running on Linux."""
        return sys.platform.startswith('linux')
    
    @staticmethod
    def is_macos() -> bool:
        """Check if running on macOS."""
        return sys.platform == 'darwin'
    
    @staticmethod
    def is_unix() -> bool:
        """Check if running on Unix-like system."""
        return not PlatformUtils.is_windows()
    
    @staticmethod
    def get_platform_name() -> str:
        """Get human-readable platform name."""
        if PlatformUtils.is_windows():
            return "Windows"
        elif PlatformUtils.is_linux():
            return "Linux"
        elif PlatformUtils.is_macos():
            return "macOS"
        else:
            return f"Unknown ({sys.platform})"


class ThreadManager:
    """Platform-specific thread management utilities."""
    
    @staticmethod
    def set_thread_timeout(timeout_seconds: float):
        """
        Set up timeout for current thread (Unix only).
        
        Args:
            timeout_seconds: Timeout in seconds
        """
        if not PlatformUtils.is_unix():
            # signal.alarm not available on Windows
            return
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Thread timeout after {timeout_seconds} seconds")
        
        with suppress(AttributeError):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))
    
    @staticmethod
    def clear_thread_timeout():
        """Clear thread timeout (Unix only)."""
        if not PlatformUtils.is_unix():
            return
        
        with suppress(AttributeError):
            signal.alarm(0)
    
    @staticmethod
    def force_thread_termination(thread: threading.Thread, timeout: float = 5.0) -> bool:
        """
        Force thread termination with platform-specific methods.
        
        Args:
            thread: Thread to terminate
            timeout: Timeout for graceful termination
            
        Returns:
            True if thread was terminated successfully
        """
        if not thread.is_alive():
            return True
        
        # Step 1: Try graceful join first
        thread.join(timeout=timeout)
        
        if not thread.is_alive():
            return True
        
        # Step 2: Platform-specific force termination
        if PlatformUtils.is_windows():
            return ThreadManager._force_windows_thread_termination(thread)
        else:
            return ThreadManager._force_unix_thread_termination(thread)
    
    @staticmethod
    def _force_windows_thread_termination(thread: threading.Thread) -> bool:
        """Force thread termination on Windows."""
        try:
            import ctypes
            
            # Get thread handle
            thread_id = thread.ident
            if not thread_id:
                return False
            
            # Try to terminate the thread (dangerous, but sometimes necessary)
            kernel32 = ctypes.windll.kernel32
            thread_handle = kernel32.OpenThread(0x0001, False, thread_id)
            
            if thread_handle:
                result = kernel32.TerminateThread(thread_handle, 0)
                kernel32.CloseHandle(thread_handle)
                return bool(result)
        
        except Exception:
            pass
        
        return False
    
    @staticmethod
    def _force_unix_thread_termination(thread: threading.Thread) -> bool:
        """Force thread termination on Unix systems."""
        try:
            # On Unix, we can try sending signals
            thread_id = thread.ident
            if not thread_id:
                return False
            
            # Try SIGTERM first, then SIGKILL
            with suppress(Exception):
                os.kill(thread_id, signal.SIGTERM)
                time.sleep(0.1)
                
                if not thread.is_alive():
                    return True
                
                os.kill(thread_id, signal.SIGKILL)
                time.sleep(0.1)
                
                return not thread.is_alive()
        
        except Exception:
            pass
        
        return False
    
    @staticmethod
    def get_thread_stack_trace(thread: threading.Thread) -> Optional[str]:
        """
        Get stack trace for a thread (if possible).
        
        Args:
            thread: Thread to get stack trace for
            
        Returns:
            Stack trace string or None
        """
        try:
            import sys
            import traceback
            
            frame = sys._current_frames().get(thread.ident)
            if frame:
                return ''.join(traceback.format_stack(frame))
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def list_thread_details() -> List[Dict[str, Any]]:
        """
        Get detailed information about all threads.
        
        Returns:
            List of thread information dictionaries
        """
        thread_details = []
        
        for thread in threading.enumerate():
            details = {
                'name': thread.name,
                'ident': thread.ident,
                'is_alive': thread.is_alive(),
                'daemon': thread.daemon,
                'class': thread.__class__.__name__
            }
            
            # Add stack trace if available
            stack_trace = ThreadManager.get_thread_stack_trace(thread)
            if stack_trace:
                details['stack_trace'] = stack_trace
            
            thread_details.append(details)
        
        return thread_details


class ProcessManager:
    """Platform-specific process management utilities."""
    
    @staticmethod
    def get_process_info() -> Dict[str, Any]:
        """
        Get information about current process.
        
        Returns:
            Process information dictionary
        """
        info = {
            'pid': os.getpid(),
            'platform': PlatformUtils.get_platform_name(),
            'python_version': sys.version,
            'thread_count': threading.active_count()
        }
        
        try:
            import psutil
            process = psutil.Process()
            
            info.update({
                'memory_rss': process.memory_info().rss,
                'memory_vms': process.memory_info().vms,
                'cpu_percent': process.cpu_percent(),
                'open_files': len(process.open_files()),
                'connections': len(process.connections())
            })
        except ImportError:
            # psutil not available
            pass
        except Exception:
            # Error getting process info
            pass
        
        return info
    
    @staticmethod
    def emergency_process_termination():
        """
        Emergency process termination as last resort.
        
        WARNING: This will terminate the entire process!
        """
        print("🚨 EMERGENCY: Performing process termination")
        print("This is a last resort to prevent infinite hanging")
        
        # Brief pause for any cleanup
        time.sleep(0.1)
        
        # Platform-specific termination
        if PlatformUtils.is_windows():
            os._exit(1)
        else:
            # On Unix, try SIGTERM first, then SIGKILL
            try:
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(1.0)
                os.kill(os.getpid(), signal.SIGKILL)
            except Exception:
                os._exit(1)
    
    @staticmethod
    def set_process_timeout(timeout_seconds: float):
        """
        Set a process-wide timeout (Unix only).
        
        Args:
            timeout_seconds: Timeout in seconds
        """
        if not PlatformUtils.is_unix():
            return
        
        def timeout_handler(signum, frame):
            print(f"🚨 Process timeout after {timeout_seconds} seconds")
            ProcessManager.emergency_process_termination()
        
        with suppress(AttributeError):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))


class FileManager:
    """Platform-specific file management utilities."""
    
    @staticmethod
    def force_close_file_handles():
        """
        Force close leaked file handles (if possible).
        
        Returns:
            Number of handles closed
        """
        closed = 0
        
        try:
            import psutil
            process = psutil.Process()
            
            # Get open files
            open_files = process.open_files()
            
            # Try to close files that look like temp files or logs
            for file_info in open_files:
                file_path = file_info.path
                
                # Skip system files and important files
                if any(keyword in file_path.lower() for keyword in [
                    'temp', 'tmp', 'log', 'cache', '.pyc'
                ]):
                    try:
                        # This is dangerous - only do in test environment
                        fd = file_info.fd
                        os.close(fd)
                        closed += 1
                    except Exception:
                        pass
        
        except ImportError:
            # psutil not available
            pass
        except Exception:
            # Error occurred
            pass
        
        return closed
    
    @staticmethod
    def get_temp_directory() -> str:
        """Get platform-appropriate temporary directory."""
        if PlatformUtils.is_windows():
            return os.environ.get('TEMP', r'C:\temp')
        else:
            return '/tmp'
    
    @staticmethod
    def cleanup_temp_files(pattern: str = "spiderfoot*"):
        """
        Clean up temporary files matching pattern.
        
        Args:
            pattern: File pattern to match
        """
        import glob
        
        temp_dir = FileManager.get_temp_directory()
        pattern_path = os.path.join(temp_dir, pattern)
        
        try:
            temp_files = glob.glob(pattern_path)
            cleaned = 0
            
            for temp_file in temp_files:
                try:
                    if os.path.isfile(temp_file):
                        os.remove(temp_file)
                        cleaned += 1
                    elif os.path.isdir(temp_file):
                        os.rmdir(temp_file)
                        cleaned += 1
                except Exception:
                    pass
            
            if cleaned > 0:
                print(f"🧹 Cleaned up {cleaned} temporary files")
        
        except Exception:
            pass


class NetworkManager:
    """Platform-specific network management utilities."""
    
    @staticmethod
    def find_free_port(start_port: int = 8000, end_port: int = 9000) -> int:
        """
        Find a free port for testing.
        
        Args:
            start_port: Start of port range
            end_port: End of port range
            
        Returns:
            Free port number
        """
        import socket
        
        for port in range(start_port, end_port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(('127.0.0.1', port))
                    return port
            except OSError:
                continue
        
        # If no free port found, return a high number
        return 8888
    
    @staticmethod
    def force_close_sockets():
        """
        Force close leaked sockets (if possible).
        
        Returns:
            Number of sockets closed
        """
        closed = 0
        
        try:
            import psutil
            process = psutil.Process()
            
            # Get connections
            connections = process.connections()
            
            for conn in connections:
                try:
                    # Only close local test connections
                    if (conn.laddr and conn.laddr.ip == '127.0.0.1' and
                        conn.laddr.port >= 8000):
                        # This is dangerous - only in test environment
                        if hasattr(conn, 'close'):
                            conn.close()
                            closed += 1
                except Exception:
                    pass
        
        except ImportError:
            # psutil not available
            pass
        except Exception:
            pass
        
        return closed


def get_platform_specific_cleanup_strategy() -> Dict[str, callable]:
    """
    Get platform-specific cleanup strategy.
    
    Returns:
        Dict mapping cleanup type to function
    """
    strategy = {
        'threads': ThreadManager.force_thread_termination,
        'files': FileManager.force_close_file_handles,
        'sockets': NetworkManager.force_close_sockets,
        'temp_files': FileManager.cleanup_temp_files
    }
    
    # Add platform-specific strategies
    if PlatformUtils.is_windows():
        strategy['process_timeout'] = lambda: None  # Not available on Windows
    else:
        strategy['process_timeout'] = ProcessManager.set_process_timeout
    
    return strategy


def perform_platform_cleanup() -> Dict[str, int]:
    """
    Perform comprehensive platform-specific cleanup.
    
    Returns:
        Dict mapping cleanup type to count of items cleaned
    """
    print(f"🧹 Performing platform-specific cleanup on {PlatformUtils.get_platform_name()}")
    
    results = {}
    
    # Clean up temp files
    FileManager.cleanup_temp_files()
    results['temp_files'] = 1
    
    # Close file handles
    closed_files = FileManager.force_close_file_handles()
    results['file_handles'] = closed_files
    
    # Close sockets
    closed_sockets = NetworkManager.force_close_sockets()
    results['sockets'] = closed_sockets
    
    # Force garbage collection
    import gc
    gc.collect()
    results['gc_collected'] = 1
    
    return results
