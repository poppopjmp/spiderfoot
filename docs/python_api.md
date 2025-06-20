# Python API Documentation

SpiderFoot provides a comprehensive Python API for integration into other tools and automation scripts. This includes both traditional scanning APIs and advanced workflow functionality.

## Core Classes

### SpiderFoot
Main engine class for scan management and configuration.

```python
from spiderfoot import SpiderFoot

# Initialize SpiderFoot with default configuration
sf = SpiderFoot()

# Initialize with custom configuration
config = {
    '_maxthreads': 3,
    '_timeout': 300,
    '_modulesenabled': ['sfp_dnsresolve', 'sfp_ssl'],
    '__database': 'spiderfoot.db'
}
sf = SpiderFoot(config)
```

### SpiderFootTarget
Represents a scan target with type validation.

```python
from spiderfoot import SpiderFootTarget

# Create target for domain
target = SpiderFootTarget("example.com", "DOMAIN_NAME")

# Create target for IP address
target = SpiderFootTarget("192.168.1.1", "IP_ADDRESS")

# Create target for email
target = SpiderFootTarget("user@example.com", "EMAILADDR")
```

### SpiderFootEvent  
Represents discovered data during scanning.

```python
from spiderfoot import SpiderFootEvent

# Create event from module discovery
event = SpiderFootEvent(
    "IP_ADDRESS", 
    "192.168.1.1", 
    "sfp_dnsresolve", 
    target,
    confidence=100
)

# Event with additional metadata
event = SpiderFootEvent(
    "SSL_CERTIFICATE_ISSUED", 
    "*.example.com", 
    "sfp_ssl",
    target,
    confidence=85,
    sourceEvent=parent_event
)
```

### SpiderFootDb
Database interface for storing and retrieving scan data.

```python
from spiderfoot import SpiderFootDb

# Initialize database connection
config = {'__database': 'spiderfoot.db'}
db = SpiderFootDb(config)

# Create new scan instance
scan_id = db.scanInstanceCreate("example.com", "DOMAIN_NAME", "Test Scan")

# Store scan events
db.scanEventStore(scan_id, event)

# Retrieve scan results
events = db.scanResultEvent(scan_id)
```

## Workflow API

*Advanced multi-target scanning and workspace management*

### Workspace Management
```python
from spiderfoot.workspace import SpiderFootWorkspace
from spiderfoot.workflow_config import WorkflowConfig

# Load workflow configuration
config = WorkflowConfig()

# Create workspace
workspace = SpiderFootWorkspace(config, name="Security Assessment 2024")
workspace.description = "Q1 security assessment targets"
workspace.save_workspace()

print(f"Created workspace: {workspace.workspace_id}")

# Add targets
target1_id = workspace.add_target("example.com", "DOMAIN_NAME", 
                                 {"priority": "high", "env": "production"})
target2_id = workspace.add_target("api.example.com", "INTERNET_NAME",
                                 {"priority": "medium", "env": "production"})

# Import existing scan
success = workspace.import_single_scan("scan_12345", {"source": "previous_assessment"})

# Get workspace summary
summary = workspace.get_workspace_summary()
print(f"Workspace has {summary['statistics']['target_count']} targets")
print(f"Event breakdown: {summary['targets_by_type']}")
```

### Multi-Target Scanning
```python
from spiderfoot.workflow import SpiderFootWorkflow

# Create workflow from workspace
workflow = workspace.create_workflow()

# Define targets and modules
targets = [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "api.example.com", "type": "INTERNET_NAME"},
    {"value": "192.168.1.1", "type": "IP_ADDRESS"}
]

modules = ["sfp_dnsresolve", "sfp_ssl", "sfp_portscan_tcp", "sfp_whois"]

# Progress callback
def progress_callback(message):
    print(f"Progress: {message}")

# Start multi-target scan
scan_ids = workflow.start_multi_target_scan(
    targets, 
    modules, 
    progress_callback=progress_callback
)

print(f"Started {len(scan_ids)} scans: {scan_ids}")

# Wait for completion
statuses = workflow.wait_for_scans_completion(scan_ids, timeout=3600)
print(f"Scan completion status: {statuses}")

# Run cross-correlation
correlations = workflow.run_cross_correlation(scan_ids)
print(f"Found {len(correlations)} correlations")
```

