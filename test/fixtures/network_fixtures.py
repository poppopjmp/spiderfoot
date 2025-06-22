# -*- coding: utf-8 -*-
"""Network and HTTP fixtures for testing SpiderFoot modules."""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
import requests


@pytest.fixture
def mock_http_response():
    """Mock HTTP response object."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = '<html><body>Test response</body></html>'
    mock_response.content = b'<html><body>Test response</body></html>'
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.url = 'https://example.com'
    mock_response.json.return_value = {'status': 'success', 'data': []}
    mock_response.raise_for_status = Mock()
    return mock_response


@pytest.fixture
def mock_json_response():
    """Mock JSON HTTP response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Type': 'application/json'}
    mock_response.json.return_value = {
        'status': 'success',
        'data': {
            'domain': 'example.com',
            'ip': '93.184.216.34',
            'country': 'US'
        }
    }
    return mock_response


@pytest.fixture
def mock_error_response():
    """Mock HTTP error response."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = 'Not Found'
    mock_response.headers = {'Content-Type': 'text/plain'}
    mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    return mock_response


@pytest.fixture
def mock_timeout_response():
    """Mock HTTP timeout response."""
    mock_response = Mock()
    mock_response.side_effect = requests.Timeout("Request timed out")
    return mock_response


@pytest.fixture
def mock_connection_error():
    """Mock HTTP connection error."""
    return requests.ConnectionError("Connection failed")


@pytest.fixture
def sample_dns_response():
    """Sample DNS response data."""
    return {
        'A': ['93.184.216.34'],
        'AAAA': ['2606:2800:220:1:248:1893:25c8:1946'],
        'MX': [{'priority': 10, 'host': 'mail.example.com'}],
        'NS': ['ns1.example.com', 'ns2.example.com'],
        'TXT': ['v=spf1 include:_spf.example.com ~all']
    }


@pytest.fixture
def sample_whois_response():
    """Sample WHOIS response data."""
    return """
Domain Name: EXAMPLE.COM
Registry Domain ID: 2336799_DOMAIN_COM-VRSN
Registrar WHOIS Server: whois.iana.org
Registrar URL: http://res-dom.iana.org
Updated Date: 2020-08-14T07:01:31Z
Creation Date: 1995-08-14T04:00:00Z
Registry Expiry Date: 2021-08-13T04:00:00Z
Registrar: RESERVED-Internet Assigned Numbers Authority
Admin Email: admin@example.com
Tech Email: tech@example.com
Name Server: A.IANA-SERVERS.NET
Name Server: B.IANA-SERVERS.NET
"""


@pytest.fixture
def sample_api_responses():
    """Collection of sample API responses for different services."""
    return {
        'virustotal': {
            'response_code': 1,
            'verbose_msg': 'Scan finished',
            'positives': 0,
            'total': 67,
            'scans': {}
        },
        'shodan': {
            'ip_str': '93.184.216.34',
            'country_name': 'United States',
            'city': 'Norwell',
            'ports': [80, 443],
            'hostnames': ['example.com']
        },
        'censys': {
            'status': 'ok',
            'results': [
                {
                    'ip': '93.184.216.34',
                    'protocols': ['80/http', '443/https'],
                    'location.country': 'United States'
                }
            ]
        }
    }


@pytest.fixture
def mock_requests_session():
    """Mock requests session for HTTP operations."""
    session = Mock()
    session.get = Mock()
    session.post = Mock()
    session.put = Mock()
    session.delete = Mock()
    session.headers = {}
    session.cookies = {}
    return session


@pytest.fixture 
def http_error_scenarios():
    """Different HTTP error scenarios for testing."""
    return {
        'timeout': requests.Timeout("Request timed out"),
        'connection_error': requests.ConnectionError("Failed to establish connection"),
        'http_error_404': requests.HTTPError("404 Client Error"),
        'http_error_500': requests.HTTPError("500 Server Error"),
        'invalid_json': json.JSONDecodeError("Invalid JSON", "", 0)
    }


class MockWebClient:
    """Mock web client for consistent HTTP testing."""
    
    def __init__(self):
        self.responses = {}
        self.request_count = 0
        self.last_request = None
        
    def set_response(self, url, response_data, status_code=200):
        """Set mock response for specific URL."""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.text = response_data
        mock_response.content = response_data.encode() if isinstance(response_data, str) else response_data
        mock_response.json.return_value = response_data if isinstance(response_data, dict) else {}
        self.responses[url] = mock_response
        
    def get(self, url, **kwargs):
        """Mock GET request."""
        self.request_count += 1
        self.last_request = {'method': 'GET', 'url': url, 'kwargs': kwargs}
        return self.responses.get(url, self._default_response())
        
    def post(self, url, **kwargs):
        """Mock POST request."""
        self.request_count += 1
        self.last_request = {'method': 'POST', 'url': url, 'kwargs': kwargs}
        return self.responses.get(url, self._default_response())
        
    def _default_response(self):
        """Default response when URL not found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        return mock_response


@pytest.fixture
def mock_web_client():
    """Create mock web client instance."""
    return MockWebClient()


@pytest.fixture
def network_test_data():
    """Common network test data."""
    return {
        'valid_domains': [
            'example.com',
            'subdomain.example.com',
            'test-domain.org'
        ],
        'valid_ips': [
            '93.184.216.34',
            '192.168.1.1',
            '10.0.0.1'
        ],
        'valid_urls': [
            'https://example.com',
            'http://subdomain.example.com/path',
            'https://example.com:8080/api/v1'
        ],
        'invalid_domains': [
            'invalid..domain',
            'toolongdomainname' * 10,
            ''
        ],
        'invalid_ips': [
            '256.256.256.256',
            '192.168.1',
            'not.an.ip'
        ]
    }


@pytest.fixture
def mock_ssl_context():
    """Mock SSL context for HTTPS testing."""
    mock_context = Mock()
    mock_context.check_hostname = False
    mock_context.verify_mode = 0
    return mock_context
