#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot REST API (modular entrypoint)
Delegates to the modular FastAPI app in spiderfoot/api/main.py
"""

import argparse
import uvicorn
from spiderfoot.api.main import app

# Re-export legacy API symbols for test and compatibility
from spiderfoot.api.dependencies import get_app_config, optional_auth
from spiderfoot.api.models import ScanRequest, WorkspaceRequest, ScanResponse, WorkspaceResponse
from spiderfoot.api.search_base import search_base
from spiderfoot.api.dependencies import app_config
from spiderfoot.db import SpiderFootDb
from spiderfoot.sflib.core import SpiderFoot
from spiderfoot.helpers import SpiderFootHelpers
from spiderfoot.api.utils import clean_user_input, build_excel
from spiderfoot.api.routers.websocket import WebSocketManager
import openpyxl
import logging

# For test patching and legacy compatibility
security = optional_auth
logger = logging.getLogger("sfapi")
Config = get_app_config().__class__ if get_app_config() else None

def main():
    """Main function to run the FastAPI application (modular)"""
    parser = argparse.ArgumentParser(description='SpiderFoot REST API Server')
    parser.add_argument('-H', '--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('-p', '--port', type=int, default=8001, help='Port to bind to')
    parser.add_argument('-c', '--config', help='Configuration file path')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    args = parser.parse_args()
    uvicorn.run(
        "spiderfoot.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
