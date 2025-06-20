# Custom Modules Development

This guide covers creating custom modules for SpiderFoot to extend its data collection capabilities with your own sources and logic.

## Getting Started

### Module Basics

SpiderFoot modules are Python classes that inherit from `SpiderFootPlugin`. Each module:
- Watches for specific event types
- Processes events when they occur
- Generates new events based on discoveries
- Can interact with external APIs or services

### Simple Module Example

```python
from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_custom_example(SpiderFootPlugin):
    meta = {
        'name': "Custom Example Module",
        'summary': "Example custom module for demonstration",
        'flags': [""],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Custom"],
        'dataSource': {
            'website': "https://example.com",
            'model': "FREE_NOAUTH_UNLIMITED"
        }
    }

    opts = {
        'timeout': 30,
        'verify': True
    }

    optdescs = {
        'timeout': "Timeout for requests in seconds",
        'verify': "Verify hostnames resolve"
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["DOMAIN_NAME"]

    def producedEvents(self):
        return ["IP_ADDRESS"]

    def handleEvent(self, event):
        eventData = event.data
        
        # Avoid duplicates
        if eventData in self.results:
            return
        self.results[eventData] = True
        
        # Your custom logic here
        self.info(f"Processing {eventData}")
        
        # Example: resolve domain to IP
        try:
            ips = self.sf.resolveHost(eventData)
            for ip in ips:
                evt = SpiderFootEvent("IP_ADDRESS", ip, self.__name__, event)
                self.notifyListeners(evt)
        except Exception as e:
            self.error(f"Error processing {eventData}: {e}")
```

## Module Development Steps

### 1. Planning Your Module

Before coding, define:
- **Purpose**: What will your module do?
- **Data Sources**: What external services will it use?
- **Input Events**: What events will trigger your module?
- **Output Events**: What new events will it generate?
- **Configuration**: What options does it need?

### 2. Setting Up Development Environment

```bash
# Navigate to SpiderFoot directory
cd spiderfoot

# Create your module file
touch modules/sfp_your_module_name.py

# Test module syntax
python -m py_compile modules/sfp_your_module_name.py

# Test module functionality
python sf.py -s example.com -t DOMAIN_NAME -m sfp_your_module_name -v
```

### 3. Module Structure

```python
from spiderfoot import SpiderFootPlugin, SpiderFootEvent
import json
import requests

class sfp_your_module(SpiderFootPlugin):
    """Your module description."""

    meta = {
        # Module metadata
    }

    opts = {
        # Configuration options
    }

    optdescs = {
        # Option descriptions
    }

    def setup(self, sfc, userOpts=dict()):
        # Initialize module
        pass

    def watchedEvents(self):
        # Return list of event types to watch
        return []

    def producedEvents(self):
        # Return list of event types this module generates
        return []

    def handleEvent(self, event):
        # Main module logic
        pass
```

## API Integration Examples

### REST API Module

```python
class sfp_api_example(SpiderFootPlugin):
    meta = {
        'name': "API Example",
        'summary': "Example API integration module",
        'categories': ["Custom"],
        'dataSource': {
            'website': "https://api.example.com",
            'model': "FREE_AUTH_LIMITED"
        }
    }

    opts = {
        'api_key': '',
        'timeout': 30,
        'max_results': 100
    }

    def handleEvent(self, event):
        if not self.opts['api_key']:
            self.error("API key required")
            return

        # Make API request
        url = f"https://api.example.com/lookup?target={event.data}"
        headers = {
            'Authorization': f'Bearer {self.opts["api_key"]}',
            'User-Agent': self.opts['_useragent']
        }

        response = self.sf.fetchUrl(
            url,
            timeout=self.opts['timeout'],
            useragent=self.opts['_useragent'],
            headers=headers
        )

        if response['content'] is None:
            self.info(f"No response from API for {event.data}")
            return

        try:
            data = json.loads(response['content'])
            self.process_api_response(data, event)
        except json.JSONDecodeError:
            self.error("Invalid JSON response from API")

    def process_api_response(self, data, source_event):
        """Process API response and generate events."""
        for item in data.get('results', []):
            if 'ip_address' in item:
                evt = SpiderFootEvent("IP_ADDRESS", item['ip_address'],
                                    self.__name__, source_event)
                self.notifyListeners(evt)
```

### Web Scraping Module

```python
class sfp_scraper_example(SpiderFootPlugin):
    meta = {
        'name': "Web Scraper Example",
        'summary': "Example web scraping module",
        'categories': ["Custom"]
    }

    def handleEvent(self, event):
        url = f"https://example.com/search?q={event.data}"
        
        response = self.sf.fetchUrl(
            url,
            timeout=self.opts['timeout'],
            useragent=self.opts['_useragent']
        )

        if response['content']:
            self.parse_html_content(response['content'], event)

    def parse_html_content(self, html, source_event):
        """Parse HTML and extract relevant data."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract emails
        for email_link in soup.find_all('a', href=True):
            if email_link['href'].startswith('mailto:'):
                email = email_link['href'][7:]  # Remove 'mailto:'
                evt = SpiderFootEvent("EMAILADDR", email,
                                    self.__name__, source_event)
                self.notifyListeners(evt)
```

## Advanced Module Features

### Rate Limiting

```python
import time

class sfp_rate_limited(SpiderFootPlugin):
    def setup(self, sfc, userOpts=dict()):
        super().setup(sfc, userOpts)
        self.last_request_time = 0
        self.min_delay = 1  # Minimum delay between requests

    def make_api_request(self, url):
        # Implement rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            self.info(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        response = self.sf.fetchUrl(url, timeout=self.opts['timeout'])
        self.last_request_time = time.time()
        
        return response
```

