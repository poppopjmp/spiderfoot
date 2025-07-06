"""
Validation Utilities for SpiderFoot

This module provides validation and utility functions shared across
CLI, API, and WebUI components.
"""

import os
import sys
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Union


class ValidationUtils:
    """Validation and utility functions for SpiderFoot."""
    
    def __init__(self):
        """Initialize validation utilities."""
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
    
    @staticmethod
    def validate_python_version(min_version: Tuple[int, int] = (3, 9)) -> None:
        """
        Validate Python version meets minimum requirements.
        
        Args:
            min_version: Minimum required Python version as tuple
            
        Raises:
            SystemExit: If Python version is too old
        """
        if sys.version_info < min_version:
            version_str = ".".join(map(str, min_version))
            print(f"SpiderFoot requires Python {version_str} or higher.")
            sys.exit(-1)
    
    @staticmethod
    def validate_directory_exists(directory: str, name: str = "Directory") -> bool:
        """
        Validate that a directory exists.
        
        Args:
            directory: Path to directory
            name: Human-readable name for error messages
            
        Returns:
            True if directory exists, False otherwise
        """
        if not os.path.isdir(directory):
            logging.getLogger("spiderfoot.validation").error(f"{name} not found: {directory}")
            return False
        return True
    
    @staticmethod
    def validate_file_exists(file_path: str, name: str = "File") -> bool:
        """
        Validate that a file exists.
        
        Args:
            file_path: Path to file
            name: Human-readable name for error messages
            
        Returns:
            True if file exists, False otherwise
        """
        if not os.path.isfile(file_path):
            logging.getLogger("spiderfoot.validation").error(f"{name} not found: {file_path}")
            return False
        return True
    
    @staticmethod
    def parse_host_port(host_port: str, default_host: str = '127.0.0.1', 
                       default_port: int = 5001) -> Tuple[str, int]:
        """
        Parse host:port string into components.
        
        Args:
            host_port: String in format "host:port"
            default_host: Default host if not specified
            default_port: Default port if not specified
            
        Returns:
            Tuple of (host, port)
            
        Raises:
            ValueError: If format is invalid
        """
        if not host_port:
            return default_host, default_port
        
        if ':' not in host_port:
            raise ValueError(f"Invalid host:port format: {host_port}")
        
        try:
            host, port_str = host_port.split(':', 1)
            port = int(port_str)
            
            if port < 1 or port > 65535:
                raise ValueError(f"Port must be between 1 and 65535, got: {port}")
                
            return host, port
            
        except ValueError as e:
            raise ValueError(f"Invalid host:port format '{host_port}': {e}")
    
    @staticmethod
    def validate_scan_name(scan_name: str) -> str:
        """
        Validate and sanitize scan name.
        
        Args:
            scan_name: Raw scan name
            
        Returns:
            Sanitized scan name
            
        Raises:
            ValueError: If scan name is invalid
        """
        if not scan_name or not scan_name.strip():
            raise ValueError("Scan name cannot be empty")
        
        # Remove dangerous characters but allow spaces and common punctuation
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', scan_name.strip())
        
        if not sanitized:
            raise ValueError("Scan name contains only invalid characters")
        
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        return sanitized
    
    @staticmethod
    def validate_target(target: str) -> str:
        """
        Validate and sanitize scan target.
        
        Args:
            target: Raw target string
            
        Returns:
            Sanitized target
            
        Raises:
            ValueError: If target is invalid
        """
        if not target or not target.strip():
            raise ValueError("Target cannot be empty")
        
        sanitized = target.strip()
        
        # Basic length check
        if len(sanitized) > 500:
            raise ValueError("Target too long (max 500 characters)")
        
        return sanitized
    
    @staticmethod
    def validate_module_list(modules: Union[str, List[str]]) -> List[str]:
        """
        Validate and parse module list.
        
        Args:
            modules: Comma-separated string or list of module names
            
        Returns:
            List of valid module names
        """
        if isinstance(modules, str):
            module_list = [m.strip() for m in modules.split(',') if m.strip()]
        elif isinstance(modules, list):
            module_list = [str(m).strip() for m in modules if str(m).strip()]
        else:
            return []
        
        # Filter out empty strings and validate names
        valid_modules = []
        for module in module_list:
            if re.match(r'^[a-zA-Z0-9_]+$', module):
                valid_modules.append(module)
            else:
                logging.getLogger("spiderfoot.validation").warning(f"Invalid module name: {module}")
        
        return valid_modules
    
    @staticmethod
    def validate_event_types(event_types: Union[str, List[str]]) -> List[str]:
        """
        Validate and parse event types list.
        
        Args:
            event_types: Comma-separated string or list of event types
            
        Returns:
            List of valid event types
        """
        if isinstance(event_types, str):
            types_list = [t.strip() for t in event_types.split(',') if t.strip()]
        elif isinstance(event_types, list):
            types_list = [str(t).strip() for t in event_types if str(t).strip()]
        else:
            return []
        
        # Filter out empty strings and validate format
        valid_types = []
        for event_type in types_list:
            if re.match(r'^[A-Z_][A-Z0-9_]*$', event_type):
                valid_types.append(event_type)
            else:
                logging.getLogger("spiderfoot.validation").warning(f"Invalid event type: {event_type}")
        
        return valid_types
    
    @staticmethod
    def validate_output_format(output_format: str) -> str:
        """
        Validate output format.
        
        Args:
            output_format: Output format string
            
        Returns:
            Validated output format
            
        Raises:
            ValueError: If format is invalid
        """
        valid_formats = ['tab', 'csv', 'json', 'xlsx', 'gexf']
        
        if output_format.lower() not in valid_formats:
            raise ValueError(f"Invalid output format '{output_format}'. Valid formats: {', '.join(valid_formats)}")
        
        return output_format.lower()
    
    @staticmethod
    def validate_scan_id(scan_id: str) -> str:
        """
        Validate scan ID format.
        
        Args:
            scan_id: Scan ID string
            
        Returns:
            Validated scan ID
            
        Raises:
            ValueError: If scan ID is invalid
        """
        if not scan_id or not scan_id.strip():
            raise ValueError("Scan ID cannot be empty")
        
        # Scan IDs should be alphanumeric with possible hyphens/underscores
        sanitized = scan_id.strip()
        if not re.match(r'^[a-zA-Z0-9_-]+$', sanitized):
            raise ValueError(f"Invalid scan ID format: {scan_id}")
        
        return sanitized
    
    @staticmethod
    def clean_user_input(input_data: Union[str, List[str]]) -> Union[str, List[str]]:
        """
        Clean user input by escaping HTML and removing dangerous characters.
        
        Args:
            input_data: String or list of strings to clean
            
        Returns:
            Cleaned input data
        """
        import html
        
        if isinstance(input_data, str):
            cleaned = html.escape(input_data, True)
            cleaned = cleaned.replace("&amp;", "&").replace("&quot;", "\"")
            return cleaned
        
        elif isinstance(input_data, list):
            cleaned_list = []
            for item in input_data:
                if item:
                    cleaned = html.escape(str(item), True)
                    cleaned = cleaned.replace("&amp;", "&").replace("&quot;", "\"")
                    cleaned_list.append(cleaned)
                else:
                    cleaned_list.append("")
            return cleaned_list
        
        return input_data
    
    @staticmethod
    def validate_config_option(key: str, value: Any, config_descriptions: Dict[str, str]) -> bool:
        """
        Validate a configuration option.
        
        Args:
            key: Configuration key
            value: Configuration value
            config_descriptions: Dictionary of valid configuration keys
            
        Returns:
            True if valid, False otherwise
        """
        if key not in config_descriptions:
            logging.getLogger("spiderfoot.validation").warning(f"Unknown configuration key: {key}")
            return False
        
        # Basic type validation based on key patterns
        if key.startswith('_') and key.endswith('timeout'):
            try:
                timeout_val = int(value)
                if timeout_val < 0:
                    return False
            except (ValueError, TypeError):
                return False
        
        elif key.startswith('_') and 'thread' in key:
            try:
                thread_val = int(value)
                if thread_val < 1 or thread_val > 100:
                    return False
            except (ValueError, TypeError):
                return False
        
        elif key.startswith('_') and 'port' in key:
            try:
                port_val = int(value)
                if port_val < 1 or port_val > 65535:
                    return False
            except (ValueError, TypeError):
                return False
        
        return True
