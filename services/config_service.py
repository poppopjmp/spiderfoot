#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot Configuration Service

A microservice responsible for managing application configuration.
This service provides centralized configuration management with:
- RESTful API for configuration CRUD operations
- Configuration validation
- Environment-specific configurations
- Configuration versioning and rollback
- Health checks and monitoring

This is the first microservice extracted from the monolithic SpiderFoot application.
"""

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from copy import deepcopy

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import uvicorn

# Add the parent directory to the path so we can import SpiderFoot modules
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

from sflib import SpiderFoot
from spiderfoot import SpiderFootDb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SpiderFoot Configuration Service",
    description="Centralized configuration management for SpiderFoot",
    version="1.0.0"
)

# CORS middleware for cross-service communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for configuration management
class ConfigItem(BaseModel):
    """Individual configuration item."""
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    scope: str = Field(default="global", description="Configuration scope")
    description: Optional[str] = Field(None, description="Configuration description")
    
    @field_validator('key')
    @classmethod
    def key_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Configuration key cannot be empty')
        return v.strip()

class ConfigUpdate(BaseModel):
    """Configuration update request."""
    configs: Dict[str, Any] = Field(..., description="Configuration updates")
    scope: str = Field(default="global", description="Configuration scope")

class ConfigResponse(BaseModel):
    """Configuration response."""
    configs: Dict[str, Any] = Field(..., description="Configuration data")
    scope: str = Field(..., description="Configuration scope")
    timestamp: datetime = Field(..., description="Last updated timestamp")

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="Service version")
    database_status: str = Field(..., description="Database connection status")

# Configuration storage class
class ConfigurationStore:
    """Configuration storage and management."""
    
    def __init__(self, db_path: str = None):
        """Initialize configuration store."""
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "config_service.db")
        
        self.db_path = db_path
        self.init_database()
        
        # Cache for frequently accessed configs
        self._config_cache = {}
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes
    
    def init_database(self):
        """Initialize the configuration database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create configuration table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_store (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scope TEXT NOT NULL DEFAULT 'global',
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        value_type TEXT NOT NULL DEFAULT 'str',
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(scope, key)
                    )
                """)
                
                # Create configuration history table for versioning
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS config_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        scope TEXT NOT NULL,
                        key TEXT NOT NULL,
                        old_value TEXT,
                        new_value TEXT,
                        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        operation TEXT NOT NULL DEFAULT 'UPDATE'
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_scope_key ON config_store(scope, key)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_scope_key ON config_history(scope, key)")
                
                conn.commit()
                logger.info(f"Configuration database initialized: {self.db_path}")
                
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize configuration database: {e}")
            raise
    
    def get_config(self, scope: str = "global", key: str = None) -> Dict[str, Any]:
        """Get configuration(s) from storage."""
        current_time = time.time()
        
        # Check cache first
        cache_key = f"{scope}:{key}" if key else scope
        if (cache_key in self._config_cache and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._config_cache[cache_key]
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if key:
                    # Get specific configuration
                    cursor.execute(
                        "SELECT key, value, value_type, description FROM config_store WHERE scope = ? AND key = ?",
                        (scope, key)
                    )
                    row = cursor.fetchone()
                    if row:
                        result = {row[0]: self._deserialize_value(row[1], row[2])}
                    else:
                        result = {}
                else:
                    # Get all configurations for scope
                    cursor.execute(
                        "SELECT key, value, value_type, description FROM config_store WHERE scope = ?",
                        (scope,)
                    )
                    rows = cursor.fetchall()
                    result = {row[0]: self._deserialize_value(row[1], row[2]) for row in rows}
                
                # Update cache
                self._config_cache[cache_key] = result
                self._cache_timestamp = current_time
                
                return result
                
        except sqlite3.Error as e:
            logger.error(f"Failed to get configuration: {e}")
            raise
    
    def set_config(self, scope: str, key: str, value: Any, description: str = None) -> bool:
        """Set configuration value."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get old value for history
                cursor.execute(
                    "SELECT value, value_type FROM config_store WHERE scope = ? AND key = ?",
                    (scope, key)
                )
                old_row = cursor.fetchone()
                old_value = self._deserialize_value(old_row[0], old_row[1]) if old_row else None
                
                # Serialize the new value
                serialized_value, value_type = self._serialize_value(value)
                
                # Insert or update configuration
                cursor.execute("""
                    INSERT OR REPLACE INTO config_store 
                    (scope, key, value, value_type, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (scope, key, serialized_value, value_type, description))
                
                # Add to history
                operation = "UPDATE" if old_value is not None else "CREATE"
                cursor.execute("""
                    INSERT INTO config_history (scope, key, old_value, new_value, operation)
                    VALUES (?, ?, ?, ?, ?)
                """, (scope, key, str(old_value), serialized_value, operation))
                
                conn.commit()
                
                # Invalidate cache
                self._invalidate_cache(scope, key)
                
                logger.info(f"Configuration updated: {scope}:{key} = {value}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Failed to set configuration: {e}")
            raise
    
    def delete_config(self, scope: str, key: str) -> bool:
        """Delete configuration."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get old value for history
                cursor.execute(
                    "SELECT value, value_type FROM config_store WHERE scope = ? AND key = ?",
                    (scope, key)
                )
                old_row = cursor.fetchone()
                if not old_row:
                    return False
                
                old_value = self._deserialize_value(old_row[0], old_row[1])
                
                # Delete configuration
                cursor.execute(
                    "DELETE FROM config_store WHERE scope = ? AND key = ?",
                    (scope, key)
                )
                
                # Add to history
                cursor.execute("""
                    INSERT INTO config_history (scope, key, old_value, new_value, operation)
                    VALUES (?, ?, ?, NULL, 'DELETE')
                """, (scope, key, str(old_value)))
                
                conn.commit()
                
                # Invalidate cache
                self._invalidate_cache(scope, key)
                
                logger.info(f"Configuration deleted: {scope}:{key}")
                return True
                
        except sqlite3.Error as e:
            logger.error(f"Failed to delete configuration: {e}")
            raise
    
    def _serialize_value(self, value: Any) -> tuple:
        """Serialize a value for database storage."""
        if isinstance(value, bool):
            return str(value), "bool"
        elif isinstance(value, int):
            return str(value), "int"
        elif isinstance(value, float):
            return str(value), "float"
        elif isinstance(value, list):
            return json.dumps(value), "list"
        elif isinstance(value, dict):
            return json.dumps(value), "dict"
        else:
            return str(value), "str"
    
    def _deserialize_value(self, value: str, value_type: str) -> Any:
        """Deserialize a value from database storage."""
        if value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "list":
            return json.loads(value)
        elif value_type == "dict":
            return json.loads(value)
        else:
            return value
    
    def _invalidate_cache(self, scope: str, key: str = None):
        """Invalidate configuration cache."""
        cache_key = f"{scope}:{key}" if key else scope
        self._config_cache.pop(cache_key, None)
        self._config_cache.pop(scope, None)  # Also invalidate scope cache
    
    def health_check(self) -> Dict[str, str]:
        """Perform health check."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                return {"status": "healthy"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

# Global configuration store instance
config_store = ConfigurationStore()

# Startup event handler
@app.on_event("startup")
async def startup_event():
    """Handle startup tasks."""
    if getattr(app.state, 'register_with_discovery', False):
        await register_with_service_discovery(
            app.state.host, app.state.port, app.state.discovery_url
        )

# API Routes
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    db_health = config_store.health_check()
    
    return HealthResponse(
        status="healthy" if db_health["status"] == "healthy" else "degraded",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database_status=db_health["status"]
    )

@app.get("/config", response_model=ConfigResponse)
async def get_all_configs(scope: str = "global"):
    """Get all configurations for a scope."""
    try:
        configs = config_store.get_config(scope)
        return ConfigResponse(
            configs=configs,
            scope=scope,
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Failed to get configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config/{key}")
async def get_config(key: str, scope: str = "global"):
    """Get a specific configuration value."""
    try:
        configs = config_store.get_config(scope, key)
        if not configs:
            raise HTTPException(status_code=404, detail=f"Configuration not found: {scope}:{key}")
        
        return {
            "key": key,
            "value": configs[key],
            "scope": scope,
            "timestamp": datetime.utcnow()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/config/{key}")
async def set_config(key: str, item: ConfigItem):
    """Set a configuration value."""
    try:
        success = config_store.set_config(
            item.scope, key, item.value, item.description
        )
        if success:
            return {
                "message": f"Configuration updated: {item.scope}:{key}",
                "timestamp": datetime.utcnow()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update configuration")
    except Exception as e:
        logger.error(f"Failed to set configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/config")
async def update_configs(update: ConfigUpdate):
    """Update multiple configurations."""
    try:
        updated_keys = []
        for key, value in update.configs.items():
            success = config_store.set_config(update.scope, key, value)
            if success:
                updated_keys.append(key)
        
        return {
            "message": f"Updated {len(updated_keys)} configurations",
            "updated_keys": updated_keys,
            "scope": update.scope,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to update configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/config/{key}")
async def delete_config(key: str, scope: str = "global"):
    """Delete a configuration value."""
    try:
        success = config_store.delete_config(scope, key)
        if success:
            return {
                "message": f"Configuration deleted: {scope}:{key}",
                "timestamp": datetime.utcnow()
            }
        else:
            raise HTTPException(status_code=404, detail=f"Configuration not found: {scope}:{key}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config/{key}/history")
async def get_config_history(key: str, scope: str = "global", limit: int = 10):
    """Get configuration change history."""
    try:
        with sqlite3.connect(config_store.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT old_value, new_value, changed_at, operation 
                FROM config_history 
                WHERE scope = ? AND key = ? 
                ORDER BY changed_at DESC 
                LIMIT ?
            """, (scope, key, limit))
            
            rows = cursor.fetchall()
            history = [
                {
                    "old_value": row[0],
                    "new_value": row[1],
                    "changed_at": row[2],
                    "operation": row[3]
                }
                for row in rows
            ]
            
            return {
                "key": key,
                "scope": scope,
                "history": history,
                "timestamp": datetime.utcnow()
            }
    except Exception as e:
        logger.error(f"Failed to get configuration history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Service initialization and migration utilities
def migrate_existing_config():
    """Migrate existing SpiderFoot configuration to the service."""
    logger.info("Migrating existing configuration...")
    
    try:
        # Try to connect to existing SpiderFoot database
        sf_db_path = os.path.join(os.path.dirname(__file__), "..", "spiderfoot.db")
        if os.path.exists(sf_db_path):
            sf_db = SpiderFootDb({"__database": sf_db_path})
            
            # Get existing configuration
            existing_config = sf_db.configGet()
            
            if existing_config:
                for key, value in existing_config.items():
                    if not key.startswith('__'):  # Skip system variables
                        config_store.set_config("global", key, value, f"Migrated from monolith")
                
                logger.info(f"Migrated {len(existing_config)} configuration items")
            else:
                logger.info("No existing configuration found to migrate")
        else:
            logger.info("No existing SpiderFoot database found")
            
        # Set some default configurations for demonstration
        default_configs = {
            "_debug": False,
            "_maxthreads": 3,
            "__logging": True,
            "_useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0",
            "_timeout": 30,
            "_fetchtimeout": 30,
            "_maxqueue": 100
        }
        
        for key, value in default_configs.items():
            try:
                config_store.set_config("global", key, value, "Default configuration")
            except:
                pass  # Ignore if already exists
                
        logger.info("Configuration migration completed")
        
    except Exception as e:
        logger.error(f"Failed to migrate configuration: {e}")

def main():
    """Main entry point for the configuration service."""
    parser = argparse.ArgumentParser(description="SpiderFoot Configuration Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to") 
    parser.add_argument("--migrate", action="store_true", help="Migrate existing configuration")
    parser.add_argument("--db-path", help="Database path for configuration storage")
    parser.add_argument("--service-discovery-url", default="http://localhost:8000", 
                       help="Service discovery URL")
    parser.add_argument("--register-service", action="store_true", default=True,
                       help="Register with service discovery")
    
    args = parser.parse_args()
    
    # Set database path if provided
    if args.db_path:
        global config_store
        config_store = ConfigurationStore(args.db_path)
    
    # Migrate existing configuration if requested
    if args.migrate:
        migrate_existing_config()
    
    logger.info(f"Starting SpiderFoot Configuration Service on {args.host}:{args.port}")
    
    # Store registration info for startup event
    if args.register_service:
        app.state.register_with_discovery = True
        app.state.host = args.host
        app.state.port = args.port
        app.state.discovery_url = args.service_discovery_url
    else:
        app.state.register_with_discovery = False
    
    # Start the service
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )

