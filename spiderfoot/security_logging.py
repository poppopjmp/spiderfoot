# -*- coding: utf-8 -*-
"""
Enhanced Error Handling and Security Logging for SpiderFoot
Provides comprehensive error handling, security event logging, and monitoring.
"""

import logging
import traceback
import time
import json
import sys
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
from pathlib import Path


class SecurityEventType(Enum):
    """Security event types for logging."""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_BREACH_ATTEMPT = "data_breach_attempt"
    SCAN_CREATED = "scan_created"
    SCAN_DELETED = "scan_deleted"
    CONFIG_CHANGED = "config_changed"
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"
    PERMISSION_DENIED = "permission_denied"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    CSRF_VIOLATION = "csrf_violation"


class SecurityLogger:
    """Enhanced security logging with structured events."""
    
    def __init__(self, log_file: str = None, console_output: bool = True):
        """Initialize security logger.
        
        Args:
            log_file: Path to security log file
            console_output: Whether to output to console
        """
        self.log_file = log_file or "logs/security.log"
        self.console_output = console_output
        
        # Create logs directory if it doesn't exist
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Set up logger
        self.logger = logging.getLogger('spiderfoot.security')
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # File handler for security events
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = logging.Formatter(
                '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def log_security_event(self, event_type: SecurityEventType, 
                          details: Dict[str, Any],
                          severity: str = 'INFO',
                          user_id: str = None,
                          ip_address: str = None,
                          user_agent: str = None) -> None:
        """Log a security event.
        
        Args:
            event_type: Type of security event
            details: Event details dictionary
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
            user_id: User identifier
            ip_address: Client IP address
            user_agent: User agent string
        """
        event_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type.value,
            'severity': severity,
            'user_id': user_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'details': details
        }
        
        # Remove None values
        event_data = {k: v for k, v in event_data.items() if v is not None}
        
        # Log as JSON for easy parsing
        log_message = json.dumps(event_data, separators=(',', ':'))
        
        # Log with appropriate level
        if severity == 'CRITICAL':
            self.logger.critical(log_message)
        elif severity == 'ERROR':
            self.logger.error(log_message)
        elif severity == 'WARNING':
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def log_login_attempt(self, username: str, success: bool, ip_address: str = None,
                         failure_reason: str = None) -> None:
        """Log login attempt.
        
        Args:
            username: Username used for login
            success: Whether login was successful
            ip_address: Client IP address
            failure_reason: Reason for login failure
        """
        if success:
            self.log_security_event(
                SecurityEventType.LOGIN_SUCCESS,
                {'username': username},
                severity='INFO',
                ip_address=ip_address
            )
        else:
            self.log_security_event(
                SecurityEventType.LOGIN_FAILURE,
                {'username': username, 'reason': failure_reason},
                severity='WARNING',
                ip_address=ip_address
            )
    
    def log_unauthorized_access(self, endpoint: str, user_id: str = None,
                               ip_address: str = None, reason: str = None) -> None:
        """Log unauthorized access attempt.
        
        Args:
            endpoint: Accessed endpoint
            user_id: User identifier
            ip_address: Client IP address
            reason: Reason for denial
        """
        self.log_security_event(
            SecurityEventType.UNAUTHORIZED_ACCESS,
            {'endpoint': endpoint, 'reason': reason},
            severity='WARNING',
            user_id=user_id,
            ip_address=ip_address
        )
    
    def log_rate_limit_exceeded(self, endpoint: str, limit_type: str,
                               user_id: str = None, ip_address: str = None) -> None:
        """Log rate limit exceeded event.
        
        Args:
            endpoint: Accessed endpoint
            limit_type: Type of rate limit (api, web, scan)
            user_id: User identifier
            ip_address: Client IP address
        """
        self.log_security_event(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            {'endpoint': endpoint, 'limit_type': limit_type},
            severity='WARNING',
            user_id=user_id,
            ip_address=ip_address
        )
    
    def log_suspicious_activity(self, activity_type: str, details: Dict[str, Any],
                               user_id: str = None, ip_address: str = None) -> None:
        """Log suspicious activity.
        
        Args:
            activity_type: Type of suspicious activity
            details: Activity details
            user_id: User identifier
            ip_address: Client IP address
        """
        event_details = {'activity_type': activity_type}
        event_details.update(details)
        
        self.log_security_event(
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            event_details,
            severity='ERROR',
            user_id=user_id,
            ip_address=ip_address
        )


