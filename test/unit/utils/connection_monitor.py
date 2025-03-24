import socket
import logging
import psutil
import os
import time
from contextlib import contextmanager


class ConnectionMonitor:
    """Utility class to help monitor and manage network connections during tests."""
    
    @staticmethod
    def get_open_connections():
        """Get information about all currently open socket connections for this process."""
        proc = psutil.Process(os.getpid())
        return [conn for conn in proc.connections(kind='inet')]
    
    @staticmethod
    def close_all_connections(exclude_ports=None):
        """Attempt to close all open connections.
        
        Args:
            exclude_ports (list): Ports to exclude from closing
            
        Returns:
            int: Number of connections closed
        """
        if exclude_ports is None:
            exclude_ports = []
        
        closed_count = 0
        connections = ConnectionMonitor.get_open_connections()
        
        for conn in connections:
            try:
                # Skip connections we want to exclude
                if conn.laddr.port in exclude_ports or conn.raddr and conn.raddr.port in exclude_ports:
                    continue
                
                if conn.status != psutil.CONN_CLOSED and hasattr(conn, 'fd') and conn.fd is not None:
                    try:
                        sock = socket.fromfd(conn.fd, socket.AF_INET, socket.SOCK_STREAM)
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                        closed_count += 1
                    except (OSError, socket.error) as e:
                        logging.debug(f"Error closing socket: {e}")
            except (AttributeError, ValueError) as e:
                logging.debug(f"Error accessing connection: {e}")
                
        return closed_count
    
    @staticmethod
    @contextmanager
    def monitor_connections():
        """Context manager to monitor connections created during a test."""
        before = set((c.laddr, c.raddr) for c in ConnectionMonitor.get_open_connections() if c.raddr)
        
        yield
        
        time.sleep(0.1)  # Give connections a moment to be established
        
        after = set((c.laddr, c.raddr) for c in ConnectionMonitor.get_open_connections() if c.raddr)
        new_connections = after - before
        
        if new_connections:
            logging.info(f"New connections created: {len(new_connections)}")
            for conn in new_connections:
                logging.debug(f"Connection: {conn[0]} -> {conn[1]}")
