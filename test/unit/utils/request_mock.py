"""Utilities for mocking HTTP requests in tests."""

import json
import re
from unittest.mock import patch, MagicMock
from contextlib import contextmanager


class RequestMock:
    """Helper class for mocking HTTP requests in tests."""
    
    @staticmethod
    def mock_response(content=None, status_code=200, headers=None):
        """Create a mock response for HTTP requests.
        
        Args:
            content (str): Response content
            status_code (int): HTTP status code
            headers (dict): HTTP headers
            
        Returns:
            dict: Mocked response in SpiderFoot format
        """
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        
        return {
            'code': str(status_code),
            'content': content,
            'headers': headers
        }
    
    @staticmethod
    def register_url_matcher(url_pattern, response, method=None):
        """Create a function that matches URLs against a pattern and returns a response.
        
        Args:
            url_pattern (str): Regex pattern to match URLs
            response (dict): Response to return for matching URLs
            method (str): HTTP method to match (GET, POST, etc.) or None for any
            
        Returns:
            function: URL matcher function
        """
        pattern = re.compile(url_pattern)
        
        def matcher(url, data=None, useragent=None, headers=None, timeout=None, noLog=False, 
                   postData=None, cookies=None, verify=True, dontMangle=False, 
                   sizeLimit=None, headOnly=False, method=None, **kwargs):
            if method and method != method:
                return None  # Method doesn't match
                
            if pattern.match(url):
                return response
            
            return None
            
        return matcher
    
    @staticmethod
    @contextmanager
    def mock_requests(url_responses=None):
        """Context manager to mock requests for specific URLs.
        
        Args:
            url_responses (dict): Dictionary mapping URL patterns to responses
            
        Yields:
            None
        """
        if url_responses is None:
            url_responses = {}
            
        matchers = []
        for url_pattern, response in url_responses.items():
            if isinstance(response, tuple):
                response = RequestMock.mock_response(
                    content=response[0], 
                    status_code=response[1] if len(response) > 1 else 200,
                    headers=response[2] if len(response) > 2 else None
                )
            
            matchers.append(RequestMock.register_url_matcher(url_pattern, response))
            
        def mock_fetch_url(self, url, *args, **kwargs):
            for matcher in matchers:
                response = matcher(url, *args, **kwargs)
                if response:
                    return response
                    
            # Default response for unmatched URLs
            return RequestMock.mock_response(
                content=json.dumps({"error": "No mock response defined for this URL"}),
                status_code=404
            )
            
        with patch('sflib.SpiderFoot.fetchUrl', mock_fetch_url):
            yield
            
    @staticmethod
    def create_generic_api_mock(responses=None):
        """Create a generic API mock object for common API interactions.
        
        Args:
            responses (dict): Dictionary mapping method names to responses
            
        Returns:
            object: Mock API object
        """
        if responses is None:
            responses = {}
            
        class MockAPI:
            def __init__(self, responses):
                self.responses = responses
                self.calls = {}
                
            def __getattr__(self, name):
                if name in self.responses:
                    self.calls[name] = self.calls.get(name, 0) + 1
                    response = self.responses[name]
                    return lambda *args, **kwargs: response
                
                # Create a new mock method that records calls
                def mock_method(*args, **kwargs):
                    self.calls[name] = self.calls.get(name, 0) + 1
                    return None
                
                return mock_method
        
        return MockAPI(responses)
