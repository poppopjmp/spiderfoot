"""
Tests for the HttpService.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from spiderfoot.http_service import HttpService, HttpServiceConfig


class TestHttpServiceConfig(unittest.TestCase):
    """Test HttpServiceConfig."""
    
    def test_defaults(self):
        config = HttpServiceConfig()
        self.assertEqual(config.proxy_type, "")
        self.assertEqual(config.timeout, 30)
        self.assertEqual(config.user_agent, "SpiderFoot")
        self.assertTrue(config.ssl_verify)
    
    def test_from_sf_config(self):
        sf_opts = {
            "_socks1type": "SOCKS5",
            "_socks2addr": "proxy.example.com",
            "_socks3port": "9050",
            "_socks4user": "user",
            "_socks5pwd": "pass",
            "_fetchtimeout": "60",
            "_googlecseapi": "gkey",
            "_googlecseid": "gid",
            "_bingkey": "bkey",
        }
        config = HttpServiceConfig.from_sf_config(sf_opts)
        self.assertEqual(config.proxy_type, "SOCKS5")
        self.assertEqual(config.proxy_host, "proxy.example.com")
        self.assertEqual(config.proxy_port, 9050)
        self.assertEqual(config.timeout, 60)
        self.assertEqual(config.google_api_key, "gkey")
        self.assertEqual(config.bing_api_key, "bkey")
    
    def test_from_sf_config_defaults(self):
        config = HttpServiceConfig.from_sf_config({})
        self.assertEqual(config.proxy_type, "")
        self.assertEqual(config.timeout, 30)


class TestHttpService(unittest.TestCase):
    """Test HttpService."""
    
    def setUp(self):
        self.http = HttpService()
    
    def test_url_fqdn(self):
        self.assertEqual(
            HttpService.url_fqdn("https://example.com/path?q=1"),
            "example.com"
        )
        self.assertEqual(
            HttpService.url_fqdn("http://sub.domain.org:8080/"),
            "sub.domain.org"
        )
    
    def test_url_base(self):
        self.assertEqual(
            HttpService.url_base("https://example.com/path/page.html"),
            "https://example.com"
        )
    
    def test_should_use_proxy_no_config(self):
        self.assertFalse(self.http._should_use_proxy("https://example.com"))
    
    def test_should_use_proxy_skip_localhost(self):
        self.http.config.proxy_type = "SOCKS5"
        self.assertFalse(self.http._should_use_proxy("http://localhost:8080"))
        self.assertFalse(self.http._should_use_proxy("http://127.0.0.1:80"))
    
    def test_should_use_proxy_external(self):
        self.http.config.proxy_type = "SOCKS5"
        self.assertTrue(self.http._should_use_proxy("https://example.com"))
    
    def test_get_proxy_dict_empty(self):
        self.assertEqual(self.http._get_proxy_dict(), {})
    
    def test_get_proxy_dict_configured(self):
        self.http.config.proxy_type = "socks5"
        self.http.config.proxy_host = "proxy.local"
        self.http.config.proxy_port = 9050
        proxies = self.http._get_proxy_dict()
        self.assertIn("http", proxies)
        self.assertIn("socks5://proxy.local:9050", proxies["http"])
    
    def test_get_proxy_dict_with_auth(self):
        self.http.config.proxy_type = "socks5"
        self.http.config.proxy_host = "proxy.local"
        self.http.config.proxy_port = 9050
        self.http.config.proxy_username = "user"
        self.http.config.proxy_password = "pass"
        proxies = self.http._get_proxy_dict()
        self.assertIn("user:pass@", proxies["http"])
    
    @patch("spiderfoot.http_service.requests")
    def test_fetch_url_success(self, mock_requests):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.url = "https://example.com"
        mock_response.text = "<html>Hello</html>"
        
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session
        
        result = self.http.fetch_url("https://example.com")
        
        self.assertEqual(result["code"], "200")
        self.assertEqual(result["content"], "<html>Hello</html>")
        mock_session.close.assert_called_once()
    
    @patch("spiderfoot.http_service.requests")
    def test_fetch_url_post(self, mock_requests):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {}
        mock_response.url = "https://example.com"
        mock_response.text = "ok"
        
        mock_session.post.return_value = mock_response
        mock_requests.Session.return_value = mock_session
        
        result = self.http.fetch_url(
            "https://example.com",
            post_data="key=value"
        )
        
        self.assertEqual(result["code"], "200")
        mock_session.post.assert_called_once()
    
    @patch("spiderfoot.http_service.requests")
    def test_fetch_url_head(self, mock_requests):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {}
        mock_response.url = "https://example.com"
        
        mock_session.head.return_value = mock_response
        mock_requests.Session.return_value = mock_session
        
        result = self.http.fetch_url("https://example.com", head_only=True)
        
        self.assertEqual(result["code"], "200")
        self.assertIsNone(result["content"])
    
    @patch("spiderfoot.http_service.requests")
    def test_fetch_url_timeout(self, mock_requests):
        mock_session = MagicMock()
        mock_session.get.side_effect = mock_requests.exceptions.Timeout()
        mock_requests.Session.return_value = mock_session
        
        result = self.http.fetch_url("https://example.com")
        
        self.assertIsNone(result["code"])
        self.assertEqual(result["status"], "Timeout")
    
    def test_stats(self):
        stats = self.http.stats()
        self.assertEqual(stats["session_count"], 0)
        self.assertFalse(stats["proxy_configured"])
    
    def test_google_iterate_no_key(self):
        result = self.http.google_iterate("test query")
        self.assertEqual(result["urls"], [])
    
    def test_bing_iterate_no_key(self):
        result = self.http.bing_iterate("test query")
        self.assertEqual(result["urls"], [])
    
    @patch("spiderfoot.http_service.requests")
    def test_google_iterate_with_results(self, mock_requests):
        self.http.config.google_api_key = "test-key"
        self.http.config.google_cse_id = "test-cse"
        
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.headers = {}
        mock_response.text = json.dumps({
            "items": [
                {"link": "https://result1.com"},
                {"link": "https://result2.com"},
            ],
            "url": "https://search.google.com/cse?q=test",
        })
        mock_response.url = "https://googleapis.com"
        
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session
        
        result = self.http.google_iterate("test query")
        
        self.assertEqual(len(result["urls"]), 2)
        self.assertIn("https://result1.com", result["urls"])


class TestHttpServiceSSL(unittest.TestCase):
    """Test SSL/TLS utilities."""
    
    def setUp(self):
        self.http = HttpService()
    
    def test_parse_cert_no_crypto(self):
        """Gracefully handle missing cryptography lib."""
        with patch("spiderfoot.http_service.HAS_CRYPTO", False):
            result = self.http.parse_cert("fake cert")
            self.assertEqual(result["issuer"], "")
            self.assertFalse(result["expired"])


if __name__ == "__main__":
    unittest.main()
