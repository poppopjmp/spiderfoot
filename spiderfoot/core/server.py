"""
Server Manager for SpiderFoot

This module handles server startup and management for both WebUI and API servers.
It provides a centralized interface for server operations.
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, Any, Optional
import multiprocessing as mp

import cherrypy
import cherrypy_cors
from cherrypy.lib import auth_digest

from spiderfoot import SpiderFootHelpers
from sfwebui import SpiderFootWebUi


class ServerManager:
    """Centralized server management for SpiderFoot."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the server manager.
        
        Args:
            config: SpiderFoot configuration dictionary
        """
        self.config = config
        self.log = logging.getLogger(f"spiderfoot.{__name__}")
        
    def start_web_server(self, web_config: Dict[str, Any], logging_queue: Optional[mp.Queue] = None) -> None:
        """
        Start the CherryPy web server.
        
        Args:
            web_config: Web server configuration
            logging_queue: Optional logging queue for multiprocessing
            
        Raises:
            SystemExit: If server fails to start
        """
        try:
            web_host = web_config.get('host', '127.0.0.1')
            web_port = web_config.get('port', 5001)
            web_root = web_config.get('root', '/')
            cors_origins = web_config.get('cors_origins', [])

            cherrypy.config.update({
                'log.screen': False,
                'server.socket_host': web_host,
                'server.socket_port': int(web_port)
            })

            self.log.info(f"Starting web server at {web_host}:{web_port}")

            # Enable access to static files via the web directory
            conf = {
                '/query': {
                    'tools.encode.text_only': False,
                    'tools.encode.add_charset': True,
                },
                '/static': {
                    'tools.staticdir.on': True,
                    'tools.staticdir.dir': os.path.join(os.getcwd(), 'spiderfoot', 'static'),
                    'tools.staticdir.root': f"{os.path.dirname(os.path.abspath(__file__))}/../.."
                }
            }

            # Handle authentication
            secrets = self._load_auth_secrets()
            using_ssl = self._setup_ssl()

            if secrets:
                self._setup_authentication(conf, secrets)
                auth_info = "with authentication enabled"
            else:
                auth_info = "with no authentication"

            # Determine URL scheme
            scheme = "https" if using_ssl else "http"
            
            if web_host == "0.0.0.0":
                url = f"{scheme}://localhost:{web_port}{web_root}"
            else:
                url = f"{scheme}://{web_host}:{web_port}{web_root}"

            # Setup CORS
            cherrypy_cors.install()
            cherrypy.config.update({
                'cors.expose.on': True,
                'cors.expose.origins': cors_origins,
                'cors.preflight.origins': cors_origins
            })

            print("")
            print("*************************************************************")
            print(" Use SpiderFoot by starting your web browser of choice and ")
            print(f" browse to {url}")
            print(f" Server running {auth_info}")
            print("*************************************************************")
            print("")

            # Disable auto-reloading of content
            cherrypy.engine.autoreload.unsubscribe()

            # Start the server
            cherrypy.quickstart(
                SpiderFootWebUi(web_config, self.config, logging_queue),
                script_name=web_root,
                config=conf
            )
            
        except Exception as e:
            self.log.critical(f"Unhandled exception in start_web_server: {e}", exc_info=True)
            sys.exit(-1)

    def start_fastapi_server(self, api_config: Dict[str, Any], logging_queue: Optional[mp.Queue] = None) -> None:
        """
        Start the FastAPI server.
        
        Args:
            api_config: API server configuration
            logging_queue: Optional logging queue for multiprocessing
            
        Raises:
            SystemExit: If server fails to start
        """
        try:
            # Check if FastAPI dependencies are available
            try:
                import uvicorn
                import fastapi
            except ImportError:
                self.log.error("FastAPI dependencies not found. Please install with: pip install fastapi uvicorn")
                sys.exit(-1)

            api_host = api_config.get('host', '127.0.0.1')
            api_port = api_config.get('port', 8001)
            api_workers = api_config.get('workers', 1)
            api_log_level = api_config.get('log_level', 'info')
            api_reload = api_config.get('reload', False)

            self.log.info(f"Starting FastAPI server at {api_host}:{api_port}")

            # Check if sfapi.py exists
            sfapi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../sfapi.py')
            if not os.path.exists(sfapi_path):
                self.log.error("sfapi.py not found. FastAPI server cannot start.")
                sys.exit(-1)

            print("")
            print("*************************************************************")
            print(" SpiderFoot FastAPI server is starting...")
            print(f" API will be available at: http://{api_host}:{api_port}")
            print(f" API documentation at: http://{api_host}:{api_port}/api/docs")
            print("*************************************************************")
            print("")

            # Run FastAPI server
            uvicorn.run(
                "sfapi:app",
                host=api_host,
                port=api_port,
                workers=api_workers,
                log_level=api_log_level,
                reload=api_reload,
                access_log=True
            )

        except Exception as e:
            self.log.critical(f"Unhandled exception in start_fastapi_server: {e}", exc_info=True)
            sys.exit(-1)

    def start_both_servers(self, web_config: Dict[str, Any], api_config: Dict[str, Any], 
                          logging_queue: Optional[mp.Queue] = None) -> None:
        """
        Start both web UI and FastAPI servers concurrently.
        
        Args:
            web_config: Web server configuration
            api_config: API server configuration
            logging_queue: Optional logging queue for multiprocessing
            
        Raises:
            SystemExit: If servers fail to start
        """
        try:
            # Check if FastAPI dependencies are available
            try:
                import uvicorn
                import fastapi
            except ImportError:
                self.log.error("FastAPI dependencies not found. Please install with: pip install fastapi uvicorn")
                self.log.info("Starting only the web UI server...")
                self.start_web_server(web_config, logging_queue)
                return

            web_host = web_config.get('host', '127.0.0.1')
            web_port = web_config.get('port', 5001)
            api_host = api_config.get('host', '127.0.0.1')
            api_port = api_config.get('port', 8001)

            self.log.info(f"Starting both servers - Web UI: {web_host}:{web_port}, API: {api_host}:{api_port}")

            print("")
            print("*************************************************************")
            print(" SpiderFoot is starting both servers...")
            print(f" Web UI: http://{web_host}:{web_port}")
            print(f" FastAPI: http://{api_host}:{api_port}")
            print(f" API Docs: http://{api_host}:{api_port}/api/docs")
            print("*************************************************************")
            print("")

            # Start FastAPI server in a separate thread
            def run_fastapi():
                try:
                    # Check if sfapi.py exists
                    sfapi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../sfapi.py')
                    if not os.path.exists(sfapi_path):
                        self.log.error("sfapi.py not found. FastAPI server will not start.")
                        return

                    uvicorn.run(
                        "sfapi:app",
                        host=api_host,
                        port=api_port,
                        workers=1,  # Use single worker when running alongside CherryPy
                        log_level=api_config.get('log_level', 'info'),
                        reload=False,  # Disable reload when running alongside CherryPy
                        access_log=True
                    )
                except Exception as e:
                    self.log.error(f"FastAPI server error: {e}")

            # Start FastAPI in background thread
            fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
            fastapi_thread.start()

            # Give FastAPI a moment to start
            time.sleep(2)

            # Start CherryPy web server (this will block)
            self.start_web_server(web_config, logging_queue)

        except Exception as e:
            self.log.critical(f"Unhandled exception in start_both_servers: {e}", exc_info=True)
            sys.exit(-1)

    def _load_auth_secrets(self) -> Dict[str, str]:
        """
        Load authentication secrets from passwd file.
        
        Returns:
            Dict containing username/password pairs
        """
        secrets = {}
        passwd_file = SpiderFootHelpers.dataPath() + '/passwd'
        
        if os.path.isfile(passwd_file):
            try:
                with open(passwd_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if ':' in line:
                            username, password = line.split(':', 1)
                            secrets[username] = password
                self.log.info(f"Loaded {len(secrets)} authentication credentials")
            except Exception as e:
                self.log.error(f"Failed to load authentication file: {e}")
        
        return secrets

    def _setup_ssl(self) -> bool:
        """
        Set up SSL configuration if certificates are available.
        
        Returns:
            True if SSL is configured, False otherwise
        """
        key_path = SpiderFootHelpers.dataPath() + '/spiderfoot.key'
        crt_path = SpiderFootHelpers.dataPath() + '/spiderfoot.crt'
        
        if os.path.isfile(key_path) and os.path.isfile(crt_path):
            cherrypy.config.update({
                'server.ssl_certificate': crt_path,
                'server.ssl_private_key': key_path
            })
            self.log.info("SSL enabled")
            return True
        
        return False

    def _setup_authentication(self, conf: Dict[str, Any], secrets: Dict[str, str]) -> None:
        """
        Set up digest authentication.
        
        Args:
            conf: CherryPy configuration dict to update
            secrets: Username/password pairs
        """
        def get_ha1(realm, username):
            if username in secrets:
                return auth_digest.get_ha1(realm, username, secrets[username])
            return None

        conf.update({
            '/': {
                'tools.auth_digest.on': True,
                'tools.auth_digest.realm': 'SpiderFoot',
                'tools.auth_digest.get_ha1': get_ha1,
                'tools.auth_digest.key': 'spiderfoot'
            }
        })
