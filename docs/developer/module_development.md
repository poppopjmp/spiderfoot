# Module Development Guide

This guide covers how to create custom modules for SpiderFoot to extend its data collection capabilities.

## Module Structure

### Basic Module Template

```python
from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_your_module(SpiderFootPlugin):
    """SpiderFoot plugin for [describe functionality]."""

    meta = {
        'name': "Your Module Name",
        'summary': "Brief description of what the module does",
        'flags': [""],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["DNS"],
        'dataSource': {
            'website': "https://example.com",
            'model': "FREE_NOAUTH_UNLIMITED"
        }
    }

    opts = {
        'timeout': 30,
        'verify': True,
        'api_key': ''
    }

    optdescs = {
        'timeout': "Timeout for requests in seconds",
        'verify': "Verify hostnames resolve",
        'api_key': "API key for the service"
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.results = self.tempStorage()

    def watchedEvents(self):
        return ["DOMAIN_NAME"]

    def producedEvents(self):
        return ["IP_ADDRESS", "SUBDOMAIN"]

    def handleEvent(self, event):
        # Module logic here
        pass
```

## Module Metadata

### Required Fields

- **name**: Human-readable module name
- **summary**: Brief description of functionality
- **categories**: Module categories (DNS, Search, etc.)
- **dataSource**: Information about the data source

### Data Source Models

- `FREE_NOAUTH_UNLIMITED`: Free service, no authentication required
- `FREE_AUTH_UNLIMITED`: Free service, authentication required
- `FREE_NOAUTH_LIMITED`: Free service with rate limits
- `COMMERCIAL_ONLY`: Paid service only
- `PRIVATE_ONLY`: Internal/private data source

### Use Cases

- **Footprint**: External reconnaissance
- **Investigate**: Deep investigation of targets
- **Passive**: Passive information gathering

### Categories

- **DNS**: DNS-related functionality
- **Search**: Search engine queries
- **Social Media**: Social media platforms
- **Threat Intel**: Threat intelligence sources
- **Secondary**: Processes data from other modules

## Event Handling

### Watched Events

Events that trigger your module:

```python
def watchedEvents(self):
    return [
        "DOMAIN_NAME",
        "IP_ADDRESS", 
        "EMAILADDR"
    ]
```

### Produced Events

Events your module generates:

```python
def producedEvents(self):
    return [
        "SUBDOMAIN",
        "IP_ADDRESS",
        "SSL_CERTIFICATE_ISSUED"
    ]
```

### Common Event Types

- **DOMAIN_NAME**: Domain names
- **IP_ADDRESS**: IP addresses
- **SUBDOMAIN**: Subdomains
- **EMAILADDR**: Email addresses
- **PHONE_NUMBER**: Phone numbers
- **SSL_CERTIFICATE_ISSUED**: SSL certificates
- **TCP_PORT_OPEN**: Open TCP ports
- **VULNERABILITY**: Security vulnerabilities

## Module Implementation

### Basic Structure

```python
def handleEvent(self, event):
    eventName = event.eventType
    srcModuleName = event.module
    eventData = event.data

    # Skip if we've already processed this data
    if eventData in self.results:
        return

    self.results[eventData] = True

    # Process the event
    try:
        results = self.query_api(eventData)
        
        for result in results:
            # Create new event
            evt = SpiderFootEvent("IP_ADDRESS", result, 
                                self.__name__, event)
            self.notifyListeners(evt)
            
    except Exception as e:
        self.error(f"Error processing {eventData}: {e}")
```

### API Integration

```python
def query_api(self, target):
    """Query external API for data."""
    url = f"https://api.example.com/lookup?target={target}"
    
    headers = {
        'User-Agent': self.opts['_useragent'],
        'Authorization': f'Bearer {self.opts["api_key"]}'
    }
    
    res = self.sf.fetchUrl(url, timeout=self.opts['timeout'],
                          useragent=self.opts['_useragent'],
                          headers=headers)
    
    if res['content'] is None:
        self.info(f"No content returned from {url}")
        return []
    
    if res['code'] != '200':
        self.error(f"API returned error: {res['code']}")
        return []
    
    try:
        data = json.loads(res['content'])
        return data.get('results', [])
    except json.JSONDecodeError:
        self.error("Invalid JSON response from API")
        return []
```

### Error Handling

```python
def handleEvent(self, event):
    try:
        # Your module logic
        pass
    except Exception as e:
        self.error(f"Module error: {e}")
        return
```

## Best Practices

### Performance

1. **Check for duplicates** to avoid reprocessing
2. **Use appropriate timeouts** for network requests
3. **Implement rate limiting** for API calls
4. **Handle errors gracefully**

### Security

1. **Validate input data** before processing
2. **Sanitize output** before creating events
3. **Use secure HTTP methods** (HTTPS)
4. **Protect API keys** in configuration

### Code Quality

1. **Follow Python conventions** (PEP 8)
2. **Add comprehensive docstrings**
3. **Use meaningful variable names**
4. **Keep functions focused and small**

## Testing Modules

### Manual Testing

```bash
# Test module directly
python sf.py -s example.com -t DOMAIN_NAME -m sfp_your_module -v

# Test with debug output
python sf.py -s example.com -t DOMAIN_NAME -m sfp_your_module --debug
```

### Unit Testing

```python
import unittest
from sfp_your_module import sfp_your_module

class TestYourModule(unittest.TestCase):
    def setUp(self):
        self.module = sfp_your_module()
        
    def test_module_functionality(self):
        # Test your module logic
        pass
```

For more detailed examples and advanced features, see the [Custom Modules Guide](../modules/custom_modules.md).

Ready to contribute? Check out the [Contributing Guide](../contributing.md) for submission guidelines.
