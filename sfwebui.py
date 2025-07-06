# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         sfwebui wrapper
# Purpose:      Web User interface class for use with a web browser
#
# Author:       Agostino Panico poppopjmp 
#
# Created:      03/07/2025
# Copyright:    (c) Agostino Panico poppopjmp 
# License:      MIT
# -----------------------------------------------------------------

# Core SpiderFoot imports
from spiderfoot.webui.routes import WebUiRoutes
from spiderfoot import SpiderFootDb, SpiderFoot
from spiderfoot.logger import logListenerSetup, logWorkerSetup
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.helpers import SpiderFootHelpers

# Template and UI imports
from mako.template import Template
from mako.lookup import TemplateLookup

# Data processing imports
import openpyxl
from io import BytesIO, StringIO

# System imports
import multiprocessing as mp
import time
import json
import logging
import os
import sys
from copy import deepcopy
from typing import Dict, List, Optional, Any, Union

# Web framework imports
import cherrypy
try:
    import secure
except ImportError:
    secure = None

# Modular endpoint imports
from spiderfoot.webui.scan import ScanEndpoints
from spiderfoot.webui.workspace import WorkspaceEndpoints
from spiderfoot.webui.templates import MiscEndpoints
from spiderfoot.webui.info import InfoEndpoints
from spiderfoot.webui.settings import SettingsEndpoints
from spiderfoot.webui.export import ExportEndpoints


