# SpiderFoot Logging System

The SpiderFoot logging system provides a centralized, thread-safe approach to logging across the entire application. This document explains how to use the logging system properly in SpiderFoot modules and other components.

## Overview

SpiderFoot's logging system is based on Python's built-in `logging` module but includes several enhancements:

- Thread-safe logging implementation
- Centralized log handling through a queue-based approach
- Support for multiple log formats and destinations
- Seamless integration with SpiderFoot modules through base class

## Logging in SpiderFoot Modules

### Using the Base Class Methods

All SpiderFoot modules inherit from `SpiderFootPlugin`, which provides logging methods. You should always use these methods for logging:

```python
def handleEvent(self, event):
    # Log a debug message
    self.debug("Processing event data")
    
    # Log an informational message
    self.info("Found interesting information")
    
    # Log an error
    self.error("An error occurred during processing")
```

### Migration from Old Logging Style

If you have modules using the old logging style with `log = get_module_logger(__name__)`, you should migrate them to use the base class methods.

Old style:
```python
from spiderfoot.logconfig import get_module_logger
log = get_module_logger(__name__)

class sfp_example(SpiderFootPlugin):
    def handleEvent(self, event):
        log.debug("Processing event")
```

New style:
```python
# Module now uses the logging from the SpiderFootPlugin base class

class sfp_example(SpiderFootPlugin):
    def handleEvent(self, event):
        self.debug("Processing event")
```

## Log Levels

SpiderFoot supports these log levels:

- `self.debug()`: Detailed information for debugging
- `self.info()`: General informational messages
- `self.error()`: Error messages
- `self.status()`: Status updates (internally handled as INFO level)

## Additional Context

The logging system automatically adds context to log messages:

- Module name (from class name)
- Scan ID (when available)
- Source file and line number (in debug logs)

## Configuration

Logging can be configured through the SpiderFoot options:

- `_debug`: Enable debug logging when true
- `__logging`: Disable all logging when false

## Log Destinations

By default, logs are sent to:

1. Console (stderr)
2. Debug log file (`spiderfoot.debug.log`)
3. Error log file (`spiderfoot.error.log`) 
4. Syslog-format file (`spiderfoot.syslog.log`)
5. SQLite database (for scan-specific logs)
6. ElasticSearch (optional)

## Migration Script

To migrate your modules to the new logging system, use the provided script:

```bash
python scripts/migrate_logging.py
```

Add `--dry-run` to see what changes would be made without modifying files.