### Cross-Correlation Analysis
```python
from spiderfoot.correlator import SpiderFootWorkspaceCorrelator

# Initialize correlator
correlator = SpiderFootWorkspaceCorrelator(config, workspace)

# Define correlation rules
correlation_rules = [
    'cross_scan_shared_infrastructure',
    'cross_scan_similar_technologies',
    'cross_scan_threat_indicators'
]

# Run correlations
correlations = correlator.run_cross_correlations(correlation_rules)

# Process correlation results
for correlation in correlations:
    print(f"Correlation: {correlation['rule_name']}")
    print(f"  Confidence: {correlation['confidence']}")
    print(f"  Events: {len(correlation['events'])}")
    print(f"  Description: {correlation['description']}")
```

### CTI Report Generation
```python
import asyncio
from spiderfoot.mcp_integration import SpiderFootMCPClient

async def generate_cti_report(workspace):
    """Generate CTI report using MCP integration."""
    
    # Generate threat assessment report
    report = await workspace.generate_cti_report(
        report_type="threat_assessment",
        custom_prompt="Focus on infrastructure risks and threat indicators"
    )
    
    print(f"Generated report: {report['report_id']}")
    print(f"Summary: {report['summary']}")
    
    return report

# Example usage (requires MCP configuration)
# report = asyncio.run(generate_cti_report(workspace))
```

### Data Export and Search
```python
# Export workspace data
export_data = workspace.export_data(format='json')
print(f"Exported {len(export_data['targets'])} targets")
print(f"Exported {len(export_data['scans'])} scans")

# Search events across workspace
search_results = workspace.search_events(
    query="certificate",
    event_types=["SSL_CERTIFICATE_ISSUED", "SSL_CERTIFICATE_EXPIRED"],
    scan_ids=scan_ids[:2]  # Search specific scans
)

print(f"Found {len(search_results)} events matching 'certificate'")

# Advanced filtering
high_confidence_events = [
    event for event in search_results 
    if event['confidence'] >= 85
]
print(f"High confidence events: {len(high_confidence_events)}")
```

## Module Development API

### Creating Custom Modules
```python
from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_custom_module(SpiderFootPlugin):
    """Custom SpiderFoot module example."""
    
    meta = {
        'name': "Custom Module",
        'summary': "Example custom module for organization-specific checks",
        'flags': [],
        'useCases': ["Investigate", "Footprint"],
        'categories': ["Custom"],
        'dataSource': {
            'website': "https://example.com",
            'model': "FREE_NOAUTH_UNLIMITED"
        }
    }
    
    opts = {
        'timeout': 30,
        'api_endpoint': 'https://api.example.com',
        'custom_setting': 'default_value'
    }
    
    optdescs = {
        'timeout': "Request timeout in seconds",
        'api_endpoint': "API endpoint URL",
        'custom_setting': "Custom module setting"
    }
    
    results = None
    
    def setup(self, sfc, userOpts=dict()):
        """Module initialization."""
        self.sf = sfc
        self.results = self.tempStorage()
        
        # Override default options with user settings
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]
    
    def watchedEvents(self):
        """Events this module watches for."""
        return ["DOMAIN_NAME", "INTERNET_NAME"]
    
    def producedEvents(self):
        """Events this module produces."""
        return ["CUSTOM_FINDING", "AFFILIATE_DOMAIN"]
    
    def handleEvent(self, event):
        """Process incoming events."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        
        # Skip if we've already processed this data
        if eventData in self.results:
            return
        
        self.results[eventData] = True
        
        self.sf.debug(f"Received event: {eventName} -> {eventData}")
        
        # Custom processing logic
        if eventName == "DOMAIN_NAME":
            self.process_domain(event, eventData)
        elif eventName == "INTERNET_NAME":
            self.process_internet_name(event, eventData)
    
    def process_domain(self, event, domain):
        """Process domain-specific logic."""
        try:
            # Example: Custom API lookup
            url = f"{self.opts['api_endpoint']}/domain/{domain}"
            response = self.sf.fetchUrl(url, timeout=self.opts['timeout'])
            
            if response['code'] == "200" and response['content']:
                # Parse response and create events
                data = json.loads(response['content'])
                
                if data.get('suspicious'):
                    evt = SpiderFootEvent(
                        "CUSTOM_FINDING",
                        f"Suspicious domain detected: {domain}",
                        self.__name__,
                        event
                    )
                    self.notifyListeners(evt)
                
                # Find affiliate domains
                for affiliate in data.get('affiliates', []):
                    evt = SpiderFootEvent(
                        "AFFILIATE_DOMAIN",
                        affiliate,
                        self.__name__,
                        event
                    )
                    self.notifyListeners(evt)
                    
        except Exception as e:
            self.sf.error(f"Error processing domain {domain}: {e}")
    
    def process_internet_name(self, event, hostname):
        """Process internet name logic."""
        # Custom logic for hostnames
        pass
```

