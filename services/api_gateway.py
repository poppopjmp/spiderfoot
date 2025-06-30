#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot API Gateway

A simple API Gateway for SpiderFoot microservices that provides:
- Request routing to appropriate services
- Load balancing across service instances
- Authentication and authorization (future)
- Rate limiting (future)
- Request/response transformation
- Health check aggregation
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SpiderFoot API Gateway",
    description="API Gateway for SpiderFoot microservices",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ServiceRouter:
    """Route requests to appropriate microservices."""
    
    def __init__(self, service_discovery_url: str = "http://localhost:8000"):
        self.service_discovery_url = service_discovery_url
        self.service_cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 30  # Cache for 30 seconds
        
        # Route configuration
        self.routes = {
            "/api/discovery": "service-discovery",
            "/api/config": "config-service", 
            "/api/configuration": "config-service",  # Alternative path
        }
        
        # Special handling for service discovery (direct URL)
        self.discovery_direct_url = service_discovery_url
    
    async def get_service_url(self, service_name: str) -> Optional[str]:
        """Get service URL from service discovery."""
        current_time = time.time()
        
        # Check cache
        if (service_name in self.service_cache and 
            service_name in self.cache_timestamp and
            current_time - self.cache_timestamp[service_name] < self.cache_ttl):
            return self.service_cache[service_name]
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.service_discovery_url}/services/{service_name}")
                
                if response.status_code == 200:
                    data = response.json()
                    services = data.get("services", [])
                    
                    # Get first healthy service
                    for service in services:
                        if service.get("status") == "healthy":
                            url = service.get("api_base_url")
                            if url:
                                # Cache the result
                                self.service_cache[service_name] = url
                                self.cache_timestamp[service_name] = current_time
                                return url
                
        except Exception as e:
            logger.error(f"Failed to discover service {service_name}: {e}")
        
        return None
    
    def find_service_for_path(self, path: str) -> Optional[str]:
        """Find the appropriate service for a given path."""
        for route_prefix, service_name in self.routes.items():
            if path.startswith(route_prefix):
                return service_name
        return None
    
    async def route_request(self, request: Request, path: str) -> Response:
        """Route request to appropriate microservice."""
        service_name = self.find_service_for_path(path)
        
        if not service_name:
            raise HTTPException(status_code=404, detail="No service found for path")
        
        # Special handling for service discovery
        if service_name == "service-discovery":
            service_url = self.discovery_direct_url
        else:
            service_url = await self.get_service_url(service_name)
            if not service_url:
                raise HTTPException(status_code=503, detail=f"Service {service_name} unavailable")
        
        # Build target URL with proper path mapping
        service_path = path
        
        # Map gateway paths to service paths
        if path.startswith("/api/discovery/"):
            service_path = "/" + path[15:]  # Remove "/api/discovery/" (15 characters)
        elif path.startswith("/api/config/") or path.startswith("/api/configuration/"):
            if path.startswith("/api/config/"):
                service_path = "/config/" + path[12:]  # Remove "/api/config/" -> "/config/"
            else:
                service_path = "/config/" + path[18:]  # Remove "/api/configuration/" -> "/config/"
        elif path.startswith("/api/"):
            service_path = "/" + path[5:]  # Remove "/api/" (5 characters)
        
        # Ensure we have a proper path
        if not service_path.startswith("/"):
            service_path = "/" + service_path
        
        target_url = service_url + service_path
        
        # Forward request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get request body
                body = await request.body()
                
                # Prepare headers (exclude host header)
                headers = dict(request.headers)
                headers.pop("host", None)
                
                # Make request to service
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    params=dict(request.query_params),
                    headers=headers,
                    content=body
                )
                
                # Return response
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.headers.get("content-type")
                )
                
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Service timeout")
        except Exception as e:
            logger.error(f"Error routing request to {service_name}: {e}")
            raise HTTPException(status_code=502, detail="Service error")

# Global service router
service_router = ServiceRouter()

@app.get("/health")
async def gateway_health():
    """Gateway health check with service status."""
    try:
        # Check service discovery
        async with httpx.AsyncClient(timeout=5.0) as client:
            discovery_response = await client.get(f"{service_router.service_discovery_url}/health")
            discovery_healthy = discovery_response.status_code == 200
            
            # Get registered services
            services_response = await client.get(f"{service_router.service_discovery_url}/services")
            services_data = services_response.json() if services_response.status_code == 200 else {}
            services = services_data.get("services", [])
            
            # Check each service health
            service_health = {}
            for service in services:
                service_name = service.get("service_name")
                service_url = service.get("api_base_url")
                health_endpoint = service.get("health_endpoint", "/health")
                
                try:
                    health_response = await client.get(f"{service_url}{health_endpoint}", timeout=3.0)
                    service_health[service_name] = {
                        "status": "healthy" if health_response.status_code == 200 else "unhealthy",
                        "url": service_url
                    }
                except:
                    service_health[service_name] = {
                        "status": "unreachable",
                        "url": service_url
                    }
            
            return {
                "status": "healthy" if discovery_healthy else "degraded",
                "gateway": "healthy",
                "service_discovery": "healthy" if discovery_healthy else "unhealthy",
                "services": service_health,
                "timestamp": time.time()
            }
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )

@app.get("/api/gateway/routes")
async def list_routes():
    """List available routes through the gateway."""
    return {
        "routes": service_router.routes,
        "description": "Available API routes through the gateway",
        "timestamp": time.time()
    }

@app.get("/api/gateway/services")
async def list_services():
    """List services discovered through service discovery."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{service_router.service_discovery_url}/services")
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=502, detail="Failed to fetch services")
                
    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        raise HTTPException(status_code=502, detail=str(e))

# Catch-all route handler for API requests
@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def route_api_request(request: Request, path: str):
    """Route API requests to appropriate microservices."""
    full_path = f"/api/{path}"
    return await service_router.route_request(request, full_path)

# Legacy SpiderFoot Web UI proxy (for backward compatibility)
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def route_legacy_request(request: Request, path: str):
    """Route legacy requests to SpiderFoot web UI or microservices."""
    # Check if this is an API request that should go to microservices
    if path.startswith("api/"):
        full_path = f"/{path}"
        return await service_router.route_request(request, full_path)
    
    # For now, return a simple response for non-API requests
    # In a full implementation, this would proxy to the legacy web UI
    if path == "" or path == "/":
        return {
            "message": "SpiderFoot API Gateway",
            "version": "1.0.0",
            "status": "active",
            "services": len(service_router.routes),
            "documentation": "/docs",
            "health": "/health"
        }
    
    # Return 404 for unknown paths
    raise HTTPException(status_code=404, detail="Path not found")

def main():
    """Main entry point for the API Gateway."""
    import argparse
    
    parser = argparse.ArgumentParser(description="SpiderFoot API Gateway")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--service-discovery-url", default="http://localhost:8000",
                       help="Service discovery URL")
    
    args = parser.parse_args()
    
    # Configure service router
    global service_router
    service_router = ServiceRouter(args.service_discovery_url)
    
    logger.info(f"Starting SpiderFoot API Gateway on {args.host}:{args.port}")
    logger.info(f"Service Discovery: {args.service_discovery_url}")
    
    # Start the gateway
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )

if __name__ == "__main__":
    main()