class ErrorHandler:
    """Enhanced error handling with security considerations."""
    
    def __init__(self, security_logger: SecurityLogger = None):
        """Initialize error handler.
        
        Args:
            security_logger: Security logger instance
        """
        self.security_logger = security_logger or SecurityLogger()
        self.error_logger = logging.getLogger('spiderfoot.errors')
        
        # Set up error logger
        if not self.error_logger.handlers:
            handler = logging.FileHandler('logs/errors.log', encoding='utf-8')
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.error_logger.addHandler(handler)
            self.error_logger.setLevel(logging.ERROR)
    
    def handle_exception(self, e: Exception, context: Dict[str, Any] = None,
                        user_id: str = None, ip_address: str = None,
                        sanitize_output: bool = True) -> Dict[str, Any]:
        """Handle exception with logging and sanitization.
        
        Args:
            e: Exception to handle
            context: Additional context information
            user_id: User identifier
            ip_address: Client IP address
            sanitize_output: Whether to sanitize error output for security
            
        Returns:
            Sanitized error response
        """
        context = context or {}
        
        # Log the full error internally
        error_id = f"ERR_{int(time.time())}_{id(e)}"
        
        self.error_logger.error(
            f"Error ID: {error_id} | "
            f"Type: {type(e).__name__} | "
            f"Message: {str(e)} | "
            f"Context: {json.dumps(context)} | "
            f"Traceback: {traceback.format_exc()}"
        )
        
        # Check for security-related exceptions
        self._check_security_implications(e, context, user_id, ip_address)
        
        # Create sanitized response
        if sanitize_output:
            return self._create_sanitized_response(e, error_id)
        else:
            return {
                'error': True,
                'error_id': error_id,
                'type': type(e).__name__,
                'message': str(e),
                'context': context
            }
    
    def _check_security_implications(self, e: Exception, context: Dict[str, Any],
                                   user_id: str = None, ip_address: str = None) -> None:
        """Check if exception has security implications.
        
        Args:
            e: Exception to analyze
            context: Exception context
            user_id: User identifier
            ip_address: Client IP address
        """
        error_message = str(e).lower()
        error_type = type(e).__name__
        
        # SQL injection attempts
        if any(keyword in error_message for keyword in [
            'sql syntax', 'sqlite', 'postgresql', 'mysql', 'injection'
        ]):
            self.security_logger.log_security_event(
                SecurityEventType.SQL_INJECTION_ATTEMPT,
                {
                    'error_type': error_type,
                    'error_message': str(e)[:200],  # Truncate for logging
                    'context': context
                },
                severity='CRITICAL',
                user_id=user_id,
                ip_address=ip_address
            )
        
        # XSS attempts
        if any(keyword in error_message for keyword in [
            'script', 'javascript', 'xss', 'onclick', 'onerror'
        ]):
            self.security_logger.log_security_event(
                SecurityEventType.XSS_ATTEMPT,
                {
                    'error_type': error_type,
                    'error_message': str(e)[:200],
                    'context': context
                },
                severity='ERROR',
                user_id=user_id,
                ip_address=ip_address
            )
        
        # Permission/access errors
        if error_type in ['PermissionError', 'AccessDenied', 'Forbidden']:
            self.security_logger.log_security_event(
                SecurityEventType.PERMISSION_DENIED,
                {
                    'error_type': error_type,
                    'context': context
                },
                severity='WARNING',
                user_id=user_id,
                ip_address=ip_address
            )
    
    def _create_sanitized_response(self, e: Exception, error_id: str) -> Dict[str, Any]:
        """Create sanitized error response for public consumption.
        
        Args:
            e: Exception
            error_id: Internal error ID
            
        Returns:
            Sanitized error response
        """
        # Map specific exceptions to user-friendly messages
        error_mappings = {
            'ValidationError': 'Invalid input provided',
            'AuthenticationError': 'Authentication required',
            'PermissionError': 'Access denied',
            'RateLimitError': 'Rate limit exceeded',
            'DatabaseError': 'Database operation failed',
            'NetworkError': 'Network operation failed',
            'ConfigurationError': 'Configuration error',
            'TimeoutError': 'Operation timed out'
        }
        
        error_type = type(e).__name__
        
        # Use mapped message or generic message
        if error_type in error_mappings:
            message = error_mappings[error_type]
        else:
            message = 'An internal error occurred'
        
        return {
            'error': True,
            'error_id': error_id,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }


