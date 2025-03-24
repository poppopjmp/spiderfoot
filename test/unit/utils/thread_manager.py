import threading
import time
import logging

class ThreadManager:
    """Utility class to help monitor and manage threads in tests."""
    
    @staticmethod
    def get_thread_info():
        """Get information about all currently running threads."""
        threads = threading.enumerate()
        return {
            'count': len(threads),
            'threads': [{'name': t.name, 'daemon': t.daemon, 'alive': t.is_alive()} for t in threads]
        }
    
    @staticmethod
    def wait_for_threads_completion(timeout=2, exclude_thread_names=None):
        """Wait for all non-daemon threads to complete within timeout.
        
        Args:
            timeout (float): Maximum time to wait in seconds
            exclude_thread_names (list): Thread names to exclude from waiting
            
        Returns:
            bool: True if all threads completed, False if timeout reached
        """
        if exclude_thread_names is None:
            exclude_thread_names = []
            
        # Always exclude the current thread
        exclude_thread_names.append(threading.current_thread().name)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            active_threads = [t for t in threading.enumerate() 
                            if not t.daemon and t.is_alive() and t.name not in exclude_thread_names]
            
            if not active_threads:
                return True
                
            time.sleep(0.1)
            
        # If we get here, we've timed out
        active_threads = [t for t in threading.enumerate() 
                        if not t.daemon and t.is_alive() and t.name not in exclude_thread_names]
        if active_threads:
            logging.warning(f"Timed out waiting for threads: {[t.name for t in active_threads]}")
            return False
        
        return True
