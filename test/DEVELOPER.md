# SpiderFoot Test Development Guide

## Overview

This guide explains how to develop effective tests for SpiderFoot, focusing on best practices to create stable, maintainable tests.

## Test Utilities

SpiderFoot includes several utilities to make testing easier:

### Base Classes

- **SpiderFootTestBase**: Base test class with cleanup for all tests
- **SpiderFootModuleTestBase**: Specialized base class for module tests

### Thread Management

- **ThreadManager**: Helps monitor and manage threads during tests
- **@safe_recursion**: Decorator to prevent infinite recursion in tests

### Network Mocking

- **ConnectionMonitor**: Tracks and closes network connections
- **RequestMock**: Simplifies HTTP request mocking

### Test Fixtures

- **test_fixtures.py**: Helper functions for common testing needs
- **cli_helper.py**: Utilities for testing command-line interfaces

## Writing Module Tests

### Basic Structure

```python
from test.unit.utils import SpiderFootModuleTestBase

class TestModuleExample(SpiderFootModuleTestBase):
    module_class = sfp_example  # The module class to test
    
    def test_watchedEvents(self):
        """Test the watchedEvents method."""
        events = self.module.watchedEvents()
        self.assertIsInstance(events, list)
        # Add specific assertions about events
    
    def test_producedEvents(self):
        """Test the producedEvents method."""
        events = self.module.producedEvents()
        self.assertIsInstance(events, list)
        # Add specific assertions about events
    
    def test_handleEvent(self):
        """Test the handleEvent method."""
        # Create a test event
        event = self.create_event('ROOT', 'example.com')
        
        # Set a target
        self.set_target('example.com')
        
        # Mock HTTP responses
        self.mock_module_response(
            data='{"result": "success"}',
            status=200
        )
        
        # Test event handling
        with self.assert_events_called(['EXAMPLE_OUTPUT']):
            self.module.handleEvent(event)
```

### Mocking HTTP Requests

```python
from test.unit.utils.request_mock import RequestMock

# Simple mock for a single response
self.mock_module_response(data=json_data, status=200)

# Complex mocking with multiple URLs
with RequestMock.mock_requests({
    r"https://api\.example\.com/v1/query.*": (
        '{"results": [{"name": "example"}]}', 
        200,
        {'Content-Type': 'application/json'}
    ),
    r"https://api\.example\.com/v1/error.*": (
        '{"error": "Access denied"}', 
        403
    )
}):
    self.module.handleEvent(event)
```

### Testing CLI Commands

```python
from test.unit.utils.cli_helper import CLIHelper

def test_cli_command():
    """Test a CLI command."""
    exit_code, stdout, stderr = CLIHelper.run_cli_command(
        my_command_function,
        args=["--option", "value"],
        stdin_input="yes\n"
    )
    
    assert exit_code == 0
    assert "Success" in stdout
    assert stderr == ""
```

## Running Tests

### Development Workflow

1. Create your test in the appropriate directory
2. Run the specific test during development:
   ```
   python -m pytest path/to/test_file.py -v
   ```
3. Run the full test suite before submitting:
   ```
   ./test/run
   ```
4. If tests hang, run in sequential mode:
   ```
   ./test/run --sequential
   ```
5. Check for memory issues:
   ```
   ./test/run --memory-check
   ```

### Debugging Tests

If you're experiencing issues with tests:

1. Use `ThreadManager` to identify thread leaks:
   ```python
   thread_info = ThreadManager.get_thread_info()
   print(f"Active threads: {thread_info['count']}")
   