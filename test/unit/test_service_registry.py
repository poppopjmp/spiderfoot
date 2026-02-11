"""
Tests for the ServiceRegistry and dependency injection.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.service_registry import (
    ServiceRegistry,
    ServiceNotFoundError,
    ServiceMixin,
    get_registry,
    reset_registry,
    initialize_services,
    SERVICE_HTTP,
    SERVICE_DNS,
    SERVICE_CACHE,
    SERVICE_DATA,
    SERVICE_EVENT_BUS,
    SERVICE_VECTOR,
)


class TestServiceRegistry(unittest.TestCase):
    """Test ServiceRegistry core functionality."""
    
    def setUp(self):
        self.registry = ServiceRegistry()
    
    def test_register_and_get(self):
        mock_service = MagicMock()
        self.registry.register("test", mock_service)
        result = self.registry.get("test")
        self.assertEqual(result, mock_service)
    
    def test_get_not_found(self):
        with self.assertRaises(ServiceNotFoundError) as ctx:
            self.registry.get("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))
    
    def test_get_optional_found(self):
        mock = MagicMock()
        self.registry.register("test", mock)
        self.assertEqual(self.registry.get_optional("test"), mock)
    
    def test_get_optional_not_found(self):
        self.assertIsNone(self.registry.get_optional("nonexistent"))
    
    def test_has(self):
        self.assertFalse(self.registry.has("test"))
        self.registry.register("test", MagicMock())
        self.assertTrue(self.registry.has("test"))
    
    def test_has_factory(self):
        self.registry.register_factory("test", lambda: MagicMock())
        self.assertTrue(self.registry.has("test"))
    
    def test_unregister(self):
        mock = MagicMock()
        self.registry.register("test", mock)
        removed = self.registry.unregister("test")
        self.assertEqual(removed, mock)
        self.assertFalse(self.registry.has("test"))
    
    def test_unregister_nonexistent(self):
        result = self.registry.unregister("nonexistent")
        self.assertIsNone(result)
    
    def test_list_services(self):
        self.registry.register("svc1", MagicMock())
        self.registry.register("svc2", MagicMock())
        self.registry.register_factory("svc3", lambda: MagicMock())
        services = self.registry.list_services()
        self.assertIn("svc1", services)
        self.assertIn("svc2", services)
        self.assertIn("svc3", services)
    
    def test_clear(self):
        self.registry.register("svc1", MagicMock())
        self.registry.register_factory("svc2", lambda: MagicMock())
        self.registry.clear()
        self.assertEqual(len(self.registry.list_services()), 0)
    
    def test_overwrite_warning(self):
        self.registry.register("test", MagicMock())
        self.registry.register("test", MagicMock())  # Should warn, not error
        self.assertTrue(self.registry.has("test"))
    
    def test_stats(self):
        self.registry.register("svc1", MagicMock(spec=object))
        self.registry.register_factory("svc2", lambda: MagicMock())
        stats = self.registry.stats()
        self.assertIn("svc1", stats["services"])
        self.assertIn("svc2", stats["pending_factories"])
        self.assertEqual(stats["total_registered"], 2)


class TestLazyFactory(unittest.TestCase):
    """Test lazy factory-based service creation."""
    
    def setUp(self):
        self.registry = ServiceRegistry()
    
    def test_factory_called_on_first_access(self):
        mock = MagicMock()
        factory = MagicMock(return_value=mock)
        
        self.registry.register_factory("test", factory)
        factory.assert_not_called()  # Not called yet
        
        result = self.registry.get("test")
        factory.assert_called_once()
        self.assertEqual(result, mock)
    
    def test_factory_result_cached(self):
        call_count = 0
        
        def factory():
            nonlocal call_count
            call_count += 1
            return MagicMock()
        
        self.registry.register_factory("test", factory)
        
        result1 = self.registry.get("test")
        result2 = self.registry.get("test")
        
        self.assertEqual(call_count, 1)  # Only called once
        self.assertEqual(result1, result2)  # Same instance
    
    def test_instance_overrides_factory(self):
        mock_instance = MagicMock()
        mock_factory = MagicMock(return_value=MagicMock())
        
        self.registry.register_factory("test", mock_factory)
        self.registry.register("test", mock_instance)
        
        result = self.registry.get("test")
        self.assertEqual(result, mock_instance)
        mock_factory.assert_not_called()


class TestGlobalRegistry(unittest.TestCase):
    """Test global registry singleton."""
    
    def setUp(self):
        reset_registry()
    
    def tearDown(self):
        reset_registry()
    
    def test_get_registry_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        self.assertIs(r1, r2)
    
    def test_reset_registry(self):
        r1 = get_registry()
        r1.register("test", MagicMock())
        reset_registry()
        r2 = get_registry()
        self.assertIsNot(r1, r2)
        self.assertFalse(r2.has("test"))


class TestServiceMixin(unittest.TestCase):
    """Test ServiceMixin for components."""
    
    def setUp(self):
        reset_registry()
    
    def tearDown(self):
        reset_registry()
    
    def test_get_service_from_local_registry(self):
        class MyComponent(ServiceMixin):
            pass
        
        registry = ServiceRegistry()
        mock_http = MagicMock()
        registry.register(SERVICE_HTTP, mock_http)
        
        component = MyComponent()
        component.set_registry(registry)
        
        result = component.get_service(SERVICE_HTTP)
        self.assertEqual(result, mock_http)
    
    def test_get_service_from_global_registry(self):
        class MyComponent(ServiceMixin):
            pass
        
        global_reg = get_registry()
        mock_dns = MagicMock()
        global_reg.register(SERVICE_DNS, mock_dns)
        
        component = MyComponent()
        result = component.get_service(SERVICE_DNS)
        self.assertEqual(result, mock_dns)
    
    def test_convenience_properties(self):
        class MyComponent(ServiceMixin):
            pass
        
        registry = ServiceRegistry()
        mock_http = MagicMock()
        mock_dns = MagicMock()
        mock_cache = MagicMock()
        
        registry.register(SERVICE_HTTP, mock_http)
        registry.register(SERVICE_DNS, mock_dns)
        registry.register(SERVICE_CACHE, mock_cache)
        
        component = MyComponent()
        component.set_registry(registry)
        
        self.assertEqual(component.http_service, mock_http)
        self.assertEqual(component.dns_service, mock_dns)
        self.assertEqual(component.cache_service, mock_cache)
    
    def test_get_service_optional(self):
        class MyComponent(ServiceMixin):
            pass
        
        component = MyComponent()
        component.set_registry(ServiceRegistry())
        
        result = component.get_service_optional("nonexistent")
        self.assertIsNone(result)


class TestInitializeServices(unittest.TestCase):
    """Test the full service initialization."""
    
    def setUp(self):
        reset_registry()
    
    def tearDown(self):
        reset_registry()
    
    def test_initialize_registers_all_factories(self):
        sf_config = {
            "__database": ":memory:",
            "__dbtype": "sqlite",
        }
        registry = initialize_services(sf_config)
        
        # All services should be registered as factories
        self.assertTrue(registry.has(SERVICE_EVENT_BUS))
        self.assertTrue(registry.has(SERVICE_DATA))
        self.assertTrue(registry.has(SERVICE_HTTP))
        self.assertTrue(registry.has(SERVICE_DNS))
        self.assertTrue(registry.has(SERVICE_CACHE))
        self.assertTrue(registry.has(SERVICE_VECTOR))
    
    def test_http_service_lazy_creation(self):
        sf_config = {}
        registry = initialize_services(sf_config)
        
        # HTTP should be created on first access
        http = registry.get(SERVICE_HTTP)
        self.assertIsNotNone(http)
        
        # Should have the expected type
        from spiderfoot.services.http_service import HttpService
        self.assertIsInstance(http, HttpService)
    
    def test_dns_service_lazy_creation(self):
        sf_config = {}
        registry = initialize_services(sf_config)
        
        dns = registry.get(SERVICE_DNS)
        self.assertIsNotNone(dns)
        
        from spiderfoot.services.dns_service import DnsService
        self.assertIsInstance(dns, DnsService)
    
    def test_cache_service_lazy_creation(self):
        sf_config = {}
        registry = initialize_services(sf_config)
        
        cache = registry.get(SERVICE_CACHE)
        self.assertIsNotNone(cache)


if __name__ == "__main__":
    unittest.main()