async def register_with_service_discovery(host: str, port: int, discovery_url: str):
    """Register this service with the service discovery."""
    import httpx
    
    registration_data = {
        "service_name": "config-service",
        "host": host,
        "port": port,
        "health_endpoint": "/health",
        "version": "1.0.0",
        "metadata": {
            "description": "SpiderFoot Configuration Service",
            "capabilities": ["config_management", "config_versioning"]
        }
    }
    
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            await asyncio.sleep(2)  # Wait a bit for service discovery to be ready
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{discovery_url}/register", json=registration_data)
                
                if response.status_code == 200:
                    data = response.json()
                    service_id = data.get("service_id")
                    logger.info(f"Successfully registered with service discovery: {service_id}")
                    
                    # Start heartbeat loop
                    asyncio.create_task(heartbeat_loop(discovery_url, service_id))
                    return
                else:
                    logger.warning(f"Failed to register with service discovery: {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} to register failed: {e}")
            
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)
    
    logger.error("Failed to register with service discovery after all retries")

async def heartbeat_loop(discovery_url: str, service_id: str):
    """Send periodic heartbeats to service discovery."""
    import httpx
    
    while True:
        try:
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(f"{discovery_url}/heartbeat/{service_id}")
                
                if response.status_code != 200:
                    logger.warning(f"Heartbeat failed: {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")

if __name__ == "__main__":
    main()