### Module Testing
```python
import unittest
from spiderfoot import SpiderFootEvent, SpiderFootTarget

class TestCustomModule(unittest.TestCase):
    """Test custom module functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.config = {
            '_maxthreads': 1,
            '__database': ':memory:'
        }
        
    def test_module_initialization(self):
        """Test module setup."""
        module = sfp_custom_module()
        module.setup(None, {})
        
        self.assertIsNotNone(module.results)
        self.assertEqual(module.opts['timeout'], 30)
    
    def test_event_handling(self):
        """Test event processing."""
        module = sfp_custom_module()
        module.setup(None, {})
        
        # Create test event
        target = SpiderFootTarget("example.com", "DOMAIN_NAME")
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "test", target)
        
        # Process event
        module.handleEvent(event)
        
        # Verify processing
        self.assertIn("example.com", module.results)

if __name__ == '__main__':
    unittest.main()
```

## REST API Integration

### API Client
```python
import requests
import json

class SpiderFootAPIClient:
    """Client for SpiderFoot REST API."""
    
    def __init__(self, base_url="http://localhost:5001"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def start_scan(self, target, target_type, modules, scan_name=None):
        """Start a new scan via API."""
        data = {
            'target': target,
            'targetType': target_type,
            'modules': modules,
            'scanName': scan_name or f"API Scan: {target}"
        }
        
        response = self.session.post(
            f"{self.base_url}/api/scans",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def get_scan_status(self, scan_id):
        """Get scan status."""
        response = self.session.get(f"{self.base_url}/api/scans/{scan_id}")
        response.raise_for_status()
        return response.json()
    
    def get_scan_results(self, scan_id, format='json'):
        """Get scan results."""
        params = {'format': format}
        response = self.session.get(
            f"{self.base_url}/api/scans/{scan_id}/results",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def list_scans(self):
        """List all scans."""
        response = self.session.get(f"{self.base_url}/api/scans")
        response.raise_for_status()
        return response.json()

# Example usage
client = SpiderFootAPIClient()

# Start scan
scan_result = client.start_scan(
    target="example.com",
    target_type="DOMAIN_NAME",
    modules=["sfp_dnsresolve", "sfp_ssl"],
    scan_name="API Test Scan"
)

scan_id = scan_result['scanId']
print(f"Started scan: {scan_id}")

# Monitor progress
import time
while True:
    status = client.get_scan_status(scan_id)
    if status['status'] in ['FINISHED', 'ABORTED', 'ERROR-FAILED']:
        break
    print(f"Scan status: {status['status']}")
    time.sleep(10)

# Get results
results = client.get_scan_results(scan_id)
print(f"Scan completed with {len(results)} events")
```

## Configuration and Utilities

### Configuration Management
```python
from spiderfoot.workflow_config import WorkflowConfig

# Load configuration
config = WorkflowConfig('workflow_config.json')

# Access configuration values
max_scans = config.get('workflow.max_concurrent_scans')
mcp_enabled = config.get('mcp.enabled')

# Update configuration
config.set('workflow.max_concurrent_scans', 10)
config.set('correlation.confidence_threshold', 80)

# Save configuration
config.save_config()

# Create sample configuration
config.create_sample_config('sample_config.json')
```

