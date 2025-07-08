#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Error Handling and Logging System for SpiderFoot

This module provides comprehensive error handling, logging, and monitoring
capabilities for production SpiderFoot deployments.
"""

import logging
import logging.handlers
import sys
import traceback
import functools
import time
import threading
from typing import Optional, Any, Dict, List, Callable
from datetime import datetime
import json
import os
from pathlib import Path


class SpiderFootErrorHandler:
    """Enhanced error handling for SpiderFoot operations."""
    
    def __init__(self, logger_name: str = "spiderfoot"):
        self.logger = logging.getLogger(logger_name)
        self.error_counts = {}
        self.lock = threading.Lock()
        
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Global exception handler."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.logger.critical(f"Uncaught exception: {error_msg}")
        
        # Track error frequency
        with self.lock:
            error_key = str(exc_type.__name__)
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
    
    def retry_with_backoff(self, max_retries: int = 3, base_delay: float = 1.0):
        """Decorator for retrying operations with exponential backoff."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt == max_retries:
                            self.logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                            raise
                        
                        delay = base_delay * (2 ** attempt)
                        self.logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                
                raise last_exception
            return wrapper
        return decorator
    
    def safe_execute(self, func: Callable, *args, default_return=None, **kwargs):
        """Safely execute a function with error handling."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error executing {func.__name__}: {e}", exc_info=True)
            return default_return


class SpiderFootLogger:
    """Enhanced logging system for SpiderFoot."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.loggers = {}
        self.setup_logging()
        
    def setup_logging(self):
        """Setup comprehensive logging configuration."""
        log_level = self.config.get('log_level', 'INFO').upper()
        log_dir = Path(self.config.get('log_dir', 'logs'))
        log_dir.mkdir(exist_ok=True)
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'spiderfoot.log',
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=10
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'spiderfoot_errors.log',
            maxBytes=25 * 1024 * 1024,  # 25MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        # JSON structured logging for critical events
        json_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'spiderfoot_structured.jsonl',
            maxBytes=25 * 1024 * 1024,
            backupCount=5
        )
        json_handler.setLevel(logging.WARNING)
        json_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(json_handler)
        
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger instance."""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
            
        if hasattr(record, 'scanId'):
            log_entry['scan_id'] = record.scanId
            
        if hasattr(record, 'module_name'):
            log_entry['spiderfoot_module'] = record.module_name
            
        return json.dumps(log_entry)


class SecurityAuditLogger:
    """Security-focused audit logging."""
    
    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.setup_audit_logger()
        
    def setup_audit_logger(self):
        """Setup security audit logging."""
        self.audit_logger = logging.getLogger('spiderfoot.security.audit')
        self.audit_logger.setLevel(logging.INFO)
        
        # Dedicated audit log file
        audit_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'security_audit.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=20
        )
        
        audit_formatter = logging.Formatter(
            '%(asctime)s - AUDIT - %(levelname)s - %(message)s'
        )
        audit_handler.setFormatter(audit_formatter)
        self.audit_logger.addHandler(audit_handler)
        
    def log_authentication(self, username: str, success: bool, ip_address: str = None):
        """Log authentication attempts."""
        status = "SUCCESS" if success else "FAILURE"
        message = f"Authentication {status} for user '{username}'"
        if ip_address:
            message += f" from IP {ip_address}"
        self.audit_logger.info(message)
        
    def log_api_access(self, endpoint: str, method: str, user: str = None, ip_address: str = None):
        """Log API access."""
        message = f"API {method} {endpoint}"
        if user:
            message += f" by user '{user}'"
        if ip_address:
            message += f" from IP {ip_address}"
        self.audit_logger.info(message)
        
    def log_configuration_change(self, setting: str, old_value: str, new_value: str, user: str = None):
        """Log configuration changes."""
        message = f"Configuration change: {setting} changed from '{old_value}' to '{new_value}'"
        if user:
            message += f" by user '{user}'"
        self.audit_logger.warning(message)
        
    def log_security_event(self, event_type: str, description: str, severity: str = "INFO"):
        """Log security events."""
        log_level = getattr(logging, severity.upper(), logging.INFO)
        self.audit_logger.log(log_level, f"SECURITY_EVENT: {event_type} - {description}")


class PerformanceMonitor:
    """Monitor and log performance metrics."""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger('spiderfoot.performance')
        self.metrics = {}
        self.lock = threading.Lock()
        
    def time_function(self, func_name: str = None):
        """Decorator to time function execution."""
        def decorator(func):
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.record_timing(name, duration)
            return wrapper
        return decorator
        
    def record_timing(self, operation: str, duration: float):
        """Record timing for an operation."""
        with self.lock:
            if operation not in self.metrics:
                self.metrics[operation] = []
            self.metrics[operation].append(duration)
            
            # Log slow operations
            if duration > 5.0:  # 5 seconds threshold
                self.logger.warning(f"Slow operation detected: {operation} took {duration:.2f}s")
                
    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance summary statistics."""
        summary = {}
        with self.lock:
            for operation, timings in self.metrics.items():
                if timings:
                    summary[operation] = {
                        'count': len(timings),
                        'total_time': sum(timings),
                        'avg_time': sum(timings) / len(timings),
                        'min_time': min(timings),
                        'max_time': max(timings)
                    }
        return summary


