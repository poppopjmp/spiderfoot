"""SpiderFoot Workflow Configuration.

Configuration management for workflow functionality, workspace settings,
and MCP integration.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any


class WorkflowConfig:
    """Configuration manager for SpiderFoot workflow functionality."""
    
    def __init__(self, config_file: str = None):
        """Initialize configuration.
        
        Args:
            config_file: Path to workflow configuration file
        """
        self.log = logging.getLogger("spiderfoot.workflow_config")
        
        # Default configuration
        self.default_config = {
            'workflow': {
                'max_concurrent_scans': 5,
                'scan_timeout': 3600,
                'correlation_enabled': True,
                'auto_correlation': True,
                'cleanup_on_completion': True,
                'progress_reporting': True
            },
            'workspace': {
                'default_retention_days': 90,
                'max_workspaces_per_user': 10,
                'auto_cleanup_enabled': True,
                'backup_enabled': False,
                'backup_interval_hours': 24
            },
            'mcp': {
                'enabled': False,
                'server_url': 'http://localhost:8000',
                'api_key': '',
                'timeout': 300,
                'retry_attempts': 3,
                'retry_delay': 5,
                'default_report_type': 'threat_assessment',
                'auto_generate_reports': False
            },
            'correlation': {
                'rules_enabled': [
                    'cross_scan_shared_infrastructure',
                    'cross_scan_similar_technologies', 
                    'cross_scan_threat_indicators'
                ],
                'confidence_threshold': 75,
                'risk_threshold': 'MEDIUM',
                'max_results_per_rule': 100,
                'parallel_processing': True
            },
            'export': {
                'default_format': 'json',
                'include_raw_data': True,
                'compress_exports': False,
                'max_export_size_mb': 100
            },
            'api': {
                'enabled': False,
                'host': '127.0.0.1',
                'port': 5001,
                'debug': False,
                'auth_required': False,
                'rate_limit_enabled': True,
                'rate_limit_per_minute': 60
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file_enabled': True,
                'file_path': 'logs/workflow.log',
                'max_file_size_mb': 10,
                'backup_count': 5
            }
        }
        
        self.config = self.default_config.copy()
        self.config_file = config_file or self._get_default_config_file()
        
        # Load configuration
        self.load_config()
    
    def _get_default_config_file(self) -> str:
        """Get default configuration file path."""
        # Use new standard config directory first
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'workflow.conf'),
            'spiderfoot_workflow.conf',
            '~/.spiderfoot/workflow.conf',
            '/etc/spiderfoot/workflow.conf',
            os.path.join(os.path.dirname(__file__), 'workflow.conf')
        ]
        for path in possible_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                return expanded_path
        # Return new config path as default
        return os.path.expanduser(possible_paths[0])
    
    def load_config(self):
        """Load configuration from file."""
        if not os.path.exists(self.config_file):
            self.log.info(f"Configuration file not found: {self.config_file}")
            self.log.info("Using default configuration")
            return
        
        try:
            with open(self.config_file, 'r') as f:
                file_config = json.load(f)
            
            # Merge with default configuration
            self._merge_config(self.config, file_config)
            self.log.info(f"Loaded configuration from: {self.config_file}")
            
        except Exception as e:
            self.log.error(f"Failed to load configuration: {e}")
            self.log.info("Using default configuration")
    
    def save_config(self):
        """Save configuration to file."""
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            self.log.info(f"Saved configuration to: {self.config_file}")
            
        except Exception as e:
            self.log.error(f"Failed to save configuration: {e}")
            raise
    
    def _merge_config(self, base: dict, update: dict):
        """Recursively merge configuration dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key.
        
        Args:
            key: Configuration key (e.g., 'workflow.max_concurrent_scans')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set configuration value by dot notation key.
        
        Args:
            key: Configuration key (e.g., 'workflow.max_concurrent_scans')
            value: Value to set
        """
        keys = key.split('.')
        config = self.config
        
        # Navigate to parent of target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def get_workflow_config(self) -> Dict[str, Any]:
        """Get workflow-specific configuration."""
        return self.config.get('workflow', {})
    
    def get_workspace_config(self) -> Dict[str, Any]:
        """Get workspace-specific configuration."""
        return self.config.get('workspace', {})
    
    def get_mcp_config(self) -> Dict[str, Any]:
        """Get MCP-specific configuration."""
        return self.config.get('mcp', {})
    
    def get_correlation_config(self) -> Dict[str, Any]:
        """Get correlation-specific configuration."""
        return self.config.get('correlation', {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API-specific configuration."""
        return self.config.get('api', {})
    
    def is_mcp_enabled(self) -> bool:
        """Check if MCP integration is enabled."""
        return self.get('mcp.enabled', False)
    
    def is_api_enabled(self) -> bool:
        """Check if API is enabled."""
        return self.get('api.enabled', False)
    
    def is_correlation_enabled(self) -> bool:
        """Check if correlation is enabled."""
        return self.get('workflow.correlation_enabled', True)
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of errors.
        
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Validate workflow settings
        max_scans = self.get('workflow.max_concurrent_scans')
        if not isinstance(max_scans, int) or max_scans < 1:
            errors.append("workflow.max_concurrent_scans must be a positive integer")
        
        timeout = self.get('workflow.scan_timeout')
        if not isinstance(timeout, int) or timeout < 60:
            errors.append("workflow.scan_timeout must be at least 60 seconds")
        
        # Validate MCP settings if enabled
        if self.is_mcp_enabled():
            server_url = self.get('mcp.server_url')
            if not server_url or not isinstance(server_url, str):
                errors.append("mcp.server_url is required when MCP is enabled")
            
            mcp_timeout = self.get('mcp.timeout')
            if not isinstance(mcp_timeout, int) or mcp_timeout < 10:
                errors.append("mcp.timeout must be at least 10 seconds")
        
        # Validate API settings if enabled
        if self.is_api_enabled():
            api_port = self.get('api.port')
            if not isinstance(api_port, int) or not (1024 <= api_port <= 65535):
                errors.append("api.port must be between 1024 and 65535")
        
        # Validate correlation settings
        confidence_threshold = self.get('correlation.confidence_threshold')
        if not isinstance(confidence_threshold, int) or not (0 <= confidence_threshold <= 100):
            errors.append("correlation.confidence_threshold must be between 0 and 100")
        
        return errors
    
    def create_sample_config(self, output_file: str = None):
        """Create a sample configuration file.
        
        Args:
            output_file: Path to output sample configuration
        """
        output_file = output_file or 'spiderfoot_workflow_sample.conf'
        
        sample_config = {
            "_comment": "SpiderFoot Workflow Configuration",
            "_version": "1.0",
            "workflow": {
                "_comment": "Workflow execution settings",
                "max_concurrent_scans": 3,
                "scan_timeout": 7200,
                "correlation_enabled": True,
                "auto_correlation": True,
                "cleanup_on_completion": True,
                "progress_reporting": True
            },
            "workspace": {
                "_comment": "Workspace management settings",
                "default_retention_days": 90,
                "max_workspaces_per_user": 10,
                "auto_cleanup_enabled": True,
                "backup_enabled": False,
                "backup_interval_hours": 24
            },
            "mcp": {
                "_comment": "Model Context Protocol integration settings",
                "enabled": False,
                "server_url": "http://localhost:8000",
                "api_key": "your-mcp-api-key-here",
                "timeout": 300,
                "retry_attempts": 3,
                "retry_delay": 5,
                "default_report_type": "threat_assessment",
                "auto_generate_reports": False
            },
            "correlation": {
                "_comment": "Cross-correlation analysis settings",
                "rules_enabled": [
                    "cross_scan_shared_infrastructure",
                    "cross_scan_similar_technologies",
                    "cross_scan_threat_indicators"
                ],
                "confidence_threshold": 75,
                "risk_threshold": "MEDIUM",
                "max_results_per_rule": 100,
                "parallel_processing": True
            },
            "export": {
                "_comment": "Data export settings",
                "default_format": "json",
                "include_raw_data": True,
                "compress_exports": False,
                "max_export_size_mb": 100
            },
            "api": {
                "_comment": "REST API settings",
                "enabled": False,
                "host": "127.0.0.1",
                "port": 5001,
                "debug": False,
                "auth_required": False,
                "rate_limit_enabled": True,
                "rate_limit_per_minute": 60
            },
            "logging": {
                "_comment": "Logging configuration",
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file_enabled": True,
                "file_path": "logs/workflow.log",
                "max_file_size_mb": 10,
                "backup_count": 5
            }
        }
        
        try:
            with open(output_file, 'w') as f:
                json.dump(sample_config, f, indent=2)
            
            print(f"Sample configuration created: {output_file}")
            print("\nKey configuration sections:")
            print("- workflow: Controls scan execution and correlation")
            print("- mcp: Model Context Protocol for CTI report generation")
            print("- api: REST API for programmatic access")
            print("- correlation: Cross-scan analysis settings")
            print("\nEdit the configuration file and enable desired features.")
            
        except Exception as e:
            self.log.error(f"Failed to create sample configuration: {e}")
            raise
    
    def setup_logging(self):
        """Set up logging based on configuration."""
        log_config = self.config.get('logging', {})
        
        # Configure root logger
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        logging.basicConfig(level=log_level, format=log_format)
        
        # Configure file logging if enabled
        if log_config.get('file_enabled', True):
            log_file = log_config.get('file_path', 'logs/workflow.log')
            
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Set up rotating file handler
            try:
                from logging.handlers import RotatingFileHandler
                
                max_bytes = log_config.get('max_file_size_mb', 10) * 1024 * 1024
                backup_count = log_config.get('backup_count', 5)
                
                file_handler = RotatingFileHandler(
                    log_file, maxBytes=max_bytes, backupCount=backup_count
                )
                file_handler.setFormatter(logging.Formatter(log_format))
                
                # Add to workflow loggers
                for logger_name in ['spiderfoot.workflow', 'spiderfoot.workspace', 'spiderfoot.mcp']:
                    logger = logging.getLogger(logger_name)
                    logger.addHandler(file_handler)
                
            except Exception as e:
                self.log.warning(f"Failed to set up file logging: {e}")


def load_workflow_config(config_file: str = None) -> WorkflowConfig:
    """Load workflow configuration.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        WorkflowConfig instance
    """
    return WorkflowConfig(config_file)


def create_sample_config(output_file: str = None):
    """Create a sample workflow configuration file.
    
    Args:
        output_file: Path to output sample configuration
    """
    config = WorkflowConfig()
    config.create_sample_config(output_file)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'create-sample':
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        create_sample_config(output_file)
    else:
        print("Usage: python workflow_config.py create-sample [output_file]")