### Database Utilities
```python
from spiderfoot import SpiderFootDb

def database_utilities(config):
    """Database maintenance utilities."""
    db = SpiderFootDb(config)
    
    # Get scan statistics
    scans = db.scanInstanceList()
    print(f"Total scans: {len(scans)}")
    
    # Clean up old scans
    for scan in scans:
        scan_id, name, target, created, ended, status, _ = scan
        if status in ['FINISHED', 'ABORTED'] and is_old_scan(created):
            print(f"Deleting old scan: {scan_id}")
            db.scanInstanceDelete(scan_id)
    
    # Database optimization
    db.dbh.execute("VACUUM")
    db.dbh.execute("ANALYZE")
    
def is_old_scan(created_time):
    """Check if scan is older than 30 days."""
    import time
    return (time.time() - created_time) > (30 * 24 * 60 * 60)

# Example usage
config = {'__database': 'spiderfoot.db'}
database_utilities(config)
```

### Logging and Debugging
```python
import logging
from spiderfoot.logger import logListenerSetup, logWorkerSetup

# Set up structured logging
def setup_logging():
    """Configure logging for SpiderFoot integration."""
    
    # Create logger
    logger = logging.getLogger('spiderfoot_integration')
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler
    file_handler = logging.FileHandler('spiderfoot_integration.log')
    file_handler.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# Example usage
logger = setup_logging()
logger.info("Starting SpiderFoot integration")
logger.debug("Debug information")
```

## Error Handling and Best Practices

### Exception Handling
```python
from spiderfoot import SpiderFootException

def robust_scan_execution(target, target_type, modules):
    """Robust scan execution with proper error handling."""
    
    try:
        # Initialize SpiderFoot
        config = load_config()
        sf = SpiderFoot(config)
        
        # Validate target
        if not validate_target(target, target_type):
            raise ValueError(f"Invalid target: {target}")
        
        # Start scan
        scan_id = start_scan_with_retry(sf, target, target_type, modules)
        
        # Monitor scan
        result = monitor_scan_progress(sf, scan_id)
        
        return result
        
    except SpiderFootException as e:
        logger.error(f"SpiderFoot error: {e}")
        return {'error': 'spiderfoot_error', 'message': str(e)}
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {'error': 'unexpected_error', 'message': str(e)}

def validate_target(target, target_type):
    """Validate target format."""
    import re
    
    validators = {
        'DOMAIN_NAME': r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'IP_ADDRESS': r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$',
        'EMAILADDR': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    }
    
    pattern = validators.get(target_type)
    if pattern:
        return bool(re.match(pattern, target))
    
    return True  # Allow unknown types

def start_scan_with_retry(sf, target, target_type, modules, max_retries=3):
    """Start scan with retry logic."""
    
    for attempt in range(max_retries):
        try:
            scan_id = simple_scan(target, target_type, modules)
            return scan_id
            
        except Exception as e:
            logger.warning(f"Scan attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5 * (attempt + 1))  # Exponential backoff
```

### Performance Optimization
```python
def optimized_batch_scanning(targets, modules, max_concurrent=5):
    """Optimized batch scanning with concurrency control."""
    
    import concurrent.futures
    import queue
    
    results = {}
    
    def scan_worker(target_info):
        """Worker function for individual scans."""
        target, target_type = target_info
        try:
            result = robust_scan_execution(target, target_type, modules)
            return target, result
        except Exception as e:
            return target, {'error': str(e)}
    
    # Process targets with thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        # Submit all tasks
        future_to_target = {
            executor.submit(scan_worker, (target['value'], target['type'])): target['value']
            for target in targets
        }
        
        # Collect results
        for future in concurrent.futures.as_completed(future_to_target):
            target = future_to_target[future]
            try:
                target_name, result = future.result()
                results[target_name] = result
                logger.info(f"Completed scan for: {target_name}")
            except Exception as e:
                logger.error(f"Failed to scan {target}: {e}")
                results[target] = {'error': str(e)}
    
    return results

# Example usage
targets = [
    {'value': 'example.com', 'type': 'DOMAIN_NAME'},
    {'value': 'test.example.com', 'type': 'INTERNET_NAME'},
    {'value': '192.168.1.1', 'type': 'IP_ADDRESS'}
]

modules = ['sfp_dnsresolve', 'sfp_ssl', 'sfp_whois']
results = optimized_batch_scanning(targets, modules, max_concurrent=3)

print(f"Processed {len(results)} targets")
for target, result in results.items():
    if 'error' in result:
        print(f"❌ {target}: {result['error']}")
    else:
        print(f"✅ {target}: {result.get('summary', 'completed')}")
```

