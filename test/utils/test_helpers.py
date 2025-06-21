# -*- coding: utf-8 -*-
"""Test helper utilities for SpiderFoot testing."""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional


class TestHelpers:
    """Collection of helper methods for testing."""
    
    @staticmethod
    def create_temp_file(content: str = "", suffix: str = ".txt") -> str:
        """Create a temporary file with content."""
        fd, path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
        except:
            os.close(fd)
            raise
        return path
    
    @staticmethod
    def create_temp_dir() -> str:
        """Create a temporary directory."""
        return tempfile.mkdtemp()
    
    @staticmethod
    def cleanup_temp_path(path: str):
        """Clean up temporary file or directory."""
        if os.path.isfile(path):
            os.unlink(path)
        elif os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
    
    @staticmethod
    def assert_dict_contains(actual: Dict, expected: Dict):
        """Assert that actual dict contains all key-value pairs from expected."""
        for key, value in expected.items():
            assert key in actual, f"Key '{key}' not found in actual dict"
            assert actual[key] == value, f"Expected {key}={value}, got {actual[key]}"
    
    @staticmethod
    def assert_list_contains_items(actual: List, expected_items: List):
        """Assert that actual list contains all expected items."""
        for item in expected_items:
            assert item in actual, f"Item '{item}' not found in actual list"
    
    @staticmethod
    def mock_module_config(module_class, config: Dict[str, Any]):
        """Mock module configuration."""
        mock_module = Mock(spec=module_class)
        mock_module.opts = config
        mock_module.tempStorage = Mock()
        mock_module.tempStorage.return_value = {}
        return mock_module


class MockSpiderFootModule:
    """Mock SpiderFoot module for testing."""
    
    def __init__(self, name: str = "test_module"):
        self.name = name
        self.opts = {}
        self.results = []
        self.errorState = False
        self.tempStorage = {}
        self.socket = None
        
    def info(self):
        """Module info."""
        return {
            'name': self.name,
            'cats': ['Test'],
            'group': 'Test',
            'flags': [],
            'desc': 'Test module',
            'website': 'https://example.com',
            'dataSource': 'Test Data Source'
        }
    
    def opts(self):
        """Module options."""
        return self.opts
        
    def setup(self, sfc, userOpts={}):
        """Setup module."""
        self.sf = sfc
        self.opts.update(userOpts)
        
    def enrichTarget(self, target):
        """Enrich target (placeholder)."""
        pass
        
    def handleEvent(self, event):
        """Handle event (placeholder)."""
        pass
        
    def checkForStop(self):
        """Check if module should stop."""
        return self.errorState
        
    def notifyListeners(self, event):
        """Notify event listeners."""
        self.results.append(event)


class DatabaseTestHelper:
    """Helper for database testing operations."""
    
    def __init__(self, db_instance):
        self.db = db_instance
        
    def insert_test_scan(self, scan_id: str = "test-scan", scan_name: str = "Test Scan"):
        """Insert a test scan record."""
        return self.db.scanInstanceCreate(scan_id, scan_name, "example.com")
        
    def insert_test_event(self, scan_id: str, event_type: str = "INTERNET_NAME", 
                         event_data: str = "example.com", module: str = "test_module"):
        """Insert a test event record."""
        from spiderfoot.event import SpiderFootEvent
        event = SpiderFootEvent(event_type, event_data, module)
        return self.db.scanEventStore(scan_id, event)
        
    def get_event_count(self, scan_id: str) -> int:
        """Get count of events for a scan."""
        events = self.db.scanResultEvent(scan_id)
        return len(events) if events else 0
        
    def cleanup_test_data(self, scan_id: str):
        """Clean up test data."""
        # Implementation would depend on database structure
        pass


