"""
ServiceRegistry — Dependency Injection container for SpiderFoot services.

Central registry that holds all service instances and provides them
to modules, scanners, and other consumers. This replaces the god-object
pattern where SpiderFoot core held all capabilities.

Usage:
    registry = ServiceRegistry()
    registry.register("http", HttpService(config))
    registry.register("dns", DnsService(config))
    
    # In a module:
    http = registry.get("http")
    result = http.fetch_url("https://example.com")
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

log = logging.getLogger("spiderfoot.registry")


# Well-known service names
SERVICE_EVENT_BUS = "event_bus"
SERVICE_DATA = "data"
SERVICE_HTTP = "http"
SERVICE_DNS = "dns"
SERVICE_CACHE = "cache"
SERVICE_VECTOR = "vector"


class ServiceNotFoundError(Exception):
    """Raised when a requested service is not registered."""
    pass


class ServiceRegistry:
    """Central service registry and dependency injection container.
    
    Thread-safe registry for managing service lifecycles.
    Supports eager registration and lazy factory-based creation.
    
    Attributes:
        _services: Dict of registered service instances
        _factories: Dict of lazy service factories
        _lock: Thread lock for safe concurrent access
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._lock = threading.RLock()
        self._initialized = False
        self.log = logging.getLogger("spiderfoot.registry")
    
    def register(self, name: str, service: Any) -> None:
        """Register a service instance.
        
        Args:
            name: Service name (use SERVICE_* constants)
            service: Service instance
        """
        with self._lock:
            if name in self._services:
                self.log.warning(f"Overwriting existing service: {name}")
            self._services[name] = service
            self.log.debug(f"Registered service: {name} ({type(service).__name__})")
    
    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a lazy service factory.
        
        The factory will be called on first access and the result cached.
        
        Args:
            name: Service name
            factory: Callable that creates the service
        """
        with self._lock:
            self._factories[name] = factory
            self.log.debug(f"Registered factory: {name}")
    
    def get(self, name: str) -> Any:
        """Get a service by name.
        
        If a factory is registered but no instance exists, the factory
        is invoked and the result is cached.
        
        Args:
            name: Service name
            
        Returns:
            Service instance
            
        Raises:
            ServiceNotFoundError: If service is not registered
        """
        with self._lock:
            # Check for existing instance
            if name in self._services:
                return self._services[name]
            
            # Try factory
            if name in self._factories:
                self.log.debug(f"Creating service from factory: {name}")
                service = self._factories[name]()
                self._services[name] = service
                del self._factories[name]
                return service
            
            raise ServiceNotFoundError(
                f"Service '{name}' not registered. "
                f"Available: {list(self._services.keys())}"
            )
    
    def get_optional(self, name: str) -> Optional[Any]:
        """Get a service by name, returning None if not found.
        
        Args:
            name: Service name
            
        Returns:
            Service instance or None
        """
        try:
            return self.get(name)
        except ServiceNotFoundError:
            return None
    
    def has(self, name: str) -> bool:
        """Check if a service is registered (instance or factory).
        
        Args:
            name: Service name
            
        Returns:
            True if registered
        """
        with self._lock:
            return name in self._services or name in self._factories
    
    def unregister(self, name: str) -> Optional[Any]:
        """Remove a service from the registry.
        
        Args:
            name: Service name
            
        Returns:
            The removed service instance, or None
        """
        with self._lock:
            service = self._services.pop(name, None)
            self._factories.pop(name, None)
            if service:
                self.log.debug(f"Unregistered service: {name}")
            return service
    
    def list_services(self) -> List[str]:
        """List all registered service names.
        
        Returns:
            List of service names (instances + pending factories)
        """
        with self._lock:
            return list(set(
                list(self._services.keys()) + list(self._factories.keys())
            ))
    
    def clear(self) -> None:
        """Remove all services."""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self.log.debug("Registry cleared")
    
    def stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        with self._lock:
            return {
                "services": {
                    name: type(svc).__name__
                    for name, svc in self._services.items()
                },
                "pending_factories": list(self._factories.keys()),
                "total_registered": len(self._services) + len(self._factories),
            }


# Global registry instance
_global_registry: Optional[ServiceRegistry] = None
_global_lock = threading.Lock()


def get_registry() -> ServiceRegistry:
    """Get the global ServiceRegistry singleton.
    
    Creates one if it doesn't exist.
    
    Returns:
        Global ServiceRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        with _global_lock:
            if _global_registry is None:
                _global_registry = ServiceRegistry()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry (mainly for testing)."""
    global _global_registry
    with _global_lock:
        if _global_registry:
            _global_registry.clear()
        _global_registry = None


def initialize_services(sf_config: Dict[str, Any]) -> ServiceRegistry:
    """Initialize all services from SpiderFoot configuration.
    
    Creates and registers all core services based on the provided
    configuration dict. This is the main entry point for bootstrapping
    the service layer.
    
    Args:
        sf_config: SpiderFoot configuration dict
        
    Returns:
        Configured ServiceRegistry with all services registered
    """
    registry = get_registry()
    
    # --- Event Bus ---
    def _create_event_bus():
        try:
            from spiderfoot.eventbus.factory import create_event_bus_from_config
            return create_event_bus_from_config(sf_config)
        except Exception as e:
            log.warning(f"EventBus creation failed, using in-memory: {e}")
            from spiderfoot.eventbus.memory import InMemoryEventBus
            return InMemoryEventBus()
    
    registry.register_factory(SERVICE_EVENT_BUS, _create_event_bus)
    
    # --- Data Service ---
    def _create_data_service():
        try:
            from spiderfoot.data_service.factory import create_data_service_from_config
            return create_data_service_from_config(sf_config)
        except Exception as e:
            log.error(f"DataService creation failed: {e}")
            raise
    
    registry.register_factory(SERVICE_DATA, _create_data_service)
    
    # --- HTTP Service ---
    def _create_http_service():
        from spiderfoot.http_service import HttpService, HttpServiceConfig
        config = HttpServiceConfig.from_sf_config(sf_config)
        return HttpService(config)
    
    registry.register_factory(SERVICE_HTTP, _create_http_service)
    
    # --- DNS Service ---
    def _create_dns_service():
        from spiderfoot.dns_service import DnsService, DnsServiceConfig
        config = DnsServiceConfig.from_sf_config(sf_config)
        return DnsService(config)
    
    registry.register_factory(SERVICE_DNS, _create_dns_service)
    
    # --- Cache Service ---
    def _create_cache_service():
        from spiderfoot.cache_service import create_cache_from_config
        return create_cache_from_config(sf_config)
    
    registry.register_factory(SERVICE_CACHE, _create_cache_service)
    
    # --- Vector Sink ---
    def _create_vector_sink():
        from spiderfoot.vector_sink import VectorSink, VectorConfig
        config = VectorConfig.from_sf_config(sf_config)
        if config.enabled:
            sink = VectorSink(config)
            sink.start()
            return sink
        return None
    
    registry.register_factory(SERVICE_VECTOR, _create_vector_sink)
    
    log.info("Service registry initialized with lazy factories")
    return registry


class ServiceMixin:
    """Mixin class that provides service access to modules/components.
    
    Add this mixin to any class that needs access to services:
    
        class MyModule(SpiderFootPlugin, ServiceMixin):
            def setup(self):
                http = self.get_service("http")
                result = http.fetch_url("https://example.com")
    """
    
    _registry: Optional[ServiceRegistry] = None
    
    def set_registry(self, registry: ServiceRegistry) -> None:
        """Set the service registry for this component."""
        self._registry = registry
    
    def get_service(self, name: str) -> Any:
        """Get a service from the registry.
        
        Falls back to the global registry if no local registry is set.
        
        Args:
            name: Service name
            
        Returns:
            Service instance
        """
        reg = self._registry or get_registry()
        return reg.get(name)
    
    def get_service_optional(self, name: str) -> Optional[Any]:
        """Get a service, returning None if not available."""
        reg = self._registry or get_registry()
        return reg.get_optional(name)
    
    @property
    def http_service(self):
        """Convenience accessor for HttpService."""
        return self.get_service(SERVICE_HTTP)
    
    @property
    def dns_service(self):
        """Convenience accessor for DnsService."""
        return self.get_service(SERVICE_DNS)
    
    @property
    def cache_service(self):
        """Convenience accessor for CacheService."""
        return self.get_service(SERVICE_CACHE)
    
    @property
    def data_service(self):
        """Convenience accessor for DataService."""
        return self.get_service(SERVICE_DATA)
    
    @property
    def event_bus(self):
        """Convenience accessor for EventBus."""
        return self.get_service(SERVICE_EVENT_BUS)