This comprehensive Python API documentation provides detailed examples for integrating SpiderFoot into other applications, from basic scanning to advanced workflow functionality, custom module development, and robust error handling.
        '_maxthreads': 3,
        '_timeout': 300,
        '_modulesenabled': modules
    }
    
    sf = SpiderFoot(config)
    target = SpiderFootTarget(target_value, target_type)
    
    # Start scan
    scan_id = sf.start_scan(target)
    
    # Wait for completion
    while sf.get_scan_status(scan_id) in ['STARTING', 'RUNNING']:
        time.sleep(5)
    
    # Get results
    results = sf.get_scan_results(scan_id)
    return results

# Usage
results = simple_scan("example.com", "DOMAIN_NAME", ["sfp_dnsresolve", "sfp_ssl"])
```

### Advanced Scan Configuration
```python
class CustomScan:
    def __init__(self):
        self.config = {
            '_maxthreads': 5,
            '_timeout': 600,
            '_modulesenabled': [],
            '_dnsserver': '8.8.8.8',
            '_fetchtimeout': 30
        }
        self.sf = SpiderFoot(self.config)
    
    def configure_modules(self, modules, options=None):
        """Configure modules with custom options."""
        self.config['_modulesenabled'] = modules
        
        if options:
            for module, opts in options.items():
                for key, value in opts.items():
                    self.config[f'{module}.{key}'] = value
    
    def scan_with_callback(self, target_value, target_type, callback=None):
        """Run scan with progress callback."""
        target = SpiderFootTarget(target_value, target_type)
        scan_id = self.sf.start_scan(target)
        
        while True:
            status = self.sf.get_scan_status(scan_id)
            if callback:
                callback(scan_id, status)
            
            if status not in ['STARTING', 'RUNNING']:
                break
            
            time.sleep(5)
        
        return self.sf.get_scan_results(scan_id)

# Usage
scanner = CustomScan()
scanner.configure_modules(
    ['sfp_dnsresolve', 'sfp_virustotal'],
    {'sfp_virustotal': {'api_key': 'your_api_key'}}
)

def progress_callback(scan_id, status):
    print(f"Scan {scan_id}: {status}")

results = scanner.scan_with_callback("example.com", "DOMAIN_NAME", progress_callback)
```

## Workspace API

### SpiderFootWorkspace
```python
from spiderfoot.workspace import SpiderFootWorkspace

# Create workspace
workspace = SpiderFootWorkspace(config, name="My Assessment")
workspace.description = "Security assessment"
workspace.save_workspace()

# Add targets
target_id = workspace.add_target("example.com", "DOMAIN_NAME", 
                                {"priority": "high"})

# List targets
targets = workspace.get_targets()
for target in targets:
    print(f"Target: {target['value']} ({target['type']})")
```

### Multi-Target Scanning
```python
from spiderfoot.workflow import SpiderFootWorkflow

# Create workflow
workflow = workspace.create_workflow()

# Start multi-target scan
targets = [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "192.168.1.1", "type": "IP_ADDRESS"}
]

modules = ["sfp_dnsresolve", "sfp_ssl", "sfp_portscan_tcp"]
scan_options = {"_maxthreads": 3, "_timeout": 300}

scan_ids = workflow.start_multi_target_scan(targets, modules, scan_options)

