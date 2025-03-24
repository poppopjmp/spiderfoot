# Tests

SpiderFoot includes various test suites.


## Unit and Integration Tests

Unit and integration tests require test dependencies to be installed:

```
pip3 install -r test/requirements.txt
```

To run the tests locally, run `./test/run` from the SpiderFoot root directory.

These tests are run on all pull requests automatically.

Module integration tests are excluded.

To run all unit and integration tests, including module integration tests, run:

```
python3 -m pytest -n auto --flake8 --dist loadfile --durations=5 --cov-report html --cov=. .
```


## Module Integration Tests

The module integration tests check module integration with remote third-party data sources.

To run the tests:

```
python3 -m pytest -n auto --flake8 --dist loadfile --durations=5 --cov-report html --cov=. test/integration/modules/
```


## Acceptance Tests

The acceptance tests check that the web intereface is working as
intended and that SpiderFooot is operating correctly as a whole.

These tests use a headless browser (Firefox by default), and
must be run with `./test/acceptance` as current working directory.

Requires SpiderFoot web server to be running on default port (`5001`).

Requires test dependencies to be installed:

```
pip3 install -r test/acceptance/requirements.txt
```

To run the tests, start the SpiderFoot web interface on the default port:

```
python3 ./sf.py -l 127.0.0.1:5001
```

Then run robot (override the `BROWSER` variable if necessary):

```
cd test/acceptance
robot --variable BROWSER:Firefox --outputdir results scan.robot
```

# SpiderFoot Testing Guide

## Overview

This document describes the testing infrastructure for SpiderFoot and best practices for writing tests.

## Running Tests

### Regular Parallel Testing

```bash
./test/run
```

### Sequential Testing (prevents test interactions)

```bash
./test/run --sequential
```

### Memory Profiling

```bash
./test/run --memory-check
```

## Test Structure

- `test/unit/`: Unit tests for individual components
- `test/integration/`: Integration tests involving multiple components
- `test/unit/utils/`: Utilities to help with testing

## Thread Management

Many SpiderFoot modules create threads, and tests need to handle these properly to avoid hangs:

1. Each test should use the `SpiderFootTestBase` base class to ensure proper cleanup
2. The `@safe_recursion` decorator prevents infinite loops in recursive functions
3. The `ThreadManager` utility helps monitor and manage threads during tests
4. The `ConnectionMonitor` utility helps manage network connections

## Writing Tests for Modules

Module tests should:

1. Inherit from `SpiderFootModuleTestBase`
2. Use `setUp()` and `tearDown()` to properly initialize and clean up
3. Mock external APIs and dependencies
4. Use `assert_events_called()` to verify event notifications

Example:

```python
@pytest.mark.usefixtures
class TestModuleExample(SpiderFootModuleTestBase):
    module_class = sfp_example
    
    def test_handleEvent(self):
        target = self.set_target('example.com')
        root_event = self.create_event('ROOT', 'example.com')
        
        # Mock API response
        self.mock_module_response({'data': 'example'}, 200)
        
        # Use context manager to capture events
        with self.assert_events_called(['EXAMPLE_EVENT']):
            self.module.handleEvent(root_event)
```

## Debugging Hanging Tests

When a test hangs, try:

1. Running it in sequential mode
2. Looking at thread dumps in the logs
3. Using the connection monitor to see open connections
4. Setting a lower timeout value
5. Adding more debug logging
