"""
Configuration Manager for SpiderFoot

This module provides centralized configuration management for all SpiderFoot components.
It handles default configurations, user overrides, and validation.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from copy import deepcopy

from spiderfoot import SpiderFootHelpers


class ConfigManager:
    """Centralized configuration management for SpiderFoot."""
    
    # Default configuration options
    DEFAULT_CONFIG = {
        '_debug': False,
        '_maxthreads': 3,
        '__logging': True,
        '__outputfilter': None,
        '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
        '_dnsserver': '',
        '_fetchtimeout': 5,
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '_genericusers': '',
        '__database': '',
        '__modules__': None,
        '__correlationrules__': None,
        '_socks1type': '',
        '_socks2addr': '',
        '_socks3port': '',
        '_socks4user': '',
        '_socks5pwd': '',
    }
    
    # Configuration descriptions
    CONFIG_DESCRIPTIONS = {
        '_debug': "Enable debugging?",
        '_maxthreads': "Max number of modules to run concurrently",
        '_useragent': "User-Agent string to use for HTTP requests. Prefix with an '@' to randomly select the User Agent from a file containing user agent strings for each request, e.g. @C:\\useragents.txt or @/home/bob/useragents.txt. Or supply a URL to load the list from there.",
        '_dnsserver': "Override the default resolver with another DNS server. For example, 8.8.8.8 is Google's open DNS server.",
        '_fetchtimeout': "Number of seconds before giving up on a HTTP request.",
        '_internettlds': "List of Internet TLDs.",
        '_internettlds_cache': "Hours to cache the Internet TLD list. This can safely be quite a long time given that the list doesn't change too often.",
        '_genericusers': "List of usernames that if found as usernames or as part of e-mail addresses, should be treated differently to non-generics.",
        '_socks1type': "SOCKS Server Type. Can be '4', '5', 'HTTP' or 'TOR'",
        '_socks2addr': 'SOCKS Server IP Address.',
        '_socks3port': 'SOCKS Server TCP Port. Usually 1080 for 4/5, 8080 for HTTP and 9050 for TOR.',
        '_socks4user': 'SOCKS Username. Valid only for SOCKS4 and SOCKS5 servers.',
        '_socks5pwd': "SOCKS Password. Valid only for SOCKS5 servers.",
        '_modulesenabled': "Modules enabled for the scan."
    }
    
    def __init__(self):
        """Initialize the configuration manager."""
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        self._config = deepcopy(self.DEFAULT_CONFIG)
        self._initialized = False
        
    def initialize(self) -> Dict[str, Any]:
        """
        Initialize configuration with runtime values.
        
        Returns:
            Dict containing the initialized configuration
        """
        try:
            # Initialize SpiderFootHelpers dependent configuration
            try:
                self._config['_genericusers'] = ",".join(
                    SpiderFootHelpers.usernamesFromWordlists(['generic-usernames'])
                )
                self._config['__database'] = f"{SpiderFootHelpers.dataPath()}/spiderfoot.db"
            except Exception as e:
                self.log.error(f"Failed to initialize SpiderFootHelpers configuration: {e}")
                # Use fallback values
                self._config['_genericusers'] = ""
                default_data_path = Path.home() / '.spiderfoot'
                default_data_path.mkdir(exist_ok=True)
                self._config['__database'] = str(default_data_path / 'spiderfoot.db')
            
            # Add configuration descriptions
            self._config['__globaloptdescs__'] = self.CONFIG_DESCRIPTIONS
            
            self._initialized = True
            self.log.info("Configuration initialized successfully")
            return deepcopy(self._config)
            
        except Exception as e:
            self.log.error(f"Failed to initialize configuration: {e}")
            raise
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current configuration.
        
        Returns:
            Dict containing the current configuration
        """
        if not self._initialized:
            return self.initialize()
        return deepcopy(self._config)
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
        """
        if not isinstance(updates, dict):
            raise TypeError("Updates must be a dictionary")
        
        self._config.update(updates)
        self.log.debug(f"Configuration updated with {len(updates)} changes")
    
    def validate_legacy_files(self) -> None:
        """
        Validate that legacy files are not present in the application directory.
        
        Raises:
            SystemExit: If legacy files are found
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check for legacy database files
        legacy_db_path = os.path.join(script_dir, '../../../spiderfoot.db')
        if os.path.exists(legacy_db_path):
            print(f"ERROR: spiderfoot.db file exists in {os.path.dirname(legacy_db_path)}")
            print("SpiderFoot no longer supports loading the spiderfoot.db database from the application directory.")
            print(f"The database is now loaded from your home directory: {SpiderFootHelpers.dataPath()}/spiderfoot.db")
            print(f"This message will go away once you move or remove spiderfoot.db from {os.path.dirname(legacy_db_path)}")
            raise SystemExit(-1)

        # Check for legacy passwd files
        legacy_passwd_path = os.path.join(script_dir, '../../../passwd')
        if os.path.exists(legacy_passwd_path):
            print(f"ERROR: passwd file exists in {os.path.dirname(legacy_passwd_path)}")
            print("SpiderFoot no longer supports loading credentials from the application directory.")
            print(f"The passwd file is now loaded from your home directory: {SpiderFootHelpers.dataPath()}/passwd")
            print(f"This message will go away once you move or remove passwd from {os.path.dirname(legacy_passwd_path)}")
            raise SystemExit(-1)
    
    def get_web_config(self, host: str = '127.0.0.1', port: int = 5001, 
                      root: str = '/', cors_origins: Optional[list] = None) -> Dict[str, Any]:
        """
        Get web server configuration.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            root: Root path
            cors_origins: CORS origins list
            
        Returns:
            Dict containing web server configuration
        """
        return {
            'host': host,
            'port': port,
            'root': root,
            'cors_origins': cors_origins or [],
        }
    
    def get_api_config(self, host: str = '127.0.0.1', port: int = 8001, 
                      workers: int = 1, log_level: str = 'info', 
                      reload: bool = False) -> Dict[str, Any]:
        """
        Get API server configuration.
        
        Args:
            host: Host to bind to
            port: Port to bind to  
            workers: Number of worker processes
            log_level: Logging level
            reload: Enable auto-reload
            
        Returns:
            Dict containing API server configuration
        """
        return {
            'host': host,
            'port': port,
            'workers': workers,
            'log_level': log_level,
            'reload': reload
        }
    
    def apply_command_line_args(self, args) -> None:
        """
        Apply command line arguments to configuration.
        
        Args:
            args: Parsed command line arguments
        """
        if hasattr(args, 'debug') and args.debug:
            self._config['_debug'] = True
            
        if hasattr(args, 'max_threads') and args.max_threads:
            self._config['_maxthreads'] = args.max_threads
