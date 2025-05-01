# -*- coding: utf-8 -*-
# -----------------------------------------------------------------
# Name:         sfapi_controller
# Purpose:      Controller for running either CherryPy or FastAPI APIs
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# FastAPI Port: '01/05/2025
# Copyright:    (c) Agostino Panico
# License:      MIT
# -----------------------------------------------------------------
import os
import json
import logging
import multiprocessing as mp
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from spiderfoot import __version__
from spiderfoot.logger import logWorkerSetup
from spiderfoot import SpiderFootDb

# This is our FastAPI application instance for sf.py integration 
app = None

def init_api(config: dict, logging_queue: Optional[mp.Queue] = None) -> FastAPI:
    """Initialize the FastAPI application.
    
    Args:
        config (dict): SpiderFoot configuration
        logging_queue (mp.Queue, optional): Logging queue for multiprocessing
        
    Returns:
        FastAPI: The FastAPI application instance
    """
    global app
    
    # Initialize logging
    if logging_queue:
        logWorkerSetup(logging_queue)
    log = logging.getLogger("spiderfoot.sfapi_controller")
    
    if app:
        log.info("FastAPI application already initialized")
        return app
        
    # Create FastAPI application
    app = FastAPI(
        title="SpiderFoot API",
        description="API for SpiderFoot OSINT reconnaissance tool",
        version=__version__
    )
    
    # Add CORS middleware with configurable origins
    origins = os.environ.get('SPIDERFOOT_CORS_ORIGINS', '*').split(',')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files if they exist
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Root redirect to docs
    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/docs")
        
    # Import and initialize the FastAPI router
    try:
        from fastapi_app import setup_api_router
        
        # Initialize router with configuration
        setup_api_router(app, config, logging_queue)
        log.info("Successfully initialized FastAPI router")
    except ImportError as e:
        log.error(f"Failed to import FastAPI application components: {e}")
        
        # Add a basic ping endpoint for testing
        @app.get("/ping")
        async def ping():
            return {"status": "SUCCESS", "version": __version__}
    
    return app

if __name__ == "__main__":
    # This allows direct execution for testing
    import argparse
    import uvicorn
    from spiderfoot.logger import logListenerSetup
    
    parser = argparse.ArgumentParser(description='SpiderFoot API Controller')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Setup logging
    logging_queue = mp.Queue()
    log_process = logListenerSetup(logging_queue)
    
    # Load config from environment or create minimal config
    config_json = os.environ.get('SPIDERFOOT_CONFIG')
    config = {}
    if config_json:
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError:
            pass
    
    # Initialize the API
    app = init_api(config, logging_queue)
    
    # Run the API server directly
    try:
        uvicorn.run(
            "sfapi_controller:app", 
            host=args.host, 
            port=args.port, 
            log_level="debug" if args.debug else "info",
            reload=args.debug
        )
    finally:
        if log_process:
            log_process.terminate()