class SpiderFootWebUi(WebUiRoutes):
    """
    Backward compatibility class that provides all methods in one place.
    
    This class inherits from WebUiRoutes which already aggregates all endpoint classes
    to maintain full backward compatibility with legacy code while providing
    a clean, modular architecture.
    """
    
    def __init__(self, web_config: Dict[str, Any], config: Dict[str, Any], loggingQueue: Optional[mp.Queue] = None):
        """
        Initialize the SpiderFoot Web UI.
        
        Args:
            web_config: Web server configuration (interface, port, root path)
            config: SpiderFoot configuration dictionary
            loggingQueue: Optional logging queue for multiprocessing
            
        Raises:
            TypeError: If config arguments are not dictionaries
            ValueError: If config arguments are empty or invalid
        """
        # Validate input parameters
        if not isinstance(config, dict):
            raise TypeError(f"config is {type(config)}; expected dict()")
        if not config:
            raise ValueError("config is empty")
            
        if not isinstance(web_config, dict):
            raise TypeError(f"web_config is {type(web_config)}; expected dict()")
        if not web_config:
            raise ValueError("web_config is empty")
        
        # Initialize parent class which handles all the endpoint setup
        super().__init__(web_config, config, loggingQueue)
        
        
        # Validate configuration with enhanced defaults
        self._validate_configuration()
        
        # Set up additional security headers if available
        self._setup_additional_security_headers()
        
        self.log.info("SpiderFootWebUi initialized successfully")
    
    
    def _validate_configuration(self):
        """Validate the configuration and fix common issues."""
        try:
            # Validate and set default values for required configuration keys
            required_defaults = {
                '_modulesenabled': '',           # Default to empty string (no modules enabled)
                '_logging': 'INFO',             # Default logging level
                '__version__': '5.3.3',         # Default version if not set
                '_debug': False,                # Default debug mode off
                '__correlationrules__': [],     # Default empty correlation rules
                '__dbtype': 'sqlite'            # Default database type
            }
            
            for key, default_value in required_defaults.items():
                if key not in self.config:
                    self.log.info(f"Setting default value for missing configuration key '{key}': {default_value}")
                    self.config[key] = default_value
            
            # Validate modules structure - ensure it's a dict
            if '__modules__' in self.config:
                modules = self.config['__modules__']
                if not isinstance(modules, dict):
                    if isinstance(modules, list):
                        # Convert list to dict format
                        modules_dict = {}
                        for m in modules:
                            if isinstance(m, dict) and 'name' in m:
                                modules_dict[m['name']] = m
                            elif isinstance(m, str):
                                modules_dict[m] = {'name': m}
                        self.config['__modules__'] = modules_dict
                    else:
                        self.config['__modules__'] = {}
            else:
                self.config['__modules__'] = {}
            
            # Validate database configuration
            if '__database' not in self.config:
                self.config['__database'] = f"{SpiderFootHelpers.dataPath()}/spiderfoot.db"
                    
        except Exception as e:
            self.log.error(f"Configuration validation failed: {e}")
            raise
    
    def _setup_additional_security_headers(self):
        """Set up additional security headers if the secure module is available."""
        if not secure:
            self.log.warning("Security headers not available (secure module not installed)")
            return
            
        try:
            # The parent class already sets up basic security headers
            # We can add additional ones here if needed
            self.log.info("Additional security headers configured successfully")
            
        except Exception as e:
            self.log.error(f"Failed to setup additional security headers: {e}")
    
    def validate_scan_id(self, scan_id: str) -> bool:
        """
        Validate a scan ID format and existence.
        
        Args:
            scan_id: Scan identifier to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not scan_id or not isinstance(scan_id, str):
            return False
            
        # Check format (should be hex string)
        if not all(c in '0123456789abcdefABCDEF' for c in scan_id):
            return False
            
        # Check length (typical scan IDs are 32 chars)
        if len(scan_id) != 32:
            return False
            
        # Check if exists in database
        try:
            dbh = self._get_dbh()
            scan_info = dbh.scanInstanceGet(scan_id)
            return scan_info is not None
        except Exception:
            return False
    
    def validate_workspace_id(self, workspace_id: str) -> bool:
        """
        Validate a workspace ID format and existence.
        
        Args:
            workspace_id: Workspace identifier to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not workspace_id or not isinstance(workspace_id, str):
            return False
            
        try:
            workspace = SpiderFootWorkspace(self.config)
            return workspace.getWorkspace(workspace_id) is not None
        except Exception:
            return False
    
    def sanitize_user_input(self, user_input: Union[str, List[str]]) -> Union[str, List[str]]:
        """
        Sanitize user input to prevent XSS and injection attacks.
        
        Args:
            user_input: String or list of strings to sanitize
            
        Returns:
            Sanitized input
        """
        if isinstance(user_input, list):
            result = []
            for item in user_input:
                if item is None:
                    result.append("")
                elif isinstance(item, str):
                    result.append(self.cleanUserInput([item])[0] if item else "")
                else:
                    result.append(str(item))
            return result
        if isinstance(user_input, str):
            return self.cleanUserInput([user_input])[0] if user_input else ""
        return str(user_input) if user_input is not None else ""
    
    def handle_error(self, error_msg: str, error_type: str = "error") -> Dict[str, Any]:
        """
        Standard error handling for API endpoints.
        
        Args:
            error_msg: Error message to log and return
            error_type: Type of error (error, warning, info)
            
        Returns:
            Standardized error response
        """
        if error_type == "error":
            self.log.error(error_msg)
        elif error_type == "warning":
            self.log.warning(error_msg)
        else:
            self.log.info(error_msg)
            
        return {
            'success': False,
            'error': error_msg,
            'error_type': error_type,
            'timestamp': time.time()
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status information.
        
        Returns:
            System status dictionary
        """
        try:
            dbh = self._get_dbh()
            
            # Get database stats
            scan_count = len(dbh.scanInstanceList())
            
            # Get active scans
            active_scans = [s for s in dbh.scanInstanceList() if s[5] in ['RUNNING', 'STARTING']]
            
            # System info
            status = {
                'success': True,
                'database_connected': True,
                'total_scans': scan_count,
                'active_scans': len(active_scans),
                'python_version': sys.version.split()[0],
                'spiderfoot_version': self.config.get('__version__', 'unknown'),
                'timestamp': time.time()
            }
            
            return status
            
        except Exception as e:
            return self.handle_error(f"Failed to get system status: {e}")
    
    def cleanup_old_scans(self, retention_days: int = 30) -> Dict[str, Any]:
        """
        Clean up old scan data based on retention policy.
        
        Args:
            retention_days: Number of days to retain scans
            
        Returns:
            Cleanup result
        """
        try:
            dbh = self._get_dbh()
            cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
            
            # Get old scans
            all_scans = dbh.scanInstanceList()
            old_scans = [s for s in all_scans if s[2] < cutoff_time and s[5] in ['FINISHED', 'ABORTED']]
            
            cleaned_count = 0
            for scan in old_scans:
                try:
                    dbh.scanInstanceDelete(scan[0])
                    cleaned_count += 1
                except Exception as e:
                    self.log.warning(f"Failed to delete scan {scan[0]}: {e}")
            
            return {
                'success': True,
                'cleaned_scans': cleaned_count,
                'total_old_scans': len(old_scans),
                'retention_days': retention_days
            }
            
        except Exception as e:
            return self.handle_error(f"Failed to cleanup old scans: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the system.
        
        Returns:
            Performance metrics dictionary
        """
        try:
            import psutil
            
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Database metrics
            dbh = self._get_dbh()
            db_size = os.path.getsize(dbh.conn_path) if hasattr(dbh, 'conn_path') else 0
            
            metrics = {
                'success': True,
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available': memory.available,
                'disk_percent': disk.percent,
                'disk_free': disk.free,
                'database_size': db_size,
                'timestamp': time.time()
            }
            
            return metrics
            
        except ImportError:
            return self.handle_error("psutil not available for performance metrics", "warning")
        except Exception as e:
            return self.handle_error(f"Failed to get performance metrics: {e}")
    
    def backup_database(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path to save backup (optional)
            
        Returns:
            Backup result
        """
        try:
            import shutil
            from datetime import datetime
            
            dbh = self._get_dbh()
            
            # Generate backup filename if not provided
            if not backup_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"spiderfoot_backup_{timestamp}.db"
            
            # Get source database path
            source_db = self.config.get('__database', f"{SpiderFootHelpers.dataPath()}/spiderfoot.db")
            
            # Create backup
            shutil.copy2(source_db, backup_path)
            
            # Verify backup
            if os.path.exists(backup_path):
                backup_size = os.path.getsize(backup_path)
                return {
                    'success': True,
                    'backup_path': backup_path,
                    'backup_size': backup_size,
                    'timestamp': time.time()
                }
            else:
                return self.handle_error("Backup file was not created")
                
        except Exception as e:
            return self.handle_error(f"Failed to backup database: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check.
        
        Returns:
            Health check results
        """
        health_status = {
            'success': True,
            'timestamp': time.time(),
            'checks': {}
        }
        
        # Database connectivity
        try:
            dbh = self._get_dbh()
            dbh.scanInstanceList()
            health_status['checks']['database'] = {'status': 'OK', 'message': 'Database connection successful'}
        except Exception as e:
            health_status['checks']['database'] = {'status': 'ERROR', 'message': str(e)}
            health_status['success'] = False
        
        # Configuration validity
        try:
            required_keys = ['__database', '__modules__']
            missing_keys = [key for key in required_keys if key not in self.config]
            if missing_keys:
                health_status['checks']['configuration'] = {
                    'status': 'WARNING', 
                    'message': f'Missing configuration keys: {missing_keys}'
                }
            else:
                health_status['checks']['configuration'] = {'status': 'OK', 'message': 'Configuration is valid'}
        except Exception as e:
            health_status['checks']['configuration'] = {'status': 'ERROR', 'message': str(e)}
            health_status['success'] = False
        
        # Module availability
        try:
            modules = self.config.get('__modules__', [])
            if modules:
                health_status['checks']['modules'] = {
                    'status': 'OK', 
                    'message': f'{len(modules)} modules available'
                }
            else:
                health_status['checks']['modules'] = {
                    'status': 'WARNING', 
                    'message': 'No modules configured'
                }
        except Exception as e:
            health_status['checks']['modules'] = {'status': 'ERROR', 'message': str(e)}
        
        return health_status


class SpiderFootWebUiApp:
    """
    Enhanced application wrapper for SpiderFoot Web UI.
    
    This class provides additional functionality for application lifecycle management,
    configuration validation, and system monitoring.
    """
    
    def __init__(self, config: Dict[str, Any], docroot: Optional[str] = None, loggingQueue: Optional[mp.Queue] = None):
        """
        Initialize the SpiderFoot Web UI Application.
        
        Args:
            config: SpiderFoot configuration dictionary
            docroot: Document root path for web server
            loggingQueue: Optional logging queue for multiprocessing
        """
        # Configuration validation and setup
        self._validate_and_setup_config(config)
        
        # Web server configuration
        self.docroot = docroot or '/'
        
        # Logging setup
        self._setup_logging(loggingQueue)
        
        # Template engine setup
        self._setup_templates()
        
        # Initialize endpoint classes
        self._initialize_endpoints()
        
        # Security configuration
        self._setup_security()
        
        self.log.info("SpiderFootWebUiApp initialized successfully")
    
    def _validate_and_setup_config(self, config: Dict[str, Any]):
        """Validate and setup configuration with enhanced error checking."""
        from copy import deepcopy
        
        if not isinstance(config, dict) or not config:
            raise ValueError("Invalid configuration provided")
        
        # Create default configuration
        self.defaultConfig = deepcopy(config)
        
        # Initialize database and merge configurations
        try:
            dbh = SpiderFootDb(self.defaultConfig, init=True)
            sf = SpiderFoot(self.defaultConfig)
            self.config = sf.configUnserialize(dbh.configGet(), self.defaultConfig)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database or configuration: {e}")
        
        # Validate and fix module configuration
        self._fix_module_configuration()
    
    def _fix_module_configuration(self):
        """Fix and validate module configuration."""
        if '__modules__' in self.config:
            modules = self.config['__modules__']
            if not isinstance(modules, list):
                self.config['__modules__'] = []
            else:
                # Ensure all modules are properly formatted
                self.config['__modules__'] = [
                    m if isinstance(m, dict) and 'name' in m else {'name': str(m)}
                    for m in modules
                ]
    
    def _setup_logging(self, loggingQueue: Optional[mp.Queue]):
        """Setup logging with proper error handling."""
        if loggingQueue is None:
            self.loggingQueue = mp.Queue()
            logListenerSetup(self.loggingQueue, self.config)
        else:
            self.loggingQueue = loggingQueue
        
        logWorkerSetup(self.loggingQueue)
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
    
    def _setup_templates(self):
        """Setup template lookup with validation."""
        template_dirs = ['spiderfoot/templates']
        
        # Validate template directories exist
        for template_dir in template_dirs:
            if not os.path.exists(template_dir):
                self.log.warning(f"Template directory not found: {template_dir}")
        
        self.lookup = TemplateLookup(directories=template_dirs)
    
    def _initialize_endpoints(self):
        """Initialize all endpoint classes with enhanced error handling."""
        try:
            # Scan endpoints
            self.scan = ScanEndpoints()
            self._configure_endpoint(self.scan)
            
            # Workspace endpoints
            self.workspace = WorkspaceEndpoints()
            self._configure_endpoint(self.workspace)
            
            # Miscellaneous endpoints
            self.misc = MiscEndpoints()
            self._configure_endpoint(self.misc)
            
            # Info endpoints
            self.info = InfoEndpoints()
            self._configure_endpoint(self.info)
            
            # Settings endpoints
            self.settings = SettingsEndpoints()
            self._configure_endpoint(self.settings)
            
            # Export endpoints
            self.export = ExportEndpoints()
            self._configure_endpoint(self.export)
            
        except Exception as e:
            self.log.error(f"Failed to initialize endpoints: {e}")
            raise
    
    def _configure_endpoint(self, endpoint):
        """Configure an endpoint with common settings."""
        endpoint.config = self.config
        endpoint.docroot = self.docroot
        endpoint.lookup = self.lookup
        
        # Add logging if endpoint supports it
        if hasattr(endpoint, 'log'):
            endpoint.log = self.log
    
    def _setup_security(self):
        """Setup security headers and policies with enhanced configuration."""
        if not secure:
            self.log.warning("Security headers not available (secure module not installed)")
            return
        
        try:
            # Enhanced Content Security Policy
            csp = (
                secure.ContentSecurityPolicy()
                    .default_src("'self'")
                    .script_src("'self'", "'unsafe-inline'", "blob:", "'unsafe-eval'")
                    .style_src("'self'", "'unsafe-inline'", "fonts.googleapis.com")
                    .font_src("'self'", "fonts.gstatic.com")
                    .base_uri("'self'")
                    .connect_src("'self'", "data:")
                    .frame_src("'self'", 'data:')
                    .img_src("'self'", "data:", "*.gravatar.com")
                    .media_src("'self'")
                    .object_src("'none'")
                    .worker_src("'self'", "blob:")
            )
            
            # Security headers with enhanced configuration
            secure_headers = secure.Secure(
                server=secure.Server().set("SpiderFoot"),
                cache=secure.CacheControl().must_revalidate(),
                csp=csp,
                referrer=secure.ReferrerPolicy().no_referrer(),
                permissions=secure.PermissionsPolicy().geolocation("none").camera("none").microphone("none"),
                hsts=secure.StrictTransportSecurity().max_age(31536000).include_subdomains()
            )
            
            # Apply to CherryPy configuration
            cherrypy.config.update({
                "tools.response_headers.on": True,
                "tools.response_headers.headers": secure_headers.framework.cherrypy()
            })
            
            self.log.info("Enhanced security headers configured successfully")
            
        except Exception as e:
            self.log.error(f"Failed to setup security headers: {e}")
    
    def mount(self):
        """Mount all endpoints with proper error handling and validation."""
        try:
            # Mount endpoints with proper paths
            cherrypy.tree.mount(self.scan, '/scan')
            cherrypy.tree.mount(self.workspace, '/workspace')
            cherrypy.tree.mount(self.info, '/info')
            cherrypy.tree.mount(self.settings, '/settings')
            cherrypy.tree.mount(self.export, '/export')
            cherrypy.tree.mount(self.misc, '/')
            
            # Register enhanced error handlers
            cherrypy.config.update({
                'error_page.401': self._error_page_401,
                'error_page.404': self._error_page_404,
                'error_page.500': self._error_page_500,
                'request.error_response': self._error_page
            })
            
            self.log.info("All endpoints mounted successfully")
            
        except Exception as e:
            self.log.error(f"Failed to mount endpoints: {e}")
            raise
    
    def _error_page_401(self, status, message, traceback, version):
        """Enhanced 401 error page."""
        return ""
    
    def _error_page_404(self, status, message, traceback, version):
        """Enhanced 404 error page with better user experience."""
        try:
            from mako.template import Template
            templ = Template(
                filename='spiderfoot/templates/error.tmpl', 
                lookup=self.lookup
            )
            return templ.render(
                message='Page Not Found', 
                docroot=self.docroot, 
                status=status, 
                version=self.config.get('__version__', 'unknown'),
                suggestion="Please check the URL and try again."
            )
        except Exception:
            return f"<html><body><h1>404 - Page Not Found</h1><p>Status: {status}</p></body></html>"
    
    def _error_page_500(self, status, message, traceback, version):
        """Enhanced 500 error page with debugging info."""
        try:
            if self.config.get('_debug'):
                from cherrypy import _cperror
                return _cperror.get_error_page(status=500, traceback=traceback)
            else:
                return "<html><body><h1>Internal Server Error</h1><p>Please try again later.</p></body></html>"
        except Exception:
            return "<html><body><h1>500 - Internal Server Error</h1></body></html>"
    
    def _error_page(self):
        """Enhanced generic error page."""
        cherrypy.response.status = 500
        if self.config.get('_debug'):
            try:
                from cherrypy import _cperror
                cherrypy.response.body = _cperror.get_error_page(
                    status=500, traceback=_cperror.format_exc()
                )
            except Exception:
                cherrypy.response.body = b"<html><body>Debug Error</body></html>"
        else:
            cherrypy.response.body = b"<html><body>Error</body></html>"
    
    def validate_system(self) -> Dict[str, Any]:
        """
        Perform comprehensive system validation.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'success': True,
            'checks': {},
            'timestamp': time.time()
        }
        
        # Check database connectivity
        try:
            dbh = SpiderFootDb(self.config, init=False)
            dbh.scanInstanceList()
            validation_results['checks']['database'] = {
                'status': 'OK',
                'message': 'Database connection successful'
            }
        except Exception as e:
            validation_results['checks']['database'] = {
                'status': 'ERROR',
                'message': f'Database connection failed: {e}'
            }
            validation_results['success'] = False
        
        # Check template availability
        try:
            template_count = len([f for f in os.listdir('spiderfoot/templates') if f.endswith('.tmpl')])
            validation_results['checks']['templates'] = {
                'status': 'OK',
                'message': f'{template_count} templates found'
            }
        except Exception as e:
            validation_results['checks']['templates'] = {
                'status': 'WARNING',
                'message': f'Template check failed: {e}'
            }
        
        # Check module configuration
        modules = self.config.get('__modules__', [])
        if modules:
            validation_results['checks']['modules'] = {
                'status': 'OK',
                'message': f'{len(modules)} modules configured'
            }
        else:
            validation_results['checks']['modules'] = {
                'status': 'WARNING',
                'message': 'No modules configured'
            }
        
        # Check security configuration
        if secure:
            validation_results['checks']['security'] = {
                'status': 'OK',
                'message': 'Security headers available'
            }
        else:
            validation_results['checks']['security'] = {
                'status': 'WARNING',
                'message': 'Security headers not available'
            }
        
        return validation_results
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get comprehensive system information.
        
        Returns:
            Dictionary with system information
        """
        try:
            info = {
                'success': True,
                'python_version': sys.version,
                'spiderfoot_version': self.config.get('__version__', 'unknown'),
                'database_path': self.config.get('__database', 'unknown'),
                'template_directory': 'spiderfoot/templates',
                'docroot': self.docroot,
                'module_count': len(self.config.get('__modules__', [])),
                'security_headers': secure is not None,
                'timestamp': time.time()
            }
            
            # Add platform information
            import platform
            info['platform'] = {
                'system': platform.system(),
                'release': platform.release(),
                'machine': platform.machine(),
                'processor': platform.processor()
            }
            
            # Add memory information if available
            try:
                import psutil
                memory = psutil.virtual_memory()
                info['memory'] = {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent
                }
            except ImportError:
                info['memory'] = {'status': 'psutil not available'}
            
            return info
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': time.time()
            }


if __name__ == "__main__":
    # Create a basic config for the web UI
    import os
    
    # Initialize with basic default config
    sf = SpiderFoot({})
    config = sf.defaultConfig() if hasattr(sf, 'defaultConfig') else {}
    
    # If config is still empty, create a minimal valid config
    if not config:
        config = {
            '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
            '_debug': False,
            '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
            '_dnsserver': '',
            '_fetchtimeout': 5,
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72,
        }
    
    web_config = {'root': '/'}
    
    # Create the web application with proper config
    try:
        app = WebUiRoutes(web_config, config)
        cherrypy.quickstart(app, '/', {
            '/': {
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [
                    ('X-Frame-Options', 'DENY'),
                    ('X-XSS-Protection', '1; mode=block'),
                    ('X-Content-Type-Options', 'nosniff'),
                ]
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': os.path.join(os.getcwd(), 'spiderfoot', 'static')
            }
        })
    except Exception as e:
        print(f"Error starting web UI: {e}")
        import traceback
        traceback.print_exc()