# -*- coding: utf-8 -*-
"""
SpiderFoot Service Client

Client library for communicating with SpiderFoot microservices.
Provides service discovery integration and simplified API access.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

class ServiceClient:
    """Client for communicating with SpiderFoot microservices."""
    
    def __init__(self, service_discovery_url: str = "http://localhost:8000"):
        """Initialize service client.
        
        Args:
            service_discovery_url: URL of the service discovery service
        """
        self.service_discovery_url = service_discovery_url
        self.service_cache = {}
        self.cache_ttl = 30  # Cache services for 30 seconds
        self.cache_timestamp = {}
        
    async def discover_service(self, service_name: str, force_refresh: bool = False) -> Optional[str]:
        """Discover a service and return its base URL.
        
        Args:
            service_name: Name of the service to discover
            force_refresh: Force refresh from service discovery
            
        Returns:
            Service base URL or None if not found
        """
        current_time = time.time()
        
        # Check cache first
        if (not force_refresh and 
            service_name in self.service_cache and 
            service_name in self.cache_timestamp and
            current_time - self.cache_timestamp[service_name] < self.cache_ttl):
            return self.service_cache[service_name]
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.service_discovery_url}/services/{service_name}")
                
                if response.status_code == 200:
                    data = response.json()
                    services = data.get("services", [])
                    
                    # Get the first healthy service
                    for service in services:
                        if service.get("status") == "healthy":
                            base_url = service.get("api_base_url")
                            if base_url:
                                # Cache the result
                                self.service_cache[service_name] = base_url
                                self.cache_timestamp[service_name] = current_time
                                return base_url
                
                logger.warning(f"No healthy instances found for service: {service_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to discover service {service_name}: {e}")
            return None
    
    async def call_service(self, service_name: str, endpoint: str, method: str = "GET", 
                          data: Any = None, params: Dict[str, Any] = None,
                          timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Call a microservice endpoint.
        
        Args:
            service_name: Name of the service to call
            endpoint: API endpoint path
            method: HTTP method (GET, POST, PUT, DELETE)
            data: Request body data
            params: Query parameters
            timeout: Request timeout
            
        Returns:
            Response data or None if failed
        """
        service_url = await self.discover_service(service_name)
        if not service_url:
            logger.error(f"Service not available: {service_name}")
            return None
        
        url = f"{service_url}{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                kwargs = {
                    "url": url,
                    "params": params or {}
                }
                
                if data is not None:
                    if method.upper() in ("POST", "PUT", "PATCH"):
                        kwargs["json"] = data
                
                response = await client.request(method, **kwargs)
                
                if response.status_code < 400:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        return {"content": response.text}
                else:
                    logger.error(f"Service call failed: {service_name}{endpoint} - {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to call service {service_name}{endpoint}: {e}")
            return None

class ConfigServiceClient(ServiceClient):
    """Client for the Configuration Service."""
    
    def __init__(self, service_discovery_url: str = "http://localhost:8000"):
        super().__init__(service_discovery_url)
        self.service_name = "config-service"
    
    async def get_config(self, key: str = None, scope: str = "global") -> Optional[Dict[str, Any]]:
        """Get configuration value(s).
        
        Args:
            key: Configuration key (if None, gets all configs for scope)
            scope: Configuration scope
            
        Returns:
            Configuration data or None if failed
        """
        if key:
            endpoint = f"/config/{key}"
            params = {"scope": scope}
        else:
            endpoint = "/config"
            params = {"scope": scope}
        
        return await self.call_service(self.service_name, endpoint, params=params)
    
    async def set_config(self, key: str, value: Any, scope: str = "global", 
                        description: str = None) -> bool:
        """Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            scope: Configuration scope
            description: Configuration description
            
        Returns:
            True if successful, False otherwise
        """
        data = {
            "key": key,
            "value": value,
            "scope": scope
        }
        if description:
            data["description"] = description
        
        result = await self.call_service(self.service_name, f"/config/{key}", "POST", data)
        return result is not None
    
    async def update_configs(self, configs: Dict[str, Any], scope: str = "global") -> bool:
        """Update multiple configuration values.
        
        Args:
            configs: Dictionary of configuration key-value pairs
            scope: Configuration scope
            
        Returns:
            True if successful, False otherwise
        """
        data = {
            "configs": configs,
            "scope": scope
        }
        
        result = await self.call_service(self.service_name, "/config", "PUT", data)
        return result is not None
    
    async def delete_config(self, key: str, scope: str = "global") -> bool:
        """Delete a configuration value.
        
        Args:
            key: Configuration key
            scope: Configuration scope
            
        Returns:
            True if successful, False otherwise
        """
        params = {"scope": scope}
        result = await self.call_service(self.service_name, f"/config/{key}", "DELETE", params=params)
        return result is not None

# Synchronous wrapper for backward compatibility
class SyncServiceClient:
    """Synchronous wrapper for ServiceClient."""
    
    def __init__(self, service_discovery_url: str = "http://localhost:8000"):
        self.async_client = ServiceClient(service_discovery_url)
    
    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)
    
    def discover_service(self, service_name: str, force_refresh: bool = False) -> Optional[str]:
        """Discover a service and return its base URL."""
        return self._run_async(self.async_client.discover_service(service_name, force_refresh))
    
    def call_service(self, service_name: str, endpoint: str, method: str = "GET",
                    data: Any = None, params: Dict[str, Any] = None,
                    timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Call a microservice endpoint."""
        return self._run_async(self.async_client.call_service(
            service_name, endpoint, method, data, params, timeout
        ))

class SyncConfigServiceClient(SyncServiceClient):
    """Synchronous client for the Configuration Service."""
    
    def __init__(self, service_discovery_url: str = "http://localhost:8000"):
        super().__init__(service_discovery_url)
        self.async_config_client = ConfigServiceClient(service_discovery_url)
    
    def get_config(self, key: str = None, scope: str = "global") -> Optional[Dict[str, Any]]:
        """Get configuration value(s)."""
        return self._run_async(self.async_config_client.get_config(key, scope))
    
    def set_config(self, key: str, value: Any, scope: str = "global", 
                  description: str = None) -> bool:
        """Set a configuration value."""
        return self._run_async(self.async_config_client.set_config(key, value, scope, description))
    
    def update_configs(self, configs: Dict[str, Any], scope: str = "global") -> bool:
        """Update multiple configuration values."""
        return self._run_async(self.async_config_client.update_configs(configs, scope))
    
    def delete_config(self, key: str, scope: str = "global") -> bool:
        """Delete a configuration value."""
        return self._run_async(self.async_config_client.delete_config(key, scope))

# Global instances for convenience
_service_discovery_url = "http://localhost:8000"
_config_client = None

def get_config_client() -> SyncConfigServiceClient:
    """Get a shared configuration service client instance."""
    global _config_client
    if _config_client is None:
        _config_client = SyncConfigServiceClient(_service_discovery_url)
    return _config_client

def set_service_discovery_url(url: str):
    """Set the service discovery URL for global clients."""
    global _service_discovery_url, _config_client
    _service_discovery_url = url
    _config_client = None  # Reset client to use new URL