### Caching Results

```python
class sfp_cached_module(SpiderFootPlugin):
    def setup(self, sfc, userOpts=dict()):
        super().setup(sfc, userOpts)
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour

    def get_cached_result(self, key):
        """Get cached result if still valid."""
        if key in self.cache:
            cached_time, result = self.cache[key]
            if time.time() - cached_time < self.cache_ttl:
                return result
        return None

    def cache_result(self, key, result):
        """Cache result with timestamp."""
        self.cache[key] = (time.time(), result)

    def handleEvent(self, event):
        # Check cache first
        cached = self.get_cached_result(event.data)
        if cached:
            self.process_result(cached, event)
            return
        
        # Fetch new data
        result = self.fetch_data(event.data)
        if result:
            self.cache_result(event.data, result)
            self.process_result(result, event)
```

### Parallel Processing

```python
import threading
from concurrent.futures import ThreadPoolExecutor

class sfp_parallel_module(SpiderFootPlugin):
    def setup(self, sfc, userOpts=dict()):
        super().setup(sfc, userOpts)
        self.max_workers = 3
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

    def handleEvent(self, event):
        # Process multiple items in parallel
        items = self.get_items_to_process(event.data)
        
        futures = []
        for item in items:
            future = self.executor.submit(self.process_item, item, event)
            futures.append(future)
        
        # Wait for all to complete
        for future in futures:
            try:
                future.result(timeout=30)
            except Exception as e:
                self.error(f"Parallel processing error: {e}")

    def process_item(self, item, source_event):
        """Process individual item in separate thread."""
        result = self.fetch_data(item)
        if result:
            evt = SpiderFootEvent("CUSTOM_EVENT", result,
                                self.__name__, source_event)
            self.notifyListeners(evt)
```

## Testing Custom Modules

### Unit Testing

```python
import unittest
from unittest.mock import Mock, patch
from sfp_your_module import sfp_your_module

class TestYourModule(unittest.TestCase):
    def setUp(self):
        self.sf = Mock()
        self.module = sfp_your_module()
        self.module.setup(self.sf, {})

    def test_handle_domain_event(self):
        """Test handling of domain name events."""
        event = Mock()
        event.eventType = "DOMAIN_NAME"
        event.data = "example.com"
        
        with patch.object(self.module, 'notifyListeners') as mock_notify:
            self.module.handleEvent(event)
            
            # Verify event was generated
            mock_notify.assert_called()

    def test_api_integration(self):
        """Test API integration functionality."""
        with patch.object(self.module.sf, 'fetchUrl') as mock_fetch:
            mock_fetch.return_value = {
                'content': '{"results": [{"ip": "192.168.1.1"}]}',
                'code': '200'
            }
            
            result = self.module.query_api("example.com")
            self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()
```

### Manual Testing

```bash
# Test module loading
python -c "from modules.sfp_your_module import sfp_your_module; print('Module loads successfully')"

# Test with specific target
python sf.py -s example.com -t DOMAIN_NAME -m sfp_your_module -v

# Test with debug output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_your_module --debug

# Test module options
python sf.py -s example.com -t DOMAIN_NAME -m sfp_your_module -o json
```

## Best Practices

### Code Quality

1. **Follow PEP 8** style guidelines
2. **Add comprehensive docstrings**
3. **Use meaningful variable names**
4. **Handle errors gracefully**
5. **Validate input data**

### Performance

1. **Implement rate limiting** for external APIs
2. **Cache results** when appropriate
3. **Use appropriate timeouts**
4. **Avoid blocking operations**
5. **Monitor resource usage**

### Security

1. **Validate all inputs**
2. **Sanitize outputs**
3. **Use HTTPS for API calls**
4. **Protect API keys**
5. **Follow secure coding practices**

## Deployment and Distribution

### Adding to SpiderFoot

1. **Place module** in `modules/` directory
2. **Test thoroughly** with various inputs
3. **Add documentation** to `docs/modules/`
4. **Submit pull request** to main repository

### Configuration Management

```python
# Example module configuration
opts = {
    'api_key': '',
    'timeout': 30,
    'max_results': 100,
    'enable_caching': True,
    'cache_ttl': 3600,
    'rate_limit_delay': 1
}

optdescs = {
    'api_key': "API key for the service",
    'timeout': "Request timeout in seconds",
    'max_results': "Maximum number of results to return",
    'enable_caching': "Enable result caching",
    'cache_ttl': "Cache time-to-live in seconds",
    'rate_limit_delay': "Minimum delay between requests in seconds"
}
```

### Module Documentation

Include comprehensive documentation:

```python
"""
Custom Module Name

This module provides [functionality description].

Configuration Options:
- api_key: Required API key from [service]
- timeout: Request timeout (default: 30 seconds)
- max_results: Maximum results to process (default: 100)

Event Types:
- Consumes: DOMAIN_NAME, IP_ADDRESS
- Produces: CUSTOM_EVENT_TYPE, ANOTHER_EVENT_TYPE

Usage Examples:
python sf.py -s example.com -t DOMAIN_NAME -m sfp_your_module

Requirements:
- requests library
- BeautifulSoup4 (for HTML parsing)
- API key from service provider
"""
```

For more information on module development, see the [Module Development Guide](../developer/module_development.md) and existing modules in the `modules/` directory for examples.
