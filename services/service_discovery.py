#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot Service Discovery

A lightweight service discovery mechanism for SpiderFoot microservices.
Provides service registration, discovery, and health monitoring.
"""

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SpiderFoot Service Discovery",
    description="Service registry and discovery for SpiderFoot microservices",
    version="1.0.0"
)

@dataclass
class ServiceInstance:
    """Service instance information."""
    service_id: str
    service_name: str
    host: str
    port: int
    health_endpoint: str
    api_base_url: str
    version: str
    metadata: Dict[str, Any]
    registered_at: datetime
    last_heartbeat: datetime
    status: str = "healthy"  # healthy, unhealthy, unknown

class ServiceRegistration(BaseModel):
    """Service registration request."""
    service_name: str = Field(..., description="Service name")
    host: str = Field(..., description="Service host")
    port: int = Field(..., description="Service port")
    health_endpoint: str = Field(default="/health", description="Health check endpoint")
    version: str = Field(default="1.0.0", description="Service version")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Service metadata")

class ServiceQuery(BaseModel):
    """Service discovery query."""
    service_name: Optional[str] = Field(None, description="Service name to filter by")
    status: Optional[str] = Field(None, description="Service status to filter by")
    limit: int = Field(default=10, description="Maximum number of results")

class ServiceDiscovery:
    """Service discovery implementation."""
    
    def __init__(self, db_path: str = None):
        """Initialize service discovery."""
        if db_path is None:
            db_path = Path(__file__).parent / "service_discovery.db"
        
        self.db_path = db_path
        self.services: Dict[str, ServiceInstance] = {}
        self.health_check_interval = 30  # seconds
        self.service_timeout = 120  # seconds
        self.init_database()
        
        # Health check loop will be started when FastAPI starts
        self._health_check_task = None
    
    def init_database(self):
        """Initialize the service discovery database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS services (
                        service_id TEXT PRIMARY KEY,
                        service_name TEXT NOT NULL,
                        host TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        health_endpoint TEXT NOT NULL DEFAULT '/health',
                        api_base_url TEXT NOT NULL,
                        version TEXT NOT NULL DEFAULT '1.0.0',
                        metadata TEXT DEFAULT '{}',
                        status TEXT DEFAULT 'healthy',
                        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_service_name ON services(service_name)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status ON services(status)
                """)
                
                conn.commit()
                logger.info(f"Service discovery database initialized: {self.db_path}")
                
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize service discovery database: {e}")
            raise
    
    def register_service(self, registration: ServiceRegistration) -> str:
        """Register a new service instance."""
        service_id = f"{registration.service_name}-{registration.host}-{registration.port}"
        api_base_url = f"http://{registration.host}:{registration.port}"
        
        service = ServiceInstance(
            service_id=service_id,
            service_name=registration.service_name,
            host=registration.host,
            port=registration.port,
            health_endpoint=registration.health_endpoint,
            api_base_url=api_base_url,
            version=registration.version,
            metadata=registration.metadata,
            registered_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow()
        )
        
        # Store in memory
        self.services[service_id] = service
        
        # Persist to database
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO services 
                    (service_id, service_name, host, port, health_endpoint, api_base_url, 
                     version, metadata, status, registered_at, last_heartbeat)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    service.service_id, service.service_name, service.host, service.port,
                    service.health_endpoint, service.api_base_url, service.version,
                    json.dumps(service.metadata), service.status,
                    service.registered_at.isoformat(), service.last_heartbeat.isoformat()
                ))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to persist service registration: {e}")
            # Continue without persistence
        
        logger.info(f"Service registered: {service_id}")
        return service_id
    
    def deregister_service(self, service_id: str) -> bool:
        """Deregister a service instance."""
        if service_id in self.services:
            del self.services[service_id]
            
            # Remove from database
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM services WHERE service_id = ?", (service_id,))
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to remove service from database: {e}")
            
            logger.info(f"Service deregistered: {service_id}")
            return True
        
        return False
    
    def discover_services(self, query: ServiceQuery) -> List[ServiceInstance]:
        """Discover services based on query parameters."""
        services = list(self.services.values())
        
        # Filter by service name
        if query.service_name:
            services = [s for s in services if s.service_name == query.service_name]
        
        # Filter by status
        if query.status:
            services = [s for s in services if s.status == query.status]
        
        # Sort by last heartbeat (most recent first)
        services.sort(key=lambda s: s.last_heartbeat, reverse=True)
        
        # Apply limit
        return services[:query.limit]
    
    def heartbeat(self, service_id: str) -> bool:
        """Update service heartbeat."""
        if service_id in self.services:
            self.services[service_id].last_heartbeat = datetime.utcnow()
            self.services[service_id].status = "healthy"
            
            # Update database
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE services 
                        SET last_heartbeat = ?, status = 'healthy'
                        WHERE service_id = ?
                    """, (datetime.utcnow().isoformat(), service_id))
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to update heartbeat in database: {e}")
            
            return True
        
        return False
    
    async def health_check_loop(self):
        """Background task to check service health."""
        import httpx
        
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                current_time = datetime.utcnow()
                timeout_threshold = current_time - timedelta(seconds=self.service_timeout)
                
                for service_id, service in list(self.services.items()):
                    # Check if service has timed out
                    if service.last_heartbeat < timeout_threshold:
                        logger.warning(f"Service timeout: {service_id}")
                        service.status = "unhealthy"
                        continue
                    
                    # Perform active health check
                    try:
                        health_url = f"{service.api_base_url}{service.health_endpoint}"
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            response = await client.get(health_url)
                            
                            if response.status_code == 200:
                                service.status = "healthy"
                                service.last_heartbeat = current_time
                            else:
                                service.status = "unhealthy"
                                logger.warning(f"Service unhealthy: {service_id} (status: {response.status_code})")
                    
                    except Exception as e:
                        service.status = "unhealthy"
                        logger.warning(f"Health check failed for {service_id}: {e}")
                
                # Clean up unhealthy services older than 24 hours
                cleanup_threshold = current_time - timedelta(hours=24)
                services_to_remove = [
                    service_id for service_id, service in self.services.items()
                    if service.status == "unhealthy" and service.last_heartbeat < cleanup_threshold
                ]
                
                for service_id in services_to_remove:
                    self.deregister_service(service_id)
                    logger.info(f"Cleaned up unhealthy service: {service_id}")
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    def load_persisted_services(self):
        """Load services from database on startup."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM services")
                rows = cursor.fetchall()
                
                for row in rows:
                    service = ServiceInstance(
                        service_id=row[0],
                        service_name=row[1],
                        host=row[2],
                        port=row[3],
                        health_endpoint=row[4],
                        api_base_url=row[5],
                        version=row[6],
                        metadata=json.loads(row[7]),
                        status=row[8],
                        registered_at=datetime.fromisoformat(row[9]),
                        last_heartbeat=datetime.fromisoformat(row[10])
                    )
                    self.services[service.service_id] = service
                
                logger.info(f"Loaded {len(rows)} persisted services")
                
        except sqlite3.Error as e:
            logger.error(f"Failed to load persisted services: {e}")

# Global service discovery instance
service_discovery = ServiceDiscovery()

@app.on_event("startup")
async def startup_event():
    """Load persisted services on startup."""
    service_discovery.load_persisted_services()
    # Start health check loop
    service_discovery._health_check_task = asyncio.create_task(service_discovery.health_check_loop())

@app.on_event("shutdown") 
async def shutdown_event():
    """Clean up on shutdown."""
    if service_discovery._health_check_task:
        service_discovery._health_check_task.cancel()

@app.post("/register")
async def register_service(registration: ServiceRegistration):
    """Register a new service instance."""
    try:
        service_id = service_discovery.register_service(registration)
        return {
            "service_id": service_id,
            "message": "Service registered successfully",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to register service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/register/{service_id}")
async def deregister_service(service_id: str):
    """Deregister a service instance."""
    success = service_discovery.deregister_service(service_id)
    
    if success:
        return {
            "message": "Service deregistered successfully",
            "timestamp": datetime.utcnow()
        }
    else:
        raise HTTPException(status_code=404, detail="Service not found")

@app.post("/discover")
async def discover_services(query: ServiceQuery):
    """Discover services based on query parameters."""
    try:
        services = service_discovery.discover_services(query)
        return {
            "services": [asdict(service) for service in services],
            "count": len(services),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to discover services: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/services")
async def list_all_services():
    """List all registered services."""
    try:
        services = list(service_discovery.services.values())
        return {
            "services": [asdict(service) for service in services],
            "count": len(services),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/services/{service_name}")
async def get_services_by_name(service_name: str):
    """Get all instances of a specific service."""
    query = ServiceQuery(service_name=service_name)
    services = service_discovery.discover_services(query)
    
    return {
        "service_name": service_name,
        "services": [asdict(service) for service in services],
        "count": len(services),
        "timestamp": datetime.utcnow()
    }

@app.post("/heartbeat/{service_id}")
async def service_heartbeat(service_id: str):
    """Update service heartbeat."""
    success = service_discovery.heartbeat(service_id)
    
    if success:
        return {
            "message": "Heartbeat updated",
            "timestamp": datetime.utcnow()
        }
    else:
        raise HTTPException(status_code=404, detail="Service not found")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "service-discovery",
        "version": "1.0.0",
        "registered_services": len(service_discovery.services),
        "timestamp": datetime.utcnow()
    }

def main():
    """Main entry point for the service discovery."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SpiderFoot Service Discovery")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--db-path", help="Database path for service registry")
    
    args = parser.parse_args()
    
    # Set database path if provided
    if args.db_path:
        global service_discovery
        service_discovery = ServiceDiscovery(args.db_path)
    
    logger.info(f"Starting SpiderFoot Service Discovery on {args.host}:{args.port}")
    
    # Start the service discovery
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )

if __name__ == "__main__":
    main()