class HealthChecker:
    """System health monitoring."""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger('spiderfoot.health')
        self.checks = []
        
    def add_check(self, name: str, check_func: Callable[[], bool], critical: bool = False):
        """Add a health check."""
        self.checks.append({
            'name': name,
            'func': check_func,
            'critical': critical
        })
        
    def run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        for check in self.checks:
            try:
                status = check['func']()
                results['checks'][check['name']] = {
                    'status': 'healthy' if status else 'unhealthy',
                    'critical': check['critical']
                }
                
                if not status:
                    if check['critical']:
                        results['overall_status'] = 'critical'
                    elif results['overall_status'] == 'healthy':
                        results['overall_status'] = 'degraded'
                        
            except Exception as e:
                self.logger.error(f"Health check '{check['name']}' failed: {e}")
                results['checks'][check['name']] = {
                    'status': 'error',
                    'error': str(e),
                    'critical': check['critical']
                }
                
                if check['critical']:
                    results['overall_status'] = 'critical'
                elif results['overall_status'] == 'healthy':
                    results['overall_status'] = 'degraded'
                    
        return results


def setup_enhanced_logging(config: Dict[str, Any] = None) -> SpiderFootLogger:
    """Setup enhanced logging for SpiderFoot."""
    logger_system = SpiderFootLogger(config)
    
    # Install global exception handler
    error_handler = SpiderFootErrorHandler()
    sys.excepthook = error_handler.handle_exception
    
    # Setup threading exception handler
    def thread_exception_handler(args):
        error_handler.logger.critical(f"Thread exception: {args.exc_value}", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    
    threading.excepthook = thread_exception_handler
    
    return logger_system


# Example usage and initialization
if __name__ == "__main__":
    # Example configuration
    config = {
        'log_level': 'DEBUG',
        'log_dir': 'logs'
    }
    
    # Setup logging
    logger_system = setup_enhanced_logging(config)
    logger = logger_system.get_logger('spiderfoot.example')
    
    # Setup security audit logging
    audit_logger = SecurityAuditLogger()
    
    # Setup performance monitoring
    perf_monitor = PerformanceMonitor()
    
    # Example usage
    @perf_monitor.time_function("example_operation")
    def example_function():
        time.sleep(0.1)
        return "completed"
    
    # Test logging
    logger.info("Enhanced logging system initialized")
    audit_logger.log_security_event("SYSTEM_START", "Enhanced logging system started")
    
    result = example_function()
    logger.info(f"Example function result: {result}")
    
    # Show performance summary
    summary = perf_monitor.get_performance_summary()
    logger.info(f"Performance summary: {summary}")