class SecurityMonitor:
    """Security monitoring and alerting."""
    
    def __init__(self, security_logger: SecurityLogger = None):
        """Initialize security monitor.
        
        Args:
            security_logger: Security logger instance
        """
        self.security_logger = security_logger or SecurityLogger()
        self.alert_thresholds = {
            'failed_logins': {'count': 5, 'window': 300},  # 5 failures in 5 minutes
            'rate_limit_violations': {'count': 10, 'window': 600},  # 10 violations in 10 minutes
            'unauthorized_access': {'count': 3, 'window': 300},  # 3 attempts in 5 minutes
        }
        self.event_cache = {}
    
    def track_security_event(self, event_type: SecurityEventType, 
                           identifier: str = None) -> bool:
        """Track security event and check for alert conditions.
        
        Args:
            event_type: Type of security event
            identifier: Event identifier (e.g., IP address, user ID)
            
        Returns:
            True if alert threshold exceeded
        """
        current_time = int(time.time())
        event_key = f"{event_type.value}_{identifier or 'global'}"
        
        # Initialize event tracking
        if event_key not in self.event_cache:
            self.event_cache[event_key] = []
        
        # Add current event
        self.event_cache[event_key].append(current_time)
        
        # Clean old events
        threshold_config = self._get_threshold_config(event_type)
        if threshold_config:
            cutoff_time = current_time - threshold_config['window']
            self.event_cache[event_key] = [
                t for t in self.event_cache[event_key] if t > cutoff_time
            ]
            
            # Check if threshold exceeded
            if len(self.event_cache[event_key]) >= threshold_config['count']:
                self._trigger_alert(event_type, identifier, 
                                  len(self.event_cache[event_key]))
                return True
        
        return False
    
    def _get_threshold_config(self, event_type: SecurityEventType) -> Optional[Dict[str, int]]:
        """Get alert threshold configuration for event type.
        
        Args:
            event_type: Security event type
            
        Returns:
            Threshold configuration or None
        """
        mapping = {
            SecurityEventType.LOGIN_FAILURE: 'failed_logins',
            SecurityEventType.RATE_LIMIT_EXCEEDED: 'rate_limit_violations',
            SecurityEventType.UNAUTHORIZED_ACCESS: 'unauthorized_access',
        }
        
        threshold_key = mapping.get(event_type)
        return self.alert_thresholds.get(threshold_key)
    
    def _trigger_alert(self, event_type: SecurityEventType, identifier: str,
                      event_count: int) -> None:
        """Trigger security alert.
        
        Args:
            event_type: Type of security event
            identifier: Event identifier
            event_count: Number of events that triggered alert
        """
        self.security_logger.log_security_event(
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            {
                'alert_type': 'threshold_exceeded',
                'triggering_event': event_type.value,
                'identifier': identifier,
                'event_count': event_count,
                'action': 'automatic_alert'
            },
            severity='CRITICAL'
        )
        
        # Additional alert actions could be implemented here
        # (e.g., send email, webhook, block IP, etc.)


# Global instances for easy access
security_logger = SecurityLogger()
error_handler = ErrorHandler(security_logger)
security_monitor = SecurityMonitor(security_logger)


def log_security_event(event_type: SecurityEventType, details: Dict[str, Any],
                      severity: str = 'INFO', **kwargs) -> None:
    """Convenience function to log security events.
    
    Args:
        event_type: Type of security event
        details: Event details
        severity: Event severity
        **kwargs: Additional parameters for logging
    """
    security_logger.log_security_event(event_type, details, severity, **kwargs)


def handle_error(e: Exception, **kwargs) -> Dict[str, Any]:
    """Convenience function to handle errors.
    
    Args:
        e: Exception to handle
        **kwargs: Additional parameters for error handling
        
    Returns:
        Sanitized error response
    """
    return error_handler.handle_exception(e, **kwargs)
