import pytest
import unittest
import socket
from unittest.mock import patch, MagicMock
import psutil
from test.unit.utils.connection_monitor import ConnectionMonitor


class TestConnectionMonitor(unittest.TestCase):
    """Test ConnectionMonitor utility."""
    
    @patch('psutil.Process')
    def test_get_open_connections(self, mock_process):
        """Test get_open_connections returns the connections from psutil."""
        mock_conn = MagicMock()
        mock_process.return_value.connections.return_value = [mock_conn]
        
        connections = ConnectionMonitor.get_open_connections()
        
        mock_process.return_value.connections.assert_called_with(kind='inet')
        self.assertEqual(connections, [mock_conn])
    
    @patch('test.unit.utils.connection_monitor.ConnectionMonitor.get_open_connections')
    def test_close_all_connections_with_no_connections(self, mock_get_connections):
        """Test close_all_connections with no connections."""
        mock_get_connections.return_value = []
        
        closed = ConnectionMonitor.close_all_connections()
        
        self.assertEqual(closed, 0)
    
    @patch('socket.fromfd')
    @patch('test.unit.utils.connection_monitor.ConnectionMonitor.get_open_connections')
    def test_close_all_connections_with_connections(self, mock_get_connections, mock_socket_fromfd):
        """Test close_all_connections with connections."""
        # Create mock connections
        mock_conn1 = MagicMock()
        mock_conn1.status = psutil.CONN_ESTABLISHED
        mock_conn1.fd = 123
        mock_laddr = MagicMock()
        mock_laddr.port = 8000
        mock_conn1.laddr = mock_laddr
        mock_raddr = MagicMock()
        mock_raddr.port = 80
        mock_conn1.raddr = mock_raddr
        
        mock_get_connections.return_value = [mock_conn1]
        
        mock_socket = MagicMock()
        mock_socket_fromfd.return_value = mock_socket
        
        closed = ConnectionMonitor.close_all_connections()
        
        mock_socket.shutdown.assert_called_with(socket.SHUT_RDWR)
        mock_socket.close.assert_called_once()
        self.assertEqual(closed, 1)
    
    @patch('test.unit.utils.connection_monitor.ConnectionMonitor.get_open_connections')
    def test_monitor_connections_context_manager(self, mock_get_connections):
        """Test the monitor_connections context manager."""
        # Setup mock connections
        mock_conn_before = MagicMock()
        mock_conn_before.laddr = ('127.0.0.1', 1234)
        mock_conn_before.raddr = ('example.com', 80)
        
        mock_conn_after = MagicMock()
        mock_conn_after.laddr = ('127.0.0.1', 1234)
        mock_conn_after.raddr = ('example.com', 80)
        
        mock_conn_new = MagicMock()
        mock_conn_new.laddr = ('127.0.0.1', 5678)
        mock_conn_new.raddr = ('newsite.com', 80)
        
        mock_get_connections.side_effect = [
            [mock_conn_before],  # Before entering context
            [mock_conn_before, mock_conn_new]  # After exiting context
        ]
        
        with patch('time.sleep') as mock_sleep:  # Mock sleep to speed up test
            with ConnectionMonitor.monitor_connections():
                # Inside context
                pass
            
            mock_sleep.assert_called_with(0.1)
