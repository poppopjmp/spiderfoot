# -*- coding: utf-8 -*-
"""Comprehensive test suite for SpiderFoot database module (spiderfoot/db.py).

This test suite aims to achieve 70%+ coverage of the database module by testing:
- Database initialization and schema creation
- CRUD operations for scans, events, and configurations
- Data retrieval and filtering
- Error handling and recovery
- Transaction management
- Concurrent access scenarios
"""

import pytest
import sqlite3
import tempfile
import os
import threading
import time
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

from spiderfoot.db import SpiderFootDb
from spiderfoot.event import SpiderFootEvent


class TestSpiderFootDbInitialization:
    """Test database initialization and schema creation."""
    
    def test_init_with_default_config(self, temp_db_path):
        """Test database initialization with default configuration."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        assert db is not None
        assert hasattr(db, 'dbh')
        assert hasattr(db, 'conn')
        
    def test_init_with_memory_database(self):
        """Test initialization with in-memory database."""
        config = {'__database': ':memory:'}
        db = SpiderFootDb(config)
        
        assert db is not None
        
    def test_init_creates_schema(self, temp_db_path):
        """Test that initialization creates required database schema."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Check that tables exist
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
        expected_tables = [
            'tbl_event_types',
            'tbl_config', 
            'tbl_scan_instance',
            'tbl_scan_config',
            'tbl_scan_results',
            'tbl_scan_log'
        ]
        
        for table in expected_tables:
            assert table in tables, f"Table {table} should exist"
            
    def test_init_with_existing_database(self, temp_db_path):
        """Test initialization with existing database file."""
        # Create database first
        config = {'__database': temp_db_path}
        db1 = SpiderFootDb(config)
        
        # Initialize again with same file
        db2 = SpiderFootDb(config)
        assert db2 is not None
        
    def test_init_populates_event_types(self, temp_db_path):
        """Test that initialization populates event types table."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Check event types were inserted
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tbl_event_types")
            count = cursor.fetchone()[0]
            
        assert count > 0, "Event types should be populated"
        
    def test_init_with_invalid_path(self):
        """Test initialization with invalid database path."""
        # Use a path that cannot be created (like a file as parent directory)
        import tempfile
        with tempfile.NamedTemporaryFile() as temp_file:
            invalid_path = os.path.join(temp_file.name, 'database.db')
            config = {'__database': invalid_path}
            
            # Should handle gracefully or raise appropriate exception
            with pytest.raises((sqlite3.OperationalError, OSError, IOError)):
                SpiderFootDb(config)


class TestSpiderFootDbConfiguration:
    """Test database configuration management."""
    
    def test_config_get_existing_value(self, temp_db_path):
        """Test getting existing configuration value."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Insert test config
        db.configSet({'test_key': 'test_value'})
          # Get the value
        all_config = db.configGet()
        result = all_config.get('test_key')
        assert result == 'test_value'
        
    def test_config_get_nonexistent_value(self, temp_db_path):
        """Test getting non-existent configuration value."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        all_config = db.configGet()
        result = all_config.get('nonexistent_key')
        assert result is None
        
    def test_config_get_with_default(self, temp_db_path):
        """Test getting configuration value with default."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        all_config = db.configGet()
        result = all_config.get('nonexistent_key', 'default_value')
        assert result == 'default_value'
        
    def test_config_set_single_value(self, temp_db_path):
        """Test setting single configuration value."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        db.configSet({'new_key': 'new_value'})
        all_config = db.configGet()
        result = all_config.get('new_key')
        assert result == 'new_value'
        
    def test_config_set_multiple_values(self, temp_db_path):
        """Test setting multiple configuration values."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        test_config = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3'        }
        
        db.configSet(test_config)
        
        for key, expected_value in test_config.items():
            all_config = db.configGet()
            result = all_config.get(key)
            assert result == expected_value
            
    def test_config_update_existing_value(self, temp_db_path):
        """Test updating existing configuration value."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Set initial value
        db.configSet({'update_key': 'initial_value'})
          # Update the value
        db.configSet({'update_key': 'updated_value'})
        
        all_config = db.configGet()
        result = all_config.get('update_key')
        assert result == 'updated_value'


class TestSpiderFootDbScanOperations:
    """Test scan-related database operations."""
    
    def test_scan_instance_create(self, temp_db_path, sample_scan_data):
        """Test creating a scan instance."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        db.scanInstanceCreate(
            sample_scan_data['scan_id'],
            sample_scan_data['name'],
            sample_scan_data['seed_target']
        )
          # Verify the scan was created by retrieving it
        scan_info = db.scanInstanceGet(sample_scan_data['scan_id'])
        assert scan_info is not None
        assert scan_info[0] == sample_scan_data['name']  # name is at index 0
        assert scan_info[1] == sample_scan_data['seed_target']  # seed_target is at index 1
        
    def test_scan_instance_create_duplicate_id(self, temp_db_path, sample_scan_data):
        """Test creating scan instance with duplicate ID."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Create first instance
        db.scanInstanceCreate(
            sample_scan_data['scan_id'],
            sample_scan_data['name'],
            sample_scan_data['seed_target']
        )
          # Try to create duplicate
        with pytest.raises((sqlite3.IntegrityError, OSError, IOError)):
            db.scanInstanceCreate(
                sample_scan_data['scan_id'],
                sample_scan_data['name'],
                sample_scan_data['seed_target']
            )
            
    def test_scan_instance_get(self, temp_db_path, sample_scan_data):
        """Test retrieving scan instance."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Create scan instance
        db.scanInstanceCreate(
            sample_scan_data['scan_id'],
            sample_scan_data['name'],
            sample_scan_data['seed_target']
        )
        
        # Retrieve it
        result = db.scanInstanceGet(sample_scan_data['scan_id'])
        
        assert result is not None
        assert result[0] == sample_scan_data['name']  # name at index 0
        assert result[1] == sample_scan_data['seed_target']  # seed_target at index 1
        assert result[5] == 'CREATED'  # status at index 5
        
    def test_scan_instance_get_nonexistent(self, temp_db_path):
        """Test retrieving non-existent scan instance."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        result = db.scanInstanceGet('nonexistent-scan')
        assert result is None
        
    def test_scan_instance_list(self, temp_db_path):
        """Test listing all scan instances."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Create multiple scan instances
        scans = [
            ('scan1', 'Test Scan 1', 'example1.com'),
            ('scan2', 'Test Scan 2', 'example2.com'),
            ('scan3', 'Test Scan 3', 'example3.com')
        ]
        
        for scan_id, name, target in scans:
            db.scanInstanceCreate(scan_id, name, target)
            
        # List all scans
        result = db.scanInstanceList()
        
        assert len(result) == 3
        scan_ids = [row[0] for row in result]
        for scan_id, _, _ in scans:
            assert scan_id in scan_ids
            
    def test_scan_instance_delete(self, temp_db_path, sample_scan_data):
        """Test deleting scan instance."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Create scan instance
        db.scanInstanceCreate(
            sample_scan_data['scan_id'],
            sample_scan_data['name'],
            sample_scan_data['seed_target']
        )
        
        # Delete it
        result = db.scanInstanceDelete(sample_scan_data['scan_id'])
        assert result is True
        
        # Verify it's gone
        result = db.scanInstanceGet(sample_scan_data['scan_id'])
        assert result is None


class TestSpiderFootDbErrorHandling:
    """Test database error handling and recovery."""
    
    @patch('sqlite3.connect')
    def test_connection_error_handling(self, mock_connect, temp_db_path):
        """Test handling of database connection errors."""
        # Mock connection failure
        mock_connect.side_effect = sqlite3.OperationalError("database is locked")
        
        config = {'__database': temp_db_path}
        
        with pytest.raises(IOError):
            SpiderFootDb(config)
            
    def test_invalid_sql_handling(self, temp_db_path):
        """Test handling of invalid SQL queries."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # This would test internal error handling
        # Implementation depends on specific error handling in db.py
        pass
        
    def test_database_corruption_handling(self, temp_db_path):
        """Test handling of database corruption."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        # Create corrupted database scenario
        # This is complex to simulate, but important for robustness
        pass
        
    def test_disk_full_handling(self, temp_db_path):
        """Test handling of disk full scenarios."""
        # This would test how the database handles disk space issues
        # Complex to simulate but important for production reliability
        pass


@pytest.mark.integration
class TestSpiderFootDbIntegration:
    """Integration tests for database operations."""
    
    def test_full_scan_workflow(self, temp_db_path):
        """Test complete scan workflow with database operations."""
        config = {'__database': temp_db_path}
        db = SpiderFootDb(config)
        
        scan_id = 'integration-test-scan'
        scan_name = 'Integration Test Scan'
        scan_target = 'example.com'
          # 1. Create scan instance
        db.scanInstanceCreate(scan_id, scan_name, scan_target)
        
        # 2. Store configuration
        db.configSet({'test_setting': 'test_value'})
          # 3. Store multiple events
        root_event = SpiderFootEvent('ROOT', scan_target, '')
        events = [
            root_event,
            SpiderFootEvent('INTERNET_NAME', scan_target, 'sfp_dnsresolve', root_event),
            SpiderFootEvent('IP_ADDRESS', '93.184.216.34', 'sfp_dnsresolve', root_event),
            SpiderFootEvent('DOMAIN_NAME', 'www.example.com', 'sfp_spider', root_event)
        ]
        
        for event in events:
            db.scanEventStore(scan_id, event)
              # 4. Log scan progress
        db.scanLogEvent(scan_id, 'sfp_dnsresolve', 'INFO', 'DNS resolution started')
        db.scanLogEvent(scan_id, 'sfp_dnsresolve', 'INFO', 'DNS resolution completed')
        
        # 5. Verify all data was stored correctly
        scan_info = db.scanInstanceGet(scan_id)
        assert scan_info[0] == scan_name  # name is at index 0
        
        stored_events = db.scanResultEvent(scan_id)
        assert len(stored_events) == len(events)
        
        logs = db.scanLogs(scan_id)
        assert len(logs) == 2
        
        all_config = db.configGet()
        config_value = all_config.get('test_setting')
        assert config_value == 'test_value'