# Monitor progress
for scan_id in scan_ids:
    status = workflow.get_scan_status(scan_id)
    print(f"Scan {scan_id}: {status}")
```

## Event Processing

### Event Listeners
```python
class CustomEventListener:
    def __init__(self):
        self.events = []
    
    def handle_event(self, event):
        """Process discovered events."""
        self.events.append(event)
        
        # Example: Alert on high-risk events
        if event.risk_level == 'HIGH':
            self.send_alert(event)
    
    def send_alert(self, event):
        """Send alert for high-risk events."""
        print(f"HIGH RISK: {event.event_type} - {event.data}")
        # Add your alerting logic here

# Usage with scan
listener = CustomEventListener()
sf.add_event_listener(listener.handle_event)
```

### Event Filtering
```python
def filter_events(events, criteria):
    """Filter events based on criteria."""
    filtered = []
    
    for event in events:
        if criteria.get('event_types') and event.event_type not in criteria['event_types']:
            continue
        
        if criteria.get('risk_levels') and event.risk_level not in criteria['risk_levels']:
            continue
        
        if criteria.get('modules') and event.module not in criteria['modules']:
            continue
        
        filtered.append(event)
    
    return filtered

# Usage
criteria = {
    'event_types': ['IP_ADDRESS', 'DOMAIN_NAME'],
    'risk_levels': ['HIGH', 'MEDIUM'],
    'modules': ['sfp_dnsresolve', 'sfp_portscan_tcp']
}

filtered_events = filter_events(scan_results, criteria)
```

## Database Operations

### Direct Database Access
```python
from spiderfoot.db import SpiderFootDb

# Initialize database
db = SpiderFootDb(config)

# Query events
events = db.scanEventsByType("DOMAIN_NAME", scan_id)

# Custom queries
query = """
    SELECT event_type, COUNT(*) as count 
    FROM tbl_scan_results 
    WHERE scan_instance_id = ? 
    GROUP BY event_type
"""
results = db.query(query, [scan_id])
```

### Bulk Data Operations
```python
def export_scan_data(scan_id, output_format='json'):
    """Export scan data in various formats."""
    db = SpiderFootDb(config)
    
    if output_format == 'json':
        events = db.scanEvents(scan_id)
        return json.dumps([event.__dict__ for event in events])
    
    elif output_format == 'csv':
        events = db.scanEvents(scan_id)
        # Convert to CSV format
        return csv_data
    
    elif output_format == 'xml':
        # Convert to XML format
        return xml_data
```

## Module Integration

### Custom Module Development
```python
from spiderfoot import SpiderFootPlugin

class sfp_custom_integration(SpiderFootPlugin):
    def __init__(self):
        super().__init__()
        self.meta = {
            'name': "Custom Integration",
            'summary': "Custom integration module",
            'categories': ["Custom"]
        }
    
    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        
        # Initialize your custom logic
        self.api_client = CustomAPIClient(self.opts.get('api_key'))
    
    def handleEvent(self, event):
        # Process event with custom logic
        if event.eventType == "DOMAIN_NAME":
            data = self.api_client.lookup(event.data)
            
            if data:
                evt = SpiderFootEvent("CUSTOM_DATA", data, 
                                    self.__name__, event)
                self.notifyListeners(evt)
```

### API Integration Helper
```python
class APIHelper:
    def __init__(self, base_url, api_key=None, timeout=30):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})
    
    def get(self, endpoint, params=None):
        """Make GET request to API."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return None
    
    def post(self, endpoint, data=None):
        """Make POST request to API."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.post(url, json=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API request failed: {e}")
            return None
```

## Automation Examples

### Scheduled Scanning
```python
import schedule
import time

