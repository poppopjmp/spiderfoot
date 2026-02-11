"""
Tests for the DnsService.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from spiderfoot.services.dns_service import DnsService, DnsServiceConfig


class TestDnsServiceConfig(unittest.TestCase):
    """Test DnsServiceConfig."""
    
    def test_defaults(self):
        config = DnsServiceConfig()
        self.assertEqual(config.nameservers, [])
        self.assertEqual(config.timeout, 5.0)
        self.assertTrue(config.cache_enabled)
    
    def test_from_sf_config(self):
        sf_opts = {
            "_dnsserver": "8.8.8.8, 1.1.1.1",
            "_dnstimeout": "10",
        }
        config = DnsServiceConfig.from_sf_config(sf_opts)
        self.assertEqual(config.nameservers, ["8.8.8.8", "1.1.1.1"])
        self.assertEqual(config.timeout, 10.0)
    
    def test_from_sf_config_empty(self):
        config = DnsServiceConfig.from_sf_config({})
        self.assertEqual(config.nameservers, [])


class TestDnsServiceCache(unittest.TestCase):
    """Test DNS caching."""
    
    def setUp(self):
        self.dns = DnsService(DnsServiceConfig(cache_enabled=True, cache_ttl=60))
    
    def test_cache_miss(self):
        result = self.dns._cache_get("nonexistent")
        self.assertIsNone(result)
    
    def test_cache_set_get(self):
        self.dns._cache_set("test_key", ["1.2.3.4"])
        result = self.dns._cache_get("test_key")
        self.assertEqual(result, ["1.2.3.4"])
    
    def test_cache_expired(self):
        import time
        self.dns.config.cache_ttl = 0  # Expire immediately
        self.dns._cache_set("test_key", ["1.2.3.4"])
        time.sleep(0.01)
        result = self.dns._cache_get("test_key")
        self.assertIsNone(result)
    
    def test_cache_disabled(self):
        self.dns.config.cache_enabled = False
        self.dns._cache_set("test_key", ["1.2.3.4"])
        result = self.dns._cache_get("test_key")
        self.assertIsNone(result)
    
    def test_cache_clear(self):
        self.dns._cache_set("key1", "val1")
        self.dns._cache_set("key2", "val2")
        self.assertEqual(self.dns.cache_size(), 2)
        self.dns.cache_clear()
        self.assertEqual(self.dns.cache_size(), 0)


class TestDnsServiceResolve(unittest.TestCase):
    """Test DNS resolution with mocked backend."""
    
    def setUp(self):
        self.dns = DnsService(DnsServiceConfig(cache_enabled=False))
    
    @patch("socket.gethostbyname_ex")
    def test_resolve_host_socket_fallback(self, mock_resolve):
        # When dnspython not available, falls back to socket
        with patch("spiderfoot.dns_service.HAS_DNSPYTHON", False):
            dns_svc = DnsService(DnsServiceConfig(cache_enabled=False))
            mock_resolve.return_value = ("example.com", [], ["93.184.216.34"])
            
            results = dns_svc.resolve_host("example.com")
            self.assertEqual(results, ["93.184.216.34"])
    
    @patch("socket.gethostbyname_ex")
    def test_resolve_host_nxdomain(self, mock_resolve):
        with patch("spiderfoot.dns_service.HAS_DNSPYTHON", False):
            dns_svc = DnsService(DnsServiceConfig(cache_enabled=False))
            import socket
            mock_resolve.side_effect = socket.gaierror("not found")
            
            results = dns_svc.resolve_host("nonexistent.example.com")
            self.assertEqual(results, [])
    
    @patch("socket.gethostbyaddr")
    def test_reverse_resolve_socket_fallback(self, mock_reverse):
        with patch("spiderfoot.dns_service.HAS_DNSPYTHON", False):
            dns_svc = DnsService(DnsServiceConfig(cache_enabled=False))
            mock_reverse.return_value = ("example.com", [], ["93.184.216.34"])
            
            results = dns_svc.reverse_resolve("93.184.216.34")
            self.assertEqual(results, ["example.com"])
    
    def test_validate_ip_match(self):
        with patch.object(self.dns, "resolve_host", return_value=["1.2.3.4"]):
            with patch.object(self.dns, "resolve_host6", return_value=[]):
                self.assertTrue(self.dns.validate_ip("example.com", "1.2.3.4"))
    
    def test_validate_ip_no_match(self):
        with patch.object(self.dns, "resolve_host", return_value=["1.2.3.4"]):
            with patch.object(self.dns, "resolve_host6", return_value=[]):
                self.assertFalse(self.dns.validate_ip("example.com", "5.6.7.8"))
    
    def test_check_wildcard_no_wildcard(self):
        with patch.object(self.dns, "resolve_host", return_value=[]):
            self.assertFalse(self.dns.check_wildcard("example.com"))
    
    def test_check_wildcard_detected(self):
        with patch.object(self.dns, "resolve_host", return_value=["1.2.3.4"]):
            self.assertTrue(self.dns.check_wildcard("example.com"))


class TestDnsServiceStats(unittest.TestCase):
    """Test stats and metrics."""
    
    def test_stats_initial(self):
        dns_svc = DnsService()
        stats = dns_svc.stats()
        self.assertEqual(stats["query_count"], 0)
        self.assertEqual(stats["cache_hits"], 0)
        self.assertEqual(stats["cache_size"], 0)
        self.assertTrue(stats["cache_enabled"])
    
    def test_query_count_increments(self):
        dns_svc = DnsService(DnsServiceConfig(cache_enabled=False))
        with patch("spiderfoot.dns_service.HAS_DNSPYTHON", False):
            dns_svc_nolib = DnsService(DnsServiceConfig(cache_enabled=False))
            with patch("socket.gethostbyname_ex", return_value=("h", [], ["1.1.1.1"])):
                dns_svc_nolib.resolve_host("test.com")
                self.assertEqual(dns_svc_nolib._query_count, 1)


if __name__ == "__main__":
    unittest.main()