class NetworkTestHelper:
    """Helper for network testing operations."""
    
    @staticmethod
    def mock_successful_response(content: str = "success", 
                                content_type: str = "text/html"):
        """Create a mock successful HTTP response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = content
        mock_response.content = content.encode()
        mock_response.headers = {'Content-Type': content_type}
        mock_response.raise_for_status = Mock()
        return mock_response
    
    @staticmethod  
    def mock_error_response(status_code: int = 404, content: str = "Not Found"):
        """Create a mock error HTTP response."""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.text = content
        mock_response.content = content.encode()
        mock_response.headers = {'Content-Type': 'text/plain'}
        
        def raise_for_status():
            if status_code >= 400:
                from requests import HTTPError
                raise HTTPError(f"{status_code} Error")
                
        mock_response.raise_for_status = raise_for_status
        return mock_response
    
    @staticmethod
    def mock_json_response(data: Dict):
        """Create a mock JSON HTTP response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = data
        mock_response.text = json.dumps(data)
        mock_response.content = json.dumps(data).encode()
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.raise_for_status = Mock()
        return mock_response


class AssertionHelpers:
    """Custom assertion helpers for SpiderFoot testing."""
    
    @staticmethod
    def assert_valid_event(event):
        """Assert that an event is valid."""
        assert event is not None, "Event should not be None"
        assert hasattr(event, 'eventType'), "Event should have eventType"
        assert hasattr(event, 'data'), "Event should have data"
        assert hasattr(event, 'module'), "Event should have module"
        assert hasattr(event, 'generated'), "Event should have generated timestamp"
        
    @staticmethod
    def assert_event_type(event, expected_type: str):
        """Assert event has expected type."""
        assert event.eventType == expected_type, f"Expected event type {expected_type}, got {event.eventType}"
        
    @staticmethod
    def assert_event_data(event, expected_data: str):
        """Assert event has expected data."""
        assert event.data == expected_data, f"Expected event data '{expected_data}', got '{event.data}'"
        
    @staticmethod
    def assert_module_called_with(mock_module, method_name: str, *args, **kwargs):
        """Assert that a mock module method was called with specific arguments."""
        method = getattr(mock_module, method_name)
        method.assert_called_with(*args, **kwargs)
        
    @staticmethod
    def assert_scan_results_count(db_helper, scan_id: str, expected_count: int):
        """Assert scan has expected number of results."""
        actual_count = db_helper.get_event_count(scan_id)
        assert actual_count == expected_count, f"Expected {expected_count} events, got {actual_count}"


class CoverageHelpers:
    """Helpers for coverage analysis and testing."""
    
    @staticmethod
    def get_uncovered_lines(module_path: str) -> List[int]:
        """Get list of uncovered line numbers for a module."""
        # This would integrate with coverage.py to analyze coverage
        # Implementation depends on coverage tooling setup
        return []
    
    @staticmethod
    def assert_minimum_coverage(module_path: str, minimum_percent: float):
        """Assert module has minimum coverage percentage."""
        # Implementation would check coverage and assert minimum
        pass
    
    @staticmethod
    def suggest_test_cases(module_path: str) -> List[str]:
        """Suggest test cases based on uncovered code."""
        # Implementation would analyze code and suggest tests
        return []


def pytest_configure():
    """Configure pytest with custom markers."""
    pytest.mark.slow = pytest.mark.slow
    pytest.mark.integration = pytest.mark.integration
    pytest.mark.unit = pytest.mark.unit
    pytest.mark.network = pytest.mark.network
    pytest.mark.database = pytest.mark.database


# Commonly used fixtures
@pytest.fixture
def test_helpers():
    """Provide TestHelpers instance."""
    return TestHelpers()


@pytest.fixture
def mock_spiderfoot_module():
    """Provide mock SpiderFoot module."""
    return MockSpiderFootModule()


@pytest.fixture
def network_helper():
    """Provide NetworkTestHelper instance."""
    return NetworkTestHelper()


@pytest.fixture
def assertion_helpers():
    """Provide AssertionHelpers instance."""
    return AssertionHelpers()


@pytest.fixture
def coverage_helpers():
    """Provide CoverageHelpers instance."""
    return CoverageHelpers()