class ScheduledScanner:
    def __init__(self, config):
        self.config = config
        self.sf = SpiderFoot(config)
    
    def daily_scan(self, targets):
        """Run daily scans for specified targets."""
        for target_info in targets:
            print(f"Starting scan for {target_info['value']}")
            
            target = SpiderFootTarget(target_info['value'], target_info['type'])
            scan_id = self.sf.start_scan(target)
            
            # Monitor and save results
            self.monitor_scan(scan_id, target_info['value'])
    
    def monitor_scan(self, scan_id, target_name):
        """Monitor scan progress and save results."""
        while True:
            status = self.sf.get_scan_status(scan_id)
            if status not in ['STARTING', 'RUNNING']:
                break
            time.sleep(60)
        
        # Export results
        results = self.sf.get_scan_results(scan_id)
        filename = f"scan_{target_name}_{time.strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f)

# Schedule daily scans
scanner = ScheduledScanner(config)
targets = [
    {"value": "example.com", "type": "DOMAIN_NAME"},
    {"value": "192.168.1.1", "type": "IP_ADDRESS"}
]

schedule.every().day.at("02:00").do(scanner.daily_scan, targets)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Integration with SIEM
```python
class SIEMIntegration:
    def __init__(self, siem_endpoint, api_key):
        self.siem_endpoint = siem_endpoint
        self.api_key = api_key
    
    def send_events(self, events):
        """Send events to SIEM system."""
        for event in events:
            if event.risk_level in ['HIGH', 'MEDIUM']:
                siem_event = {
                    'timestamp': event.received_time,
                    'source': 'SpiderFoot',
                    'event_type': event.event_type,
                    'data': event.data,
                    'risk_level': event.risk_level,
                    'module': event.module
                }
                
                self.send_to_siem(siem_event)
    
    def send_to_siem(self, event_data):
        """Send individual event to SIEM."""
        headers = {'Authorization': f'Bearer {self.api_key}'}
        response = requests.post(self.siem_endpoint, 
                               json=event_data, headers=headers)
        
        if response.status_code != 200:
            print(f"Failed to send event to SIEM: {response.text}")

# Usage
siem = SIEMIntegration("https://siem.company.com/api/events", "api_key")
scan_results = sf.get_scan_results(scan_id)
siem.send_events(scan_results)
```

## Error Handling

### Robust Error Handling
```python
class RobustScanner:
    def __init__(self, config):
        self.config = config
        self.sf = SpiderFoot(config)
    
    def safe_scan(self, target_value, target_type, modules):
        """Run scan with comprehensive error handling."""
        try:
            target = SpiderFootTarget(target_value, target_type)
            scan_id = self.sf.start_scan(target)
            
            return self.monitor_scan_with_retry(scan_id)
            
        except Exception as e:
            print(f"Scan failed: {e}")
            return None
    
    def monitor_scan_with_retry(self, scan_id, max_retries=3):
        """Monitor scan with retry logic."""
        retries = 0
        
        while retries < max_retries:
            try:
                while True:
                    status = self.sf.get_scan_status(scan_id)
                    
                    if status == 'ERROR-FAILED':
                        raise Exception("Scan failed")
                    
                    if status not in ['STARTING', 'RUNNING']:
                        break
                    
                    time.sleep(10)
                
                return self.sf.get_scan_results(scan_id)
                
            except Exception as e:
                retries += 1
                print(f"Scan monitoring failed (attempt {retries}): {e}")
                
                if retries < max_retries:
                    time.sleep(30)  # Wait before retry
                else:
                    raise
```

## Best Practices

### Performance Optimization
```python
# Use connection pooling for HTTP requests
import requests.adapters

def create_optimized_session():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=3
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Batch processing for large datasets
def process_events_in_batches(events, batch_size=100):
    for i in range(0, len(events), batch_size):
        batch = events[i:i + batch_size]
        process_batch(batch)
        time.sleep(1)  # Rate limiting
```

### Memory Management
```python
# Use generators for large result sets
def scan_results_generator(scan_id):
    db = SpiderFootDb(config)
    offset = 0
    batch_size = 1000
    
    while True:
        events = db.scanEventsPaginated(scan_id, offset, batch_size)
        if not events:
            break
        
        for event in events:
            yield event
        
        offset += batch_size

# Usage
for event in scan_results_generator(scan_id):
    process_event(event)
```

For more examples and detailed API documentation, see the [REST API Documentation](rest_api.md) and [Module Development Guide](developer/module_development.md).
