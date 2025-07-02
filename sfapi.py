#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot REST API (modular entrypoint)
Delegates to the modular FastAPI app in spiderfoot/api/main.py
"""

import argparse
import uvicorn
from spiderfoot.api.main import app

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
